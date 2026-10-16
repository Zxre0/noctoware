# Snapshots, rollback and recovery

## Layout
Btrfs installs use these subvolumes (`calamares/modules/mount.conf`):

| subvolume | mount | rolled back? |
|---|---|---|
| `@` | `/` | **yes** — this is what snapshots capture and rollbacks replace |
| `@home` | `/home` | no |
| `@root` | `/root` | no |
| `@srv` | `/srv` | no |
| `@cache` | `/var/cache` | no |
| `@tmp` | `/var/tmp` | no |
| `@log` | `/var/log` | no (logs survive a rollback for diagnosis) |
| `@snapshots` | `/.snapshots` | no (separate, so snapshots survive replacing `@`) |

## Automatic snapshots
* `snap-pac` takes a **pre** and **post** snapshot around every pacman
  transaction (`sudo pacman -Syu`, installs, removals).
* Before snap-pac's pre snapshot, `04-noctoware-boot-backup.hook` copies the
  current `/boot/vmlinuz-*` and `/boot/initramfs-*` into
  `/var/lib/noctoware/boot-backup/`, inside `@`. Every snapshot therefore
  contains the kernel image that matches its `/usr/lib/modules`.
* Cleanup: `snapper-cleanup.timer` keeps the 12 newest numbered snapshots
  (6 marked important). Timeline snapshots are off by default
  (`TIMELINE_CREATE` in `/etc/snapper/configs/root`).
* The installer creates snapshot #1, "Noctoware fresh install".

## Rolling back
```
sudo noctoware-rollback --list          # show snapshots
sudo noctoware-rollback 42              # restore @ from snapshot 42
reboot
```
`noctoware-rollback` renames the current `@` to `@.broken-<date>` (nothing is
deleted), snapshots #42 into a new `@`, and copies that snapshot's saved
kernel + initramfs back onto the ESP so the bootloader starts a kernel whose
modules exist in the restored root. Delete `@.broken-*` later with
`sudo btrfs subvolume delete` from a mount of `subvolid=5`.

### If the system no longer boots
1. In the boot menu pick **Noctoware Linux (LTS recovery kernel)**
   (or its *fallback initramfs* entry) and roll back from there; or
2. boot the Noctoware ISO, open a terminal and run
   `sudo noctoware-rollback --device /dev/<btrfs-partition> --boot <esp-mountpoint> 42`
   after mounting the ESP (e.g. `sudo mount /dev/nvme0n1p1 /mnt/esp`).

## Why not boot snapshots from the boot menu?
UEFI installs use systemd-boot with kernels on the ESP; systemd-boot cannot
read Btrfs snapshots. BIOS installs use GRUB: install `grub-btrfs` and enable
`grub-btrfsd` to get a "snapshots" submenu (optional, not default in 0.1).

## Kernel recovery strategy
* Two kernels are always installed: `linux-cachyos` (default) and
  `linux-cachyos-lts` (recovery), each with default and fallback initramfs
  entries. A broken kernel update therefore never leaves the machine without
  a bootable kernel.
* Both are updated by `pacman -Syu`; mkinitcpio's pacman hooks regenerate the
  images at the same paths the static boot entries use.
* NVIDIA: the prebuilt `linux-cachyos(-lts)-nvidia-open` modules are version
  locked to their kernels by CachyOS, so pacman upgrades kernel and module
  together or not at all. With the DKMS variant, `dkms` rebuilds on update.

## ext4 installs
No snapshots (snapper requires Btrfs). Recovery relies on the LTS kernel and
the fallback initramfs entries, and on reinstalling packages from the ISO.
