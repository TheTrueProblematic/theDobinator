"""
The Dobinator — companion HTTP server.

A tiny stdlib-only HTTP server that exposes the one thing IIS can't do
as a static host: executing dobWin.bat when the web portal's power
button is clicked.

Endpoints
---------
POST /power            -> launches dobWin.bat in a detached process; returns 200
POST /update           -> launches configs/dobGitManual.bat to apply an update now
POST /schedule-update  -> writes logs/update_scheduled.flag so dobd.py applies the
                          update once the current drive finishes processing
POST /update-reboot    -> launches git_update.py --reboot now (pull, clear flag,
                          restart the whole PC); for updates that need a reboot
POST /schedule-update-reboot -> schedules a reboot-update for after the current drive
POST /submit-drive     -> writes a blank-drive submission ({token,name,country})
                          into logs/submissions/ for dobd.py to format + queue
GET  /health           -> liveness check; returns 200 {"ok": true}
*    *                 -> 404

Runs on 0.0.0.0:5050 by default. Configure on the Windows box via Task
Scheduler so it starts at boot. See HostingInstructions.md.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# Paths and config
# ---------------------------------------------------------------------------

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))                    # ...\srvr
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)                                   # ...\theDobinator
DOB_BAT     = os.path.join(PROJECT_DIR, "dobWin.bat")
UPDATE_BAT  = os.path.join(PROJECT_DIR, "configs", "dobGitManual.bat")
LOGS_DIR    = os.path.join(PROJECT_DIR, "logs")
UPDATE_SCHEDULED_FLAG = os.path.join(LOGS_DIR, "update_scheduled.flag")
SUBMISSIONS_DIR = os.path.join(LOGS_DIR, "submissions")
STATUS_FILE = os.path.join(SCRIPT_DIR, "status.json")
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


def _launch_bat_detached(bat_path: str) -> tuple[bool, str]:
    """Run a .bat file detached, with no window and stdin closed. Returns (ok, message)."""
    if not os.path.isfile(bat_path):
        return False, f"{os.path.basename(bat_path)} not found at {bat_path}"
    try:
        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                cwd=PROJECT_DIR,
                creationflags=flags,
                stdin=subprocess.DEVNULL,   # closed stdin lets the bat's `pause` return immediately
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                ["/bin/sh", "-c", f'echo "[mock] would run {bat_path}"'],
                cwd=PROJECT_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        return True, f"{os.path.basename(bat_path)} launched"
    except Exception as exc:
        return False, f"failed to launch: {exc!r}"


def trigger_update_now() -> tuple[bool, str]:
    """Apply an update immediately by launching configs/dobGitManual.bat."""
    return _launch_bat_detached(UPDATE_BAT)


def trigger_update_reboot_now() -> tuple[bool, str]:
    """
    Apply a reboot-required update immediately: launch git_update.py --reboot
    detached. That script stops the bot, pulls the new code, clears the
    reboot-required flag, then restarts the whole PC.
    """
    updater = os.path.join(PROJECT_DIR, "configs", "git_updater", "git_update.py")
    if not os.path.isfile(updater):
        return False, f"git_update.py not found at {updater}"
    try:
        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            subprocess.Popen(
                [sys.executable, updater, "--reboot"],
                cwd=PROJECT_DIR,
                creationflags=flags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                [sys.executable, updater, "--reboot"],
                cwd=PROJECT_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        return True, "reboot-update launched (git_update.py --reboot)"
    except Exception as exc:
        return False, f"failed to launch reboot update: {exc!r}"


def _write_schedule_flag(content: str) -> tuple[bool, str]:
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(UPDATE_SCHEDULED_FLAG, "w", encoding="utf-8") as f:
            f.write(content)
        return True, f"update scheduled for after current drive ({content})"
    except Exception as exc:
        return False, f"failed to schedule update: {exc!r}"


def schedule_update() -> tuple[bool, str]:
    """Schedule a normal update for once the current drive finishes."""
    return _write_schedule_flag("scheduled")


def schedule_update_reboot() -> tuple[bool, str]:
    """Schedule a reboot-required update for once the current drive finishes."""
    return _write_schedule_flag("reboot")


_TOKEN_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def submit_drive(body: dict) -> tuple[bool, str]:
    """
    Persist a blank-drive submission for dobd.py to pick up. Expects
    {token, name, country}; writes logs/submissions/<safe-token>.json. dobd.py
    re-validates and sanitizes everything, so this only does light checks.
    """
    token = str(body.get("token", "")).strip()
    name = str(body.get("name", "")).strip()
    country = str(body.get("country", "")).strip().upper()

    if not token or not name or not re.fullmatch(r"[A-Z]{3}", country):
        return False, "token, name, and a 3-letter country code are all required"

    safe_token = _TOKEN_SAFE.sub("_", token)[:64] or "drive"
    try:
        os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
        # Unique filename per submission so a re-submit can't clobber a pending one.
        fname = f"{safe_token}-{int(time.time() * 1000)}.json"
        fpath = os.path.join(SUBMISSIONS_DIR, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump({"token": token, "name": name, "country": country}, f)
        return True, f"submission accepted ({fname})"
    except Exception as exc:
        return False, f"failed to write submission: {exc!r}"


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

    def _read_json_body(self) -> dict:
        """Read and parse a JSON request body; return {} on any problem."""
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        try:
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/power":
            ok, msg = trigger_power_toggle()
            logger.info("power toggle requested: ok=%s msg=%s", ok, msg)
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg})
            return
        if path == "/update":
            ok, msg = trigger_update_now()
            logger.info("immediate update requested: ok=%s msg=%s", ok, msg)
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg})
            return
        if path == "/schedule-update":
            ok, msg = schedule_update()
            logger.info("scheduled update requested: ok=%s msg=%s", ok, msg)
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg})
            return
        if path == "/update-reboot":
            ok, msg = trigger_update_reboot_now()
            logger.info("immediate reboot-update requested: ok=%s msg=%s", ok, msg)
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg})
            return
        if path == "/schedule-update-reboot":
            ok, msg = schedule_update_reboot()
            logger.info("scheduled reboot-update requested: ok=%s msg=%s", ok, msg)
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg})
            return
        if path == "/submit-drive":
            body = self._read_json_body()
            ok, msg = submit_drive(body)
            logger.info("drive submission: ok=%s msg=%s", ok, msg)
            self._send_json(200 if ok else 400, {"ok": ok, "message": msg})
            return
        self._send_json(404, {"ok": False, "error": "not found"})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def _is_dobd_running() -> bool:
    """True if a python/pythonw process is currently running dobd.py (Windows only)."""
    if os.name != "nt":
        return False
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$p = Get-CimInstance Win32_Process -Filter "
             "\"Name = 'python.exe' OR Name = 'pythonw.exe'\" | "
             "Where-Object { $_.CommandLine -match 'dobd.py' }; "
             "if ($p) { exit 0 } else { exit 1 }"],
            creationflags=0x08000000,  # CREATE_NO_WINDOW
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc.returncode == 0
    except Exception as exc:
        logger.info("could not determine if dobd.py is running: %r", exc)
        return False


def reset_status_if_bot_down() -> None:
    """
    On startup (typically the logon that follows a reboot), if the main bot is
    NOT running, scrub the transient fields in status.json so the WebUI doesn't
    resurrect a stale popup / pending list / "running" state that a hard reboot
    froze in place. The bot rewrites these the moment it starts, so this is safe.
    """
    if _is_dobd_running():
        logger.info("dobd.py is already running; leaving status.json untouched.")
        return
    if not os.path.isfile(STATUS_FILE):
        return
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
        data["Running"] = 0
        data["StatusNumber"] = 0
        data["BlankDrives"] = []
        data["PendingDrives"] = []
        data["TotalBaseFiles"] = -1
        data["CompletedBaseFiles"] = -1
        data["TotalMainFiles"] = -1
        data["CompletedMainFiles"] = -1
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logger.info("dobd.py not running at API startup; reset transient status.json fields.")
    except Exception as exc:
        logger.info("could not reset status.json at startup: %r", exc)


def main():
    logger.info("dob_srvr_api starting on %s:%d (project=%s)", HOST, PORT, PROJECT_DIR)
    logger.info("dobWin.bat path: %s (exists=%s)", DOB_BAT, os.path.isfile(DOB_BAT))
    reset_status_if_bot_down()
    server = ThreadingHTTPServer((HOST, PORT), PowerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down (keyboard interrupt)")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
