# Secure Boot (not supported out of the box in 0.1)

Noctoware 0.1 installs an unsigned systemd-boot and, on NVIDIA machines,
kernel modules that are not signed by a key your firmware trusts. Disable
Secure Boot in firmware setup before installing.

To use Secure Boot with your own keys afterwards (advanced):
```
sudo pacman -S sbctl
sudo sbctl status            # firmware must be in Setup Mode
sudo sbctl create-keys
sudo sbctl enroll-keys -m    # -m keeps Microsoft keys (needed by many GPUs' option ROMs)
sudo sbctl sign -s /boot/EFI/systemd/systemd-bootx64.efi
sudo sbctl sign -s /boot/EFI/BOOT/BOOTX64.EFI
sudo sbctl sign -s /boot/vmlinuz-linux-cachyos
sudo sbctl sign -s /boot/vmlinuz-linux-cachyos-lts
```
sbctl's pacman hook re-signs files on updates. Out-of-tree modules (NVIDIA)
additionally need module signing or a kernel that does not enforce module
signatures under lockdown; this is outside the scope of 0.1.
