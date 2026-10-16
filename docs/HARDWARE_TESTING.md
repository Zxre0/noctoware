# Hardware test checklist

VM tests (docs/TESTING.md) do not prove hardware compatibility. Use this on
real machines and attach the output of `noctoware-hwreport` to each result.
**Use a spare disk or a machine you can wipe** — installation erases the
selected disk.

## Per machine
1. Boot the ISO (UEFI; also BIOS if the machine supports CSM). Note the GPU,
   whether the live desktop appears, and whether the installer starts.
2. Install (Btrfs, default desktop; once per vendor also "Hyprland + KDE Plasma").
3. First boot: log into **Noctoware Hyprland** and **Plasma (Wayland)**.
4. Check:
   - [ ] `noctoware-gpu plan` matches the hardware; `/etc/noctoware/gpu.json`
   - [ ] NVIDIA: `nvidia-smi` works, `cat /sys/module/nvidia_drm/parameters/modeset` = `Y`
   - [ ] `vulkaninfo --summary` lists the real GPU (not only llvmpipe)
   - [ ] Steam starts; a Vulkan/Proton game runs; `gamemoderun`, `mangohud` work
   - [ ] audio output/input (PipeWire), Wi-Fi/Ethernet (NetworkManager), Bluetooth pairing
   - [ ] screen sharing in a browser (xdg-desktop-portal) in both desktops
   - [ ] external/second monitor, hot-plug, different refresh rates
   - [ ] suspend/resume (laptops: lid close), especially with NVIDIA
   - [ ] hybrid laptops: `prime-run glxinfo | grep renderer` shows the NVIDIA GPU
   - [ ] `sudo pacman -Syu` (after the repository is published)
   - [ ] optional: `sudo noctoware-secureboot setup` with the firmware in Setup Mode
5. Run `noctoware-hwreport`, review it, and record the result in
   docs/TESTING.md ("Hardware results").

## Priority matrix for 0.1
| class | example | why |
|---|---|---|
| NVIDIA RTX 40 desktop | RTX 4070 SUPER | most common gaming setup; CachyOS nvidia-open path |
| NVIDIA RTX 50 | RTX 5070 | newest generation (open modules only) |
| NVIDIA RTX 20/30 | RTX 2060 / 3060 | Turing boundary, GSP firmware |
| AMD RDNA2/3 | RX 6600 / 7800 XT | RADV path |
| Intel Arc / iGPU | A750, Iris Xe | ANV + media driver |
| Hybrid laptop | Intel + RTX 3050/4060 | PRIME, power management |
