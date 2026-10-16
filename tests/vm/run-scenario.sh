#!/usr/bin/env bash
# run-scenario.sh NAME ISO [install args...] -- [installed args...]
# Install with test_install.py, then verify with test_installed.py, into
# tests/artifacts/NAME/{install,installed}; summary in NAME/summary.txt.
set -uo pipefail
name="$1" iso="$2"; shift 2
inst=() post=()
while (($#)) && [[ "$1" != -- ]]; do inst+=("$1"); shift; done
[[ "${1:-}" == -- ]] && shift; post=("$@")
root="$(cd "$(dirname "$0")/../.." && pwd)"; A="$root/tests/artifacts/$name"
rm -rf "$A"; mkdir -p "$A"
python3 -u "$root/tests/vm/test_install.py" "$iso" --artifacts "$A/install" "${inst[@]}" >"$A/install.log" 2>&1
echo "install exit=$?" >"$A/summary.txt"
args=(--disk "$A/install/disk.qcow2" --artifacts "$A/installed")
[[ -f "$A/install/OVMF_VARS.fd" ]] && args+=(--vars "$A/install/OVMF_VARS.fd")
python3 -u "$root/tests/vm/test_installed.py" "${args[@]}" "${post[@]}" >"$A/installed.log" 2>&1
echo "installed exit=$?" >>"$A/summary.txt"
grep -hE "^\[(PASS|FAIL)\]|checks passed" "$A/install.log" "$A/installed.log" >>"$A/summary.txt"
