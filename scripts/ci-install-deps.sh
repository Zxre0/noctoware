#!/usr/bin/env bash
# Install (as root, e.g. in a CI container) everything needed to BUILD the
# Noctoware packages: all makedepends/checkdepends, plus the link-time
# depends of the packages that compile code.  Derived from the
# PKGBUILDs, so workflows never carry hand-maintained dependency lists.
source "$(dirname "$0")/lib/common.sh"
((EUID == 0)) || die "run as root" "$E_USAGE"
mapfile -t ours < <(package_dirs)
deps=()
for p in "${ours[@]}"; do
    info="$(cd "$NOCTO_ROOT/packages/$p" && runuser -u nobody -- makepkg --printsrcinfo 2>/dev/null || makepkg --printsrcinfo)"
    mapfile -t -O "${#deps[@]}" deps < <(awk -F' = ' '/^\t(makedepends|checkdepends) = /{print $2}' <<<"$info")
    # link-time deps only for packages that compile code (CMake builds)
    if grep -q $'^\tmakedepends = cmake' <<<"$info"; then
        mapfile -t -O "${#deps[@]}" deps < <(awk -F' = ' '/^\tdepends = /{print $2}' <<<"$info")
    fi
done
# drop version constraints, our own packages and virtual names they provide
mapfile -t deps < <(printf '%s\n' "${deps[@]}" | sed 's/[<>=].*//' | sort -u |
    grep -vxF -f <(printf '%s\n' "${ours[@]}" calamares) | grep -v '^noctoware-')
log "installing ${#deps[@]} build dependencies"
pacman -S --needed --noconfirm "${deps[@]}"
