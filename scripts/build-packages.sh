#!/usr/bin/env bash
# Build, sign and add Noctoware packages to the local [noctoware] repository.
#
# Usage: scripts/build-packages.sh [--force] [--syncdeps] [PACKAGE...]
#   --force      rebuild even if pkgver-pkgrel is already in the repository
#   --syncdeps   install missing build deps with pacman (CI containers);
#                default is --nodeps: runtime deps are not needed to build
#                these packages, makedepends must be present on the host
#   PACKAGE      only build these package directories (default: BUILD_ORDER)
#
# Output: repository/x86_64/{*.pkg.tar.zst,*.sig,noctoware.db*,noctoware.files*}
source "$(dirname "$0")/lib/common.sh"
need makepkg repo-add gpg bsdtar

force=0 depmode=--nodeps
pkgs=()
for a in "$@"; do
    case "$a" in
        --force) force=1 ;;
        --syncdeps) depmode=--syncdeps ;;
        -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
        -*) die "unknown option $a" "$E_USAGE" ;;
        *) pkgs+=("$a") ;;
    esac
done
((${#pkgs[@]})) || mapfile -t pkgs < <(package_dirs)

key="$(signing_key)" || die "no signing key: run scripts/gen-dev-key.sh (local) or set NOCTO_SIGNING_KEY" "$E_SIGN"
[[ -s "${NOCTO_KEYS_DIR}/public/noctoware.gpg" ]] || "$(dirname "$0")/export-keyring.sh"

mkdir -p "$NOCTO_REPO_DIR" "$NOCTO_WORK/build" "$NOCTO_WORK/src" "$NOCTO_WORK/logs"
export PKGDEST="$NOCTO_REPO_DIR" BUILDDIR="$NOCTO_WORK/build" SRCDEST="$NOCTO_WORK/src"
export PACKAGER="Noctoware Build <build@noctoware.invalid>"
export GNUPGHOME="$NOCTO_GNUPGHOME"

built=()
for p in "${pkgs[@]}"; do
    dir="$NOCTO_ROOT/packages/$p"
    [[ -f "$dir/PKGBUILD" ]] || die "no PKGBUILD for $p" "$E_USAGE"
    # every file this PKGBUILD would produce
    mapfile -t files < <(cd "$dir" && makepkg --packagelist)
    if [[ $force -eq 0 ]]; then
        missing=0
        for f in "${files[@]}"; do [[ -f "$f" && -f "$f.sig" ]] || missing=1; done
        if [[ $missing -eq 0 ]]; then
            ok "$p: up to date ($(basename "${files[0]}"))"
            continue
        fi
    fi
    log "building $p"
    if ! (cd "$dir" && makepkg -f --noconfirm --clean --cleanbuild "$depmode") >"$NOCTO_WORK/logs/$p.log" 2>&1; then
        tail -25 "$NOCTO_WORK/logs/$p.log" >&2
        die "build of $p failed (full log: work/logs/$p.log)" "$E_BUILD"
    fi
    for f in "${files[@]}"; do
        [[ -f "$f" ]] || die "$p did not produce $(basename "$f")" "$E_BUILD"
        rm -f "$f.sig"
        gpg --batch --yes --detach-sign --no-armor -u "$key" "$f" || die "signing $f failed" "$E_SIGN"
        built+=("$f")
    done
    ok "$p built and signed"
done

if ((${#built[@]})); then
    log "updating repository database"
    repo-add --sign --key "$key" --verify --remove --prevent-downgrade \
        "$NOCTO_REPO_DIR/noctoware.db.tar.gz" "${built[@]}" >"$NOCTO_WORK/logs/repo-add.log" 2>&1 ||
        { cat "$NOCTO_WORK/logs/repo-add.log" >&2; die "repo-add failed" "$E_BUILD"; }
fi
"$(dirname "$0")/check-repo.sh"
ok "repository ready: $NOCTO_REPO_DIR"
