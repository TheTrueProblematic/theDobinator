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
GET  /update-status    -> whether an update is pending, needs a reboot, and whether
                          a drive is processing (so the WebUI can show its badge)
GET  /health           -> liveness check; returns 200 {"ok": true}
*    *                 -> 404

This process also OWNS update detection now (it used to live in dobd.py, which
meant it stopped the moment the bot was powered off). A background thread polls
GitHub and publishes logs/update_state.json; both portals read it from there.

It also restarts the bot after an update-driven reboot — see maybe_autostart().

Label printing is NOT here. It moved to its own site (drivelabel.c-nav.com) and
its own server, drivelabel/label_api.py on port 5051.

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
import threading
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
# Written by git_update.py right before an update-driven reboot; consumed once at
# startup by maybe_autostart() to bring the bot back up.
AUTOSTART_FLAG = os.path.join(LOGS_DIR, "autostart.flag")

HOST = os.environ.get("DOB_API_HOST", "0.0.0.0")
PORT = int(os.environ.get("DOB_API_PORT", "5050"))
# Seconds between GitHub update checks. Conditional (ETag) requests make these
# nearly free, but there's no reason to be chatty — dobd.py's old watcher fired
# every 5s, which was only that frequent because it piggybacked the drive loop.
UPDATE_CHECK_INTERVAL_S = int(os.environ.get("DOB_UPDATE_CHECK_INTERVAL", "120"))

# The update checker is shared with git_update.py's world; configs/git_updater
# isn't a package, so put it on the path the same way the rest of this project
# resolves siblings.
sys.path.insert(0, os.path.join(PROJECT_DIR, "configs", "git_updater"))
import update_check  # noqa: E402  (deliberately after the sys.path tweak)

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
# Update detection (moved here from dobd.py)
# ---------------------------------------------------------------------------
#
# This lives in the API rather than the bot because the bot gets powered off, and
# an update that's pending while the bot is off is exactly the case that used to
# go unreported on both portals. This process runs from logon to shutdown.
#
# State is published to logs/update_state.json, NOT into srvr/status.json:
# dobd.py writes status.json from several threads under an RLock, and that lock
# can't stop a second *process* from interleaving a write.

_update_checker = update_check.UpdateChecker(PROJECT_DIR, logger)


def _update_watch_loop() -> None:
    """Poll GitHub forever, publishing update state. Never lets an error escape."""
    if not _update_checker.has_pat:
        logger.info(
            "no GitHub PAT in configs/keys.json — update detection is disabled. "
            "Paste a token into the GITHUB_PAT field and restart this task."
        )
        return
    while True:
        try:
            _update_checker.check_once()
        except Exception as exc:
            logger.info("update check raised (non-fatal): %r", exc)
        time.sleep(UPDATE_CHECK_INTERVAL_S)


def start_update_watcher() -> None:
    threading.Thread(target=_update_watch_loop, name="update-watcher", daemon=True).start()


def read_status_processing() -> bool:
    """
    True when a drive is actively being worked, so an update can't be applied
    right now. Mirrors isProcessing() in app.js: running, and on an in-progress
    step (1–9 build/format/country, 12–14 imagery verification) — the terminal
    states 10/11 and idle 0 don't count.
    """
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            text = f.read().strip()
        data = json.loads(text) if text else {}
        if not isinstance(data, dict):
            return False
    except Exception:
        return False
    running = data.get("Running") in (1, True, "1")
    try:
        n = int(data.get("StatusNumber", 0) or 0)
    except (TypeError, ValueError):
        n = 0
    return bool(running and n >= 1 and n not in (10, 11))


def update_status_payload() -> dict:
    state = update_check.read_update_state(LOGS_DIR)
    return {
        "available": state["available"],
        "reboot": state["reboot"],
        "processing": read_status_processing(),
    }


# ---------------------------------------------------------------------------
# Auto-start after an update-driven reboot
# ---------------------------------------------------------------------------

def maybe_autostart() -> None:
    """
    Bring the bot back up after an update that restarted the PC.

    git_update.py writes logs/autostart.flag just before `shutdown /r`. Only that
    path writes it, so an ordinary manual reboot still leaves the bot off — this
    restores the state an update took away rather than changing what a reboot
    means. The flag is consumed (deleted) whether or not the launch succeeds, so a
    failure can't leave the box starting the bot on every future logon.
    """
    if not os.path.isfile(AUTOSTART_FLAG):
        return
    try:
        with open(AUTOSTART_FLAG, "r", encoding="utf-8") as f:
            wanted = f.read().strip().lower() in ("1", "true", "yes")
    except Exception:
        wanted = False
    try:
        os.remove(AUTOSTART_FLAG)
    except Exception as exc:
        logger.info("could not clear autostart flag: %r", exc)

    if not wanted:
        return
    if _is_dobd_running():
        logger.info("autostart requested but dobd.py is already running; nothing to do.")
        return

    # dobWin.bat is a TOGGLE, so this is only safe because we just confirmed the
    # bot isn't running — otherwise it would shut it back down.
    ok, msg = trigger_power_toggle()
    logger.info("autostart after update: ok=%s msg=%s", ok, msg)


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
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._send_json(200, {"ok": True, "service": "dob_srvr_api"})
            return
        if path == "/update-status":
            self._send_json(200, {"ok": True, **update_status_payload()})
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
    # Scrub stale status FIRST, then bring the bot back if an update took it down —
    # otherwise the scrub would wipe the state the restarting bot just published.
    maybe_autostart()
    start_update_watcher()
    server = ThreadingHTTPServer((HOST, PORT), PowerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down (keyboard interrupt)")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
