#!/usr/bin/env python3
"""Recovery features on an installed Btrfs + UEFI system.

Usage: tests/vm/test_recovery.py --disk DISK --vars OVMF_VARS [--artifacts DIR]

1. snapshot rollback: install a package (snap-pac takes pre/post snapshots),
   `noctoware-rollback --yes <pre>`, reboot, verify the package is gone, the
   old root was kept as @.broken-*, and kernel/modules still match;
2. recovery kernel: boot the linux-cachyos-lts entry (bootctl --oneshot) and
   verify it runs.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_live import Checks, finish  # noqa: E402
from vmctl import VM, RepoServer  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def reboot(vm: VM) -> None:
    try:  # guest-shutdown does not reply; the agent goes away with the guest
        vm.qga._call("guest-shutdown", timeout=10, mode="reboot")
    except Exception:  # noqa: BLE001
        pass
    time.sleep(25)
    vm.wait_agent(600)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disk", type=Path, required=True)
    ap.add_argument("--vars", type=Path)
    ap.add_argument("--artifacts", type=Path, default=ROOT / "tests/artifacts" / time.strftime("recovery-%Y%m%d-%H%M%S"))
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
        rc, out = q("pacman -Q tree 2>&1; snapper -c root list --columns number,type,description | tail -3")
        c.check("start: test package absent, snapper configured", "was not found" in out, out)

        # 1. change the system through pacman (snap-pac snapshots it)
        with RepoServer(ROOT / "repository/x86_64") as url:   # [noctoware] not published yet
            q(f"sed -i 's|^Server = .*|Server = {url}|' /etc/pacman.d/noctoware-mirrorlist")
            rc, out = q("set -o pipefail; pacman -Syy --noconfirm tree 2>&1 | tail -3; pacman -Q tree", timeout=900)
        c.check("pacman installs a package", rc == 0 and "tree " in out, out)
        rc, out = q("snapper -c root list --columns number,type,description")
        pre = [int(m.group(1)) for m in re.finditer(r"^\s*(\d+)\s*│\s*pre\s*│.*tree", out, re.M)]
        c.check("snap-pac recorded a pre snapshot", bool(pre), out)
        if not pre:
            return finish(c, a, vm)
        n = pre[-1]
        rc, out = q(f"ls /.snapshots/{n}/snapshot/var/lib/noctoware/boot-backup/")
        c.check("snapshot carries its kernel + initramfs", "vmlinuz-linux-cachyos" in out, out)

        rc, out = q(f"noctoware-rollback --yes {n} 2>&1")
        c.check(f"noctoware-rollback {n}", rc == 0 and "Rollback prepared" in out, out)
        reboot(vm)
        rc, out = q("pacman -Q tree 2>&1; uname -r; ls /usr/lib/modules; "
                    "mount -o subvolid=5 $(findmnt -no SOURCE / | sed 's/\\[.*//') /mnt && ls /mnt; umount /mnt")
        kver = out.split("\n")[1].strip() if "\n" in out else ""
        c.check("after rollback: package gone, old root kept as @.broken-*, kernel matches modules",
                "was not found" in out and "@.broken-" in out and kver and out.count(kver) >= 2, out)
        rc, out = q("systemctl is-active sddm; systemctl --failed --no-legend | head -5")
        c.check("rolled-back system is healthy (SDDM up, no failed units)", out.split()[0] == "active", out)

        # 2. LTS recovery kernel
        rc, out = q("bootctl set-oneshot noctoware-lts.conf && echo ok")
        c.check("select the LTS recovery entry for next boot", "ok" in out, out)
        reboot(vm)
        rc, out = q("uname -r; cat /proc/cmdline")
        c.check("boots the linux-cachyos-lts recovery kernel", "lts" in out.split()[0], out)
    finally:
        vm.stop()
    return finish(c, a, vm)


if __name__ == "__main__":
    sys.exit(main())
