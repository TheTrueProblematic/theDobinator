"""
The Dobinator — companion HTTP server.

A tiny stdlib-only HTTP server that exposes the one thing IIS can't do
as a static host: executing dobWin.bat when the web portal's power
button is clicked.

Endpoints
---------
POST /power     -> launches dobWin.bat in a detached process; returns 200
GET  /health    -> liveness check; returns 200 {"ok": true}
*    *          -> 404

Runs on 0.0.0.0:5050 by default. Configure on the Windows box via Task
Scheduler so it starts at boot. See HostingInstructions.md.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# Paths and config
# ---------------------------------------------------------------------------

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))                    # ...\srvr
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)                                   # ...\theDobinator
DOB_BAT     = os.path.join(PROJECT_DIR, "dobWin.bat")
LOG_FILE    = os.path.join(SCRIPT_DIR, "srvr_api.log")

HOST = os.environ.get("DOB_API_HOST", "0.0.0.0")
PORT = int(os.environ.get("DOB_API_PORT", "5050"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("dob_srvr_api")
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)
logger.addHandler(logging.StreamHandler(sys.stdout))


# ---------------------------------------------------------------------------
# Power toggle
# ---------------------------------------------------------------------------

def trigger_power_toggle() -> tuple[bool, str]:
    """Run dobWin.bat in the project root, detached. Returns (ok, message)."""
    if not os.path.isfile(DOB_BAT):
        return False, f"dobWin.bat not found at {DOB_BAT}"

    try:
        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            subprocess.Popen(
                ["cmd.exe", "/c", DOB_BAT],
                cwd=PROJECT_DIR,
                creationflags=flags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            # Non-Windows path is for local dev/smoke testing only.
            subprocess.Popen(
                ["/bin/sh", "-c", f'echo "[mock] would run dobWin.bat at {DOB_BAT}"'],
                cwd=PROJECT_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        return True, "dobWin.bat launched"
    except Exception as exc:
        return False, f"failed to launch: {exc!r}"


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age":       "86400",
}


class PowerHandler(BaseHTTPRequestHandler):
    server_version = "DobinatorAPI/1.0"

    # Quieter default access log; route through our logger instead.
    def log_message(self, fmt, *args):
        logger.info("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, status: int, body: dict):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            self._send_json(200, {"ok": True, "service": "dob_srvr_api"})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/power":
            ok, msg = trigger_power_toggle()
            logger.info("power toggle requested: ok=%s msg=%s", ok, msg)
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg})
            return
        self._send_json(404, {"ok": False, "error": "not found"})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    logger.info("dob_srvr_api starting on %s:%d (project=%s)", HOST, PORT, PROJECT_DIR)
    logger.info("dobWin.bat path: %s (exists=%s)", DOB_BAT, os.path.isfile(DOB_BAT))
    server = ThreadingHTTPServer((HOST, PORT), PowerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down (keyboard interrupt)")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
