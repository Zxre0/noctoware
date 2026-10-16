#!/usr/bin/env python3
"""Frozen-database mirror for reproducible ISO builds.

  frozen-mirror.py FROZEN_DIR PORT REPO=UPSTREAM_URL...

GET /<repo>/<repo>.db[.sig]  -> served from FROZEN_DIR/<repo>/ (the snapshot)
GET /<repo>/<anything else>  -> 302 redirect to UPSTREAM_URL/<file>

Every pacman run of the build (mkarchiso's pacstrap and the offline-cache
download) therefore sees the same databases, while package files still come
from the real mirrors.  Redirecting instead of 404ing keeps pacman's
per-server error counter at zero.
"""
import http.server
import sys
from pathlib import Path

FROZEN = Path(sys.argv[1])
PORT = int(sys.argv[2])
UPSTREAM = dict(arg.split("=", 1) for arg in sys.argv[3:])


class Handler(http.server.BaseHTTPRequestHandler):
    def _route(self, head: bool) -> None:
        parts = self.path.lstrip("/").split("/")
        if len(parts) != 2 or parts[0] not in UPSTREAM:
            self.send_error(404)
            return
        repo, name = parts
        local = FROZEN / repo / name
        if name.startswith(f"{repo}.db") or name.startswith(f"{repo}.files"):
            if not local.is_file():
                self.send_error(404)
                return
            data = local.read_bytes()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            if not head:
                self.wfile.write(data)
            return
        self.send_response(302)
        self.send_header("Location", f"{UPSTREAM[repo].rstrip('/')}/{name}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._route(False)

    def do_HEAD(self):
        self._route(True)

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
