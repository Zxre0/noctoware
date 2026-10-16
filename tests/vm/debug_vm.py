#!/usr/bin/env python3
"""Interactive helper: start a VM in the background and leave it running.
   debug_vm.py start ISO|DISK DIR      (prints when the guest agent is up)
   debug_vm.py run DIR 'command' [user]
   debug_vm.py shot DIR name
   debug_vm.py keys DIR key...         / type DIR text / click DIR x y
   debug_vm.py stop DIR"""
import sys, time, os, signal, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from vmctl import VM, QMP, QGA

cmd, args = sys.argv[1], sys.argv[2:]
if cmd == "start":
    src, d = Path(args[0]).resolve(), Path(args[1])
    extra = args[2:]
    kw = {"iso": src} if src.suffix == ".iso" else {"disk": src}
    if len(extra) and extra[0].endswith((".qcow2", ".raw")):
        kw["disk"] = Path(extra[0]).resolve()
    vm = VM(d, **kw).start()
    (d / "pid").write_text(str(vm.proc.pid))
    print(f"agent up after {vm.wait_agent(600):.0f}s")
    os._exit(0)  # leave qemu running
d = Path(args[0])
if cmd == "run":
    rc, out = QGA(str(d / "qga.sock")).run(args[1], timeout=1800, user=args[2] if len(args) > 2 else None)
    print(out); print(f"[rc={rc}]")
elif cmd == "shot":
    q = QMP(str(d / "qmp.sock")); print(q.screenshot(str(d / f"{args[1]}.png")))
elif cmd == "keys":
    QMP(str(d / "qmp.sock")).keys(*args[1:])
elif cmd == "type":
    QMP(str(d / "qmp.sock")).type(args[1])
elif cmd == "click":
    QMP(str(d / "qmp.sock")).click(int(args[1]), int(args[2]), 1920, 1080)
elif cmd == "push":   # push DIR LOCAL REMOTE [mode]
    import base64
    data = base64.b64encode(Path(args[1]).read_bytes()).decode()
    q = QGA(str(d / "qga.sock"))
    q.run(f"rm -f {args[2]}.b64")
    for i in range(0, len(data), 48000):
        q.run(f"printf %s '{data[i:i+48000]}' >> {args[2]}.b64")
    rc, out = q.run(f"base64 -d {args[2]}.b64 > {args[2]} && rm {args[2]}.b64 && chmod {args[3] if len(args) > 3 else '644'} {args[2]}")
    print(f"pushed {args[1]} -> {args[2]} rc={rc} {out}")
elif cmd == "stop":
    try:
        QMP(str(d / "qmp.sock")).cmd("quit")
    except Exception:
        os.kill(int((d / "pid").read_text()), signal.SIGKILL)
