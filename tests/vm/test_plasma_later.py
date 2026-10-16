#!/usr/bin/env python3
"""Add KDE Plasma to an existing Hyprland-only install with pacman.

Usage: tests/vm/test_plasma_later.py --disk DISK --vars OVMF_VARS [--artifacts DIR]

Verifies `sudo pacman -S noctoware-plasma` on an installed system: Plasma
(Wayland) appears in SDDM, no second display manager, HyDE's files are not
modified, the running Hyprland session is not switched, and a Plasma login
works afterwards.  [noctoware] is served from this machine.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_installed import login_session, logout  # noqa: E402
from test_live import Checks, finish  # noqa: E402
from vmctl import VM, RepoServer  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disk", type=Path, required=True)
    ap.add_argument("--vars", type=Path)
    ap.add_argument("--user", default="nocto")
    ap.add_argument("--password", default="Noctoware-Test-2026")
    ap.add_argument("--artifacts", type=Path, default=ROOT / "tests/artifacts" / time.strftime("plasma-later-%Y%m%d-%H%M%S"))
    a = ap.parse_args()
    a.keep = False
    a.artifacts.mkdir(parents=True, exist_ok=True)
    if a.vars:
        shutil.copy(a.vars, a.artifacts / "OVMF_VARS.fd")
    c = Checks()
    vm = VM(a.artifacts, disk=a.disk.resolve())
    vm.start()
    q = vm.qga.run
    try:
        vm.wait_agent(600)
        rc, out = q("pacman -Qq noctoware-plasma 2>&1")
        c.check("starting point: Hyprland-only install", "was not found" in out, out)
        login_session(vm, a.user, a.password, "noctoware-hyprland.desktop",
                      f"pgrep -u {a.user} -x Hyprland && pgrep -u {a.user} -x waybar")
        hyde_sum = (f"cd /home/{a.user} && find .config/hypr .config/hyde .config/waybar .config/kitty "
                    ".local/share/hyde .local/lib/hyde -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum")
        _, before = q(hyde_sum)
        with RepoServer(ROOT / "repository/x86_64") as url:
            q(f"sed -i 's|^Server = .*|Server = {url}|' /etc/pacman.d/noctoware-mirrorlist")
            rc, out = q("pacman -Syy --noconfirm noctoware-plasma > /tmp/plasma-install.log 2>&1; echo rc=$?; "
                        "grep -vE 'downloading|^ ' /tmp/plasma-install.log | grep -iE 'error|warning|fail|rc=' | tail -20",
                        timeout=3600)
            _, full = q("cat /tmp/plasma-install.log")
            (a.artifacts / "pacman-plasma.log").write_text(full)
        c.check("sudo pacman -S noctoware-plasma succeeds", out.startswith("rc=0"), out)
        rc, out = q(f"pgrep -u {a.user} -x Hyprland && ! pgrep -u {a.user} -x kwin_wayland")
        c.check("running Hyprland session was not switched", rc == 0, out)
        _, after = q(hyde_sum)
        c.check("HyDE files untouched by installing KDE", before == after and before.strip() != "", f"{before} / {after}")
        rc, out = q("ls /usr/share/wayland-sessions; pacman -Qq plasma-login-manager 2>&1; "
                    "systemctl is-enabled sddm; systemctl list-unit-files | grep -ciE '^(gdm|lightdm|plasmalogin)'")
        c.check("Plasma (Wayland) session added, SDDM still the only display manager",
                "plasma.desktop" in out and "was not found" in out and out.strip().endswith("0"), out)
        logout(vm, a.user)
        if "plasma.desktop" not in q("ls /usr/share/wayland-sessions")[1]:
            return finish(c, a, vm)
        try:
            out = login_session(vm, a.user, a.password, "plasma.desktop",
                                f"pgrep -u {a.user} -x plasmashell && pgrep -u {a.user} -x kwin_wayland")
            c.check("log out → Plasma (Wayland) login works", True, out)
            time.sleep(15)
            vm.screenshot("plasma-after-install")
        except TimeoutError as e:
            c.check("log out → Plasma (Wayland) login works", False, str(e))
    finally:
        vm.stop()
    return finish(c, a, vm)


if __name__ == "__main__":
    sys.exit(main())
