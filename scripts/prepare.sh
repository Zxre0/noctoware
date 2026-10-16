#!/usr/bin/env bash
# Prepare an Arch Linux (or CachyOS) build host for Noctoware.
#
#   scripts/prepare.sh [--yes] [--no-qemu]
#
# Installs (with sudo pacman -S --needed) the tools needed to build packages,
# the ISO and to run the QEMU tests, and creates the local dev signing key.
# On plain Arch, the CachyOS keyring package is installed so archiso can verify
# [cachyos] packages: its fingerprint is printed for you to check first.
source "$(dirname "$0")/lib/common.sh"
need pacman sudo

yes=0 qemu=1
for a in "$@"; do
    case "$a" in
        --yes) yes=1 ;;
        --no-qemu) qemu=0 ;;
        -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
        *) die "unknown option $a" "$E_USAGE" ;;
    esac
done
grep -qE '^ID(_LIKE)?=.*arch' /etc/os-release || die "Noctoware builds require an Arch-based host" "$E_DEPS"

PKGS=(archiso arch-install-scripts base-devel git uv python python-gobject gtk4 librsvg imagemagick
      cmake ninja cli11 nlohmann-json hyprlang hyprutils pkgconf rsync curl gnupg jq squashfs-tools libisoburn)
((qemu)) && PKGS+=(qemu-desktop edk2-ovmf swtpm socat)
noconfirm=(); ((yes)) && noconfirm=(--noconfirm)

missing=()
for p in "${PKGS[@]}"; do pacman -Qq "$p" >/dev/null 2>&1 || missing+=("$p"); done
if ((${#missing[@]})); then
    log "installing: ${missing[*]}"
    sudo pacman -S --needed "${noconfirm[@]}" "${missing[@]}" || die "package installation failed" "$E_DEPS"
else
    ok "build tools present"
fi

if [[ ! -f /usr/share/pacman/keyrings/cachyos.gpg ]]; then
    warn "host has no CachyOS keyring (plain Arch host)"
    url="https://mirror.cachyos.org/repo/x86_64/cachyos/"
    f="$(curl -fsSL "$url" | grep -o 'cachyos-keyring-[0-9][^"]*-any\.pkg\.tar\.zst' | sort -V | tail -1)"
    [[ -n "$f" ]] || die "cannot locate cachyos-keyring on $url" "$E_DEPS"
    tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
    curl -fsSL "$url$f" -o "$tmp/$f"
    bsdtar -xOf "$tmp/$f" usr/share/pacman/keyrings/cachyos.gpg | gpg --show-keys --with-fingerprint
    echo "Verify this fingerprint against https://wiki.cachyos.org before continuing."
    if ((yes == 0)); then read -r -p "Install $f? [y/N] " a; [[ "$a" =~ ^[Yy]$ ]] || die "aborted" "$E_DEPS"; fi
    sudo pacman -U "${noconfirm[@]}" "$tmp/$f"
fi

"$(dirname "$0")/gen-dev-key.sh"
ok "host prepared. Next: scripts/build-packages.sh && sudo scripts/build-iso.sh"
