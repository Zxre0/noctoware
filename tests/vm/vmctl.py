"""Minimal QEMU control for Noctoware VM tests (stdlib only).

* VM: launches qemu-system-x86_64 with UEFI (OVMF), virtio GPU, a QMP socket
  and a QEMU guest-agent channel.
* QMP: screenshots, keyboard and absolute-pointer input, power control.
* QGA: run commands inside the guest (the ISO ships qemu-guest-agent) and
  read files - so tests assert on the guest's real state, not on guesses.
"""
from __future__ import annotations

import base64
import signal
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

OVMF_CODE = next((p for p in ("/usr/share/edk2/x64/OVMF_CODE.4m.fd", "/usr/share/OVMF/OVMF_CODE.fd") if os.path.exists(p)), None)
OVMF_VARS = next((p for p in ("/usr/share/edk2/x64/OVMF_VARS.4m.fd", "/usr/share/OVMF/OVMF_VARS.fd") if os.path.exists(p)), None)


class JsonSocket:
    def __init__(self, path: str, timeout: float = 30):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect(path)
        self.buf = b""

    def send(self, obj) -> None:
        self.sock.sendall(json.dumps(obj).encode() + b"\n")

    def recv(self, timeout: float | None = None) -> dict:
        if timeout is not None:
            self.sock.settimeout(timeout)
        while b"\n" not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("socket closed")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)

    def close(self) -> None:
        self.sock.close()


class QMP:
    def __init__(self, path: str):
        self.s = JsonSocket(path)
        self.s.recv()  # greeting
        self.cmd("qmp_capabilities")

    def cmd(self, execute: str, **arguments):
        msg = {"execute": execute}
        if arguments:
            msg["arguments"] = arguments
        self.s.send(msg)
        while True:
            r = self.s.recv()
            if "event" in r:
                continue
            if "error" in r:
                raise RuntimeError(f"QMP {execute}: {r['error']}")
            return r.get("return")

    def screenshot(self, path: str) -> str:
        self.cmd("screendump", filename=os.path.abspath(path), format="png")
        for _ in range(50):
            if os.path.exists(path) and os.path.getsize(path) > 0:
                break
            time.sleep(0.1)
        return path

    def keys(self, *combos: str, hold_ms: int = 50, gap: float = 0.2) -> None:
        """Send key combos like 'alt-n', 'ret', 'tab', 'shift-tab'."""
        for combo in combos:
            keys = [{"type": "qcode", "data": k} for k in combo.split("-")]
            self.cmd("send-key", keys=keys, **{"hold-time": hold_ms})
            time.sleep(gap)

    _SHIFTED = {'!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
                '_': 'minus', '+': 'equal', ':': 'semicolon', '"': 'apostrophe', '?': 'slash', '<': 'comma', '>': 'dot',
                '{': 'bracket_left', '}': 'bracket_right', '|': 'backslash', '~': 'grave_accent'}
    _PLAIN = {' ': 'spc', '-': 'minus', '=': 'equal', ';': 'semicolon', "'": 'apostrophe', '/': 'slash', ',': 'comma',
              '.': 'dot', '[': 'bracket_left', ']': 'bracket_right', '\\': 'backslash', '`': 'grave_accent', '\n': 'ret'}

    def type(self, text: str) -> None:
        for ch in text:
            if ch.isalpha():
                self.keys(("shift-" if ch.isupper() else "") + ch.lower(), gap=0.22)
            elif ch.isdigit():
                self.keys(ch, gap=0.22)
            elif ch in self._PLAIN:
                self.keys(self._PLAIN[ch], gap=0.22)
            elif ch in self._SHIFTED:
                self.keys("shift-" + self._SHIFTED[ch], gap=0.22)
            else:
                raise ValueError(f"cannot type {ch!r}")

    def click(self, x: int, y: int, width: int, height: int, button: str = "left") -> None:
        """Click at screen pixel (x, y) given the current screen size."""
        ax, ay = int(x * 32767 / max(1, width - 1)), int(y * 32767 / max(1, height - 1))
        self.cmd("input-send-event", events=[
            {"type": "abs", "data": {"axis": "x", "value": ax}},
            {"type": "abs", "data": {"axis": "y", "value": ay}}])
        time.sleep(0.1)
        for down in (True, False):
            self.cmd("input-send-event", events=[{"type": "btn", "data": {"down": down, "button": button}}])
            time.sleep(0.08)


class QGA:
    def __init__(self, path: str):
        self.path = path

    def _call(self, execute: str, timeout: float = 30, **arguments):
        s = JsonSocket(self.path, timeout=timeout)
        try:
            # sync handshake discards stale replies from earlier sessions
            token = int(time.time() * 1000) % 2**31
            s.send({"execute": "guest-sync", "arguments": {"id": token}})
            while s.recv().get("return") != token:
                pass
            msg = {"execute": execute}
            if arguments:
                msg["arguments"] = arguments
            s.send(msg)
            r = s.recv()
            if "error" in r:
                raise RuntimeError(f"QGA {execute}: {r['error']}")
            return r.get("return")
        finally:
            s.close()

    def ping(self) -> bool:
        try:
            self._call("guest-ping", timeout=3)
            return True
        except (OSError, ConnectionError, RuntimeError, ValueError):
            return False

    def run(self, cmd: str, timeout: float = 120, user: str | None = None) -> tuple[int, str]:
        """Run a shell command in the guest; returns (exit code, stdout+stderr)."""
        if user:
            import shlex  # single-quote: the outer shell must not expand $?, $VAR, ...
            cmd = f"runuser -u {user} -- bash -lc {shlex.quote(cmd)}"
        pid = self._call("guest-exec", path="/bin/bash", arg=["-c", cmd], **{"capture-output": True})["pid"]
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self._call("guest-exec-status", pid=pid)
            if st.get("exited"):
                out = base64.b64decode(st.get("out-data", "")).decode(errors="replace")
                err = base64.b64decode(st.get("err-data", "")).decode(errors="replace")
                return st.get("exitcode", -1), (out + err).strip()
            time.sleep(0.5)
        raise TimeoutError(f"guest command timed out: {cmd}")


def render_node() -> str | None:
    """Prefer a Mesa-driven render node for virgl (works headless everywhere)."""
    best = None
    for n in sorted(Path("/dev/dri").glob("renderD*")):
        drv = os.path.basename(os.path.realpath(f"/sys/class/drm/{n.name}/device/driver"))
        if drv in ("amdgpu", "i915", "xe", "radeon", "nouveau", "virtio_gpu"):
            return str(n)
        best = best or str(n)
    return best


class VM:
    def __init__(self, workdir: Path, *, iso: Path | None = None, disk: Path | None = None,
                 memory: str = "8G", cpus: int = 4, gl: bool = True, firmware: str = "uefi",
                 extra: list[str] | None = None, net: bool = True, outputs: int = 1):
        self.dir = Path(workdir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.qmp_path = str(self.dir / "qmp.sock")
        self.qga_path = str(self.dir / "qga.sock")
        self.iso, self.disk, self.gl, self.firmware = iso, disk, gl, firmware
        self.memory, self.cpus, self.extra, self.net = memory, cpus, extra or [], net
        self.outputs = outputs
        self.proc: subprocess.Popen | None = None
        self.qmp: QMP | None = None
        self.qga = QGA(self.qga_path)

    def argv(self) -> list[str]:
        a = ["qemu-system-x86_64", "-name", "noctoware-test", "-machine", "q35,accel=kvm", "-cpu", "host",
             "-smp", str(self.cpus), "-m", self.memory,
             "-qmp", f"unix:{self.qmp_path},server=on,wait=off",
             "-chardev", f"socket,path={self.qga_path},server=on,wait=off,id=qga0",
             "-device", "virtio-serial", "-device", "virtserialport,chardev=qga0,name=org.qemu.guest_agent.0",
             "-device", "qemu-xhci", "-device", "usb-tablet", "-device", "usb-kbd",
             *(["-netdev", "user,id=n0", "-device", "virtio-net-pci,netdev=n0"] if self.net else ["-nic", "none"]),
             "-audiodev", "none,id=snd0", "-device", "intel-hda", "-device", "hda-output,audiodev=snd0",
             "-serial", f"file:{self.dir / 'serial.log'}", "-monitor", "none"]
        if self.firmware == "uefi":
            vars_copy = self.dir / "OVMF_VARS.fd"
            if not vars_copy.exists():
                shutil.copy(OVMF_VARS, vars_copy)
            a += ["-drive", f"if=pflash,format=raw,readonly=on,file={OVMF_CODE}",
                  "-drive", f"if=pflash,format=raw,file={vars_copy}"]
        if self.gl:
            node = render_node()
            a += ["-device", f"virtio-vga-gl,xres=1920,yres=1080,max_outputs={self.outputs}",
                  "-display", "egl-headless" + (f",rendernode={node}" if node else "")]
        else:
            a += ["-device", "virtio-vga,xres=1920,yres=1080", "-display", "none"]
        if self.disk:
            fmt = "qcow2" if str(self.disk).endswith(".qcow2") else "raw"
            a += ["-drive", f"file={self.disk},format={fmt},if=virtio,cache=unsafe,discard=unmap"]
        if self.iso:
            a += ["-drive", f"file={self.iso},media=cdrom,readonly=on,if=none,id=cd0",
                  "-device", "ide-cd,drive=cd0,bootindex=0"]
        return a + self.extra

    def start(self) -> "VM":
        for s in (self.qmp_path, self.qga_path):
            if os.path.exists(s):
                os.unlink(s)
        log = open(self.dir / "qemu.log", "w")
        self.proc = subprocess.Popen(self.argv(), stdout=log, stderr=subprocess.STDOUT)
        for _ in range(100):
            if os.path.exists(self.qmp_path):
                try:
                    self.qmp = QMP(self.qmp_path)
                    return self
                except OSError:
                    pass
            if self.proc.poll() is not None:
                raise RuntimeError("qemu exited: " + (self.dir / "qemu.log").read_text()[-2000:])
            time.sleep(0.2)
        raise TimeoutError("QMP socket never appeared")

    def wait_agent(self, timeout: float = 600) -> float:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc and self.proc.poll() is not None:
                raise RuntimeError("VM exited while waiting for the guest agent")
            if self.qga.ping():
                return time.time() - t0
            time.sleep(3)
        raise TimeoutError("guest agent did not come up")

    def wait_for(self, cmd: str, timeout: float = 300, interval: float = 3, user: str | None = None) -> str:
        t0, last = time.time(), ""
        while time.time() - t0 < timeout:
            try:
                rc, last = self.qga.run(cmd, timeout=60, user=user)
                if rc == 0:
                    return last
            except (OSError, RuntimeError, TimeoutError, ConnectionError):
                pass
            time.sleep(interval)
        raise TimeoutError(f"condition not met within {timeout}s: {cmd}\nlast output: {last}")

    def paste(self, text: str) -> None:
        """Type text reliably: put it on the session's Wayland clipboard and
        press Ctrl+V (synthetic key events can be dropped by busy guests)."""
        import shlex
        rc, out = self.qga.run(
            "for d in /run/user/*/; do u=$(stat -c %U $d); s=$(ls $d | grep -E '^wayland-[0-9]+$' | head -1); "
            # text as an argument and no inherited stdio: wl-copy forks to serve the
            # clipboard and must not keep the guest agent's output pipes open
            f"[ -n \"$s\" ] && {{ runuser -u $u -- env XDG_RUNTIME_DIR=$d WAYLAND_DISPLAY=$s "
            f"wl-copy -- {shlex.quote(text)} </dev/null >/dev/null 2>&1; exit 0; }}; done; exit 3", timeout=30)
        if rc != 0:
            raise RuntimeError(f"wl-copy failed: {out}")
        time.sleep(0.3)
        self.qmp.keys("ctrl-v")
        time.sleep(0.3)

    def fill(self, x: int, y: int, text: str) -> None:
        """Click a text field, clear it and paste text into it."""
        self.qmp.click(x, y, 1920, 1080)
        time.sleep(0.4)
        self.qmp.keys("ctrl-a", "backspace")
        self.paste(text)

    def screenshot(self, name: str, user: str | None = None) -> Path:
        """Screenshot of what the user sees.  With a Wayland session running,
        capture inside the compositor (grim): QEMU's screendump cannot read
        GL/dmabuf scanouts under egl-headless.  Falls back to screendump
        (boot menus, SDDM's X11 greeter, consoles)."""
        p = self.dir / f"{name}.png"
        try:  # KDE Plasma: KWin has no wlr-screencopy; use Spectacle
            rc, out = self.qga.run(
                "pid=$(pgrep -x kwin_wayland | head -1); [ -n \"$pid\" ] || exit 3; u=$(ps -o user= -p $pid); "
                "uid=$(id -u $u); s=$(ls /run/user/$uid | grep -E '^wayland-[0-9]+$' | head -1); "
                "runuser -u $u -- env XDG_RUNTIME_DIR=/run/user/$uid "
                "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus WAYLAND_DISPLAY=$s "
                "spectacle -b -n -f -o /tmp/nocto-shot.png >/dev/null 2>&1 && base64 -w0 /tmp/nocto-shot.png", timeout=90)
            if rc == 0 and out:
                p.write_bytes(base64.b64decode(out))
                return p
        except Exception:  # noqa: BLE001
            pass
        try:
            rc, out = self.qga.run(
                "for d in /run/user/*/; do u=$(stat -c %U $d); s=$(ls $d | grep -E '^wayland-[0-9]+$' | head -1); "
                "[ -n \"$s\" ] && { runuser -u $u -- env XDG_RUNTIME_DIR=$d WAYLAND_DISPLAY=$s grim -t png - | base64 -w0; exit 0; }; done; exit 3",
                timeout=60)
            if rc == 0 and out:
                p.write_bytes(base64.b64decode(out))
                return p
        except Exception:  # noqa: BLE001
            pass
        try:  # X11 (SDDM's greeter runs on Xorg)
            rc, out = self.qga.run("a=$(ls /run/sddm/xauth_* 2>/dev/null | head -1); [ -n \"$a\" ] && "
                                   "DISPLAY=:0 XAUTHORITY=$a import -window root png:- | base64 -w0", timeout=60)
            if rc == 0 and out:
                p.write_bytes(base64.b64decode(out))
                return p
        except Exception:  # noqa: BLE001
            pass
        try:
            self.qmp.screenshot(str(p))
        except RuntimeError:
            pass
        return p

    def stop(self, timeout: float = 60) -> None:
        if not self.proc:
            return
        try:
            if self.qmp:
                self.qmp.cmd("system_powerdown")
            self.proc.wait(timeout=timeout)
        except Exception:
            self.proc.kill()
            self.proc.wait()
        finally:
            self.proc = None


def create_disk(path: Path, size: str = "64G") -> Path:
    path = Path(path)
    if path.exists():
        path.unlink()
    subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(path), size], check=True)
    return path


class RepoServer:
    """Serve a local directory over HTTP to the guest (QEMU user-net: host = 10.0.2.2)."""
    def __init__(self, directory: Path, port: int = 0):
        if port == 0:  # pick a free port so parallel VM tests don't collide
            with socket.socket() as s:
                s.bind(("0.0.0.0", 0))
                port = s.getsockname()[1]
        self.dir, self.port = Path(directory), port
        self.proc = None

    def __enter__(self):
        self.proc = subprocess.Popen(["python3", "-m", "http.server", str(self.port), "--bind", "0.0.0.0",
                                      "--directory", str(self.dir)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        return f"http://10.0.2.2:{self.port}"

    def __exit__(self, *exc):
        self.proc.terminate()
        self.proc.wait()


# A killed test (SIGTERM) must still run its `finally:` blocks so the VM is
# powered off and its disk image unlocked.
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(143)))
