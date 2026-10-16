#!/usr/bin/env bash
# Verify that everything Noctoware depends on resolves in the exact repository
# set an installed system uses ([noctoware], [cachyos] generic x86-64, Arch
# core/extra/multilib), and detect upstream drift.
#
# Needs no root and never touches the host's pacman databases: sync DBs are
# downloaded into work/depcheck/ and pacman runs with --dbpath/--config there.
#
# Usage: scripts/check-dependencies.sh [--offline]   (--offline reuses DBs)
source "$(dirname "$0")/lib/common.sh"
need pacman curl bsdtar

ARCH_MIRROR="${NOCTO_ARCH_MIRROR:-https://geo.mirror.pkgbuild.com}"
CACHY_MIRROR="${NOCTO_CACHY_MIRROR:-https://mirror.cachyos.org/repo}"
W="$NOCTO_WORK/depcheck"
offline=0; [[ "${1:-}" == --offline ]] && offline=1
mkdir -p "$W/db/sync" "$W/cache"

cat >"$W/pacman.conf" <<CONF
[options]
Architecture = x86_64
SigLevel = Never
[noctoware]
Server = file://$NOCTO_REPO_DIR
[cachyos]
Server = $CACHY_MIRROR/x86_64/cachyos
[core]
Server = $ARCH_MIRROR/core/os/x86_64
[extra]
Server = $ARCH_MIRROR/extra/os/x86_64
[multilib]
Server = $ARCH_MIRROR/multilib/os/x86_64
CONF

if [[ $offline -eq 0 ]]; then
    log "downloading sync databases"
    curl -fsSL "$CACHY_MIRROR/x86_64/cachyos/cachyos.db" -o "$W/db/sync/cachyos.db" || die "cachyos db download failed" "$E_DEPS"
    for r in core extra multilib; do
        curl -fsSL "$ARCH_MIRROR/$r/os/x86_64/$r.db" -o "$W/db/sync/$r.db" || die "$r db download failed" "$E_DEPS"
    done
fi
[[ -f "$NOCTO_REPO_DIR/noctoware.db.tar.gz" ]] || die "build packages first (scripts/build-packages.sh)" "$E_DEPS"
cp -fL "$NOCTO_REPO_DIR/noctoware.db.tar.gz" "$W/db/sync/noctoware.db"

pac() { pacman --config "$W/pacman.conf" --dbpath "$W/db" --cachedir "$W/cache" --noconfirm "$@"; }
si() { pac -Si "$1" 2>/dev/null; }
field() { awk -v f="$2" -F' *: ' '$1==f{ $1=""; sub(/^ /,""); print; exit }' <<<"$1"; }

fail=0
bad() { warn "$*"; fail=1; }

# 1. full closure of every meta package and of the ISO package list
iso_pkgs=()
mapfile -t iso_pkgs < <(grep -vE '^\s*(#|$)' "$NOCTO_ROOT/iso/packages.x86_64" 2>/dev/null)
for target in noctoware-desktop noctoware-plasma noctoware-revo noctoware-calamares-config; do
    if out="$(pac -Sp --print-format '%r/%n' "$target" 2>&1)"; then
        ok "$target resolves ($(wc -l <<<"$out") packages)"
        if grep -q '^chaotic-aur/' <<<"$out"; then bad "$target pulls packages from chaotic-aur"; fi
    else
        bad "$target does not resolve:"; echo "$out" | grep -v '^::' | head -15 >&2
    fi
done
if ((${#iso_pkgs[@]})); then
    if out="$(pac -Sp --print-format '%n' "${iso_pkgs[@]}" 2>&1)"; then
        ok "ISO package list resolves ($(wc -l <<<"$out") packages)"
    else
        bad "ISO package list does not resolve:"; echo "$out" | grep -v '^::' | head -15 >&2
    fi
fi

# 1b. conflict check (pacman -Sp resolves dependencies but skips conflict
#     checks; e.g. a provider pick of jack2 next to pipewire-jack)
echo "noctoware cachyos core extra multilib" >"$W/db/sync/ORDER"
if ((${#iso_pkgs[@]})); then
    set_out="$(pac -Sp --print-format '%n' "${iso_pkgs[@]}" noctoware-plasma 2>/dev/null)"
    if c="$(python3 -I "$NOCTO_ROOT/scripts/lib/pkgset.py" conflicts "$W/db/sync" <<<"$set_out")"; then
        ok "ISO set + noctoware-plasma: no package conflicts ($(wc -l <<<"$set_out") packages)"
    else
        bad "package conflicts in the ISO set:"; echo "$c" >&2
    fi
fi

# 2. noctoware-plasma must track plasma-meta minus plasma-login-manager
meta_deps="$(field "$(si plasma-meta)" "Depends On" | tr -s ' ' '\n' | sed 's/[<>=].*//' | sort -u)"
ours="$(sed -n '/^_plasma=(/,/^)/p' "$NOCTO_ROOT/packages/noctoware-plasma/PKGBUILD" | tr -s ' ()' '\n' | grep -vE '^(_plasma=|)$' | sort -u)"
missing="$(comm -23 <(grep -vx plasma-login-manager <<<"$meta_deps") <(echo "$ours"))"
[[ -z "$missing" ]] && ok "noctoware-plasma covers plasma-meta (minus plasma-login-manager)" ||
    bad "plasma-meta gained components missing from noctoware-plasma: $(tr '\n' ' ' <<<"$missing")"

# 3. CachyOS NVIDIA modules must match the nvidia-utils pacman will pick
for mod in linux-cachyos-nvidia-open linux-cachyos-lts-nvidia-open; do
    need_ver="$(field "$(si "$mod")" "Depends On" | tr ' ' '\n' | sed -n 's/^nvidia-utils=//p')"
    have_ver="$(pac -Sp -dd --print-format '%v' nvidia-utils 2>/dev/null | head -1 | sed 's/-[0-9.]*$//')"
    if [[ -n "$need_ver" && "$have_ver" == "$need_ver"* ]]; then ok "$mod ↔ nvidia-utils $have_ver"
    else bad "$mod wants nvidia-utils=$need_ver but the repos provide $have_ver"; fi
    kmod_kernel="$(field "$(si "$mod")" "Depends On" | tr ' ' '\n' | sed -n 's/^linux-cachyos\(-lts\)\{0,1\}=//p')"
    kname="${mod%-nvidia-open}"
    kver="$(field "$(si "$kname")" Version)"
    [[ "$kmod_kernel" == "$kver" ]] && ok "$mod built for $kname $kver" || bad "$mod built for $kname=$kmod_kernel, repo has $kver"
done

# 4. HyDE: every pacman dependency of the deployed dots is a package dependency
hyde_pkg="$(ls -1 "$NOCTO_REPO_DIR"/noctoware-hyde-*.pkg.tar.zst 2>/dev/null | tail -1)"
if [[ -n "$hyde_pkg" ]] && command -v python3 >/dev/null; then
    tmp="$(mktemp -d)"
    bsdtar -xf "$hyde_pkg" -C "$tmp" usr/share/noctoware/hyde/upstream/Scripts/dots .PKGINFO
    drift="$(python3 -I - "$tmp" <<'PY'
import sys, tomllib, re, pathlib
root = pathlib.Path(sys.argv[1])
dots = root / "usr/share/noctoware/hyde/upstream/Scripts/dots"
grp = root / "usr/share/noctoware/hyde/upstream/Scripts/dots-groups/noctoware.toml"
names = ["deps"] + [re.search(r"dots/(.+)\.toml", i).group(1)
                    for i in tomllib.load(open(grp, "rb"))["global"]["include"]] if grp.exists() else ["deps"]
want = set()
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            (want.update(v) if k == "pacman" and isinstance(v, list) else walk(v))
    elif isinstance(o, list):
        for i in o: walk(i)
for n in names:
    f = dots / f"{n}.toml"
    if f.exists(): walk(tomllib.load(open(f, "rb")))
have = {l.split(" = ", 1)[1].strip() for l in open(root / ".PKGINFO") if l.startswith("depend = ")}
have = {re.split(r"[<>=]", h)[0] for h in have} | {"electron"}  # electron: optional by design
print(" ".join(sorted({re.split(r"[<>=]", w)[0] for w in want} - have)))
PY
)"
    rm -rf "$tmp"
    [[ -z "$drift" ]] && ok "noctoware-hyde depends cover HyDE's deployed dots" || bad "HyDE needs packages noctoware-hyde lacks: $drift"
fi

# 5. Python minor version the HyDE venv was built for
if [[ -n "$hyde_pkg" ]]; then
    venv_py="$(bsdtar -xOf "$hyde_pkg" usr/lib/noctoware/hyde/python_env/pyvenv.cfg 2>/dev/null | sed -n 's/^version_info *= *\([0-9]*\.[0-9]*\).*/\1/p; s/^version *= *\([0-9]*\.[0-9]*\).*/\1/p' | head -1)"
    repo_py="$(field "$(si python)" Version | cut -d. -f1-2)"
    [[ "$venv_py" == "$repo_py" ]] && ok "HyDE venv python $venv_py matches repo python" ||
        bad "noctoware-hyde venv built for python $venv_py, repos have $repo_py: bump pkgrel and rebuild"
fi

((fail == 0)) || die "dependency check FAILED" "$E_DEPS"
ok "all dependency checks passed"
