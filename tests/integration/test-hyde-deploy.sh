#!/usr/bin/env bash
# Deploy HyDE from the built noctoware-hyde package into a throwaway HOME,
# offline, then check: theme applied, package tree untouched, user edits
# preserved on redeploy (package upgrade), and idempotency.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"; R="$root/repository/x86_64"
T="$(mktemp -d)"; trap 'chmod -R u+w "$T"; rm -rf "$T"' EXIT
for p in noctoware-hyde noctoware-branding hyprquery; do
    bsdtar -xf "$(ls "$R"/$p-[0-9]*.pkg.tar.zst | tail -1)" -C "$T/" 2>/dev/null || { mkdir -p "$T"; bsdtar -xf "$(ls "$R"/$p-[0-9]*.pkg.tar.zst | tail -1)" -C "$T"; }
done
cp "$root/desktop/hyde/bin/noctoware-hyde-deploy" "$T/usr/bin/"   # test the working-tree version
for l in "$T"/usr/share/noctoware/hyde/themes/Noctoware/{wallpapers,logo}/*; do ln -sfn "$T$(readlink "$l")" "$l"; done
H="$T/home"; mkdir -p "$H"
sum() { (cd "$T/usr" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum); }
before="$(sum)"
dep() { env -i PATH="$T/usr/bin:/usr/bin:/bin" HOME="$H" USER=test LANG=C.UTF-8 \
          NOCTO_HYDE_SHARE="$T/usr/share/noctoware/hyde" NOCTO_HYDE_VENV="$T/usr/lib/noctoware/hyde/python_env" \
          "$T/usr/bin/noctoware-hyde-deploy" "$@" >"$T/deploy.log" 2>&1; }
dep
[[ "$(sum)" == "$before" ]] || { echo "deploy modified the package tree"; exit 1; }
grep -q 'HYDE_THEME="Noctoware"' "$H/.local/state/hyde/staterc"
grep -q 'icon_theme=Papirus-Dark' "$H/.config/qt6ct/qt6ct.conf"
[[ -f "$H/.config/hypr/hyprland.lua" && -x "$H/.local/bin/hyde-shell" && -x "$H/.local/state/hyde/python_env/bin/python" ]]
grep -q '"/usr/share/noctoware/fastfetch/noctoware-ascii.txt"' "$H/.config/fastfetch/config.jsonc"
# user customisations survive a package upgrade (forced redeploy)
echo "-- my edit" >>"$H/.config/hypr/hyprland.lua"
echo "# my kitty" >>"$H/.config/kitty/kitty.conf"
echo "user-pick" >"$H/.config/fastfetch/config.jsonc"
cp -r "$H/.config/hyde/themes/Noctoware" "$H/.config/hyde/themes/My Theme"   # a user-installed theme
sed -i 's/^HYDE_THEME=.*/HYDE_THEME="My Theme"/' "$H/.local/state/hyde/staterc"
dep --force
grep -q -- "-- my edit" "$H/.config/hypr/hyprland.lua"
grep -q "# my kitty" "$H/.config/kitty/kitty.conf"
[[ "$(cat "$H/.config/fastfetch/config.jsonc")" == user-pick ]]
grep -q 'HYDE_THEME="My Theme"' "$H/.local/state/hyde/staterc"   # user's theme choice kept
[[ -d "$H/.config/hyde/themes/My Theme" ]]
# no-op when already current
dep && ! grep -q "deploying HyDE" <(tail -1 "$T/deploy.log")
echo "hyde deploy OK"
