#!/usr/bin/env python3
"""Foreman live dashboard server (read-only).

  python3 scripts/dashboard.py            -> http://127.0.0.1:8787
  python3 scripts/dashboard.py --port 9000

Serves the front end in dashboard/ (index.html, styles.css, app.js) and a JSON
snapshot at /api/state. It only reads tasks.json and reports/. All changes
still happen in the Switch room, where the agents run scripts/board.py.
Standard library only.
"""
import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as B  # noqa: E402

WEB = B.ROOT / "dashboard"
STATIC = {  # explicit allow-list, so nothing else in the repo is served
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


def state() -> dict:
    data = B.load()
    return {
        "project": data["project"],
        "release": data["release"],
        "tasks": data["tasks"],
        "team": B.TEAM,
        "load": B.loads(data),
        "health": B.health(data),
        "activity": B.activity(data)[:40],
        "report": B.latest_report(),
        "generated": B.stamp(),
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            try:
                self._send(200, json.dumps(state()).encode(), "application/json")
            except Exception as e:  # board mid-write or invalid: tell the page, don't crash
                self._send(503, json.dumps({"error": str(e)}).encode(), "application/json")
        elif path in STATIC:
            name, ctype = STATIC[path]
            self._send(200, (WEB / name).read_bytes(), ctype)
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *_):
        pass


def main():
    p = argparse.ArgumentParser(description="Foreman live dashboard (read-only)")
    p.add_argument("--port", type=int, default=8787)
    a = p.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"Foreman dashboard: http://127.0.0.1:{a.port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
