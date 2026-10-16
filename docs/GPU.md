# GPU drivers

`noctoware-gpu` (from `noctoware-system`) reads `/sys/bus/pci/devices`,
classifies every display controller and installs **only** the matching stack.
The installer runs `noctoware-gpu apply --root /tmp/calamares-root`; afterwards
you can inspect it with `noctoware-gpu plan` or the Welcome app.

| Hardware | Packages | Notes |
|---|---|---|
| all | mesa, lib32-mesa, vulkan-icd-loader (+lib32), vulkan-mesa-layers | |
| AMD | vulkan-radeon, lib32-vulkan-radeon | RADV |
| Intel | vulkan-intel, lib32-vulkan-intel, intel-media-driver, vpl-gpu-rt | ANV, VA-API, oneVPL |
| NVIDIA Turing+ (RTX 20/30/40/50, GTX 16) | linux-cachyos-nvidia-open, linux-cachyos-lts-nvidia-open, nvidia-utils, lib32-nvidia-utils, nvidia-settings, libva-nvidia-driver, egl-wayland | open kernel modules prebuilt by CachyOS for both kernels; `nvidia_drm modeset=1 fbdev=1`; suspend/hibernate/resume services |
| NVIDIA hybrid laptop (+ Intel/AMD iGPU) | both stacks + nvidia-prime | NVIDIA-only GL/GBM variables are **not** forced; use `prime-run <app>` or Steam's per-game launch options |
| NVIDIA pre-Turing | vulkan-nouveau (+lib32) | open modules do not support these GPUs; legacy proprietary branches are not packaged in 0.1 |
| QEMU/virtio, VMware, VirtualBox | vulkan-swrast (+virtio venus), guest tools | |

Detection is the PCI device ID: every NVIDIA GPU with device ID ≥ 0x1E00
(TU102) is Turing or newer. `tests/unit/test_gpu.py` covers each case with
real PCI IDs (RTX 2080/3060M/4070S/4090/5090, GTX 1660/1080, Arc A770,
RX 7900 XTX, hybrids, VMs, Secure Boot, DKMS).

## Testing without the hardware
`noctoware-gpu` reads PCI ids from `/run/noctoware/gpu-mock-ids` when that
file exists (tmpfs only, never persisted). The VM tests use it to install
the hybrid Intel + NVIDIA stack through the real installer, fully offline:
`tests/vm/test_install.py ISO --no-net --mock-gpu 1af4:1050,8086:9bc4,10de:2560`.
This proves package selection, offline availability and system integration,
not that the driver works on a physical GPU.

## DKMS alternative
`NOCTO_NVIDIA_DKMS=1 noctoware-gpu apply --root / --dkms` (or at install
time) uses `nvidia-open-dkms` + kernel headers instead of the prebuilt
modules. Never both: the plan removes the other variant.

## Secure Boot
The NVIDIA modules and systemd-boot are not signed with keys your firmware
trusts. Noctoware 0.1 expects Secure Boot **disabled**; see
`docs/SECURE_BOOT.md` for enrolling your own keys with `sbctl`.

## Hardware validation status
Only virtual GPUs have been tested by the Noctoware test suite. Compatibility
with physical NVIDIA/AMD/Intel GPUs is *not* claimed until tested on real
hardware (see `docs/TESTING.md`).
