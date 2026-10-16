# KDE Plasma 6 (optional desktop)

Hyprland + HyDE is always installed and stays the default. KDE Plasma 6 is
an **additional** Wayland session:

* during installation: choose **Noctoware Hyprland + KDE Plasma** on the
  Desktop page (installed from the ISO's offline cache, network fallback);
* later: `sudo pacman -S noctoware-plasma`, log out, choose
  **Plasma (Wayland)** in SDDM. Your current session is not switched.

`noctoware-plasma` = every component of Arch's `plasma-meta` **except
`plasma-login-manager`** (SDDM stays the only display manager) + Konsole,
Dolphin, Kate, Ark, Gwenview, Okular, Spectacle, KCalc, Filelight, Partition
Manager, thumbnailers, KWallet manager, SDDM KCM, plus Noctoware branding:
look-and-feel `org.noctoware.desktop`, `Noctoware` color scheme, wallpaper,
Konsole profile. Branding is installed as **system defaults** (`/etc/xdg`,
lowest priority), so it never overwrites settings a user has changed.

## Coexistence with HyDE
* HyDE's session environment lives in `~/.config/uwsm/` and only applies to
  the Hyprland session.
* Both HyDE and Plasma write `~/.config/kdeglobals`. Noctoware keeps one copy
  per desktop (`/usr/lib/noctoware/kdeglobals-swap`, run by the Hyprland
  session wrapper and Plasma's `plasma-workspace/env` hook), so switching
  desktops never leaks one desktop's theme into the other.
* Installing or removing Plasma does not touch HyDE files.
