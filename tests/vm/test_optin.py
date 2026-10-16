#!/usr/bin/env python3
"""Opt-in components on an installed system: Claude Code setup and Revo Shell.

Usage: tests/vm/test_optin.py --disk DISK --vars OVMF_VARS [--artifacts DIR] [--skip-revo]

* Claude Code: runs `noctoware-claude-setup --yes` (the --yes stands in for
  the user's consent) which downloads Anthropic's official installer; then
  `claude --version` must work through the same `claude` command.
* Revo Shell: installs noctoware-revo from the locally served [noctoware],
  runs `noctoware-revo-setup --yes` (fetches Revo from its upstream and runs
  its own installer with the macOS interface), then switches shells with
  noctoware-shell and checks HyDE's configuration survives the round trip.
  Revo's installer uses sudo; the test user gets NOPASSWD sudo inside this
  throwaway VM only.
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
    ap.add_argument("--skip-revo", action="store_true")
    ap.add_argument("--artifacts", type=Path, default=ROOT / "tests/artifacts" / time.strftime("optin-%Y%m%d-%H%M%S"))
    a = ap.parse_args()
    a.keep = False
    a.artifacts.mkdir(parents=True, exist_ok=True)
    if a.vars:
        shutil.copy(a.vars, a.artifacts / "OVMF_VARS.fd")
    c = Checks()
    vm = VM(a.artifacts, disk=a.disk.resolve())
    vm.start()
    q = vm.qga.run
    u = a.user
    try:
        vm.wait_agent(600)
        # ---- Claude Code (official installer, user consent simulated by --yes)
        rc, out = q("claude --version </dev/null; echo rc=$?", user=u)
        c.check("before setup: claude explains how to install", "rc=127" in out, out)
        rc, out = q("noctoware-claude-setup --yes 2>&1 | tail -6; echo rc=$?", user=u, timeout=900)
        c.check("noctoware-claude-setup runs Anthropic's official installer", out.strip().endswith("rc=0"), out)
        rc, out = q("claude --version; echo rc=$?; readlink -f ~/.local/bin/claude", user=u)
        c.check("`claude` works after setup (native install in ~/.local/bin)",
                "rc=0" in out and "Claude Code" in out and ".local/share/claude/versions" in out, out)
        rc, out = q("ls -la ~/.claude ~/.claude.json 2>&1 | head -5; grep -rl 'ANTHROPIC_API_KEY\\|sk-ant' /etc /usr/lib/noctoware "
                    "2>/dev/null | head -3; echo end", user=u)
        c.check("no credentials bundled or stored by Noctoware", out.strip().endswith("end")
                and "sk-ant" not in out, out)

        if not a.skip_revo:
            # ---- Revo Shell (fetched from upstream on request)
            q(f"echo '{u} ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/99-test-only && chmod 440 /etc/sudoers.d/99-test-only")
            with RepoServer(ROOT / "repository/x86_64") as url:
                q(f"sed -i 's|^Server = .*|Server = {url}|' /etc/pacman.d/noctoware-mirrorlist")
                rc, out = q("set -o pipefail; pacman -Syyu --noconfirm noctoware-revo 2>&1 | tail -4", timeout=1800)
            c.check("sudo pacman -S noctoware-revo", rc == 0, out)
            hyde_sum = f"cd /home/{u} && find .config/hypr .config/kitty -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum"
            _, hyde_before = q(hyde_sum)
            rc, out = q("noctoware-revo-setup --yes > /tmp/revo.log 2>&1; echo rc=$?; tail -5 /tmp/revo.log",
                        user=u, timeout=3600)
            _, full = q("cat /tmp/revo.log")
            (a.artifacts / "revo-setup.log").write_text(full)
            c.check("noctoware-revo-setup fetches Revo (macos interface) from upstream", out.startswith("rc=0"), out)
            rc, out = q("noctoware-shell status; ls ~/.config/quickshell | head", user=u)
            c.check("Revo active with the macOS interface", "active shell: revo" in out and "macos" in out, out)
            login_session(vm, u, a.password, "noctoware-hyprland.desktop", f"pgrep -u {u} -x Hyprland")
            try:
                out = vm.wait_for(f"pgrep -u {u} -f quickshell", timeout=300)  # slow under parallel load
            except TimeoutError as e:
                out = str(e)
                vm.screenshot("revo-no-quickshell")
            time.sleep(15)
            rc, out = q(f"pid=$(pgrep -u {u} -x Hyprland); tr '\\0' '\\n' < /proc/$pid/environ | grep -c HYPRLAND_CONFIG; "
                        f"pgrep -u {u} -a quickshell | head -2; pgrep -u {u} -x waybar; echo end")
            lines = out.split()
            c.check("Revo Shell runs alone (quickshell up; no HyDE config, no waybar)",
                    lines[0] == "0" and "quickshell" in out and "waybar" not in out
                    and q(f"pgrep -u {u} -x waybar")[0] != 0, out)
            vm.screenshot("revo-macos")
            logout(vm, u)
            rc, out = q("noctoware-shell switch hyde", user=u)
            _, hyde_after = q(hyde_sum)
            c.check("switch back to HyDE restores its configuration byte-for-byte",
                    hyde_before == hyde_after and rc == 0, f"{out}\n{hyde_before} / {hyde_after}")
            login_session(vm, u, a.password, "noctoware-hyprland.desktop",
                          f"pgrep -u {u} -x Hyprland && pgrep -u {u} -x waybar")
            rc, out = q(f"pgrep -u {u} -x waybar && ! pgrep -u {u} -f quickshell")
            c.check("HyDE desktop back after switching", rc == 0, out)
            q("rm -f /etc/sudoers.d/99-test-only")
    finally:
        vm.stop()
    return finish(c, a, vm)


if __name__ == "__main__":
    sys.exit(main())
