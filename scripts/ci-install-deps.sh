#!/usr/bin/env bash
# Install (as root, e.g. in a CI container) everything needed to BUILD the
# Noctoware packages: all makedepends/checkdepends, plus the link-time
# depends of the packages that compile code.  Derived from the
# PKGBUILDs, so workflows never carry hand-maintained dependency lists.
source "$(dirname "$0")/lib/common.sh"
((EUID == 0)) || die "run as root" "$E_USAGE"
# --runtime PKG...: also install the runtime depends of these packages
# (integration tests exercise them, e.g. the offline HyDE deploy)
runtime=()
if [[ "${1:-}" == --runtime ]]; then shift; runtime=("$@"); fi
mapfile -t ours < <(package_dirs)
deps=()
for p in "${ours[@]}"; do
    # PKGBUILDs only set variables at top level (no makepkg as root needed)
    mapfile -t -O "${#deps[@]}" deps < <(cd "$NOCTO_ROOT/packages/$p" && (
        set +eu; source ./PKGBUILD
        printf '%s\n' "${makedepends[@]}" "${checkdepends[@]}"
        # link-time deps only for packages that compile code (CMake builds)
        [[ " ${makedepends[*]} " == *" cmake "* ]] && printf '%s\n' "${depends[@]}"
        true))
done
for p in "${runtime[@]}"; do
    mapfile -t -O "${#deps[@]}" deps < <(cd "$NOCTO_ROOT/packages/$p" && (set +eu; source ./PKGBUILD; printf '%s\n' "${depends[@]}"))
done
# drop version constraints, our own packages and virtual names they provide
mapfile -t deps < <(printf '%s\n' "${deps[@]}" | sed 's/[<>=].*//' | sort -u |
    grep -vxF -f <(printf '%s\n' "${ours[@]}" calamares) | grep -v '^noctoware-')
# runtime-only deps from other repos (e.g. [cachyos] mkinitcpio-openswap) are not needed to build
mapfile -t avail < <(pacman -Slq | sort -u)
missing=($(comm -23 <(printf '%s\n' "${deps[@]}") <(printf '%s\n' "${avail[@]}")))
((${#missing[@]})) && warn "not in this host's repos, skipped: ${missing[*]}"
mapfile -t deps < <(comm -12 <(printf '%s\n' "${deps[@]}") <(printf '%s\n' "${avail[@]}"))
log "installing ${#deps[@]} build dependencies"
pacman -S --needed --noconfirm "${deps[@]}"
