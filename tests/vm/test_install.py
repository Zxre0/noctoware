#!/usr/bin/env python3
"""Install Noctoware with Calamares in QEMU, driving the real installer GUI.

Usage: tests/vm/test_install.py ISO [--desktop hyprland|plasma] [--fs btrfs|ext4]
                                    [--artifacts DIR] [--attach DIR]

Boots the ISO with an empty 64 GiB qcow2 image (never a physical disk),
waits for the autostarted installer, then clicks through every page exactly
as a user would (screenshots of each page are saved), confirms the
"Install now" prompt and waits for the result.  Writes disk.qcow2 and
OVMF_VARS.fd into the artifacts dir for tests/vm/test_installed.py.

--attach DIR reuses a VM already started with tests/vm/debug_vm.py.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_live import Checks, finish  # noqa: E402
from vmctl import QGA, QMP, VM, create_disk  # noqa: E402

# Screen coordinates (1920x1080) of the Noctoware Calamares layout.
NEXT = (1786, 1046)
ERASE_DISK = (328, 112)
FS_COMBO = (480, 175)
DESKTOP_PLASMA = (310, 85)
USER_FIELDS = {"name": (310, 98), "login": (310, 158), "host": (310, 216), "pw": (310, 276), "pw2": (516, 276)}
CONFIRM_INSTALL = (1038, 590)
# Sidebar step rows (y at 1920x1080); the current step is highlighted purple.
STEPS = {"welcome": 150, "location": 190, "keyboard": 228, "partitions": 266, "desktop": 306,
         "users": 345, "summary": 384, "install": 422, "finish": 462}


def on_step(png: Path, step: str) -> bool:
    from PIL import Image
    im = Image.open(png).convert("RGB")
    sx, sy = im.size[0] / 1920, im.size[1] / 1080
    r, g, b = im.getpixel((int(30 * sx), int(STEPS[step] * sy)))
    return r > 120 and b > 200 and g < 150   # #9b6bff-ish highlight


def wait_step(vm, step: str, timeout: float = 120) -> None:
    """Block until Calamares shows `step` (pages can be slow, e.g. offline)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if on_step(vm.screenshot("_probe"), step):
            time.sleep(0.8)  # let the page finish laying out
            return
        time.sleep(1)
    raise TimeoutError(f"installer never reached the {step} page")
LOG = "/root/.cache/calamares/session.log"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("iso", type=Path, nargs="?")
    ap.add_argument("--desktop", choices=["hyprland", "plasma"], default="hyprland")
    ap.add_argument("--fs", choices=["btrfs", "ext4"], default="btrfs")
    ap.add_argument("--user", default="nocto")
    ap.add_argument("--password", default="Noctoware-Test-2026")
    ap.add_argument("--no-net", action="store_true", help="no network: everything must come from the ISO")
    ap.add_argument("--mock-gpu", help="PCI ids the installer's GPU detection should see, e.g. 8086:9bc4,10de:2560")
    ap.add_argument("--bios", action="store_true", help="legacy BIOS (SeaBIOS) instead of UEFI")
    ap.add_argument("--artifacts", type=Path, default=Path("tests/artifacts") / time.strftime("install-%Y%m%d-%H%M%S"))
    ap.add_argument("--attach", type=Path, help="drive an already running debug VM in this dir")
    ap.add_argument("--keep", action="store_true", help="leave the VM running")
    a = ap.parse_args()
    a.keep = a.keep or bool(a.attach)

    c = Checks()
    if a.attach:
        vm = VM(a.attach)
        vm.qmp, vm.qga = QMP(str(a.attach / "qmp.sock")), QGA(str(a.attach / "qga.sock"))
        a.artifacts = a.attach
    else:
        a.artifacts.mkdir(parents=True, exist_ok=True)
        disk = create_disk(a.artifacts / "disk.qcow2", "64G")
        vm = VM(a.artifacts, iso=a.iso.resolve(), disk=disk, firmware="bios" if a.bios else "uefi",
                net=not a.no_net)
        vm.start()
    shot = lambda n: vm.screenshot(n)  # noqa: E731
    try:
        vm.wait_agent(900)
        vm.wait_for("pgrep -x calamares", timeout=300)
        if a.mock_gpu:
            vm.qga.run(f"mkdir -p /run/noctoware && echo {a.mock_gpu} > /run/noctoware/gpu-mock-ids")
        rc, live_mid = vm.qga.run("cat /etc/machine-id")
        (a.artifacts / "live-machine-id").write_text(live_mid)
        time.sleep(8)

        def click(xy, wait=1.5):
            vm.qmp.click(*xy, 1920, 1080)
            time.sleep(wait)

        wait_step(vm, "welcome", 180)
        shot("01-welcome")
        click(NEXT); wait_step(vm, "location"); shot("02-location")
        click(NEXT); wait_step(vm, "keyboard"); shot("03-keyboard")
        click(NEXT); wait_step(vm, "partitions"); shot("04-partitions")
        click(ERASE_DISK, 2)
        if a.fs == "ext4":
            click(FS_COMBO)
            vm.qmp.keys("down", "ret")
            time.sleep(1)
        shot("05-erase-disk")
        click(NEXT); wait_step(vm, "desktop"); shot("06-desktop")
        if a.desktop == "plasma":
            click(DESKTOP_PLASMA)
            shot("06b-desktop-plasma")
        click(NEXT); wait_step(vm, "users")
        vm.fill(*USER_FIELDS["name"], "Nocto Tester")
        vm.fill(*USER_FIELDS["login"], a.user)
        vm.fill(*USER_FIELDS["host"], "noctotest")
        vm.fill(*USER_FIELDS["pw"], a.password)
        vm.fill(*USER_FIELDS["pw2"], a.password)
        time.sleep(1)
        shot("07-users")
        click(NEXT); wait_step(vm, "summary"); shot("08-summary")
        rc, s = vm.qga.run(f"grep -c 'Erase' {LOG}; grep -o 'packagechooser_desktop.*' {LOG} | tail -1")
        click(NEXT, 2); shot("09-confirm")
        click(CONFIRM_INSTALL, 5)
        wait_step(vm, "install", 60)
        shot("10-installing")

        t0, result, last_job = time.time(), None, ""
        while time.time() - t0 < 3600:
            rc, out = vm.qga.run(f"grep -E 'Starting job|onInstallationFailed|ERROR: Installation failed|"
                                 f"ViewManager::next|finished' {LOG} | tail -2")
            if "Installation failed" in out or "onInstallationFailed" in out:
                result = "failed"
                break
            if out != last_job:
                last_job = out
            rc, fin = vm.qga.run(f"grep -qE 'completion: succe(ss|eded)' {LOG}; echo $?")
            if fin.strip().endswith("0"):
                result = "success"
                break
            time.sleep(15)
        time.sleep(3)
        shot("11-finished")
        rc, tail = vm.qga.run(f"grep -E 'Starting job|ERROR|details' {LOG} | tail -12")
        c.check(f"Calamares installation completes ({a.desktop}, {a.fs}, {'bios' if a.bios else 'uefi'})", result == "success",
                f"{result} after {time.time() - t0:.0f}s\n{tail}")
        vm.qga.run(f"cp {LOG} /tmp/install.log; chmod 644 /tmp/install.log")
        rc, log = vm.qga.run("cat /tmp/install.log")
        (a.artifacts / "calamares-session.log").write_text(log)
    finally:
        if not (a.attach or a.keep):
            vm.stop()
    return finish(c, a, vm)


if __name__ == "__main__":
    sys.exit(main())
