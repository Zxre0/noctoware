# Secure Boot

Noctoware supports UEFI Secure Boot with **your own keys** on systemd-boot
installs (the default on UEFI). There is no shim/Microsoft-signed path yet,
so Secure Boot is off on a fresh install; turn it on afterwards:

1. In the firmware settings, reset/clear the Secure Boot keys so the firmware
   is in **Setup Mode** (wording varies: "Reset to Setup Mode", "Clear keys").
2. Boot Noctoware and run
   ```
   sudo pacman -S sbctl
   sudo noctoware-secureboot setup          # add --no-microsoft only if you know you don't need them
   sudo reboot
   ```
   This creates keys with `sbctl`, enrolls them **together with Microsoft's**
   (GPU/NIC option ROMs and Windows dual-boot usually need them), and signs
   systemd-boot (including the `systemd-bootx64.efi.signed` copy `bootctl`
   installs on updates) and both kernels.
3. If the firmware does not enable Secure Boot by itself, enable it.

`sbctl`'s pacman hook re-signs boot files on every update.
`noctoware-secureboot status` / `verify` show the state.

**NVIDIA and other out-of-tree modules** keep working: the CachyOS kernels
enable no lockdown and do not enforce module signatures under Secure Boot
(`/sys/kernel/security/lockdown` = `[none]`, `sig_enforce` = `N`, verified in
QEMU with Secure Boot enforced).

Verified in QEMU (OVMF Secure Boot firmware): `tests/vm/test_secureboot.py` —
Setup Mode → enroll → reboot with Secure Boot enforced → kernel update
re-signed automatically → boots again (7/7). Real-firmware behaviour varies;
keep the Noctoware ISO at hand and know how to disable Secure Boot.

BIOS/GRUB installs: not supported by this tool.
