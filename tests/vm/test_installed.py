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


# Field positions of the Noctoware SDDM theme at 1920x1080.
SDDM_USER, SDDM_PASSWORD, SDDM_SESSION = (364, 596), (364, 656), (304, 716)
SDDM_SESSION_ROW0, SDDM_SESSION_ROW_H = 757, 41   # first row of the opened session list


def sddm_login(vm: VM, user: str, password: str, session_index_down: int | None = None) -> None:
    """Log in through the Noctoware SDDM theme (works whether or not SDDM
    remembered the last user).  session_index_down: pick the Nth session."""
    vm.qmp.click(*SDDM_USER, 1920, 1080)
    vm.qmp.keys("ctrl-a", "backspace")
    vm.qmp.type(user)
    if session_index_down is not None:   # open the session list and click the Nth row
        vm.qmp.click(*SDDM_SESSION, 1920, 1080)
        time.sleep(1.0)
        vm.qmp.click(SDDM_SESSION[0], SDDM_SESSION_ROW0 + SDDM_SESSION_ROW_H * session_index_down, 1920, 1080)
        time.sleep(0.8)
    vm.qmp.click(*SDDM_PASSWORD, 1920, 1080)
    vm.qmp.keys("ctrl-a", "backspace")
    vm.qmp.type(password)
    vm.qmp.keys("ret")


def session_index(vm: VM, desktop_file: str) -> int:
    """SDDM lists wayland sessions sorted by file name."""
    _, out = vm.qga.run("ls /usr/share/wayland-sessions | sort")
    return out.split().index(desktop_file)


def logout(vm: VM, user: str) -> None:
    vm.qga.run(f"loginctl terminate-user {user}")
    vm.wait_for(f"! pgrep -u {user} -x Hyprland && ! pgrep -u {user} -x kwin_wayland && systemctl is-active sddm",
                timeout=120)
    time.sleep(8)  # greeter restarts


def login_session(vm: VM, user: str, password: str, desktop_file: str, ready: str, timeout: int = 240) -> str:
    idx = session_index(vm, desktop_file)
    for attempt in range(3):
        sddm_login(vm, user, password, session_index_down=idx)
        try:
            return vm.wait_for(ready, timeout=timeout // 3)
        except TimeoutError:
            vm.screenshot(f"login-{desktop_file}-attempt{attempt + 1}")
    raise TimeoutError(f"could not log into {desktop_file}")


def session_env(user: str, proc: str) -> str:
    """Shell prefix that runs a command inside the user's graphical session."""
    return (f"pid=$(pgrep -u {user} -x {proc} | head -1); "
            f"eval $(tr '\\0' '\\n' < /proc/$pid/environ | grep -E "
            "'^(WAYLAND_DISPLAY|DISPLAY|XDG_RUNTIME_DIR|DBUS_SESSION_BUS_ADDRESS|XDG_CURRENT_DESKTOP|PATH)=' "
            "| sed 's/^/export /; s/=/=\"/; s/$/\"/'); ")


def steam_launches(vm: VM, user: str, proc: str) -> tuple[bool, str]:
    """Start Steam inside the session and check the bootstrapper runs."""
    vm.qga.run(f"pkill -u {user} -f steam; rm -f /tmp/steam-{proc}.log; test -n \"$(pgrep -u {user} -x {proc})\"",
               timeout=30)
    if vm.qga.run(f"pgrep -u {user} -x {proc}")[0] != 0:
        return False, f"no {proc} session running"
    vm.qga.run(session_env(user, proc) + f"runuser -u {user} -- env WAYLAND_DISPLAY=$WAYLAND_DISPLAY "
               f"DISPLAY=$DISPLAY XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS "
               f"PATH=$PATH setsid steam > /tmp/steam-{proc}.log 2>&1 < /dev/null &", timeout=30)
    # the real client (ubuntu12_32/steam) only starts once the bootstrapper has
    # updated Steam over the network and found a working display + 32-bit stack
    try:
        vm.wait_for(f"pgrep -u {user} -f 'ubuntu12_32/steam' >/dev/null", timeout=900, interval=10)
        ok = True
    except TimeoutError:
        ok = False
    _, log = vm.qga.run(f"tail -5 /tmp/steam-{proc}.log; pgrep -u {user} -a steam | head -3")
    return ok, log


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disk", type=Path, required=True)
    ap.add_argument("--vars", type=Path, help="OVMF_VARS.fd from the install run (keeps the NVRAM boot entry)")
    ap.add_argument("--user", default="nocto")
    ap.add_argument("--password", default="Noctoware-Test-2026")
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
        # bluetooth.service only starts when an adapter exists (none in the VM): check it is enabled
        rc, out = q("systemctl is-active sddm NetworkManager; systemctl is-enabled bluetooth snapper-cleanup.timer fstrim.timer")
        c.check("services: sddm + NetworkManager active; bluetooth, snapper-cleanup, fstrim enabled",
                out.split() == ["active", "active", "enabled", "enabled", "enabled"], out)
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
        try:
            login_session(vm, a.user, a.password, "noctoware-hyprland.desktop", f"pgrep -u {a.user} -x Hyprland")
        except TimeoutError:
            pass  # reported by the next check
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
        rc, out = q("codex --version && { claude --version </dev/null; echo rc=$?; }", user=a.user)
        c.check("codex works; claude offers the consent-based setup", "rc=127" in out and "noctoware-claude-setup" in out, out)

        ok_steam, log = steam_launches(vm, a.user, "Hyprland")
        c.check("Steam launches from Hyprland", ok_steam, log)
        vm.screenshot("hyprland-steam")
        vm.qga.run(f"pkill -u {a.user} -f steam")

        if a.plasma:
            # ---- switch to KDE Plasma (Wayland) and back
            logout(vm, a.user)
            try:
                out = login_session(vm, a.user, a.password, "plasma.desktop",
                                    f"pgrep -u {a.user} -x plasmashell && pgrep -u {a.user} -x kwin_wayland")
                c.check("SDDM → Plasma (Wayland) session starts", True, out)
            except TimeoutError as e:
                c.check("SDDM → Plasma (Wayland) session starts", False, str(e))
            time.sleep(15)
            vm.screenshot("plasma-desktop")
            rc, out = q(f"cat /home/{a.user}/.local/state/noctoware/kdeglobals/active; "
                        f"grep -c 'ColorScheme=colors' /home/{a.user}/.config/kdeglobals 2>/dev/null; true")
            c.check("Plasma gets its own kdeglobals (HyDE's not applied)", out.split()[0] == "plasma"
                    and (len(out.split()) == 1 or out.split()[1] == "0"), out)
            rc, out = q(session_env(a.user, "plasmashell") + "echo $XDG_CURRENT_DESKTOP; echo $PATH; "
                        "command -v codex claude fastfetch")
            c.check("Plasma session: KDE desktop, codex + claude (shim) on PATH",
                    "KDE" in out and "/usr/lib/noctoware/shims/claude" in out and "/usr/bin/codex" in out, out)
            rc, out = q("fastfetch --pipe --logo none", user=a.user)
            ok_steam, log = steam_launches(vm, a.user, "plasmashell")
            c.check("Steam launches from Plasma", ok_steam, log)
            logout(vm, a.user)
            try:
                out = login_session(vm, a.user, a.password, "noctoware-hyprland.desktop",
                                    f"pgrep -u {a.user} -x Hyprland && pgrep -u {a.user} -x waybar")
                c.check("switch back to Noctoware Hyprland", True, out)
            except TimeoutError as e:
                c.check("switch back to Noctoware Hyprland", False, str(e))
            rc, out = q(f"cat /home/{a.user}/.local/state/noctoware/kdeglobals/active; "
                        f"grep -c 'ColorScheme=colors' /home/{a.user}/.config/kdeglobals; "
                        f"grep HYDE_THEME /home/{a.user}/.local/state/hyde/staterc")
            c.check("HyDE configuration intact after using Plasma",
                    out.split()[0] == "hyprland" and "Noctoware" in out, out)

        # ---- real `sudo pacman -Syu`, with [noctoware] served from this machine
        bump = a.artifacts / "repo"
        prepare_bumped_repo(a.repo_dir, bump)
        with RepoServer(bump) as url:
            q(f"sed -i 's|^Server = .*|Server = {url}|' /etc/pacman.d/noctoware-mirrorlist")
            before = q("pacman -Q noctoware-welcome")[1]
            rc, out = q("set -o pipefail; pacman -Syu --noconfirm 2>&1 | tail -25", timeout=3600)
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
