# Revo Shell (optional)

Revo Shell (https://github.com/vzbc/revo-shell) is a third-party Quickshell
desktop with several interfaces (default for Noctoware: `macos`).

**Licensing:** the upstream repository has no license file, so Noctoware
cannot redistribute it. It is not on the ISO and not in `[noctoware]`.
`noctoware-revo` contains only Noctoware's own scripts.

```
sudo pacman -S noctoware-revo
noctoware-revo-setup                      # asks for consent, downloads from upstream
noctoware-revo-setup --interfaces macos,ii,k4
noctoware-shell status
noctoware-shell switch hyde               # back to HyDE (and `switch revo` again)
noctoware-shell interface macduo          # change the Revo interface
noctoware-shell doctor                    # Revo's health check (hyprpm plugins …)
```
Both shells write `~/.config/{hypr,rofi,kitty,quickshell,waybar}`;
`noctoware-shell` keeps a full copy per shell and swaps them, so neither
configuration is lost. Log out and in after switching.

Hyprland plugins: Revo uses `hyprpm` plugins compiled against the running
Hyprland. After a Hyprland update, `hyprpm update` rebuilds them (the setup
runs it once; `noctoware-shell doctor` reports mismatches). Revo's installer
pins nothing; `noctoware-revo-setup` checks out commit 62e13cd (tested) unless
`--latest` is given.
