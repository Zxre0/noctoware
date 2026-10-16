#!/usr/bin/env python3
"""Multi-monitor: boot an installed disk with two virtio-gpu outputs and check
that Hyprland + HyDE drive both (monitors, waybar per output, screenshot).

Usage: tests/vm/test_multimonitor.py --disk DISK --vars OVMF_VARS [--artifacts DIR]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_installed import login_session, session_env  # noqa: E402
from test_live import Checks, finish  # noqa: E402
from vmctl import VM  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--disk", type=Path, required=True)
    ap.add_argument("--vars", type=Path)
    ap.add_argument("--artifacts", type=Path, default=ROOT / "tests/artifacts" / time.strftime("multimon-%Y%m%d-%H%M%S"))
    a = ap.parse_args()
    a.keep = False
    a.artifacts.mkdir(parents=True, exist_ok=True)
    if a.vars:
        shutil.copy(a.vars, a.artifacts / "OVMF_VARS.fd")
    c = Checks()
    # QEMU's egl-headless only enables head 0 of a virtio-gpu, so the second
    # monitor hangs off a second (2D) virtio GPU — like an external display on
    # another GPU; Hyprland must drive both.
    vm = VM(a.artifacts, disk=a.disk.resolve(), extra=["-device", "virtio-gpu-pci,xres=1920,yres=1080"])
    vm.start()
    try:
        vm.wait_agent(600)
        login_session(vm, "nocto", "Noctoware-Test-2026", "noctoware-hyprland.desktop",
                      "pgrep -u nocto -x Hyprland && pgrep -u nocto -x waybar")
        time.sleep(20)
        rc, out = vm.qga.run(session_env("nocto", "Hyprland") + "runuser -u nocto -- env "
                             "XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR HYPRLAND_INSTANCE_SIGNATURE=$(ls /run/user/1000/hypr | head -1) "
                             "hyprctl monitors -j")
        try:
            mons = json.loads(out)
            c.check("Hyprland drives both outputs", len(mons) == 2,
                    ", ".join(f"{m['name']} {m['width']}x{m['height']}@{m['x']},{m['y']}" for m in mons))
        except ValueError:
            c.check("Hyprland drives both outputs", False, out)
        rc, out = vm.qga.run("pgrep -u nocto -x waybar | wc -l; "
                             "for c in /sys/class/drm/card*-Virtual-*; do cat $c/status; done | grep -c '^connected'")
        c.check("two connected displays; waybar running", out.split()[-1] == "2" and int(out.split()[0]) >= 1, out)
        p = vm.screenshot("two-monitors")
        from PIL import Image
        w, h = Image.open(p).size
        c.check("screenshot spans both monitors", w >= 3840 or h >= 2160, f"{w}x{h}")
    finally:
        vm.stop()
    return finish(c, a, vm)


if __name__ == "__main__":
    sys.exit(main())
