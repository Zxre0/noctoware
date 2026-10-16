#!/usr/bin/env bash
# noctoware-shell must swap HyDE/Revo profiles without losing either config.
set -euo pipefail
trap 'echo "FAILED at ${BASH_SOURCE[0]##*/}:$LINENO: $BASH_COMMAND" >&2' ERR
root="$(cd "$(dirname "$0")/../.." && pwd)"; N="$root/desktop/revo/noctoware-shell"
H="$(mktemp -d)"; trap 'rm -rf "$H"' EXIT
mkdir -p "$H/.config/hypr" "$H/.config/kitty" "$H/.local/share/noctoware/shells/revo/hypr"
echo hyde-conf >"$H/.config/hypr/hyprland.lua"; echo hyde-kitty >"$H/.config/kitty/kitty.conf"
echo revo-conf >"$H/.local/share/noctoware/shells/revo/hypr/hyprland.lua"
run() { env -u XDG_CONFIG_HOME -u XDG_DATA_HOME HOME="$H" "$N" "$@"; }
run switch revo >/dev/null
[[ "$(cat "$H/.config/hypr/hyprland.lua")" == revo-conf ]]
[[ ! -e "$H/.config/kitty/kitty.conf" ]]
echo user-edit >>"$H/.config/hypr/hyprland.lua"          # edit while on revo
run switch hyde >/dev/null
[[ "$(cat "$H/.config/hypr/hyprland.lua")" == hyde-conf ]]
[[ "$(cat "$H/.config/kitty/kitty.conf")" == hyde-kitty ]]
run switch revo >/dev/null
grep -q user-edit "$H/.config/hypr/hyprland.lua"            # revo edit survived the round trip
run status | grep -q "active shell: revo"
! run switch nonsense 2>/dev/null
echo "shell switch OK"
