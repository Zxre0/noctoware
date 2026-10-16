# Progress log — Noctoware Linux 0.1 Alpha

## Status against the Definition of Done (2026-10-16)

| Requirement | Status | Evidence |
|---|---|---|
| Bootable ISO exists | ✅ | `out/noctoware-0.1-alpha-2026.10.16-x86_64.iso` (≈5 GB incl. ≈1 GB offline cache), signed (dev key) |
| ISO passes UEFI QEMU boot testing | ✅ | `test_live.py`: 20/20 UEFI, 20/20 BIOS |
| Calamares installs the OS | ✅ | GUI-driven installs: Btrfs/ext4, UEFI/BIOS, Hyprland / Hyprland+Plasma, fully offline |
| Installed system boots | ✅ | `test_installed.py` 22–29 checks per variant |
| CachyOS kernel active | ✅ | `linux-cachyos` from `[cachyos]` (+ `linux-cachyos-lts` recovery kernel, boot-tested) |
| Hyprland and HyDE work | ✅ | login via SDDM → Noctoware Hyprland, HyDE deployed (offline), waybar, portals, PipeWire; multi-monitor |
| Noctoware branding applied | ✅ | os-release, SDDM theme, Calamares, boot menus, GRUB, wallpapers, Fastfetch, Plasma L&F |
| Steam installed | ✅ | installed and the Steam client launches from Hyprland and from Plasma |
| Claude Code / Codex | ✅ | Codex preinstalled (Apache-2.0); Claude Code via consent-gated official installer → `claude` 2.1.301 verified |
| Noctoware pacman repository functions | ✅ (locally) | signed `[noctoware]`, served to VMs; integrity + dependency + update simulation scripts |
| `sudo pacman -Syu` succeeds | ✅ in VMs / ⏳ publicly | real `pacman -Syu` upgrades a Noctoware package with snapshots; **public repo not published yet** (needs your decision: docs/RELEASE.md) |
| All automated tests pass | ✅ | fast suite 12/12; VM release suite (docs/TESTING.md); CI on GitHub |
| Known limitations documented | ✅ | docs/KNOWN_ISSUES.md |

## Key decisions
* **Arch base, CachyOS kernel**: repo order `[noctoware]` → `[cachyos]` (generic
  x86-64) → Arch. `[cachyos]` must precede Arch: its NVIDIA modules pin
  CachyOS' `nvidia-utils` build.
* **Offline installer**: Calamares copies the live squashfs (unpackfs);
  KDE Plasma and every GPU driver package come from a signed offline cache on
  the ISO, resolved from the same frozen database snapshot as the image.
* **HyDE as a package**: pinned upstream, Python env built from HyDE's
  `uv.lock`, network-fetched tools vendored (grimblast, app2unit), deployed
  per user by HyDE's own `deez` with its preserve/sync semantics.
* **systemd-boot static entries** (UEFI) so ordinary `pacman -Syu` kernel
  updates keep booting; GRUB on BIOS.
* **Snapshots**: Btrfs layout with `@snapshots`; snap-pac pre/post;
  boot-file backup in every snapshot so `noctoware-rollback` restores a
  matching kernel; LTS recovery kernel.
* **Licensing**: Claude Code (all rights reserved) and Revo Shell (no
  license) are never redistributed; both are fetched from upstream only with
  user consent.

## Bugs found by the VM tests and fixed (selection)
* CachyOS' prebuilt Calamares linked against an older boost → built from
  source as `noctoware-calamares`.
* HyDE's first login downloaded tools from the internet and failed offline.
* GRUB on Btrfs could not read kernel images with a sparse tail (`no-holes`)
  → boot images rewritten non-sparse at install and after every kernel update.
* HyDE's idle daemon suspended the live system mid-installation.
* waybar raced `uwsm finalize`; Revo inherited HyDE's `HYPRLAND_CONFIG`.
* Offline installs: missing driver packages in the cache; installer deps
  removed before KDE needed them.
* Arch's stock mirrorlist ships with every server commented out.
* `plasma-meta` pulls in a second display manager (plasma-login-manager).
* `jack2` vs `pipewire-jack` provider conflict.

## Open items
1. Publish `[noctoware]` (release key, public repo, `release-repo` workflow).
2. ISO hosting (GitHub release assets are limited to 2 GiB).
3. Real-hardware validation (NVIDIA RTX 20–50, AMD, Intel, hybrid laptop).
4. ~~Secure Boot~~ done: `noctoware-secureboot` (own keys via sbctl), verified in QEMU with enforcement.
