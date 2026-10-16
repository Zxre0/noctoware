#!/usr/bin/env python3
"""Boot the Noctoware ISO in QEMU (UEFI) and verify the live system.

Usage: tests/vm/test_live.py ISO [--artifacts DIR] [--bios] [--no-gl] [--keep]
Exit code 0 only if every check passes.  Results: DIR/results.json + screenshots.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vmctl import VM, RepoServer  # noqa: E402
ROOT = Path(__file__).resolve().parents[2]


class Checks:
    def __init__(self):
        self.results = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.results.append({"check": name, "ok": bool(ok), "detail": detail[-1500:]})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail.splitlines()[0][:120]}" if detail else ""), flush=True)
        return ok

    @property
    def passed(self) -> bool:
        return all(r["ok"] for r in self.results)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("iso", type=Path)
    ap.add_argument("--artifacts", type=Path, default=Path("tests/artifacts") / time.strftime("live-%Y%m%d-%H%M%S"))
    ap.add_argument("--bios", action="store_true")
    ap.add_argument("--no-gl", action="store_true")
    ap.add_argument("--keep", action="store_true", help="leave the VM running for inspection")
    a = ap.parse_args()

    c = Checks()
    vm = VM(a.artifacts, iso=a.iso.resolve(), firmware="bios" if a.bios else "uefi", gl=not a.no_gl)
    vm.start()
    try:
        try:
            t = vm.wait_agent(timeout=900)
            c.check("ISO boots (guest agent reachable)", True, f"{t:.0f}s")
        except Exception as e:  # noqa: BLE001
            vm.screenshot("boot-failure")
            c.check("ISO boots (guest agent reachable)", False, str(e))
            return finish(c, a, vm)

        rc, out = vm.qga.run("uname -r; cat /proc/cmdline")
        c.check("CachyOS kernel running", rc == 0 and "cachyos" in out.splitlines()[0], out)
        rc, out = vm.qga.run("cat /etc/os-release")
        c.check("os-release identifies Noctoware",
                all(s in out for s in ('NAME="Noctoware"', 'PRETTY_NAME="Noctoware Linux"', "ID=noctoware",
                                       "ID_LIKE=arch", "BUILD_ID=rolling")), out)
        fw = "bios" if a.bios else "uefi"
        rc, out = vm.qga.run("test -d /sys/firmware/efi && echo uefi || echo bios")
        c.check(f"booted via {fw.upper()}", out.strip() == fw, out)

        try:
            out = vm.wait_for("systemctl is-active sddm", timeout=180)
            c.check("SDDM running", True, out)
        except TimeoutError as e:
            c.check("SDDM running", False, str(e))
        try:
            out = vm.wait_for("pgrep -x Hyprland && pgrep -u liveuser -x Hyprland", timeout=300)
            c.check("Hyprland started (liveuser session)", True, out)
        except TimeoutError as e:
            vm.screenshot("no-hyprland")
            _, j = vm.qga.run("journalctl -b --no-pager | tail -60")
            c.check("Hyprland started (liveuser session)", False, str(e) + "\n" + j)
        try:
            out = vm.wait_for("test -f /home/liveuser/.local/state/noctoware/hyde-deployed && "
                              "cat /home/liveuser/.local/state/noctoware/hyde-deployed && pgrep -x waybar", timeout=300)
            c.check("HyDE deployed and waybar running", True, out)
        except TimeoutError as e:
            _, log = vm.qga.run("tail -40 /home/liveuser/.local/state/noctoware/hyde-deploy.log")
            c.check("HyDE deployed and waybar running", False, str(e) + "\n" + log)
        rc, out = vm.qga.run("grep HYDE_THEME /home/liveuser/.local/state/hyde/staterc")
        c.check("HyDE uses the Noctoware theme", "Noctoware" in out, out)
        try:
            out = vm.wait_for("pgrep -x calamares", timeout=180)
            c.check("Calamares installer launched", True, out)
        except TimeoutError as e:
            c.check("Calamares installer launched", False, str(e))

        time.sleep(8)
        vm.screenshot("live-desktop")
        rc, out = vm.qga.run("ldd /usr/bin/calamares | grep 'not found'; echo rc=$?")
        c.check("calamares binary links against installed libraries", out.strip().endswith("rc=1"), out)

        rc, out = vm.qga.run("pacman -Q steam openai-codex noctoware-desktop noctoware-hyde linux-cachyos linux-cachyos-lts")
        c.check("Steam, Codex, desktop and kernels installed", rc == 0, out)
        rc, out = vm.qga.run("codex --version", user="liveuser")
        c.check("codex command works", rc == 0, out)
        rc, out = vm.qga.run("claude --version </dev/null", user="liveuser")
        c.check("claude shim explains setup (Claude Code not bundled)",
                rc == 127 and "noctoware-claude-setup" in out, out)
        rc, out = vm.qga.run("ls /usr/lib/noctoware/shims/claude && ! pacman -Qq claude-code 2>/dev/null")
        c.check("Claude Code binary not redistributed", rc == 0, out)

        rc, ff = vm.qga.run("fastfetch --pipe --logo none", user="liveuser")
        _, cpu = vm.qga.run("sed -n 's/^model name\\s*: //p' /proc/cpuinfo | head -1")
        _, mem = vm.qga.run("free -b | awk '/Mem:/{print $2}'")
        c.check("fastfetch shows Noctoware Linux", "Noctoware Linux" in ff, ff)
        cpu_words = [w for w in re.split(r"[\s()@]+", cpu) if len(w) > 3][:2]
        c.check("fastfetch reports the real CPU", rc == 0 and all(w in ff for w in cpu_words), f"cpu={cpu}\n{ff}")
        c.check("fastfetch shows the CachyOS kernel", "cachyos" in ff, ff)

        rc, out = vm.qga.run("noctoware-gpu plan --json")
        try:
            plan = json.loads(out)
            c.check("GPU detection: virtual GPU identified", plan["profile"] == "virtual"
                    and "vulkan-virtio" in plan["install"] and "nvidia-utils" not in plan["install"], out[:800])
        except (ValueError, KeyError) as e:
            c.check("GPU detection: virtual GPU identified", False, f"{e}: {out}")

        # [noctoware] is served from this machine (the public repo may not be
        # published yet); Arch and CachyOS come from their real mirrors.
        try:
            vm.wait_for("systemctl is-active pacman-init", timeout=180)
            with RepoServer(ROOT / "repository/x86_64") as url:
                vm.qga.run(f"sed -i 's|^Server = .*|Server = {url}|' /etc/pacman.d/noctoware-mirrorlist")
                rc, out = vm.qga.run("pacman -Syy --noconfirm 2>&1 && pacman -Sl noctoware | head -3", timeout=300)
            c.check("pacman syncs [noctoware], [cachyos], core, extra, multilib (signed dbs)",
                    rc == 0 and all(r in out for r in ("noctoware", "cachyos", "core", "extra", "multilib")), out)
        except TimeoutError as e:
            c.check("pacman syncs repositories", False, str(e))
        rc, out = vm.qga.run("pacman-conf SigLevel; grep -c '^SigLevel.*Never' /etc/pacman.conf")
        c.check("signature checking enforced", "Required" in out and out.strip().endswith("0"), out)
    finally:
        if not a.keep:
            vm.stop()
    return finish(c, a, vm)


def finish(c: Checks, a, vm) -> int:
    a.artifacts.mkdir(parents=True, exist_ok=True)
    (a.artifacts / "results.json").write_text(json.dumps(c.results, indent=2))
    n_ok = sum(r["ok"] for r in c.results)
    print(f"\n{n_ok}/{len(c.results)} checks passed — artifacts in {a.artifacts}")
    if not a.keep:
        vm.stop()
    return 0 if c.passed else 5


if __name__ == "__main__":
    sys.exit(main())
