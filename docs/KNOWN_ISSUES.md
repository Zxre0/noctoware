# Known issues and limitations — 0.1 Alpha

* **Signing key**: `keys/public` currently holds a *local development key*.
  It must be replaced by the project release key before anything is
  published (publish-repo.sh refuses dev-signed packages).
* **Not yet published**: the GitHub Releases repository URL in
  `noctoware.conf` (`noctoware/noctoware`) is a placeholder until the project
  is pushed; until then `pacman -Syu` on an installed system can't reach
  `[noctoware]`
  (Arch/CachyOS updates work).
* **Secure Boot** unsupported out of the box (see docs/SECURE_BOOT.md).
* **Snapshot booting** from the boot menu is not available with systemd-boot
  (UEFI default); use `noctoware-rollback` (docs/RECOVERY.md).
* **NVIDIA pre-Turing** GPUs (GTX 10 and older) use nouveau; legacy
  proprietary branches are not packaged.
* **Physical hardware**: only virtual machines have been tested so far.
* **HyDE migrations** that need a running compositor are retried on the next
  HyDE update if they fail during the pre-session deploy (harmless).
* **kdeglobals**: shared by HyDE and Plasma; Noctoware swaps per-session
  copies. Starting the stock "Hyprland" session entries (not "Noctoware
  Hyprland") skips the swap.
* **HyDE `xdg-prefs`** (optional GUI) is not bundled (PySide6 size).
* **Revo Shell** is never shipped (no upstream license); opt-in download.
