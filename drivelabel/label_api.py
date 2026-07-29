"""
Drive Label — companion HTTP server.

The dynamic backend for the Drive Label site (drivelabel.c-nav.com). It exists
because IIS can only hand out static files, and printing a label means running
the *separate* driveLabelPrinter project on this machine.

These two endpoints used to live in theDobinator's srvr_api.py (port 5050);
they were moved here when label printing became its own site so the two sites
share nothing but the host they run on.

Endpoints
---------
GET  /print-defaults -> returns the installed driveLabelPrinter label.json so the
                        site can pre-fill the (admin-only) printer settings
POST /print-label    -> renders + prints one drive label via driveLabelPrinter
                        (at C:/driveLabelPrinter); runs synchronously and returns
                        the real result
GET  /health         -> liveness check; returns 200 {"ok": true}
*    *               -> 404

Runs on 0.0.0.0:5051 by default (theDobinator's API owns 5050). Configure on the
Windows box via Task Scheduler so it starts at logon. See README.md next to this
file.
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

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))                    # ...\drivelabel
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)                                   # ...\theDobinator
LOGS_DIR    = os.path.join(PROJECT_DIR, "logs")
LOG_FILE    = os.path.join(LOGS_DIR, "labelApi.log")

HOST = os.environ.get("LABEL_API_HOST", "0.0.0.0")
PORT = int(os.environ.get("LABEL_API_PORT", "5051"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Own dedicated log file per AGENTS.md §4. Uses RotatingFileHandler rather than
# the rotate_prev_log() pattern for the same reason srvr_api.py does: this is a
# long-lived server with no "run" boundary to roll on.

os.makedirs(LOGS_DIR, exist_ok=True)

logger = logging.getLogger("drivelabel_api")
logger.setLevel(logging.INFO)
logger.propagate = False
_handler = RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)
logger.addHandler(logging.StreamHandler(sys.stdout))


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
# pre-fill the site's printer settings when the real label.json can't be read.
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
# Site mode -> driveLabelPrinter.py CLI args.
_PRINT_MODES = {
    "print":  [],                # real run: render, record a serial, and print
    "test":   ["--test-print"],  # print a test label; records nothing
    "render": ["--no-print"],    # render the PDF only; no print, no record
}


def read_label_defaults() -> dict:
    """Best-effort read of the installed label.json so the site can pre-fill the
    printer settings with the operator's current values. Falls back to the
    bundled example defaults if the file is missing or unreadable.

    Note the site ignores the `label` block in here on purpose — label content
    always starts blank so a previous print's values can never be reprinted by
    accident."""
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
    """Validate the site's form body and assemble a driveLabelPrinter config.
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
    server is threaded) so we can report real success/failure to the site."""
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
# CORS is required even though the site and this API are on the same machine:
# the page is served from port 80 and this listens on 5051, which makes every
# request cross-origin.

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age":       "86400",
}


class LabelHandler(BaseHTTPRequestHandler):
    server_version = "DriveLabelAPI/1.0"

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
            self._send_json(200, {"ok": True, "service": "drivelabel_api"})
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

def main():
    logger.info("drivelabel_api starting on %s:%d", HOST, PORT)
    logger.info("driveLabelPrinter entry: %s (exists=%s)",
                LABEL_PRINTER_PY, os.path.isfile(LABEL_PRINTER_PY))
    logger.info("driveLabelPrinter venv:  %s (exists=%s)",
                LABEL_PRINTER_VENV_PY, os.path.isfile(LABEL_PRINTER_VENV_PY))
    server = ThreadingHTTPServer((HOST, PORT), LabelHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("shutting down (keyboard interrupt)")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
