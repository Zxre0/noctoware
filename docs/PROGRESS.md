# Progress log

## 2026-10-15 — 0.1 Alpha development

### Done and verified (commands actually run, results observed)
* Project structure, central config, shared script library with exit codes.
* Original branding (logo, 3 wallpapers, Fastfetch ASCII logo) — rendered and
  visually checked; Fastfetch config verified on real hardware (shows live
  CPU/GPU/RAM, nothing hardcoded).
* 16 packages build and are signed; `[noctoware]` db signed; integrity check
  passes (`scripts/build-packages.sh`, `scripts/check-repo.sh`).
* `noctoware-hyde`: HyDE fa2fd57 packaged with an offline Python env built
  from HyDE's uv.lock; per-user deploy verified offline in a clean home
  (theme applied, user edits preserved across upgrade).
* Dependency closure of desktop/plasma/revo/installer and the 991-package ISO
  set resolves against live `[cachyos]` + Arch repos; caught and fixed:
  plasma-meta gained `kup`/`union`; `jack2` vs `pipewire-jack` provider
  conflict; NVIDIA module ↔ nvidia-utils coherence requires `[cachyos]` first.
* `pacman -Syu` simulation passes (also surfaced Arch's zlib→zlib-ng-compat
  replacement, handled by pacman).
* GPU detection: 24 unit tests pass; real host correctly classified as
  hybrid (RTX 4070 SUPER + Ryzen iGPU).
* Fast test suite: 11/11 pass.

### ISO + QEMU results (2026-10-15, UEFI/OVMF, virtio-gpu, KVM)
ISO: `noctoware-0.1-alpha-2026.10.15-x86_64.iso` (4.7 GB, incl. 910 MB
offline cache for KDE Plasma + NVIDIA), signed with the dev key.

* **Live boot** (`tests/vm/test_live.py`): boots in ~18 s; CachyOS kernel;
  os-release; SDDM autologin → Noctoware Hyprland + HyDE (Noctoware theme,
  waybar); Calamares autostarts; Steam/Codex present; `claude` shim; fastfetch
  shows the real host CPU; GPU detection = virtual; `pacman -Sy` syncs all five
  repos with signed databases.
* **Calamares GUI install** (`tests/vm/test_install.py`, driven through the
  real installer pages): erase-disk Btrfs install completes in ~70 s
  (offline, from the squashfs).
* **Installed system** (`tests/vm/test_installed.py`): **22/22 checks pass** —
  boots without the ISO; CachyOS kernel; no live leftovers; fresh machine-id;
  systemd-boot static entries for linux-cachyos + LTS; no archiso hooks in the
  initramfs; Btrfs subvolumes, snapper config and install snapshot; VM-only GPU
  drivers; Steam/Codex/kernels; SDDM the only DM; login through the Noctoware
  SDDM theme → Hyprland + HyDE first-login deploy; fastfetch; portal +
  PipeWire + WirePlumber; **real `sudo pacman -Syu`** (Arch + CachyOS +
  locally served [noctoware]) upgrades a Noctoware package with snap-pac
  pre/post snapshots and boot-file backup.

### Bugs found by testing and fixed
* CachyOS' prebuilt Calamares links boost 1.91 (Arch: 1.92) → Noctoware now
  builds `noctoware-calamares` from the same source.
* HyDE's idle daemon suspended the live system mid-install → no idle daemon
  and masked sleep targets on the live ISO.
* HyDE launches waybar concurrently with `uwsm finalize` → restart drop-in.
* Stock Arch mirrorlist has every server commented out → working defaults.
* Installer scripts vanished from the target before use → run-in-target.
* GPU driver pruning order, snap-pac during install, kernels needed before
  pacman hooks, missing qml dir with `calamares -c`, offline db signatures,
  pacman disabling `file://` servers (frozen-mirror proxy), welcome contrast.
