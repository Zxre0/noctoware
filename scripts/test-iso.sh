#!/usr/bin/env bash
# Test a Noctoware ISO in QEMU.
#
#   scripts/test-iso.sh [live|install|installed|all] [ISO] [-- extra test args]
#
#   live       boot the ISO (UEFI) and verify the live system
#   install    install to a fresh virtual disk with Calamares (desktop: hyprland)
#   installed  boot the installed disk and verify the installed system
#   all        live, install, installed
# Artifacts (screenshots, logs, results.json): tests/artifacts/<run>/
# Never touches physical disks: only image files under tests/artifacts.
source "$(dirname "$0")/lib/common.sh"
need qemu-system-x86_64 python3

mode="${1:-live}"; shift || true
iso="${1:-}"; [[ -n "$iso" && "$iso" != -- ]] && shift || iso="$(ls -t "$NOCTO_OUT"/noctoware-*.iso 2>/dev/null | head -1)"
[[ "${1:-}" == -- ]] && shift
[[ -f "$iso" ]] || die "no ISO found (build one with: sudo scripts/build-iso.sh)" "$E_USAGE"
[[ -r /dev/kvm ]] || die "/dev/kvm not accessible" "$E_DEPS"

run="$NOCTO_ROOT/tests/artifacts/$(date +%Y%m%d-%H%M%S)"
rc=0
step() {
    local name="$1"; shift
    log "test: $name"
    python3 "$NOCTO_ROOT/tests/vm/$name" "$@" || rc=$E_TEST
}
case "$mode" in
    live)      step test_live.py "$iso" --artifacts "$run/live" "$@" ;;
    install)   step test_install.py "$iso" --artifacts "$run/install" "$@" ;;
    installed) step test_installed.py --artifacts "$run/installed" "$@" ;;
    all)
        step test_live.py "$iso" --artifacts "$run/live" "$@"
        step test_install.py "$iso" --artifacts "$run/install" "$@"
        step test_installed.py --disk "$run/install/disk.raw" --vars "$run/install/OVMF_VARS.fd" --artifacts "$run/installed" "$@"
        ;;
    *) die "unknown mode $mode" "$E_USAGE" ;;
esac
((rc == 0)) && ok "all $mode tests passed ($run)" || die "$mode tests failed ($run)" "$E_TEST"
