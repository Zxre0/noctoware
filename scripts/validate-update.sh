#!/usr/bin/env bash
# Simulate `sudo pacman -Syu` from the previously published Noctoware state to
# the locally built repository — without root and without touching the host.
#
#   scripts/validate-update.sh            old state = currently published repo
#                                         (falls back to a fresh-install check)
#   scripts/validate-update.sh --remote   only verify the published repo itself
#
# Method: fakeroot + pacman --dbonly records an install of noctoware-desktop
# (and noctoware-plasma) from the OLD [noctoware] db plus current Arch/CachyOS
# dbs into a throwaway database, then swaps in the NEW db and asks pacman for
# the full system upgrade.  Dependency breaks, conflicts and replaces show up
# exactly as they would for users.
source "$(dirname "$0")/lib/common.sh"
need pacman fakeroot curl python3 vercmp

mode="${1:-}"
"$(dirname "$0")/check-dependencies.sh" >/dev/null || die "fix check-dependencies.sh failures first" "$E_DEPS"
DC="$NOCTO_WORK/depcheck"           # sync dbs downloaded by check-dependencies.sh
T="$NOCTO_WORK/update-sim"; rm -rf "$T"; mkdir -p "$T/db/sync" "$T/root"
cp "$DC"/db/sync/{core,extra,multilib,cachyos}.db "$T/db/sync/"

old_db="$T/old-noctoware.db"
if curl -fsSL "$NOCTO_REPO_URL/noctoware.db" -o "$old_db" 2>/dev/null; then
    log "old state: published repo ($NOCTO_REPO_URL)"
else
    [[ "$mode" == --remote ]] && die "no published repository at $NOCTO_REPO_URL" "$E_TEST"
    warn "nothing published yet: validating a fresh install + no-op upgrade"
    cp -L "$NOCTO_REPO_DIR/noctoware.db.tar.gz" "$old_db"
fi
[[ "$mode" == --remote ]] && new_db="$old_db" || new_db="$NOCTO_REPO_DIR/noctoware.db.tar.gz"

conf="$T/pacman.conf"
sed "s|file://$NOCTO_REPO_DIR|$NOCTO_REPO_URL|" "$DC/pacman.conf" >"$conf"
pac() { fakeroot pacman --config "$conf" --root "$T/root" --dbpath "$T/db" --noconfirm --disable-sandbox "$@"; }
echo "noctoware cachyos core extra multilib" >"$T/db/sync/ORDER"
pkgset() { python3 -I "$NOCTO_ROOT/scripts/lib/pkgset.py" "$@"; }

# old state: what a machine installed from the ISO (+ Plasma) looks like
cp -L "$old_db" "$T/db/sync/noctoware.db"
mapfile -t targets < <(grep -vE '^\s*(#|$)' "$NOCTO_ROOT/iso/packages.x86_64")
old_set="$(pac -Sp --print-format '%n' "${targets[@]}" noctoware-plasma 2>"$T/old.err")" ||
    { cat "$T/old.err" >&2; die "old state does not resolve" "$E_TEST"; }
pkgset mklocal "$T/db/sync" "$T/db/local" <<<"$old_set"
ok "old state: $(pac -Qq | wc -l) packages recorded"

# new state: swap in the new [noctoware] db and ask for the system upgrade
cp -L "$new_db" "$T/db/sync/noctoware.db"
log "simulating pacman -Syu"
if ! up="$(pac -Su --print --print-format '%n %v' 2>&1)"; then
    echo "$up" | tail -20 >&2
    die "pacman -Syu would FAIL for users (dependency resolution)" "$E_TEST"
fi
grep -E '^(noctoware|hyprquery|bibata)' <<<"$up" | sed 's/^/  ↑ /' || true
# post-upgrade set: every installed name resolved against the new state
# (follows replaces=, e.g. zlib -> zlib-ng-compat), then conflict-checked
post="$(pac -Sp --print-format '%n' $(pac -Qq) 2>/dev/null | sort -u)"
if c="$(pkgset conflicts "$T/db/sync" <<<"$post")"; then
    ok "pacman -Syu resolves cleanly ($(grep -c . <<<"$up" || true) package(s) to upgrade, no conflicts)"
else
    echo "$c" >&2; die "pacman -Syu would hit package conflicts" "$E_TEST"
fi
