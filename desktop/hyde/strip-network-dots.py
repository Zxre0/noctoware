#!/usr/bin/env python3
"""strip-network-dots.py SRC DST NAME...  — copy a deez dots TOML file without
the named dot tables ([name], [[name.files]], [[name.dependency]], ...).
Used at package build time to drop dots that download from the internet;
Noctoware ships those files pinned instead (see noctoware-hyde PKGBUILD)."""
import re
import sys

src, dst, names = sys.argv[1], sys.argv[2], set(sys.argv[3:])
out, skipping = [], False
header = re.compile(r"^\s*\[\[?\s*([A-Za-z0-9_.-]+?)(?:\.[A-Za-z0-9_-]+)?\s*\]\]?\s*$")
for line in open(src):
    m = header.match(line)
    if m:
        skipping = m.group(1).split(".")[0] in names
    if not skipping:
        out.append(line)
open(dst, "w").write("".join(out))
removed = [n for n in names if f"[{n}]" not in "".join(out)]
print(f"{dst}: removed {sorted(removed)}")
