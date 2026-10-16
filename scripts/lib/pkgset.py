#!/usr/bin/env python3
"""Package-set helpers for Noctoware's dependency tooling (stdlib only).

  pkgset.py conflicts DBDIR < names          check a resolved set for conflicts
  pkgset.py mklocal DBDIR LOCALDIR < names   write a synthetic pacman local db

`pacman -Sp` resolves dependencies but does not run conflict checks, and a
real --dbonly transaction still downloads every package.  This applies
pacman's conflict rule (a package's CONFLICTS entry matching another
package's name or PROVIDES, honouring version constraints) to the set.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tarfile
from functools import lru_cache
from pathlib import Path

DEP_RE = re.compile(r"^([^<>=]+)(?:(<=|>=|<|>|=)(.+))?$")


def parse_desc(text: str) -> dict[str, list[str]]:
    out, key = {}, None
    for line in text.splitlines():
        if line.startswith("%") and line.endswith("%"):
            key = line.strip("%")
            out[key] = []
        elif line and key:
            out[key].append(line)
    return out


def load_dbs(dbdir: Path) -> dict[str, dict]:
    """name -> desc for every package; first repository wins (pacman order is
    preserved by sorting on the order file if present, else filename order)."""
    pkgs: dict[str, dict] = {}
    order = (dbdir / "ORDER").read_text().split() if (dbdir / "ORDER").exists() else None
    dbs = [dbdir / f"{r}.db" for r in order] if order else sorted(dbdir.glob("*.db"))
    for db in dbs:
        with tarfile.open(db) as tf:
            for m in tf.getmembers():
                if m.name.endswith("/desc"):
                    d = parse_desc(tf.extractfile(m).read().decode())
                    pkgs.setdefault(d["NAME"][0], d)
    return pkgs


@lru_cache(maxsize=None)
def vercmp(a: str, b: str) -> int:
    return int(subprocess.run(["vercmp", a, b], capture_output=True, text=True, check=True).stdout)


def satisfies(version: str, op: str | None, want: str | None) -> bool:
    if not op:
        return True
    if "-" not in want:  # constraint without pkgrel compares upstream version only
        version = version.rsplit("-", 1)[0]
    c = vercmp(version, want)
    return {"=": c == 0, "<": c < 0, ">": c > 0, "<=": c <= 0, ">=": c >= 0}[op]


def conflicts(pkgs: dict[str, dict], names: list[str]) -> list[str]:
    provided: dict[str, list[tuple[str, str]]] = {}
    for n in names:
        p = pkgs[n]
        ver = p["VERSION"][0]
        provided.setdefault(n, []).append((n, ver))
        for prov in p.get("PROVIDES", []):
            m = DEP_RE.match(prov)
            provided.setdefault(m.group(1), []).append((n, m.group(3) or ver))
    problems = []
    for n in names:
        for c in pkgs[n].get("CONFLICTS", []):
            m = DEP_RE.match(c)
            cname, op, want = m.group(1), m.group(2), m.group(3)
            for other, over in provided.get(cname, []):
                if other != n and satisfies(over, op, want):
                    problems.append(f"{n} conflicts with {other} ({c})")
    return sorted(set(problems))


def mklocal(pkgs: dict[str, dict], names: list[str], local: Path) -> None:
    local.mkdir(parents=True, exist_ok=True)
    (local / "ALPM_DB_VERSION").write_text("9\n")
    for n in names:
        p = pkgs[n]
        d = local / f"{n}-{p['VERSION'][0]}"
        d.mkdir(exist_ok=True)
        fields = ["NAME", "VERSION", "BASE", "DESC", "URL", "ARCH", "BUILDDATE", "PACKAGER", "SIZE",
                  "LICENSE", "REPLACES", "DEPENDS", "OPTDEPENDS", "CONFLICTS", "PROVIDES"]
        body = "".join(f"%{k}%\n" + "\n".join(p[k]) + "\n\n" for k in fields if p.get(k))
        body += "%INSTALLDATE%\n1700000000\n\n%REASON%\n0\n\n%VALIDATION%\nnone\n\n"
        (d / "desc").write_text(body)
        (d / "files").write_text("")


def main() -> int:
    cmd, dbdir = sys.argv[1], Path(sys.argv[2])
    names = [l.strip() for l in sys.stdin if l.strip()]
    pkgs = load_dbs(dbdir)
    missing = [n for n in names if n not in pkgs]
    if missing:
        print("unknown packages: " + " ".join(missing), file=sys.stderr)
        return 2
    if cmd == "conflicts":
        probs = conflicts(pkgs, names)
        for p in probs:
            print(p)
        return 1 if probs else 0
    if cmd == "mklocal":
        mklocal(pkgs, names, Path(sys.argv[3]))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
