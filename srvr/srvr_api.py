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
GET  /print-defaults   -> returns the installed driveLabelPrinter label.json so the
                          WebUI can pre-fill the Print Label form
POST /print-label      -> renders + prints one drive label via the separate
                          driveLabelPrinter project (at C:/driveLabelPrinter); runs
                          synchronously and returns the result
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
# Drive-label printing (driveLabelPrinter integration)
# ---------------------------------------------------------------------------
#
# The driveLabelPrinter project is a *separate* repo installed alongside
# theDobinator on the host. Per deployment it lives at C:\driveLabelPrinter
# (override with DOB_LABEL_PRINTER_DIR). We never modify it — we just write a
# config it accepts (--config) and invoke its entry point in its own venv.

LABEL_PRINTER_DIR     = os.environ.get("DOB_LABEL_PRINTER_DIR", r"C:\driveLabelPrinter")
LABEL_PRINTER_PY      = os.path.join(LABEL_PRINTER_DIR, "src", "driveLabelPrinter.py")
LABEL_PRINTER_VENV_PY = os.path.join(LABEL_PRINTER_DIR, "local", "venv", "Scripts", "python.exe")
LABEL_PRINTER_CONFIG  = os.path.join(LABEL_PRINTER_DIR, "label.json")
# The per-print config we hand to driveLabelPrinter via --config (kept in our
# own logs/ dir so we only ever write inside theDobinator).
LABEL_JOB_CONFIG      = os.path.join(LOGS_DIR, "label_print.json")

# Mirrors the example label.json shipped with driveLabelPrinter; used to
# pre-fill the WebUI form when the real label.json can't be read.
DEFAULT_LABEL_CONFIG = {
    "printer_name": "Brother QL-810W",
    "cage_code": "5ET05",
    "qr_url": "churchillnavigation.com/specifications",
    "copies": 1,
    "label_media": "0.94\" Dia",
    "print_scale": "noscale",
    "master_records_path": "Z:\\SerialNumbers\\SERIAL_NUMBERS.txt",
    "label": {
        "customer": "",
        "purpose": "",
        "hardware": "Other",
        "prepared_by": "",
        "box_serial": "",
    },
}

_VALID_SCALES = ("noscale", "fit", "shrink")
# WebUI mode -> driveLabelPrinter.py CLI args.
_PRINT_MODES = {
    "print":  [],                # real run: render, record a serial, and print
    "test":   ["--test-print"],  # print a test label; records nothing
    "render": ["--no-print"],    # render the PDF only; no print, no record
}


def read_label_defaults() -> dict:
    """Best-effort read of the installed label.json so the WebUI can pre-fill the
    print form with the operator's current values. Falls back to the bundled
    example defaults if the file is missing or unreadable."""
    try:
        with open(LABEL_PRINTER_CONFIG, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.pop("_comment", None)
            return data
    except Exception as exc:
        logger.info("could not read label.json defaults (%s); using built-ins", exc)
    return DEFAULT_LABEL_CONFIG


def _build_label_config(body: dict) -> tuple[dict | None, str]:
    """Validate the WebUI form body and assemble a driveLabelPrinter config.
    Mirrors the validation in driveLabelPrinter's config.py. Returns
    (config_dict, "") on success or (None, error_message)."""
    def s(key: str, default: str = "") -> str:
        return str(body.get(key, default) or "").strip()

    printer_name = s("printer_name")
    cage_code = s("cage_code")
    qr_url = s("qr_url")
    if not printer_name or not cage_code or not qr_url:
        return None, "printer name, CAGE code, and QR URL are all required"

    raw_copies = body.get("copies", 1)
    try:
        copies = int(raw_copies)
    except (TypeError, ValueError):
        return None, "copies must be a whole number"
    if copies < 1:
        return None, "copies must be at least 1"

    label_media = s("label_media") or '0.94" Dia'

    print_scale = s("print_scale").lower() or "noscale"
    if print_scale not in _VALID_SCALES:
        return None, f"print scale must be one of: {', '.join(_VALID_SCALES)}"

    master_records_path = s("master_records_path") or r"Z:\SerialNumbers\SERIAL_NUMBERS.txt"

    label_raw = body.get("label") if isinstance(body.get("label"), dict) else {}
    def ls(key: str) -> str:
        return str(label_raw.get(key, "") or "").strip()

    config = {
        "printer_name": printer_name,
        "cage_code": cage_code,
        "qr_url": qr_url,
        "copies": copies,
        "label_media": label_media,
        "print_scale": print_scale,
        "master_records_path": master_records_path,
        "label": {
            "customer": ls("customer"),
            "purpose": ls("purpose"),
            "hardware": ls("hardware"),
            "prepared_by": ls("prepared_by"),
            "box_serial": ls("box_serial"),
        },
    }
    return config, ""


def print_label(body: dict) -> tuple[bool, str]:
    """Render + print one drive label via the driveLabelPrinter project.

    Writes the form values to a temp config and runs driveLabelPrinter.py with
    --config pointing at it. Runs synchronously (it's a short one-shot, and the
    server is threaded) so we can report real success/failure to the WebUI."""
    if not os.path.isfile(LABEL_PRINTER_PY):
        return False, f"driveLabelPrinter not found at {LABEL_PRINTER_PY}"

    if os.path.isfile(LABEL_PRINTER_VENV_PY):
        python_exe = LABEL_PRINTER_VENV_PY
    else:
        python_exe = sys.executable
        logger.info("label printer venv missing at %s; falling back to %s",
                    LABEL_PRINTER_VENV_PY, python_exe)

    mode = str(body.get("mode", "print")).strip().lower() or "print"
    if mode not in _PRINT_MODES:
        return False, f"unknown print mode: {mode!r}"

    config, err = _build_label_config(body)
    if config is None:
        return False, err

    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(LABEL_JOB_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as exc:
        return False, f"failed to write label config: {exc!r}"

    cmd = [python_exe, LABEL_PRINTER_PY, "--config", LABEL_JOB_CONFIG] + _PRINT_MODES[mode]
    logger.info("printing label: mode=%s cmd=%s", mode, cmd)
    try:
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        proc = subprocess.run(
            cmd,
            cwd=LABEL_PRINTER_DIR,
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, "printing timed out after 180s — check the printer and the driveLabelPrinter logs"
    except Exception as exc:
        return False, f"failed to launch label printer: {exc!r}"

    if proc.returncode == 0:
        verb = {"print": "printed", "test": "test-printed", "render": "rendered"}[mode]
        return True, f"label {verb} successfully"

    tail = (proc.stdout or "").strip().splitlines()[-6:]
    detail = " / ".join(line.strip() for line in tail if line.strip()) or f"exit code {proc.returncode}"
    return False, f"label printer failed (exit {proc.returncode}): {detail}"


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
        if path == "/print-defaults":
            self._send_json(200, {"ok": True, "defaults": read_label_defaults()})
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
        if path == "/print-label":
            body = self._read_json_body()
            ok, msg = print_label(body)
            logger.info("print label: ok=%s msg=%s", ok, msg)
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg})
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
