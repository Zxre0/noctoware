#!/usr/bin/env bash
# Full release test suite in QEMU (two lanes in parallel, ~1.5 h).
#   tests/vm/run-all.sh [ISO]
# Results: tests/artifacts/release-<date>/SUMMARY.md
set -uo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
iso="$(realpath "${1:-$(ls -t "$root"/out/noctoware-*.iso | head -1)}")"
R="$root/tests/artifacts/release-$(date +%Y%m%d-%H%M)"
mkdir -p "$R"
V="$root/tests/vm"
py() { python3 -u "$@"; }

lane_a() {
    py "$V/test_live.py" "$iso" --artifacts "$R/live-uefi" >"$R/live-uefi.log" 2>&1
    py "$V/test_install.py" "$iso" --artifacts "$R/hypr/install" >"$R/hypr-install.log" 2>&1
    py "$V/test_installed.py" --disk "$R/hypr/install/disk.qcow2" --vars "$R/hypr/install/OVMF_VARS.fd" \
        --artifacts "$R/hypr/installed" >"$R/hypr-installed.log" 2>&1
    # derived scenarios on copies of the Hyprland install
    for t in plasma_later optin recovery multimonitor; do
        cp "$R/hypr/install/disk.qcow2" "$R/$t.qcow2"
        py "$V/test_$t.py" --disk "$R/$t.qcow2" --vars "$R/hypr/install/OVMF_VARS.fd" \
            --artifacts "$R/$t" >"$R/$t.log" 2>&1
        rm -f "$R/$t.qcow2"
    done
}
lane_b() {
    py "$V/test_live.py" "$iso" --bios --artifacts "$R/live-bios" >"$R/live-bios.log" 2>&1
    py "$V/test_install.py" "$iso" --bios --artifacts "$R/bios/install" >"$R/bios-install.log" 2>&1
    py "$V/test_installed.py" --bios --disk "$R/bios/install/disk.qcow2" --artifacts "$R/bios/installed" \
        >"$R/bios-installed.log" 2>&1
    py "$V/test_install.py" "$iso" --fs ext4 --artifacts "$R/ext4/install" >"$R/ext4-install.log" 2>&1
    py "$V/test_installed.py" --disk "$R/ext4/install/disk.qcow2" --vars "$R/ext4/install/OVMF_VARS.fd" \
        --artifacts "$R/ext4/installed" >"$R/ext4-installed.log" 2>&1
    py "$V/test_install.py" "$iso" --no-net --mock-gpu 1af4:1050,8086:9bc4,10de:2560 --desktop plasma \
        --artifacts "$R/plasma-nvidia/install" >"$R/plasma-nvidia-install.log" 2>&1
    py "$V/test_installed.py" --plasma --expect-gpu hybrid-nvidia --disk "$R/plasma-nvidia/install/disk.qcow2" \
        --vars "$R/plasma-nvidia/install/OVMF_VARS.fd" --artifacts "$R/plasma-nvidia/installed" \
        >"$R/plasma-nvidia-installed.log" 2>&1
}

lane_a & a=$!
lane_b & b=$!
wait $a $b

{
    echo "# Noctoware release test run — $(date -Is)"
    echo
    echo "ISO: \`$(basename "$iso")\` (sha256 \`$(sha256sum "$iso" | cut -c1-16)…\`)"
    echo
    echo "| scenario | result |"
    echo "|---|---|"
    for l in live-uefi live-bios hypr-install hypr-installed bios-install bios-installed ext4-install \
             ext4-installed plasma-nvidia-install plasma-nvidia-installed plasma_later optin recovery multimonitor; do
        res="$(grep -hoE '[0-9]+/[0-9]+ checks passed' "$R/$l.log" 2>/dev/null | tail -1)"
        echo "| $l | ${res:-did not finish} |"
    done
    echo
    echo "## Failures"
    grep -h '^\[FAIL\]' "$R"/*.log 2>/dev/null || echo "none"
} >"$R/SUMMARY.md"
cat "$R/SUMMARY.md"
