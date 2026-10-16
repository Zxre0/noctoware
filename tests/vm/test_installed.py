#!/usr/bin/env python3
"""Boot an installed Noctoware disk (no ISO attached) and verify it.

Usage: tests/vm/test_installed.py --disk DISK --vars OVMF_VARS [--user U --password P]
                                  [--plasma] [--repo-dir DIR] [--artifacts DIR]

Checks the installed system boots independently, carries no live-session
leftovers, identifies as Noctoware with the CachyOS kernel, has correct boot
entries, snapshots, GPU drivers for the VM, Steam/AI tools, that SDDM lists
the right sessions and a user can log into Noctoware Hyprland (and Plasma),
and that a real `sudo pacman -Syu` works — including upgrading a Noctoware
package served from a local copy of [noctoware].
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_live import Checks, finish  # noqa: E402
from vmctl import VM, RepoServer  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def sddm_login(vm: VM, user: str, password: str, session_index_down: int = 0) -> None:
    """Log in through the Noctoware SDDM theme with the keyboard only."""
    vm.qmp.keys("ctrl-a")
    vm.qmp.type(user)
    vm.qmp.keys("tab")
    vm.qmp.type(password)
    if session_index_down:
        vm.qmp.keys("tab")                       # session combo box
        vm.qmp.keys("spc")
        time.sleep(0.5)
        for _ in range(session_index_down):
            vm.qmp.keys("down")
        vm.qmp.keys("ret")
        vm.qmp.keys("shift-tab")                 # back to the password field
    vm.qmp.keys("ret")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disk", type=Path, required=True)
    ap.add_argument("--vars", type=Path, help="OVMF_VARS.fd from the install run (keeps the NVRAM boot entry)")
    ap.add_argument("--user", default="nocto")
    ap.add_argument("--password", default="noctoware-test")
    ap.add_argument("--plasma", action="store_true", help="the install chose Hyprland + KDE Plasma")
    ap.add_argument("--repo-dir", type=Path, default=ROOT / "repository/x86_64")
    ap.add_argument("--artifacts", type=Path, default=ROOT / "tests/artifacts" / time.strftime("installed-%Y%m%d-%H%M%S"))
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    a.artifacts.mkdir(parents=True, exist_ok=True)
    if a.vars:
        shutil.copy(a.vars, a.artifacts / "OVMF_VARS.fd")
    c = Checks()
    vm = VM(a.artifacts, disk=a.disk.resolve())
    vm.start()
    try:
        try:
            c.check("installed system boots without the ISO", True, f"{vm.wait_agent(600):.0f}s")
        except Exception as e:  # noqa: BLE001
            vm.screenshot("boot-failure")
            c.check("installed system boots without the ISO", False, str(e))
            return finish(c, a, vm)
        q = vm.qga.run

        rc, out = q("uname -r; findmnt -no SOURCE,FSTYPE,OPTIONS /; ls /run/archiso 2>&1 | head -1")
        c.check("CachyOS kernel, root on disk (not the ISO)", "cachyos" in out and "No such file" in out, out)
        rc, out = q("cat /etc/os-release")
        c.check("os-release: Noctoware Linux", 'PRETTY_NAME="Noctoware Linux"' in out and "ID=noctoware" in out, out)

        rc, out = q("id liveuser 2>&1; ls /etc/sudoers.d; grep -rl NOPASSWD /etc/sudoers.d /etc/sudoers 2>/dev/null; "
                    "ls /etc/sddm.conf.d; pacman -Qq cachyos-calamares noctoware-calamares-config 2>&1; "
                    "ls /etc/mkinitcpio.conf.d /opt/noctoware 2>&1; cat /etc/machine-id; "
                    "systemctl is-enabled pacman-init 2>&1")
        leaked = [s for s in ("90-noctoware-live", "liveuser:", "uid=", "archiso.conf", "/offline") if s in out]
        c.check("no live-session leftovers (user, NOPASSWD sudo, autologin, installer, archiso hooks, offline cache)",
                not leaked and "90-noctoware-live.conf" not in out, out)
        mid = out.split()[-2] if out else ""
        c.check("unique machine-id generated", bool(re.fullmatch(r"[0-9a-f]{32}", mid)) and mid != "uninitialized", mid)

        rc, out = q("bootctl status 2>/dev/null | sed -n '1,25p'; ls /boot /boot/loader/entries; "
                    "cat /boot/loader/entries/noctoware.conf; cat /etc/fstab")
        efi = "systemd-boot" in out
        c.check("systemd-boot with static entries for both kernels",
                efi and all(x in out for x in ("noctoware.conf", "noctoware-lts.conf", "noctoware-fallback.conf",
                                               "vmlinuz-linux-cachyos", "initramfs-linux-cachyos.img")), out)
        rc, out = q("lsinitcpio -a /boot/initramfs-linux-cachyos.img 2>/dev/null | head -20; "
                    "lsinitcpio /boot/initramfs-linux-cachyos.img | grep -c archiso")
        c.check("final initramfs has no archiso hooks", out.strip().endswith("0"), out)

        rc, out = q("findmnt -no FSTYPE /")
        if out.strip() == "btrfs":
            rc, out = q("btrfs subvolume list / | awk '{print $NF}'; snapper -c root list; "
                        "ls /usr/share/libalpm/hooks | grep -E 'snap-pac|noctoware'")
            c.check("Btrfs subvolumes + snapper config + fresh-install snapshot + snap-pac hooks",
                    all(s in out for s in ("@home", "@snapshots", "@log", "fresh install", "snap-pac", "noctoware-boot-backup")), out)

        rc, out = q("cat /etc/noctoware/gpu.json")
        try:
            g = json.loads(out)
            rc2, inst = q("pacman -Qq nvidia-utils vulkan-intel vulkan-radeon vulkan-virtio lib32-vulkan-swrast qemu-guest-agent 2>&1")
            c.check("GPU drivers match the VM (virtual profile, no NVIDIA/Intel/AMD stacks)",
                    g["profile"] == "virtual" and "vulkan-virtio" in inst and "was not found" in inst
                    and inst.count("was not found") == 3, inst)
        except (ValueError, KeyError) as e:
            c.check("GPU drivers match the VM", False, f"{e}: {out}")

        rc, out = q("pacman -Q steam gamescope gamemode mangohud lib32-mangohud openai-codex noctoware-ai-tools linux-cachyos linux-cachyos-lts")
        c.check("Steam/gaming stack, Codex and both kernels installed", rc == 0, out)
        rc, out = q(f"getent passwd {a.user}")
        c.check("installer-created user exists with zsh", out.endswith("/usr/bin/zsh"), out)
        rc, out = q("systemctl is-active sddm NetworkManager bluetooth; systemctl is-enabled snapper-cleanup.timer fstrim.timer")
        c.check("services: sddm, NetworkManager, bluetooth, snapper-cleanup, fstrim", "inactive" not in out and "disabled" not in out, out)
        rc, out = q("ls /usr/share/wayland-sessions/; cat /var/lib/sddm/state.conf")
        want = ["noctoware-hyprland.desktop"] + (["plasma.desktop"] if a.plasma else [])
        c.check("SDDM sessions: " + ", ".join(want) + (" (no plasma)" if not a.plasma else ""),
                all(w in out for w in want) and (a.plasma or "plasma.desktop" not in out)
                and "noctoware-hyprland.desktop" in out.split("Session=")[-1], out)
        rc, out = q("pacman -Qq plasma-login-manager 2>&1; systemctl list-unit-files | grep -iE 'gdm|lightdm|plasmalogin' ")
        c.check("SDDM is the only display manager", "was not found" in out, out)

        # ---- graphical login into Noctoware Hyprland
        time.sleep(5)
        vm.screenshot("sddm-greeter")
        sddm_login(vm, a.user, a.password)
        try:
            out = vm.wait_for(f"pgrep -u {a.user} -x Hyprland && test -f /home/{a.user}/.local/state/noctoware/hyde-deployed "
                              f"&& pgrep -u {a.user} -x waybar", timeout=300)
            c.check("login → Noctoware Hyprland with HyDE (first-login deploy)", True, out)
        except TimeoutError as e:
            vm.screenshot("login-failed")
            _, j = q(f"journalctl -b --no-pager | grep -iE 'sddm|hypr|noctoware' | tail -40")
            c.check("login → Noctoware Hyprland with HyDE (first-login deploy)", False, str(e) + "\n" + j)
        time.sleep(10)
        vm.screenshot("hyprland-desktop")
        rc, out = q("fastfetch --pipe --logo none", user=a.user)
        _, cpu = q("sed -n 's/^model name\\s*: //p' /proc/cpuinfo | head -1")
        c.check("fastfetch: Noctoware Linux + real CPU + Hyprland",
                "Noctoware Linux" in out and cpu.split()[0] in out and "Hyprland" in out, out)
        rc, out = q("XDG_RUNTIME_DIR=/run/user/$(id -u {u}) busctl --user list 2>/dev/null | grep -c portal; "
                    "pgrep -u {u} -f xdg-desktop-portal-hyprland; pgrep -u {u} -x pipewire; pgrep -u {u} -x wireplumber"
                    .format(u=a.user), user=None)
        c.check("portal (screen sharing), PipeWire and WirePlumber running in the session",
                len(out.splitlines()) >= 4, out)
        rc, out = q("codex --version; claude --version </dev/null; echo rc=$?", user=a.user)
        c.check("codex works; claude offers the consent-based setup", "rc=127" in out and "noctoware-claude-setup" in out, out)

        # ---- real `sudo pacman -Syu`, with [noctoware] served from this machine
        bump = a.artifacts / "repo"
        prepare_bumped_repo(a.repo_dir, bump)
        with RepoServer(bump) as url:
            q(f"sed -i 's|^Server = .*|Server = {url}|' /etc/pacman.d/noctoware-mirrorlist")
            before = q("pacman -Q noctoware-welcome")[1]
            rc, out = q("pacman -Syu --noconfirm 2>&1 | tail -25", timeout=3600)
            after = q("pacman -Q noctoware-welcome")[1]
            c.check("sudo pacman -Syu succeeds (Arch + CachyOS + [noctoware], signatures verified)", rc == 0, out)
            c.check("Noctoware package upgraded via pacman", before != after, f"{before} -> {after}")
            rc, out = q("snapper -c root list | tail -3")
            c.check("snap-pac created pre/post snapshots for the update", "pre" in out and "post" in out, out)
            rc, out = q("ls /var/lib/noctoware/boot-backup/")
            c.check("boot files saved for rollback", "vmlinuz-linux-cachyos" in out, out)
    finally:
        if not a.keep:
            vm.stop()
    return finish(c, a, vm)


def prepare_bumped_repo(src: Path, dst: Path) -> None:
    """Copy [noctoware] and add noctoware-welcome with pkgrel+1, signed and indexed,
    so the update test exercises a real Noctoware package upgrade."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=False)
    subprocess.run([str(ROOT / "tests/vm/make-bump.sh"), str(dst)], check=True)


if __name__ == "__main__":
    sys.exit(main())
