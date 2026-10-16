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

### Pending (requires root on the build host)
* Install archiso + QEMU display modules, build the ISO, run the QEMU tests
  (live boot, Calamares install, installed-system boot, `pacman -Syu`).
