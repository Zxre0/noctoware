#!/usr/bin/env python3
"""Secure Boot with the user's own keys (noctoware-secureboot) on an installed
UEFI system, using OVMF's Secure Boot firmware starting in Setup Mode.

Usage: tests/vm/test_secureboot.py --disk DISK [--artifacts DIR]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_live import Checks, finish  # noqa: E402
from test_recovery import reboot  # noqa: E402
from vmctl import VM, RepoServer  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def sb_state(q) -> str:
    rc, out = q("od -An -t u1 /sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c | awk '{print $NF}'")
    return out.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disk", type=Path, required=True)
    ap.add_argument("--artifacts", type=Path, default=ROOT / "tests/artifacts" / time.strftime("secureboot-%Y%m%d-%H%M%S"))
    a = ap.parse_args()
    a.keep = False
    a.artifacts.mkdir(parents=True, exist_ok=True)
    c = Checks()
    vm = VM(a.artifacts, disk=a.disk.resolve(), firmware="uefi-sb")
    vm.start()
    q = vm.qga.run
    try:
        vm.wait_agent(600)
        rc, out = q("bootctl status 2>/dev/null | grep -iE 'secure boot|setup mode'")
        c.check("Secure Boot firmware in Setup Mode, Secure Boot off", sb_state(q) == "0" and "setup" in out.lower(), out)
        with RepoServer(ROOT / "repository/x86_64") as url:   # [noctoware] not published yet
            q(f"sed -i 's|^Server = .*|Server = {url}|' /etc/pacman.d/noctoware-mirrorlist")
            rc, out = q("set -o pipefail; pacman -Syyu --noconfirm --needed sbctl noctoware-system 2>&1 | tail -3", timeout=1800)
        c.check("install sbctl + noctoware-secureboot", rc == 0 and q("command -v noctoware-secureboot")[0] == 0, out)
        rc, out = q("noctoware-secureboot setup --yes 2>&1 | tail -15", timeout=600)
        c.check("noctoware-secureboot setup: keys enrolled, boot chain signed",
                rc == 0 and "Done" in out and "not signed" not in out.lower(), out)
        reboot(vm)
        rc, out = q("bootctl status 2>/dev/null | grep -iE 'secure boot'; uname -r; sbctl status")
        c.check("reboots with Secure Boot ENFORCED (signed systemd-boot + kernel)",
                sb_state(q) == "1" and "cachyos" in out, out)
        rc, out = q("set -o pipefail; pacman -S --noconfirm linux-cachyos 2>&1 | tail -4; sbctl verify 2>&1 | tail -6",
                    timeout=1800)
        c.check("kernel update is re-signed by sbctl's pacman hook", "not signed" not in out.lower() and "✓" in out, out)
        reboot(vm)
        rc, out = q("uname -r")
        c.check("boots again after the kernel update with Secure Boot on", sb_state(q) == "1", out)
        rc, out = q("systemctl is-active sddm")
        c.check("desktop stack up under Secure Boot (SDDM active)", out.strip() == "active", out)
    finally:
        vm.stop()
    return finish(c, a, vm)


if __name__ == "__main__":
    sys.exit(main())
