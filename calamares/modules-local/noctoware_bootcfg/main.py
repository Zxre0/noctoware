#!/usr/bin/env python3
# Noctoware boot configuration for Calamares.
#
# UEFI: installs systemd-boot and writes STATIC Arch-style loader entries
#       (/vmlinuz-<pkgbase>, /initramfs-<pkgbase>.img).  mkinitcpio's pacman
#       hooks regenerate exactly those paths on every kernel update, so
#       `pacman -Syu` keeps the system bootable with no extra tooling.
#       Entries: default + fallback for linux-cachyos and the
#       linux-cachyos-lts recovery kernel.
# BIOS: sets globalstorage so the stock `bootloader` module installs GRUB.
#
# SPDX-License-Identifier: MIT
import os
import subprocess

import libcalamares

GS_KEY = "noctoware_bootloader"
TITLES = {"linux-cachyos": "Noctoware Linux", "linux-cachyos-lts": "Noctoware Linux (LTS recovery kernel)"}
SORT = {"linux-cachyos": "1", "linux-cachyos-lts": "2"}


def pretty_name():
    return "Configuring boot loader"


def kernel_params():
    gs = libcalamares.globalstorage
    params = list(libcalamares.job.configuration.get("kernelParams", ["quiet"]))
    params.append("rw")
    root_uuid, crypt, resume = "", [], ""
    for p in gs.value("partitions") or []:
        luks = "luksMapperName" in p
        if p.get("fs") == "linuxswap" and p.get("claimed", True):
            resume = f"resume=/dev/mapper/{p['luksMapperName']}" if luks else f"resume=UUID={p['uuid']}"
        if p.get("mountPoint") == "/":
            root_uuid = p.get("uuid", "")
            if luks:
                crypt = [f"rd.luks.name={p['luksUuid']}={p['luksMapperName']}",
                         f"root=/dev/mapper/{p['luksMapperName']}"]
            if p.get("fs") == "btrfs":
                sub = gs.value("btrfsRootSubvolume")
                if sub:
                    params.append("rootflags=subvol=" + sub)
    if crypt:
        params.extend(crypt)
    elif root_uuid:
        params.append(f"root=UUID={root_uuid}")
    else:
        raise RuntimeError("could not determine the root filesystem UUID")
    if resume:
        params.append(resume)
    return params


def installed_kernels(root):
    kernels = []
    moddir = os.path.join(root, "usr/lib/modules")
    for kver in sorted(os.listdir(moddir)):
        pb = os.path.join(moddir, kver, "pkgbase")
        if os.path.isfile(pb):
            kernels.append(open(pb).read().strip())
    return kernels


def install_systemd_boot(root):
    esp = libcalamares.globalstorage.value("efiSystemPartition") or "/boot"
    if esp != "/boot":
        raise RuntimeError(f"Noctoware expects the ESP at /boot (got {esp}); fix partition.conf")
    # --graceful: still succeed when firmware NVRAM is read-only; the
    # removable-media fallback path (EFI/BOOT/BOOTX64.EFI) is always written.
    rc = libcalamares.utils.target_env_call(["bootctl", "--esp-path=/boot", "install", "--graceful"])
    if rc != 0:
        raise RuntimeError(f"bootctl install failed with exit code {rc}")

    opts = " ".join(kernel_params())
    entries = os.path.join(root, "boot/loader/entries")
    os.makedirs(entries, exist_ok=True)
    kernels = installed_kernels(root)
    if "linux-cachyos" not in kernels:
        raise RuntimeError("linux-cachyos is not installed in the target")
    for pkgbase in kernels:
        title = TITLES.get(pkgbase, f"Noctoware Linux ({pkgbase})")
        stem = "noctoware" if pkgbase == "linux-cachyos" else f"noctoware-{pkgbase.removeprefix('linux-cachyos-') or pkgbase}"
        for kind, suffix in (("", ""), ("-fallback", " — fallback initramfs")):
            with open(os.path.join(entries, f"{stem}{kind}.conf"), "w") as f:
                f.write(f"title   {title}{suffix}\n"
                        f"sort-key {SORT.get(pkgbase, '3')}{'b' if kind else 'a'}\n"
                        f"linux   /vmlinuz-{pkgbase}\n"
                        f"initrd  /initramfs-{pkgbase}{kind}.img\n"
                        f"options {opts}\n")
    with open(os.path.join(root, "boot/loader/loader.conf"), "w") as f:
        f.write("default noctoware.conf\ntimeout 4\nconsole-mode keep\neditor no\n")
    # Keep /etc/kernel/cmdline in sync for tools that read it (kernel-install, sbctl)
    os.makedirs(os.path.join(root, "etc/kernel"), exist_ok=True)
    with open(os.path.join(root, "etc/kernel/cmdline"), "w") as f:
        f.write(opts + "\n")
    # Update the boot loader binary itself when systemd is upgraded
    libcalamares.utils.target_env_call(["systemctl", "enable", "systemd-boot-update.service"])


def run():
    gs = libcalamares.globalstorage
    root = gs.value("rootMountPoint")
    fw = gs.value("firmwareType")
    try:
        if fw == "efi":
            install_systemd_boot(root)
            gs.insert(GS_KEY, "none")      # stock bootloader module: nothing more to do
        else:
            gs.insert(GS_KEY, "grub")      # stock bootloader module installs GRUB (i386-pc)
    except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
        return ("Boot loader configuration failed", str(e))
    return None
