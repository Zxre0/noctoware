# Testing

## Fast suite (no root, every commit; CI: `ci.yml`)
`tests/run-tests.sh` runs:

| test | what it proves |
|---|---|
| bash-syntax / python-compile / yaml-configs | every script and config parses |
| unit-tests (`tests/unit/test_gpu.py`, 24 cases) | GPU detection with real mock PCI IDs: RTX 20/30/40/50, GTX 16/10, hybrid Intel+NVIDIA and AMD+NVIDIA, AMD, Intel Arc, QEMU/VMware, no GPU, Secure Boot, DKMS, Steam's 32-bit Vulkan requirement |
| calamares-sequence | installer step order invariants, scripts exist, desktop chooser ↔ install script, bootloader handshake, Btrfs layout, machine-id regeneration |
| pkgbuild-srcinfo | every PKGBUILD parses |
| os-release | built `noctoware-release` contains the required identity |
| shell-switch | HyDE ↔ Revo profile swap loses nothing |
| kdeglobals-swap | Hyprland and Plasma keep separate kdeglobals |
| hyde-deploy | HyDE deploys **offline** from the built package into an empty home, applies the Noctoware theme, never modifies package files, **preserves user edits across a package upgrade**, is idempotent |
| repo-integrity | every package and db signed and consistent |

## Repository checks
* `scripts/check-dependencies.sh` — resolves every meta package and the ISO
  set against the real `[cachyos]` + Arch repos; conflict check; plasma-meta
  parity; NVIDIA module ↔ nvidia-utils/kernel version lock; HyDE dependency
  drift; Python ABI of the bundled venv.
* `scripts/validate-update.sh` — simulates `sudo pacman -Syu` from the
  published state to the new build (dependency + conflict checks).

## VM tests (QEMU + KVM, needs /dev/kvm)
Each test boots real QEMU VMs, talks to QMP (screenshots, keyboard/mouse) and
the QEMU guest agent (assertions run **inside** the guest), and writes
screenshots, logs and `results.json` to `tests/artifacts/`. Only image files
are written; no physical disk is ever touched. Screenshots come from inside
the guest (grim under Hyprland, Spectacle under KWin, `import` for the X11
greeter) because QEMU cannot read GL scanouts in egl-headless mode.

| script | scenario |
|---|---|
| `test_live.py ISO [--bios]` | live ISO boot (UEFI or BIOS) |
| `test_install.py ISO [--desktop plasma] [--fs ext4] [--bios] [--no-net] [--mock-gpu IDS]` | clicks through the real Calamares pages and installs to a fresh 64 GiB image |
| `test_installed.py --disk D [--plasma] [--bios] [--expect-gpu P]` | boots the installed image without the ISO and verifies it (below) |
| `test_plasma_later.py --disk D` | `sudo pacman -S noctoware-plasma` on a Hyprland-only install |
| `test_optin.py --disk D` | Claude Code via the official installer; Revo Shell fetch + switching |
| `test_recovery.py --disk D` | snapper rollback with `noctoware-rollback`; LTS recovery kernel |

`scripts/test-iso.sh all` runs live → install → installed.

[noctoware] is served to the guests from the build host (the public GitHub
repository is not published yet); Arch and CachyOS come from their mirrors.

### Results — 2026-10-16, ISO noctoware-0.1-alpha (KVM, virtio-gpu)
| scenario | result |
|---|---|
| live boot, UEFI | 20/20 |
| live boot, BIOS (syslinux) | 20/20 |
| install Hyprland, Btrfs, UEFI → installed system | 1/1 → 23/23 |
| install Hyprland, Btrfs, **BIOS** (GRUB) → installed system | 1/1 → 23/23 |
| install Hyprland, **ext4**, UEFI → installed system | 1/1 → 22/22 |
| install **Hyprland + KDE Plasma** → installed system incl. both sessions, switching, Steam in each | 1/1 → 29/29 |
| install KDE later with pacman on a Hyprland install | 6/6 |
| Claude Code official installer + Revo Shell (macOS) + shell switching | 10/10 |
| snapshot rollback + LTS recovery kernel | 9/9 |

What `test_installed.py` verifies: boots without the ISO; CachyOS kernel;
`os-release`; no live-session leftovers (liveuser, NOPASSWD sudo, autologin,
installer, archiso hooks, offline cache); new machine-id; boot loader
(systemd-boot static entries for both kernels on UEFI, GRUB on BIOS);
initramfs without archiso hooks; Btrfs subvolumes + snapper + install
snapshot (or ext4 without snapper); GPU-specific drivers only; Steam, gaming
stack, Codex, both kernels; zsh user; services; SDDM sessions and SDDM as the
only display manager; login through the Noctoware SDDM theme → Noctoware
Hyprland + first-login HyDE deploy; Fastfetch with real hardware info;
portals + PipeWire + WirePlumber; `codex` and the `claude` setup shim; Steam
client launch; with `--plasma` the Plasma session, separate kdeglobals, PATH,
Steam from Plasma and switching back; **real `sudo pacman -Syu`** upgrading a
Noctoware package with snap-pac pre/post snapshots and boot-file backup.

### Not covered by VMs
Physical GPUs (NVIDIA/AMD/Intel), Secure Boot, laptops (hybrid graphics,
suspend), Wi-Fi/Bluetooth hardware, multi-monitor setups. Hardware
compatibility is **not** claimed from VM results; see docs/GPU.md.

## Results log
See `docs/PROGRESS.md` for every run with dates and outcomes. Hardware
compatibility is not claimed from VM results.
