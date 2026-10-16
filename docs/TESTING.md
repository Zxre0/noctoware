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

## VM tests (QEMU + OVMF, needs /dev/kvm)
`scripts/test-iso.sh live|install|installed|all [ISO]` — uses QMP for
screenshots/input and the QEMU guest agent to run assertions **inside** the
guest. Artifacts (screenshots, results.json, serial/qemu logs) land in
`tests/artifacts/`. Only image files are written; no physical disk is ever
touched.

## Results log
See `docs/PROGRESS.md` for every run with dates and outcomes. Hardware
compatibility is not claimed from VM results.
