#!/usr/bin/env bash
# Repository integrity check for [noctoware].
#   * every package and both databases carry a valid detached signature made
#     by a key in keys/public (checked in an isolated keyring)
#   * database entries and package files match one-to-one, checksums agree
#   * file names are safe for GitHub Releases (no ':' — no epochs)
# Usage: scripts/check-repo.sh [REPO_DIR]
source "$(dirname "$0")/lib/common.sh"
need gpg bsdtar sha256sum

dir="${1:-$NOCTO_REPO_DIR}"
[[ -f "$dir/noctoware.db.tar.gz" ]] || die "no database in $dir" "$E_BUILD"
tmpg="$(mktemp -d)"; trap 'rm -rf "$tmpg"' EXIT
GNUPGHOME="$tmpg" gpg --batch --quiet --import "$NOCTO_KEYS_DIR/public/noctoware.gpg" 2>/dev/null ||
    die "cannot import keys/public/noctoware.gpg" "$E_SIGN"
verify() { GNUPGHOME="$tmpg" gpg --batch --quiet --verify "$1.sig" "$1" 2>/dev/null; }

fail=0
for f in noctoware.db.tar.gz noctoware.files.tar.gz; do
    if [[ -f "$dir/$f.sig" ]] && verify "$dir/$f"; then ok "signature: $f"
    else warn "BAD/MISSING signature: $f"; fail=1; fi
done

declare -A in_db
while IFS=$'\t' read -r fname sha; do
    in_db["$fname"]=1
    if [[ ! -f "$dir/$fname" ]]; then warn "db lists missing file $fname"; fail=1; continue; fi
    [[ "$(sha256sum "$dir/$fname" | cut -d' ' -f1)" == "$sha" ]] || { warn "checksum mismatch: $fname"; fail=1; }
    if [[ -f "$dir/$fname.sig" ]] && verify "$dir/$fname"; then :; else warn "BAD/MISSING signature: $fname"; fail=1; fi
    [[ "$fname" != *:* ]] || { warn "':' in $fname breaks GitHub Releases hosting (drop the epoch)"; fail=1; }
done < <(bsdtar -xOf "$dir/noctoware.db.tar.gz" --include='*/desc' |
         awk '/^%FILENAME%$/{getline f} /^%SHA256SUM%$/{getline s; print f "\t" s}')

n=${#in_db[@]}
for f in "$dir"/*.pkg.tar.zst; do
    [[ -e "$f" ]] || continue
    [[ -n "${in_db[$(basename "$f")]:-}" ]] || warn "not in database (stale build?): $(basename "$f")"
done
((fail == 0)) || die "repository integrity check FAILED" "$E_SIGN"
ok "repository integrity OK ($n packages, all signed)"
