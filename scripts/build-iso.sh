#!/usr/bin/env bash
# Build the Noctoware live/install ISO with archiso.
#
#   sudo scripts/build-iso.sh [--no-offline] [--keep-work]
#
# Must run as root (mkarchiso requirement).  Never touches the host's pacman
# keyring or databases: a private keyring (work/iso/gnupg) and a frozen
# snapshot of every repository database (work/iso/frozen) are used, so the
# live system and the ISO's offline package cache come from the same state.
#
# --no-offline   skip the offline cache (KDE Plasma + NVIDIA packages); the
#                installer then fetches those from the network when needed
# --keep-work    keep work/iso/archiso for debugging
source "$(dirname "$0")/lib/common.sh"

offline=1 keep=0
for a in "$@"; do
    case "$a" in
        --no-offline) offline=0 ;;
        --keep-work) keep=1 ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
        *) die "unknown option $a" "$E_USAGE" ;;
    esac
done
((EUID == 0)) || die "run as root: sudo $0 $*" "$E_USAGE"
need mkarchiso pacman pacman-key curl rsync sha256sum

ARCH_MIRROR="${NOCTO_ARCH_MIRROR:-https://geo.mirror.pkgbuild.com}"
CACHY_MIRROR="${NOCTO_CACHY_MIRROR:-https://mirror.cachyos.org/repo}"
W="$NOCTO_WORK/iso"
P="$W/profile"
OFFLINE_TARGETS=(noctoware-plasma
                 linux-cachyos-nvidia-open linux-cachyos-lts-nvidia-open nvidia-utils lib32-nvidia-utils
                 nvidia-settings libva-nvidia-driver egl-wayland nvidia-prime)

[[ -f "$NOCTO_REPO_DIR/noctoware.db.tar.gz" ]] || die "no [noctoware] repo: run scripts/build-packages.sh first" "$E_BUILD"
[[ -s "$NOCTO_KEYS_DIR/public/noctoware.gpg" ]] || die "missing keys/public/noctoware.gpg" "$E_SIGN"
for kr in archlinux cachyos; do
    [[ -f "/usr/share/pacman/keyrings/$kr.gpg" ]] || die "host lacks the $kr keyring (run scripts/prepare.sh)" "$E_DEPS"
done

log "preparing work directory $W"
rm -rf "$P" "$W/frozen" "$W/offline-db"
mkdir -p "$W" "$NOCTO_OUT"
rsync -a --delete "$NOCTO_ROOT/iso/" "$P/"

# 1. private pacman keyring: Arch + CachyOS + Noctoware signing key
if [[ ! -f "$W/gnupg/pubring.gpg" && ! -f "$W/gnupg/pubring.kbx" ]]; then
    log "creating private pacman keyring"
    pacman-key --gpgdir "$W/gnupg" --init >/dev/null
    pacman-key --gpgdir "$W/gnupg" --populate archlinux cachyos >/dev/null
fi
pacman-key --gpgdir "$W/gnupg" --add "$NOCTO_KEYS_DIR/public/noctoware.gpg" >/dev/null
while IFS=: read -r fpr _; do
    pacman-key --gpgdir "$W/gnupg" --lsign-key "$fpr" >/dev/null
done <"$NOCTO_KEYS_DIR/public/noctoware-trusted"

# 2. frozen repository snapshot
log "freezing repository databases"
for r in core extra multilib; do
    mkdir -p "$W/frozen/$r"
    curl -fsSL "$ARCH_MIRROR/$r/os/x86_64/$r.db" -o "$W/frozen/$r/$r.db" || die "download $r.db failed" "$E_BUILD"
done
mkdir -p "$W/frozen/cachyos"
curl -fsSL "$CACHY_MIRROR/x86_64/cachyos/cachyos.db" -o "$W/frozen/cachyos/cachyos.db" || die "download cachyos.db failed" "$E_BUILD"
archive_date="$(date -u -d yesterday +%Y/%m/%d)"
sed -e "s|@FROZEN@|$W/frozen|g" -e "s|@LOCALREPO@|$NOCTO_REPO_DIR|g" \
    -e "s|@ARCHIVE_DATE@|$archive_date|g" -e "s|@GPGDIR@|$W/gnupg|g" \
    "$P/pacman.conf.in" >"$P/pacman.build.conf"
rm -f "$P/pacman.conf.in"

# 3. offline package cache for optional components (same frozen state)
if [[ $offline -eq 1 ]]; then
    log "building offline package cache"
    db="$W/offline-db"
    mkdir -p "$db/sync"
    cp "$W"/frozen/*/*.db "$db/sync/"
    cp -L "$NOCTO_REPO_DIR/noctoware.db.tar.gz" "$db/sync/noctoware.db"
    pac() { pacman --config "$P/pacman.build.conf" --dbpath "$db" --noconfirm "$@"; }
    mapfile -t iso_pkgs < <(grep -vE '^\s*(#|$)' "$P/packages.x86_64")
    live_set="$(pac -Sp --print-format '%n' "${iso_pkgs[@]}" | sort -u)" || die "ISO package list does not resolve" "$E_BUILD"
    want_set="$(pac -Sp --print-format '%n' "${iso_pkgs[@]}" "${OFFLINE_TARGETS[@]}" | sort -u)" || die "offline targets do not resolve" "$E_BUILD"
    mapfile -t extra < <(comm -13 <(echo "$live_set") <(echo "$want_set"))
    cache="$P/airootfs/opt/noctoware/offline/pkg"
    mkdir -p "$cache" "$P/airootfs/opt/noctoware/offline/sync"
    if ((${#extra[@]})); then
        pac -Sw -dd --cachedir "$cache" "${extra[@]}" >/dev/null || die "offline download failed" "$E_BUILD"
    fi
    cp "$db"/sync/*.db "$P/airootfs/opt/noctoware/offline/sync/"
    ok "offline cache: ${#extra[@]} packages ($(du -sh "$cache" | cut -f1))"
fi

# 4. build
log "running mkarchiso (this takes a while)"
rm -rf "$W/archiso"
mkarchiso -v -w "$W/archiso" -o "$NOCTO_OUT" "$P" >"$W/mkarchiso.log" 2>&1 || {
    tail -40 "$W/mkarchiso.log" >&2
    die "mkarchiso failed (log: $W/mkarchiso.log)" "$E_BUILD"
}
[[ $keep -eq 1 ]] || rm -rf "$W/archiso"

iso="$(ls -t "$NOCTO_OUT"/noctoware-*.iso | head -1)"
(cd "$NOCTO_OUT" && sha256sum "$(basename "$iso")" >"$(basename "$iso").sha256")
if [[ -n "${SUDO_USER:-}" ]]; then
    chown "$SUDO_USER:" "$iso" "$iso.sha256"
    key="$(signing_key || true)"
    if [[ -n "$key" ]]; then
        sudo -u "$SUDO_USER" env GNUPGHOME="$NOCTO_GNUPGHOME" gpg --batch --yes --detach-sign -u "$key" "$iso" &&
            ok "signed $(basename "$iso").sig"
    fi
fi
ok "ISO ready: $iso ($(du -h "$iso" | cut -f1))"
