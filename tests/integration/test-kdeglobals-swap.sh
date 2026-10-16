#!/usr/bin/env bash
# Hyprland (HyDE) and Plasma must each keep their own ~/.config/kdeglobals.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"; S="$root/desktop/session/kdeglobals-swap"
H="$(mktemp -d)"; trap 'rm -rf "$H"' EXIT
run() { env -u XDG_CONFIG_HOME -u XDG_STATE_HOME HOME="$H" sh "$S" "$@"; }
mkdir -p "$H/.config"; printf '[UiSettings]\nColorScheme=colors\n' >"$H/.config/kdeglobals"   # written by HyDE
run plasma
[[ ! -e "$H/.config/kdeglobals" ]]                          # first Plasma login: system defaults
printf '[General]\nColorScheme=Noctoware\n' >"$H/.config/kdeglobals"                     # user tweaks Plasma
run hyprland
grep -q 'ColorScheme=colors' "$H/.config/kdeglobals"         # HyDE's copy is back
run plasma
grep -q 'ColorScheme=Noctoware' "$H/.config/kdeglobals"      # Plasma's copy is back
run plasma; grep -q 'ColorScheme=Noctoware' "$H/.config/kdeglobals"   # idempotent
echo "kdeglobals swap OK"
