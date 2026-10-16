#!/usr/bin/env bash
# End-to-end test of scripts/publish-repo.sh without touching GitHub: a stub
# `gh` stores "release assets" in a local directory, which is then served over
# HTTP and validated with real pacman (scripts/validate-update.sh --remote
# against that URL).  Exercises: first publish, an upgrade publish (old
# packages kept for cached clients), and the refusal paths.
set -Eeuo pipefail
trap 'echo "FAILED at ${BASH_SOURCE[0]##*/}:$LINENO: $BASH_COMMAND" >&2' ERR
root="$(cd "$(dirname "$0")/../.." && pwd)"
T="$(mktemp -d)"; trap 'kill $srv 2>/dev/null; rm -rf "$T"' EXIT
assets="$T/assets"; mkdir -p "$assets" "$T/bin"

# --- stub gh: release view/create/upload/download/delete-asset on $assets
cat >"$T/bin/gh" <<EOF
#!/usr/bin/env bash
A="$assets"
case "\$1 \$2" in
  "release view")
    [[ -f "\$A/.created" ]] || exit 1
    if [[ " \$* " == *" --json assets "* ]]; then ls -1 "\$A"; fi ;;
  "release create") touch "\$A/.created" ;;
  "release upload") shift 2; for f in "\$@"; do [[ -f "\$f" ]] && cp -f "\$f" "\$A/\$(basename "\$f")"; done ;;
  "release download")
    shift 2; pat="" dir=.
    while ((\$#)); do case "\$1" in -p) pat="\$2"; shift;; -D) dir="\$2"; shift;; esac; shift; done
    [[ -f "\$A/\$pat" ]] || exit 1; mkdir -p "\$dir"; cp "\$A/\$pat" "\$dir/" ;;
  "release delete-asset") rm -f "\$A/\$4" ;;
  *) echo "stub gh: unsupported: \$*" >&2; exit 2 ;;
esac
EOF
chmod +x "$T/bin/gh"

# --- clean clone on the release branch (publish refuses dirty trees)
git clone -q "$root" "$T/src"
cd "$T/src"; git checkout -q -B main
mkdir -p repository keys
cp -a "$root/keys/public" keys/
cp -a "$root/keys/private" keys/
cp -a "$root/repository/x86_64" repository/
port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
python3 -m http.server "$port" --bind 127.0.0.1 --directory "$assets" >/dev/null 2>&1 & srv=$!
sleep 1
export PATH="$T/bin:$PATH" NOCTO_REPO_URL="http://127.0.0.1:$port" NOCTO_WORK="$T/work"

# refusal: the local dev key must never be published by default
if scripts/publish-repo.sh --confirm >"$T/refuse.log" 2>&1; then echo "published with dev key!"; exit 1; fi
grep -q "DEV key" "$T/refuse.log"

export NOCTO_ALLOW_DEV_KEY=1
scripts/publish-repo.sh >"$T/dry.log" 2>&1                       # dry run changes nothing
[[ -z "$(ls -A "$assets")" ]]
scripts/publish-repo.sh --confirm >"$T/pub1.log" 2>&1
for f in noctoware.db noctoware.db.sig noctoware.files noctoware.files.sig; do [[ -f "$assets/$f" && ! -L "$assets/$f" ]]; done
n1=$(ls "$assets"/*.pkg.tar.zst | wc -l)
(( n1 >= 17 ))
scripts/validate-update.sh --remote >"$T/val1.log" 2>&1          # pacman against the "published" repo
grep -q "resolves cleanly" "$T/val1.log"

# upgrade publish: bump a package; the previous version stays for cached clients
"$root/tests/vm/make-bump.sh" "$T/src/repository/x86_64" 4 >/dev/null
scripts/publish-repo.sh --confirm >"$T/pub2.log" 2>&1
ls "$assets" | grep -q 'noctoware-welcome-.*-4-any.pkg.tar.zst$'
ls "$assets" | grep -qE 'noctoware-welcome-.*-3-any.pkg.tar.zst$'   # kept (previous generation)
bsdtar -xOf "$assets/noctoware.db" --include='noctoware-welcome-*/desc' | grep -q -- '-4$'

# refusal: dirty working tree
echo x >> README.md
if scripts/publish-repo.sh --confirm >"$T/dirty.log" 2>&1; then echo "published from dirty tree!"; exit 1; fi
grep -q "not clean" "$T/dirty.log"
echo "publish pipeline OK ($n1 packages, upgrade publish keeps previous generation)"
