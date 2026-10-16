# Known issues and limitations — 0.1 Alpha

* **Signing key**: `keys/public` currently holds a *local development key*.
  It must be replaced by the project release key before anything is
  published (publish-repo.sh refuses dev-signed packages).
* **Repository not yet published**: `[noctoware]` is configured for
  GitHub Releases of `Zxre0/noctoware` (tag `repo-x86_64`). Until it is
  published there, `sudo pacman -Syu` on an installed system fails at the
  `[noctoware]` database download (pacman aborts the whole sync). The VM tests
  serve the repository locally instead. **The GitHub repository must be public**
  for pacman to download release assets without credentials (or move hosting,
  see docs/REPOSITORY.md).
* **Secure Boot** is off after installation (no shim / Microsoft-signed
  boot path); enable it afterwards with your own keys: `noctoware-secureboot`
  (docs/SECURE_BOOT.md). BIOS/GRUB installs are not covered.
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
* **SDDM after a crashed session**: if a desktop session is killed abruptly
  (compositor crash, `loginctl terminate-user`), SDDM 0.21 may not bring the
  greeter back (black screen). Switch to a text console (Ctrl+Alt+F3) and run
  `sudo systemctl restart sddm`. Normal logouts are not affected.
* **Two welcome apps on first Plasma login**: KDE's Welcome Center and the
  Noctoware Welcome app both open once.
* **ISO hosting**: the ISO (~5 GB including the offline KDE Plasma + driver
  cache) exceeds GitHub's 2 GiB release-asset limit; host it on object
  storage or a mirror (docs/RELEASE.md).
* **Hyprland "updated" notice** appears once in Revo Shell sessions (Revo's
  configuration does not suppress Hyprland's first-run dialog).
