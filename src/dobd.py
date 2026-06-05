import os
import re
import sys
import time
import ctypes
import string
import logging
import csv
import shutil
import subprocess
import json
import threading
import queue
import zipfile
import datetime
import tempfile
import urllib.request
import urllib.error

# --- Logging Setup ---
# Find the project root by going up one level from the 'src' directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

# Ensure the logs directory exists
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LOG_FILE = os.path.join(LOGS_DIR, "dobLog.log")
PREV_LOG_FILE = os.path.join(LOGS_DIR, "dobLogPrev.log")
# Dedicated log for the polling process (drive scanning loop + GitHub update
# watcher). Kept separate from dobLog.log so the rest of the bot's logs aren't
# drowned out by the once-a-second polling chatter.
POLLING_LOG_FILE = os.path.join(LOGS_DIR, "pollingLog.log")
POLLING_PREV_LOG_FILE = os.path.join(LOGS_DIR, "pollingLogPrev.log")
# Dedicated log for the Open Interpreter subprocess runs (their verbose output
# is captured by dobd.py and funneled here, keeping it out of dobLog.log).
LLM_LOG_FILE = os.path.join(LOGS_DIR, "llmRunner.log")
LLM_PREV_LOG_FILE = os.path.join(LOGS_DIR, "llmRunnerPrev.log")
RUN_SEPARATOR = "\n" + "="*50 + " END OF RUN " + "="*50 + "\n"

# --- Completed-drive history (persisted forever) ---
# Every completed drive is appended here as "ISO-timestamp,name,issues" and
# kept indefinitely. The WebUI only surfaces the last 24 hours (see
# StatusManager._load_recent_completed_drives), but the full record lives here.
COMPLETED_DRIVES_CSV = os.path.join(LOGS_DIR, "completedDrives.csv")

# --- Update / queue-resume coordination files ---
# update_scheduled.flag is written by the companion API (srvr_api.py) when the
# user asks to apply an update once the current drive finishes. drive_queue.json
# holds the drives still waiting to be processed so they survive the program
# restart that an update triggers.
UPDATE_SCHEDULED_FLAG = os.path.join(LOGS_DIR, "update_scheduled.flag")
SAVED_QUEUE_FILE = os.path.join(LOGS_DIR, "drive_queue.json")

# --- Blank-drive submission inbox ---
# When a drive without packfiles.txt is detected, the WebUI prompts the user for
# a Drive Name + Country. The companion API (srvr_api.py) drops one JSON file per
# submission into this directory ({token, name, country}); the monitoring loop in
# dobd.py consumes them, formats+queues the matching drive, and deletes the file.
SUBMISSIONS_DIR = os.path.join(LOGS_DIR, "submissions")

# --- GitHub update watcher configuration ---
# Used purely to poll for new commits via cheap HTTP conditional (ETag)
# requests so we can light up the "update available" indicator in the WebUI
# without burning the rate limit.
GITHUB_REPO = "TheTrueProblematic/theDobinator"
GITHUB_BRANCH = "main"
GITHUB_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPO}/commits"
    f"?sha={GITHUB_BRANCH}&per_page=1"
)
# Contents API for the reboot-required flag file on the remote. When a new commit
# is detected, the watcher reads this to decide whether the *incoming* update
# needs a full PC restart (red update button) vs a normal update (yellow).
GITHUB_FLAG_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPO}/contents/configs/reboot_required.flag"
    f"?ref={GITHUB_BRANCH}"
)
# How many 1-second drive-poll iterations between GitHub checks (~5 seconds).
GITHUB_CHECK_EVERY = 5
# How many 1-second poll iterations between full physical-disk scans (~2 seconds).
# Disk enumeration spawns PowerShell, so it is throttled relative to the loop.
DISK_SCAN_EVERY = 2

# --- Secrets / keys file ---
# The GitHub fine-grained PAT is deliberately NOT stored in source (it would
# leak the moment the repo is pushed). It lives in configs/keys.json, which is
# gitignored. That file is auto-created with a blank key slot on first run, and
# the program refuses to run until the key has been filled in.
CONFIGS_DIR = os.path.join(PROJECT_ROOT, "configs")
KEYS_FILE = os.path.join(CONFIGS_DIR, "keys.json")
# Committed flag (1/0) marking whether the published update needs a PC reboot.
# Agents set it per AGENTS.md; git_update.py --reboot clears it after applying.
REBOOT_FLAG_FILE = os.path.join(CONFIGS_DIR, "reboot_required.flag")
GITLOG_FILE = os.path.join(LOGS_DIR, "gitLog.log")
GITHUB_PAT_LABEL = "GITHUB_PAT"
KEYS_FILE_TEMPLATE = {
    "_README": (
        "The Dobinator secrets file. NEVER commit this file (it is gitignored). "
        "Paste your GitHub fine-grained Personal Access Token (scoped to "
        "Contents: Read on TheTrueProblematic/theDobinator) between the quotes "
        "for GITHUB_PAT below. The Dobinator will not run until this is filled in."
    ),
    "GITHUB_PAT": ""
}

def rotate_prev_log(log_file, prev_log_file):
    """
    Before a log file is truncated for a new run, fold its last run into the
    matching *Prev.log file, keeping the 5 most recent runs (separated by
    RUN_SEPARATOR). Used for both dobLog.log and pollingLog.log.
    """
    if not os.path.exists(log_file):
        return
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            last_run_log = f.read().strip()

        if last_run_log:
            prev_logs = []
            if os.path.exists(prev_log_file):
                with open(prev_log_file, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    prev_logs = [log.strip() for log in content.split(RUN_SEPARATOR) if log.strip()]

            # Keep the last 4 logs, then add the most recent run
            prev_logs = prev_logs[-4:]
            prev_logs.append(last_run_log)

            with open(prev_log_file, 'w', encoding='utf-8') as f:
                f.write(RUN_SEPARATOR.join(prev_logs) + RUN_SEPARATOR)
    except Exception as e:
        print(f"Failed to update previous logs for {log_file}: {e}")


# Maintain the past 5 runs in each *Prev.log before the handlers truncate them.
rotate_prev_log(LOG_FILE, PREV_LOG_FILE)
rotate_prev_log(POLLING_LOG_FILE, POLLING_PREV_LOG_FILE)
rotate_prev_log(LLM_LOG_FILE, LLM_PREV_LOG_FILE)

class LessNoiseFilter(logging.Filter):
    def filter(self, record):
        noisy_loggers = ('litellm', 'openai', 'httpx', 'httpcore', 'asyncio', 'markdown_it', 'interpreter', 'urllib3')
        if record.name.startswith(noisy_loggers):
            if record.levelno < logging.INFO:
                return False
            
        msg = str(record.getMessage())
        if 'fake_key' in msg or 'invalid_api_key' in msg:
            return False
            
        noisy_strings = [
            'model_response.choices',
            'Using proactor:',
            'LiteLLM-Async Success Call',
            'LiteLLM-Success Call',
            'RAW RESPONSE:',
            'Received openai error',
            'entering code: StateBlock',
            'entering fence: StateBlock',
            'entering blockquote: StateBlock',
            'entering hr: StateBlock',
            'entering list: StateBlock',
            'entering reference: StateBlock',
            'entering html_block: StateBlock',
            'entering heading: StateBlock',
            'entering lheading: StateBlock',
            'entering paragraph: StateBlock'
        ]
        for s in noisy_strings:
            if s in msg:
                return False
        return True

file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
stream_handler = logging.StreamHandler()

noise_filter = LessNoiseFilter()
file_handler.addFilter(noise_filter)
stream_handler.addFilter(noise_filter)

# Configure logging to write to the file (resetting every run with mode='w')
# and also output to the console.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[file_handler, stream_handler]
)

# --- Dedicated polling logger ---
# Everything from the polling process (the drive-scanning loop and the GitHub
# update watcher) goes here -> pollingLog.log, and is kept OUT of dobLog.log via
# propagate=False. The console (stream_handler) still shows it so nothing is
# hidden during live runs.
polling_file_handler = logging.FileHandler(POLLING_LOG_FILE, mode='w', encoding='utf-8')
polling_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
polling_file_handler.addFilter(noise_filter)

plog = logging.getLogger("dobinator.polling")
plog.setLevel(logging.DEBUG)
plog.propagate = False
plog.addHandler(polling_file_handler)
plog.addHandler(stream_handler)

# --- Dedicated Open Interpreter runner logger ---
# The (very verbose) output of each Open Interpreter subprocess is captured by
# the LLM class and written here -> llmRunner.log, kept out of dobLog.log.
llm_file_handler = logging.FileHandler(LLM_LOG_FILE, mode='w', encoding='utf-8')
llm_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
llm_file_handler.addFilter(noise_filter)

llmlog = logging.getLogger("dobinator.llm")
llmlog.setLevel(logging.DEBUG)
llmlog.propagate = False
llmlog.addHandler(llm_file_handler)
llmlog.addHandler(stream_handler)

STATUS_FILE = os.path.join(PROJECT_ROOT, "srvr", "status.json")

class StatusManager:
    """Manages the status.json file for tracking program state."""
    def __init__(self, filepath):
        self.filepath = filepath
        # All read-modify-write sequences go through this lock because status.json
        # is now written from several threads (worker + drive-monitor loop).
        # RLock so methods that call each other (add_completed_drive ->
        # refresh_completed_drives) don't self-deadlock.
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

    def _read_data(self):
        data = {
            "StatusNumber": 0,
            "TotalBaseFiles": -1,
            "CompletedBaseFiles": -1,
            "TotalMainFiles": -1,
            "CompletedMainFiles": -1,
            "CompletedDrives": [],
            "BlankDrives": [],
            "PendingDrives": [],
            "UpdateAvailable": 0,
            "RebootRequired": 0,
            "Running": 1
        }
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data.update(json.load(f))
            except Exception as e:
                pass
        return data

    def _write_data(self, data):
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to write status to {self.filepath}: {e}")

    def update(self, status_number=None, total_base=None, comp_base=None, total_main=None, comp_main=None, running=None, completed_drives=None):
        with self._lock:
            data = self._read_data()

            if status_number is not None:
                data["StatusNumber"] = status_number
                if status_number == 0:
                    data["TotalBaseFiles"] = -1
                    data["CompletedBaseFiles"] = -1
                    data["TotalMainFiles"] = -1
                    data["CompletedMainFiles"] = -1

            if total_base is not None: data["TotalBaseFiles"] = total_base
            if comp_base is not None: data["CompletedBaseFiles"] = comp_base
            if total_main is not None: data["TotalMainFiles"] = total_main
            if comp_main is not None: data["CompletedMainFiles"] = comp_main
            if completed_drives is not None: data["CompletedDrives"] = completed_drives
            if running is not None: data["Running"] = running

            self._write_data(data)

    def set_update_available(self, available):
        """Flip the WebUI 'update available' indicator on or off."""
        with self._lock:
            data = self._read_data()
            new_val = 1 if available else 0
            if data.get("UpdateAvailable", 0) != new_val:
                data["UpdateAvailable"] = new_val
                self._write_data(data)

    def set_reboot_required(self, required):
        """Flip the WebUI 'this update needs a PC restart' indicator (red button)."""
        with self._lock:
            data = self._read_data()
            new_val = 1 if required else 0
            if data.get("RebootRequired", 0) != new_val:
                data["RebootRequired"] = new_val
                self._write_data(data)

    def set_drive_lists(self, blank_drives, pending_drives):
        """
        Publish the current blank-drive (awaiting user input) and pending-drive
        (queued, not yet started) lists to status.json for the WebUI.
        """
        with self._lock:
            data = self._read_data()
            data["BlankDrives"] = list(blank_drives)
            data["PendingDrives"] = list(pending_drives)
            self._write_data(data)

    def _load_recent_completed_drives(self, hours=24):
        """
        Read the permanent completedDrives.csv and return the entries that
        completed within the last `hours` hours, newest last. Each entry is a dict
        {name, issues, verified, missingImagery, timestamp} matching the WebUI.

        CSV columns: timestamp, name, issues(0/1), verified(0/1),
        missingImagery("|"-joined filenames). The verified and missingImagery
        columns are newer — rows without them (and drives that never run imagery
        verification, e.g. country drives) default to verified=True / [].
        """
        recent = []
        if not os.path.exists(COMPLETED_DRIVES_CSV):
            return recent
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
        try:
            with open(COMPLETED_DRIVES_CSV, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 2:
                        continue
                    ts_str, name = row[0].strip(), row[1]
                    issues = False
                    if len(row) >= 3:
                        issues = row[2].strip().lower() in ("1", "true", "yes")
                    # Default True for legacy 3-column rows so old history stays green.
                    verified = True
                    if len(row) >= 4:
                        verified = row[3].strip().lower() in ("1", "true", "yes")
                    missing_imagery = []
                    if len(row) >= 5 and row[4].strip():
                        missing_imagery = [m for m in row[4].split("|") if m.strip()]
                    try:
                        ts = datetime.datetime.fromisoformat(ts_str)
                    except ValueError:
                        continue
                    if ts >= cutoff:
                        recent.append({
                            "name": name, "issues": issues, "verified": verified,
                            "missingImagery": missing_imagery, "timestamp": ts_str,
                        })
        except Exception as e:
            logging.error(f"Failed to read {COMPLETED_DRIVES_CSV}: {e}")
        return recent

    def refresh_completed_drives(self):
        """Recompute the last-24h completed-drive list and store it in status.json."""
        with self._lock:
            recent = self._load_recent_completed_drives()
            data = self._read_data()
            data["CompletedDrives"] = recent
            self._write_data(data)

    def add_completed_drive(self, name, had_issues, verified=True, missing_imagery=None):
        """
        Permanently record a completed drive in completedDrives.csv (kept
        forever) and refresh the last-24h view exposed to the WebUI.

        Columns: timestamp, name, issues(0/1), verified(0/1),
        missingImagery("|"-joined filenames). `verified` is the imagery-verification
        outcome (packfiles drives); country/no-packfiles drives are recorded
        verified=True with no missing imagery. `missing_imagery` may be full
        "data\\imagery\\..." paths; only the filenames are stored for display.
        """
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        # Store just the filename (basename) of each missing entry — cleaner to show.
        basenames = []
        for entry in (missing_imagery or []):
            base = str(entry).replace("/", "\\").split("\\")[-1].strip()
            if base:
                basenames.append(base)
        try:
            os.makedirs(os.path.dirname(COMPLETED_DRIVES_CSV), exist_ok=True)
            with open(COMPLETED_DRIVES_CSV, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([ts, name, "1" if had_issues else "0",
                                 "1" if verified else "0", "|".join(basenames)])
            logging.info(
                f"Recorded completed drive '{name}' (issues={bool(had_issues)}, "
                f"verified={bool(verified)}, missing_imagery={len(basenames)}) at {ts}"
            )
        except Exception as e:
            logging.error(f"Failed to append to {COMPLETED_DRIVES_CSV}: {e}")
        self.refresh_completed_drives()

status_mgr = StatusManager(STATUS_FILE)


def sanitize_drive_name(name):
    """
    Normalize a user-entered drive name: strip leading/trailing whitespace and
    replace any internal run of whitespace with a single underscore. Mirrors the
    sanitization the WebUI does so the backend never trusts raw input.
    """
    return re.sub(r"\s+", "_", (name or "").strip())


def drive_size_tb(drive_path):
    """Total capacity of the drive rounded to the nearest (decimal) TB."""
    try:
        total = shutil.disk_usage(drive_path).total
        return int(round(total / 1_000_000_000_000))
    except Exception as e:
        logging.error(f"Failed to read size of {drive_path}: {e}")
        return 0


class DriveManager:
    """
    Thread-safe registry of drives the bot knows about but has not finished:

      * blank-awaiting — drives detected WITHOUT packfiles.txt that are waiting
        for the user to supply a Drive Name + Country in the WebUI. Each gets a
        unique `token` so the WebUI can serialize the popups even if a drive
        letter is later reused.
      * pending — jobs that have been queued for the worker but have not started
        yet (both packfiles drives and submitted country drives).

    Both lists are published to status.json (BlankDrives / PendingDrives) for the
    WebUI after every change.
    """

    def __init__(self, status_mgr):
        self.status_mgr = status_mgr
        self._lock = threading.Lock()
        self._blank = []      # [{token, disk, sizeTB, serial}]
        self._pending = []    # [job dicts]
        self._token_seq = 0

    def _publish(self):
        # Caller holds self._lock.
        blank_pub = [{"token": b["token"], "sizeTB": b["sizeTB"]} for b in self._blank]
        pending_pub = [{"name": j.get("name", ""), "sizeTB": j.get("sizeTB", 0)} for j in self._pending]
        self.status_mgr.set_drive_lists(blank_pub, pending_pub)

    # --- blank-awaiting drives (identified by physical disk number) ------------
    def add_blank(self, disk, size_tb, serial=""):
        with self._lock:
            # If this disk is already awaiting input, don't add a duplicate.
            if any(b["disk"] == disk for b in self._blank):
                return None
            self._token_seq += 1
            token = f"blk-{self._token_seq}-d{disk}"
            self._blank.append({"token": token, "disk": disk, "sizeTB": size_tb, "serial": serial})
            self._publish()
            plog.info(f"Blank disk #{disk} registered awaiting user input (token={token}).")
            return token

    def remove_blank_by_disk(self, disk):
        with self._lock:
            before = len(self._blank)
            self._blank = [b for b in self._blank if b["disk"] != disk]
            if len(self._blank) != before:
                self._publish()

    def pop_blank_by_token(self, token):
        with self._lock:
            match = next((b for b in self._blank if b["token"] == token), None)
            if match:
                self._blank = [b for b in self._blank if b["token"] != token]
                self._publish()
            return match

    # --- pending (queued) jobs -------------------------------------------------
    def add_pending(self, job):
        with self._lock:
            self._pending.append(job)
            self._publish()

    def start_job(self, job):
        """Mark a job as started (remove it from the pending list)."""
        with self._lock:
            before = len(self._pending)
            self._pending = [j for j in self._pending if j.get("disk") != job.get("disk")]
            if len(self._pending) != before:
                self._publish()

    def remove_pending_by_disk(self, disk):
        """Drop any queued (not-yet-started) job for a disk that was unplugged."""
        with self._lock:
            before = len(self._pending)
            self._pending = [j for j in self._pending if j.get("disk") != disk]
            if len(self._pending) != before:
                self._publish()

    def reset(self):
        """
        Clear all tracked drives and publish the empty lists. Called at startup so
        stale BlankDrives/PendingDrives left in status.json by a previous run (or a
        hard reboot) never resurrect a phantom popup. This honors the project's
        ephemeral-state rule: drive state resets completely every launch.
        """
        with self._lock:
            self._blank = []
            self._pending = []
            self._publish()


drive_manager = DriveManager(status_mgr)


class WorkVars:
    """Manages the workVars.csv file in the dobDir directory."""
    def __init__(self, filepath):
        self.filepath = filepath
        # Create the file with defaults if it doesn't exist
        if not os.path.exists(self.filepath):
            with open(self.filepath, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["VariableName", "Data"])
                writer.writerow(["Region", "X"])
            logging.info(f"Created new workVars file at {self.filepath}")
    
    def _read_all(self):
        with open(self.filepath, mode='r', newline='') as f:
            reader = csv.reader(f)
            return list(reader)
            
    def _write_all(self, rows):
        with open(self.filepath, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    def add_row(self, var_name, data):
        rows = self._read_all()
        rows.append([str(var_name), str(data)])
        self._write_all(rows)
        logging.debug(f"Added row to workVars: {var_name}, {data}")

    def remove_row(self, var_name=None, row_index=None):
        rows = self._read_all()
        if row_index is not None:
            if 0 <= row_index < len(rows):
                del rows[row_index]
                self._write_all(rows)
                logging.debug(f"Removed row {row_index} from workVars.")
        elif var_name is not None:
            # Keep rows that don't match the var_name
            new_rows = [r for r in rows if len(r) > 0 and r[0] != var_name]
            self._write_all(new_rows)
            logging.debug(f"Removed row(s) with VariableName {var_name} from workVars.")

    def _format_data(self, data_val):
        """Removes leading/trailing whitespace and converts to lowercase."""
        return str(data_val).strip().lower()

    def get_data_by_name(self, var_name):
        rows = self._read_all()
        for r in rows:
            if len(r) >= 2 and r[0] == var_name:
                return self._format_data(r[1])
        return None

    def get_data_by_row(self, row_index):
        rows = self._read_all()
        if 0 <= row_index < len(rows):
            r = rows[row_index]
            if len(r) >= 2:
                return self._format_data(r[1])
        return None


def _kill_process_tree(proc):
    """
    Kill a subprocess AND its descendants. Critical here because the Open
    Interpreter runner spawns a Jupyter kernel as a grandchild; killing only the
    runner would orphan the kernel. On Windows we use `taskkill /T`.
    """
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc.kill()
    except Exception as e:
        logging.error(f"Failed to kill LLM subprocess tree (pid={proc.pid}): {e}")
        try:
            proc.kill()
        except Exception:
            pass


# Hard ceiling for a single Open Interpreter run. Legitimate matchFiles runs can
# take ~15-20 minutes, so this is generous; it exists purely so a hung kernel can
# never freeze a drive build forever (the historical "Matching Specific Files"
# bug). It is a safety net — the subprocess isolation is what actually prevents
# the hang.
LLM_RUN_TIMEOUT_S = 2700  # 45 minutes


class LLM:
    """
    Interacts with a remote LLM via Open Interpreter, but runs every chat in its
    OWN SUBPROCESS (src/llm_runner.py) rather than in-process.

    This is deliberate: Open Interpreter relies on Jupyter/ipykernel + asyncio +
    signal handling, which only behave reliably on a process's MAIN thread. Since
    dobd.py processes drives on a background worker thread, running Open
    Interpreter inline there caused intermittent, permanent kernel hangs (the
    "Matching Specific Files" freeze). A subprocess gets a real main thread, full
    isolation (its own CWD and kernel), and — crucially — a boundary we can
    enforce a hard timeout on and kill if it ever exceeds it.

    Each instance is used for a single prompt, so no cross-call conversation
    state is lost by running one-shot subprocesses.
    """
    def __init__(self, ip_address="192.168.11.65", port=1234, working_directory=None,
                 model="openai/qwen/qwen3.6-27b", context_window=40000, api_key="fake_key",
                 max_tokens=4096, timeout=LLM_RUN_TIMEOUT_S):
        self.ip_address = ip_address
        self.port = port
        self.working_directory = working_directory
        self.model = model
        self.context_window = context_window
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.timeout = timeout
        logging.debug(
            f"LLM configured for model {self.model} at "
            f"http://{self.ip_address}:{self.port}/v1 (subprocess mode, timeout={self.timeout}s)"
        )

    def use(self, prompt):
        """Runs the prompt in the working directory set during initialization."""
        if not self.working_directory:
            logging.warning("No working directory set for LLM instance. Using current directory.")
            return self.useLoc(prompt, os.getcwd())
        return self.useLoc(prompt, self.working_directory)

    def useLoc(self, prompt, directory):
        """
        Run the prompt in `directory` by launching llm_runner.py as a subprocess.
        Returns the runner's exit code (0 = success), or None on failure/timeout.
        Side effects the callers rely on (files written by the LLM) land on the
        real filesystem exactly as before.
        """
        if not (directory and os.path.exists(directory)):
            logging.error(f"Directory {directory} does not exist. Cannot execute prompt.")
            return None

        runner = os.path.join(SCRIPT_DIR, "llm_runner.py")
        if not os.path.exists(runner):
            logging.error(f"llm_runner.py not found at {runner}; cannot run LLM.")
            return None

        cfg = {
            "ip_address": self.ip_address,
            "port": self.port,
            "model": self.model,
            "context_window": self.context_window,
            "api_key": self.api_key,
            "max_tokens": self.max_tokens,
            "working_directory": directory,
            "prompt": prompt,
        }

        cfg_fd, cfg_path = tempfile.mkstemp(prefix="dob_llm_", suffix=".json")
        try:
            with os.fdopen(cfg_fd, "w", encoding="utf-8") as f:
                json.dump(cfg, f)

            logging.info(f"LLM executing prompt in {directory} via subprocess (timeout={self.timeout}s).")
            llmlog.info("=" * 70)
            llmlog.info(f"LLM RUN START — model={self.model}  dir={directory}")
            llmlog.info(f"PROMPT: {prompt}")

            creationflags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
            proc = subprocess.Popen(
                [sys.executable, runner, cfg_path],
                cwd=directory,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )

            # Pump the child's output into the dedicated LLM log on a helper
            # thread so we keep full visibility without blocking the timeout.
            def _pump():
                try:
                    for line in proc.stdout:
                        llmlog.debug(line.rstrip("\n"))
                except Exception:
                    pass

            pump = threading.Thread(target=_pump, daemon=True)
            pump.start()

            try:
                proc.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                logging.error(
                    f"LLM subprocess exceeded the {self.timeout}s timeout — killing it. "
                    "This is the guard against the historical 'Matching Specific Files' hang."
                )
                llmlog.error(f"LLM RUN TIMED OUT after {self.timeout}s — killing subprocess tree.")
                _kill_process_tree(proc)
                try:
                    proc.wait(timeout=30)
                except Exception:
                    pass
                return None
            finally:
                pump.join(timeout=5)

            rc = proc.returncode
            if rc == 0:
                logging.info("LLM subprocess completed successfully.")
                llmlog.info("LLM RUN FINISHED OK.")
            else:
                logging.error(f"LLM subprocess exited with non-zero code {rc}.")
                llmlog.error(f"LLM RUN FINISHED WITH EXIT CODE {rc}.")
            return rc
        except Exception as e:
            logging.error(f"LLM subprocess execution failed: {e}", exc_info=True)
            return None
        finally:
            try:
                os.remove(cfg_path)
            except Exception:
                pass



def is_admin():
    """
    True if this process is running elevated (administrator). Disk formatting
    (Clear-Disk/Initialize-Disk/Format-Volume) and `shutdown /r` require this, so
    we log it loudly at startup to make a missing-elevation misconfiguration easy
    to diagnose.
    """
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def get_connected_drives():
    """Returns a set of connected drive letters (e.g., {'C:\\', 'D:\\'})."""
    drives = set()
    # GetLogicalDrives returns a bitmask of available drives (1 for A, 2 for B, 4 for C, etc.)
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            drives.add(f"{letter}:\\")
        bitmask >>= 1
    return drives

def get_volume_name(drive_path):
    """Returns the volume name of the given drive path using ctypes."""
    try:
        volume_name_buffer = ctypes.create_unicode_buffer(1024)
        result = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(drive_path),
            volume_name_buffer,
            ctypes.sizeof(volume_name_buffer),
            None, None, None, None, 0
        )
        if result != 0:
            vol_name = volume_name_buffer.value
            if vol_name:
                return vol_name
    except Exception as e:
        logging.error(f"Error getting volume name for {drive_path}: {e}")
    
    # Fallback to drive letter (e.g. "Drive D")
    return f"Drive {drive_path[0]}"

def eject_drive(drive_path):
    """Force ejects the drive using PowerShell."""
    try:
        drive_letter = drive_path[:2] # e.g. "D:"
        cmd = [
            "powershell",
            "-NoProfile",
            "-WindowStyle", "Hidden",
            "-Command",
            f"$driveEject = New-Object -comObject Shell.Application; $driveEject.Namespace(17).ParseName('{drive_letter}').InvokeVerb('Eject')"
        ]
        # creationflags=0x08000000 prevents a window from popping up
        subprocess.run(cmd, creationflags=0x08000000, check=False)
        logging.info(f"Successfully requested Windows to eject {drive_letter}")
    except Exception as e:
        logging.error(f"Failed to eject {drive_path}: {e}")

def classifyRegion(llm_instance, drive_path, work_vars):
    """
    Uses the provided LLM instance to classify the region of the drive.
    The LLM has access to the drive and is instructed to update the Region variable 
    in the dobDir/workVars.csv file based on its findings.
    """
    status_mgr.update(status_number=2)
    logging.info("--- Starting Region Classification ---")
    
    # Read the current region value and log it before the LLM runs
    region_before = work_vars.get_data_by_name("Region")
    logging.info(f"Region BEFORE LLM processing: {region_before}")
    
    # ========================================================================
    # LLM PROMPT FOR REGION CLASSIFICATION
    # ========================================================================
    # Type your prompt for the LLM here. 
    # The LLM will run with 'drive_path' as its working directory.
    prompt = (
        "Look at the packfiles.txt file in this folder and determine the region it belongs to (US or International). Once determined, rename packfiles.txt to either packfiles-I.txt (for international) or packfiles-U.txt (for US). "
    )
    # ========================================================================
    
    logging.info(f"Sending prompt to LLM: '{prompt}'")
    llm_instance.useLoc(prompt, drive_path)
    
    # Check for renamed files and process accordingly
    packfiles_u_path = os.path.join(drive_path, "packfiles-U.txt")
    packfiles_i_path = os.path.join(drive_path, "packfiles-I.txt")
    original_packfiles_path = os.path.join(drive_path, "packfiles.txt")
    
    region_determined = None
    if os.path.exists(packfiles_u_path):
        region_determined = "U"
        os.rename(packfiles_u_path, original_packfiles_path)
    elif os.path.exists(packfiles_i_path):
        region_determined = "I"
        os.rename(packfiles_i_path, original_packfiles_path)
        
    if region_determined:
        logging.info(f"LLM successfully renamed packfiles. Region is: {region_determined}")
        work_vars.remove_row("Region")
        work_vars.add_row("Region", region_determined)
    else:
        logging.warning("LLM failed to rename packfiles.txt to indicate region.")
    
    # Read the region value again to log the result
    region_after = work_vars.get_data_by_name("Region")
    logging.info(f"Region AFTER LLM processing: {region_after}")
    logging.info("--- Finished Region Classification ---")

def copy_region_files(drive_path, work_vars, status_number=3):
    """
    Copies the appropriate base files to the drive based on the identified region.

    `status_number` lets callers reflect the WebUI step: both the full build
    (process_drive) and the country-drive build (process_country_drive) report
    step 3 ("Copying Base Files") here.
    """
    status_mgr.update(status_number=status_number)
    logging.info("--- Starting File Copy Process ---")
    region = work_vars.get_data_by_name("Region")
    
    if not region or region == "x":
        logging.error("Region not properly identified. Cannot proceed with file copying.")
        return

    commands = []
    
    if region == "u":
        commands = [
            ["robocopy", r"U:\ARS\Data\vector\Baseline\_all_installs", os.path.join(drive_path, r"ARS\data\vector")],
            ["robocopy", r"U:\ARS\Data\vector\Baseline\usa", os.path.join(drive_path, r"ARS\data\vector")],
            ["robocopy", r"G:\Shared drives\ARS\bin", os.path.join(drive_path, r"ARS\bin"), "/e"],
            ["robocopy", r"G:\Shared drives\ARS\data", os.path.join(drive_path, r"ARS\data"), "/e"],
            ["robocopy", r"U:\ARS\Data\imagery\usa", os.path.join(drive_path, r"ARS\data\imagery"), "usa_faa*"],
            ["robocopy", r"U:\ARS\Data\imagery\GLOBAL", os.path.join(drive_path, r"ARS\data\imagery"), "BlueMarble.esp"],
            ["robocopy", r"U:\ARS\Data\imagery\GLOBAL", os.path.join(drive_path, r"ARS\data\imagery"), "HYP_HR_SR_W_DR.esp"],
            ["robocopy", r"U:\ARS\Data\imagery\usa", os.path.join(drive_path, r"ARS\data\imagery"), "terrain_usa_CONUS*.esp"],
            ["robocopy", r"U:\ARS\Data\imagery\GLOBAL", os.path.join(drive_path, r"ARS\data\imagery"), "terrain_Global_SRTM3_90M.esp"],
            ["robocopy", r"U:\ARS\Data\imagery\usa", os.path.join(drive_path, r"ARS\data\imagery"), "usgs_drg.esp"],
            ["robocopy", r"U:\ARS\Data\geocode\usa", os.path.join(drive_path, r"ARS\Data\geocode\usa")],
            ["robocopy", r"U:\ARS\Data\geocode\__global", os.path.join(drive_path, r"ARS\Data\geocode\__global")],
            ["robocopy", r"U:\ARS\Data\Geocoders", os.path.join(drive_path, r"ARS\Data\Geocoders")]
        ]
    elif region == "i":
        commands = [
            ["robocopy", r"U:\ARS\Data\vector\Baseline\_all_installs", os.path.join(drive_path, r"ARS\data\vector")],
            ["robocopy", r"G:\Shared drives\ARS\bin", os.path.join(drive_path, r"ARS\bin"), "/e"],
            ["robocopy", r"G:\Shared drives\ARS\data", os.path.join(drive_path, r"ARS\data"), "/e"],
            ["robocopy", r"U:\ARS\Data\imagery\GLOBAL", os.path.join(drive_path, r"ARS\data\imagery"), "BlueMarble.esp"],
            ["robocopy", r"U:\ARS\Data\imagery\GLOBAL", os.path.join(drive_path, r"ARS\data\imagery"), "HYP_HR_SR_W_DR.esp"],
            ["robocopy", r"U:\ARS\Data\imagery\GLOBAL", os.path.join(drive_path, r"ARS\data\imagery"), "terrain_Global_SRTM3_90M.esp"],
            ["robocopy", r"U:\ARS\Data\geocode\__global", os.path.join(drive_path, r"ARS\data\geocode\__global")],
            ["robocopy", r"U:\ARS\Data\geocoders", os.path.join(drive_path, r"ARS\data\geocoders")]
        ]
    else:
        logging.warning(f"Unknown region '{region}', unable to copy files.")
        return

    logging.info(f"Starting file copy for region '{region}' to drive {drive_path}")

    # Generate a reference batch file in dobDir
    dobdir_path = os.path.join(drive_path, "dobDir")
    bat_file_path = os.path.join(dobdir_path, "copy_files.bat")
    try:
        with open(bat_file_path, "w") as f:
            for cmd in commands:
                quoted_cmd = []
                for arg in cmd:
                    if " " in arg:
                        quoted_cmd.append(f'"{arg}"')
                    else:
                        quoted_cmd.append(arg)
                f.write(" ".join(quoted_cmd) + "\n")
            f.write("pause\n")
        logging.debug(f"Created reference batch file at {bat_file_path}")
    except Exception as e:
        logging.error(f"Failed to create temporary batch file {bat_file_path}: {e}")

    totalBaseFiles = len(commands)
    completedBaseFiles = 0
    status_mgr.update(total_base=totalBaseFiles, comp_base=0)
    logging.info(f"Total base items to copy (totalBaseFiles): {totalBaseFiles}")

    for cmd in commands:
        cmd_str = " ".join(cmd)
        logging.info(f"Running command: {cmd_str}")
        try:
            # 0x08000000 is CREATE_NO_WINDOW
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
            if result.returncode >= 8:
                logging.error(f"Robocopy failed with exit code {result.returncode}: {result.stderr or result.stdout}")
            else:
                completedBaseFiles += 1
                status_mgr.update(comp_base=completedBaseFiles)
                logging.info(f"Robocopy completed with exit code {result.returncode}. Completed: {completedBaseFiles}/{totalBaseFiles}")
        except Exception as e:
            logging.error(f"Failed to execute robocopy command: {e}")

    logging.info(f"--- Finished File Copy Process. Successfully copied {completedBaseFiles} out of {totalBaseFiles} items. ---")

# Source locations on the U drive for the country-specific file sets.
COUNTRY_IMAGERY_SRC = r"U:\ARS\Data\imagery\GLOBAL\COUNTRIES"
COUNTRY_VECTOR_SRC  = r"U:\ARS\Data\vector\Baseline"
COUNTRY_GEOCODE_SRC = r"U:\ARS\Data\geocode"

def copy_country_files(drive_path, iso):
    """
    Copies the three country-specific data sets for a non-US country drive,
    keyed purely off the ISO Alpha-3 code (no LLM involved). Reports WebUI
    step 8 ("Copying Country Files") and drives the progress bar via the
    "main file" counters (TotalMainFiles/CompletedMainFiles), which country
    drives do not otherwise use.

    The three sets (DRIVE = the working drive root):
      1. Imagery file(s)  U:\\ARS\\Data\\imagery\\GLOBAL\\COUNTRIES\\<iso>_*.esp
                          ->  DRIVE\\ARS\\data\\imagery\\
      2. Vector contents  U:\\ARS\\Data\\vector\\Baseline\\<iso>\\*
                          ->  DRIVE\\ARS\\data\\vector  (contents, NOT a \\<iso> subfolder)
      3. Geocode folder   U:\\ARS\\Data\\geocode\\<iso>
                          ->  DRIVE\\ARS\\data\\geocode\\<iso>
    """
    status_mgr.update(status_number=8)
    iso_l = iso.lower()
    logging.info(f"--- Starting Country-Specific File Copy for '{iso_l}' ---")

    imagery_dst = os.path.join(drive_path, "ARS", "data", "imagery")
    vector_dst  = os.path.join(drive_path, "ARS", "data", "vector")
    geocode_dst = os.path.join(drive_path, "ARS", "data", "geocode")
    for d in (imagery_dst, vector_dst, geocode_dst):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception as e:
            logging.error(f"Failed to create destination folder {d}: {e}")

    commands = []

    # 1. Imagery: copy every file in the COUNTRIES folder whose name starts with
    #    "<iso>_" (e.g. can_s2_2021_10m.esp for Canada). Matched by code alone.
    if os.path.isdir(COUNTRY_IMAGERY_SRC):
        try:
            for fn in os.listdir(COUNTRY_IMAGERY_SRC):
                if fn.lower().startswith(iso_l + "_"):
                    commands.append(["robocopy", COUNTRY_IMAGERY_SRC, imagery_dst, fn])
        except Exception as e:
            logging.error(f"Failed to list imagery source {COUNTRY_IMAGERY_SRC}: {e}")
        if not any(c[1] == COUNTRY_IMAGERY_SRC for c in commands):
            logging.warning(f"No imagery file found in {COUNTRY_IMAGERY_SRC} starting with '{iso_l}_'.")
    else:
        logging.error(f"Imagery COUNTRIES source not found: {COUNTRY_IMAGERY_SRC}")

    # 2. Vector: copy the CONTENTS of U:\ARS\Data\vector\Baseline\<iso> directly
    #    into DRIVE\ARS\data\vector (NOT into a \<iso> subfolder). robocopy copies
    #    the contents of the source dir into the dest dir, so omitting the <iso>
    #    component lands the files at ...\data\vector\[files].
    vec_src = os.path.join(COUNTRY_VECTOR_SRC, iso_l)
    commands.append(["robocopy", vec_src, vector_dst, "/e"])

    # 3. Geocode folder: U:\ARS\Data\geocode\<iso> -> DRIVE\ARS\data\geocode\<iso>
    geo_src = os.path.join(COUNTRY_GEOCODE_SRC, iso_l)
    commands.append(["robocopy", geo_src, os.path.join(geocode_dst, iso_l), "/e"])

    totalMainFiles = len(commands)
    completedMainFiles = 0
    status_mgr.update(total_main=totalMainFiles, comp_main=0)
    logging.info(f"Total country-specific items to copy (totalMainFiles): {totalMainFiles}")

    for cmd in commands:
        cmd_str = " ".join([f'"{x}"' if " " in x else x for x in cmd])
        logging.info(f"Running command: {cmd_str}")
        try:
            # 0x08000000 is CREATE_NO_WINDOW
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
            if result.returncode >= 8:
                logging.error(f"Robocopy failed with exit code {result.returncode}: {result.stderr or result.stdout}")
            else:
                completedMainFiles += 1
                status_mgr.update(comp_main=completedMainFiles)
                logging.info(f"Robocopy completed with exit code {result.returncode}. Completed: {completedMainFiles}/{totalMainFiles}")
        except Exception as e:
            logging.error(f"Failed to execute robocopy command: {e}")

    logging.info(f"--- Finished Country-Specific File Copy. Copied {completedMainFiles} of {totalMainFiles} items. ---")

# Source location of the airport archive on the U drive.
AIRPORT_ZIP_SOURCE = r"U:\ARS\Data\airport\airport.zip"

def copy_airport(drive_path, source_zip=AIRPORT_ZIP_SOURCE):
    """
    Copies airport.zip from the U drive into the target drive's ARS\\data folder,
    extracts its contents into a new 'airport' subfolder, then deletes the copied
    zip so that only its extracted contents remain.
    """
    status_mgr.update(status_number=7)
    logging.info("--- Starting copy_airport Process ---")

    # The ARS\data folder is expected to already exist (created by copy_region_files).
    data_dir = os.path.join(drive_path, "ARS", "data")
    dest_zip = os.path.join(data_dir, "airport.zip")
    airport_dir = os.path.join(data_dir, "airport")

    logging.debug(f"copy_airport source zip: {source_zip}")
    logging.debug(f"copy_airport destination data dir: {data_dir}")
    logging.debug(f"copy_airport destination zip: {dest_zip}")
    logging.debug(f"copy_airport extraction dir: {airport_dir}")

    if not os.path.exists(source_zip):
        logging.error(f"Airport source zip not found at {source_zip}. Skipping copy_airport.")
        return

    if not os.path.isdir(data_dir):
        logging.error(f"Destination data folder does not exist at {data_dir}. Skipping copy_airport.")
        return

    # 1. Copy the zip from U: to the drive's ARS\data folder.
    try:
        logging.info(f"Copying airport.zip from {source_zip} to {dest_zip}")
        shutil.copy2(source_zip, dest_zip)
        logging.info(f"SUCCESS: Copied airport.zip to {dest_zip}")
    except Exception as e:
        logging.error(f"FAILED to copy airport.zip from {source_zip} to {dest_zip}: {e}")
        return

    # 2. Unzip its contents into a new 'airport' folder.
    try:
        logging.info(f"Extracting {dest_zip} into {airport_dir}")
        os.makedirs(airport_dir, exist_ok=True)
        with zipfile.ZipFile(dest_zip, 'r') as zf:
            zf.extractall(airport_dir)
        logging.info(f"SUCCESS: Extracted airport.zip into {airport_dir}")
    except Exception as e:
        logging.error(f"FAILED to extract {dest_zip} into {airport_dir}: {e}")
        return

    # 3. Delete the copied zip, leaving only its extracted contents behind.
    try:
        os.remove(dest_zip)
        logging.info(f"SUCCESS: Deleted {dest_zip}, leaving contents in {airport_dir}")
    except Exception as e:
        logging.error(f"FAILED to delete {dest_zip}: {e}")

    logging.info("--- Finished copy_airport Process ---")

# The instructions handed to the matchFiles LLM. Pulled out to a module-level
# constant so the imagery-verification fix_loop can quote it verbatim as the
# "previous agent's prompt" when asking a corrective LLM to recover misses.
MATCH_FILES_PROMPT = (
        "You are currently on the root of a drive that has some data on it, but needs even more. "
        "Currently, it has a file called packfiles.txt, a dobDir folder, and an ARS folder. "
        "In that ARS folder is another subfolder called data. In that data folder are a variety "
        "of folders with different types of data in them.\n\n"
        "In packfiles.txt all of the data files are listed out with their paths relative to the data "
        "folder (in the ARS folder). Some are already on this drive (for example "
        "\"data\\imagery\\BlueMarble.esp\" is already on this drive under \"ARS\\data...\". "
        "The rest of the files that are not yet on this drive can be found in the subfolders of the U "
        "drive at \"U:\\ARS\\Data\\...\". Matching them up is a bit more complicated than it may seem, "
        "however, because the folder structure on U does not match where those files will end up on this "
        "drive. Additionally, the files can be renamed slightly from what they were called before when "
        "this packfiles.txt document was made.\n\n"
        "Your goal, is to create a new csv file in dobDir called \"mapping.csv\" that has both the source "
        "paths of all of the remaining files, as well as the destination paths of all of these files. "
        "There should be no header or title rows or columns but only the matched pairs of the source and "
        "destination paths.\n\n"
        "For example, if this is listed in packfiles.txt: "
        "data\\vector\\n_can-on-ottawa_police_neighborhoods_polygons_t_polygon_c_20250728.esp\n"
        "You would need a row in the csv like this:\n"
        "U:\\ARS\\Data\\vector\\LIMITED_DISTRIBUTION\\can-on_OttawaPolice\\n_can-on-ottawa_police_neighborhoods_polygons_t_polygon_c_20250728.esp, D:ARS\\data\\vector\\n_can-on-ottawa_police_neighborhoods_polygons_t_polygon_c_20250728.esp\n\n"
        "Additionally, for another example, if you saw this listed in packfiles.txt: "
        "data\\geocode\\can\\can2025_06_mn_pd_ph_2025-08-29.voc\n"
        "You may need a row in the csv that looks like this:\n"
        "U:\\ARS\\Data\\geocode\\can\\can2025_12_mn_pd_ph_2026-02-17.voc, D:ARS\\data\\geocode\\can\\can2025_12_mn_pd_ph_2026-02-17.voc\n"
        "Note that even though the date in the packfiles list is older, we found the newer date and listed "
        "it exactly as is to be transferred since we will want this newer data set (keep the new name).\n\n"
        "Finally, something to note is that for geocode, you are generally looking for a whole folder of "
        "data to copy over from the U drive. For example, for a canada drive, we might see multiple things "
        "in packfiles listed starting with \"data\\geocode\\can\\...\". You can then quickly check if "
        "everything under \"U:\\ARS\\Data\\geocode\\can\\...\" generally matches (except for dates and such), "
        "and just copy that whole directory over.\n\n"
        "ALSO NOTE! This csv will be fed into a python script that will run robocopy on it. Make sure the "
        "names are exactly right and that there is no fluff. Things must be perfectly formatted such that "
        "python can interpret this list and robocopy the files. Also note that robocopy supports directories "
        "if applicable (see previous note).\n\n"
        "Final Note: All of the files that you are looking for are in one of three subfolders of \"U:\\ARS\\Data\\...\". Namely the imagery, geocode, and vector folders. There is no need to look in any other folders such as imagery_old, imagery_stage, vector_old, etc. Don't look in these folders.\n\n"
        "SAFETY WARNING: The U drive you should treat as READ ONLY. Do not make any files here, even temporary files. You are just reading information from it.\n\n"
        "CRITICAL: MAKE ABSOLUTE SURE THAT YOU FIND ALL FILES IN PACKFILES IN IMAGERY, VECTORS, AND GEOCODE!"
)


def matchFiles(drive_path):
    """
    Instructs the AI on how to actually find the rest of the files.
    Creates a new LLM instance with the working directory on the root of the processing drive.
    """
    status_mgr.update(status_number=4)
    logging.info("--- Starting matchFiles Process ---")

    # Create a new LLM object with its working directory on the root of the drive
    match_llm = LLM(working_directory=drive_path)

    prompt = MATCH_FILES_PROMPT
    logging.info(f"Sending prompt to LLM in matchFiles: '{prompt}'")
    match_llm.use(prompt)

    logging.info("--- Finished FIRST pass of matchFiles Process ---")

    # ========================================================================
    # SECOND PASS: VERIFICATION LLM
    # ========================================================================
    # Spin up a fresh LLM instance (no shared conversation history) in the root
    # of the drive to double-check the mapping.csv produced above and fix any
    # files the first agent missed. Declared with the full constructor signature
    # (model spelled out explicitly so it is easy to swap later) and given a
    # larger 100000 context window so it can reason over packfiles.txt and the
    # full mapping.csv at once.
    verify_llm = LLM(
        ip_address="192.168.11.65",
        port=1234,
        working_directory=drive_path,
        model="openai/qwen/qwen3.6-27b",
        context_window=100000,
        api_key="fake_key",
        max_tokens=4096
    )

    verify_prompt = (
        "An AI agent, much like you, was just run on this drive with this as its prompt and goal:\n\n"
        "-------------------- PREVIOUS AGENT'S PROMPT --------------------\n"
        f"{prompt}\n"
        "-----------------------------------------------------------------\n\n"
        "It supposedly completed this goal and everything should be in the csv it created "
        "(dobDir\\mapping.csv), but I am skeptical that it got all of the files. For example, "
        "just the other day I ran it on a packfile that contained these files in imagery:\n\n"
        "data\\imagery\\BlueMarble.esp\n"
        "data\\imagery\\HYP_HR_SR_W_DR.esp\n"
        "data\\imagery\\terrain_Global_SRTM3_90M.esp\n"
        "data\\imagery\\terrain_usa-nm_2007-2022_1m-10m.esp\n"
        "data\\imagery\\terrain_usa_conus_2024_10m.esp\n"
        "data\\imagery\\usa-az_naip_small_2023_31cm.esp\n"
        "data\\imagery\\usa-co_naip_small_2023_31cm.esp\n"
        "data\\imagery\\usa-nm-bernalillocounty_2021_15cm.esp\n"
        "data\\imagery\\usa-nm_2022_61cm.esp\n"
        "data\\imagery\\usa-ok_naip_small_2023_31cm.esp\n"
        "data\\imagery\\usa-tx_naip_small_2023_61cm.esp\n"
        "data\\imagery\\usa-ut_naip_small_2023_61cm.esp\n"
        "data\\imagery\\usa_faa_ifr_enr_gom_vertical_flight_ref_2025-04-17_37m.esp\n"
        "data\\imagery\\usa_faa_ifr_enr_high_2025-04-17_143m.esp\n"
        "data\\imagery\\usa_faa_ifr_enr_hi_pacific_2025-04-17_442m.esp\n"
        "data\\imagery\\usa_faa_ifr_enr_low_area_2025-04-17_92m.esp\n"
        "data\\imagery\\usa_faa_vfr_caribbean_2025-04-17_86m.esp\n"
        "data\\imagery\\usa_faa_vfr_flyways_2025-04-17_21m.esp\n"
        "data\\imagery\\usa_faa_vfr_grand_canyon_2025-04-17_21m.esp\n"
        "data\\imagery\\usa_faa_vfr_heli_2025-04-17_14m.esp\n"
        "data\\imagery\\usa_faa_vfr_sectionals_2025-04-17_47m.esp\n"
        "data\\imagery\\usa_faa_vfr_tac_2025-04-17_21m.esp\n"
        "data\\imagery\\usgs_drg.esp\n\n"
        "But after it completed, I ran ls on the imagery folder and saw only these files in it:\n\n"
        "Mode                 LastWriteTime         Length Name\n"
        "----                 -------------         ------ ----\n"
        "------         11/8/2019   4:37 PM      282272404 BlueMarble.esp\n"
        "------         11/8/2019   4:38 PM      282272416 HYP_HR_SR_W_DR.esp\n"
        "------         8/12/2021   3:44 PM    17080963648 terrain_Global_SRTM3_90M.esp\n"
        "------         2/19/2024   4:29 PM    67152599684 terrain_usa_conus_2024_10m.esp\n"
        "-a----         5/29/2026  11:18 AM      438251640 usa_faa_ifr_enr_high_2026-06-11_143m.esp\n"
        "-a----         5/29/2026  11:20 AM       54557972 usa_faa_ifr_enr_hi_pacific_2026-06-11_442m.esp\n"
        "-a----         5/29/2026  11:09 AM     1110090000 usa_faa_ifr_enr_low_area_2026-06-11_92m.esp\n"
        "-a----         5/25/2026  10:52 AM       57525852 usa_faa_vfr_caribbean_2026-06-11_86m.esp\n"
        "-a----         5/25/2026  10:30 AM      200103400 usa_faa_vfr_flyways_2026-06-11_21m.esp\n"
        "-a----         5/25/2026  10:52 AM       19531628 usa_faa_vfr_grand_canyon_2026-06-11_21m.esp\n"
        "-a----         5/25/2026  10:52 AM      279645984 usa_faa_vfr_heli_2026-06-11_14m.esp\n"
        "-a----         5/25/2026  10:48 AM     3173666076 usa_faa_vfr_sectionals_2026-06-11_47m.esp\n"
        "-a----         5/25/2026  10:29 AM      627613088 usa_faa_vfr_tac_2026-06-11_21m.esp\n"
        "------         9/30/2022   3:43 PM   156704702732 usgs_drg.esp\n\n"
        "With several obviously and notably missing. For example "
        "data\\imagery\\usa-nm_2022_61cm.esp is not on the drive. This file should have been added "
        "to the csv, with its pairing in U drive actually found at "
        "U:\\ARS\\Data\\imagery\\usa\\usa-nm_naip_2024_30cm.esp (note the different name). Another "
        "example of this is the file data\\imagery\\usa-nm-bernalillocounty_2021_15cm.esp which "
        "should have had its pairing matched from U drive as "
        "U:\\ARS\\Data\\imagery\\usa\\usa-nm-bernalillocounty_2021_15cm.esp (note despite the same "
        "name how it still wasn't added to the CSV).\n\n"
        "Given all of this, your task is to slowly, carefully, with extreme precision find any "
        "errors that the initial agent could have caused and correct them. Read the initial prompt "
        "carefully so you don't make any errors. You can start by just looking at packfiles.txt and "
        "the mapping.csv that the previous agent made and making sure that everything from packfile "
        "is in the csv. Try as hard as you can to get this perfect. It matters a lot to me that you "
        "do this right and you have to nail it! PLEASE!!!"
    )
    logging.info(f"Sending verification prompt to second LLM in matchFiles: '{verify_prompt}'")
    verify_llm.use(verify_prompt)

    logging.info("--- Finished matchFiles Process ---")

def _copy_from_mapping(drive_path, mapping_csv, status_number=5, issues_filename="ISSUES.txt"):
    """
    Core robocopy routine shared by mainCopy and the imagery-verification fix_loop.

    Reads `mapping_csv` (rows of "source,destination"), copies each entry with
    robocopy, and tracks progress through the main-file status counters
    (TotalMainFiles/CompletedMainFiles) under `status_number`. When
    `issues_filename` is given, any errors are written to dobDir\\<issues_filename>;
    pass None to skip writing an issues file (fix_loop runs don't want to clobber
    or re-trigger the ISSUES flow). Returns the list of errors encountered.
    """
    status_mgr.update(status_number=status_number)
    dobdir_path = os.path.join(drive_path, "dobDir")
    errors_encountered = []

    if not os.path.exists(mapping_csv):
        logging.error(f"Mapping CSV not found at {mapping_csv}. Nothing to copy.")
        return errors_encountered

    try:
        with open(mapping_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Remove empty rows and keep only those with at least source and destination
            rows = [row for row in reader if row and len(row) >= 2]
    except Exception as e:
        logging.error(f"Failed to read {mapping_csv}: {e}")
        return errors_encountered

    totalMainFiles = len(rows)
    completedMainFiles = 0
    status_mgr.update(total_main=totalMainFiles, comp_main=0)

    logging.info(f"Total items to copy from {os.path.basename(mapping_csv)} (totalMainFiles): {totalMainFiles}")

    for row in rows:
        source_path = row[0].strip()
        dest_path = row[1].strip()

        logging.debug(f"Processing copy from {source_path} to {dest_path}")

        if not os.path.exists(source_path):
            error_msg = f"Source path does not exist: {source_path}"
            logging.error(error_msg)
            errors_encountered.append(f"{error_msg} (Destination was: {dest_path})")
            continue

        cmd = []
        if os.path.isdir(source_path):
            # If it's a directory, use the /E flag for recursive copy
            cmd = ["robocopy", source_path, dest_path, "/e"]
        else:
            # If it's a file, split into dir and filename for robocopy
            source_dir = os.path.dirname(source_path)
            dest_dir = os.path.dirname(dest_path)
            filename = os.path.basename(source_path)
            cmd = ["robocopy", source_dir, dest_dir, filename]

        cmd_str = " ".join([f'"{x}"' if ' ' in x else x for x in cmd])
        logging.info(f"Running command: {cmd_str}")

        try:
            # 0x08000000 is CREATE_NO_WINDOW
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
            if result.returncode >= 8:
                error_msg = f"Robocopy failed for {source_path} with exit code {result.returncode}: {result.stderr or result.stdout}"
                logging.error(error_msg)
                errors_encountered.append(error_msg)
            else:
                completedMainFiles += 1
                status_mgr.update(comp_main=completedMainFiles)
                logging.debug(f"Successfully copied {source_path}. Completed: {completedMainFiles}/{totalMainFiles}")
        except Exception as e:
            error_msg = f"Exception occurred while trying to copy {source_path}: {e}"
            logging.error(error_msg)
            errors_encountered.append(error_msg)

    logging.info(f"Copy from {os.path.basename(mapping_csv)} completed. Copied {completedMainFiles} of {totalMainFiles} items.")

    if errors_encountered and issues_filename:
        issues_path = os.path.join(dobdir_path, issues_filename)
        logging.warning(f"Writing {len(errors_encountered)} errors to {issues_path}")
        try:
            with open(issues_path, 'w', encoding='utf-8') as f:
                f.write(f"Errors encountered during copy on {time.strftime('%Y-%m-%d %H:%M:%S')}:\n")
                f.write("-" * 50 + "\n")
                for err in errors_encountered:
                    f.write(err + "\n")
        except Exception as e:
            logging.error(f"Failed to write to {issues_path}: {e}")

    return errors_encountered


def mainCopy(drive_path):
    """
    Reads the mapping.csv created by matchFiles and copies the files using robocopy.
    Tracks total and completed files, and logs any errors to ISSUES.txt.
    """
    logging.info("--- Starting mainCopy Process ---")
    mapping_csv = os.path.join(drive_path, "dobDir", "mapping.csv")
    _copy_from_mapping(drive_path, mapping_csv, status_number=5, issues_filename="ISSUES.txt")
    logging.info("--- Finished mainCopy Process ---")

def summarizeIssues(drive_path):
    """
    Summarizes the issues logged in ISSUES.txt using the LLM.
    Moves the resulting ISSUES.md to the root of the drive.
    """
    status_mgr.update(status_number=6)
    logging.info("--- Starting summarizeIssues Process ---")
    dobdir_path = os.path.join(drive_path, "dobDir")
    issues_txt = os.path.join(dobdir_path, "ISSUES.txt")
    
    if not os.path.exists(issues_txt):
        logging.info("No ISSUES.txt found to summarize.")
        return
        
    summary_llm = LLM(working_directory=dobdir_path)
    
    prompt = (
        "You are being run in a folder that contains a file called ISSUES.txt. "
        "This file is a verbose log of issues encountered during the automated copying of files by a program called \"The Dobinator\". "
        "Your task is to read through this log and then summarize the issues in human readable text. "
        "The goal is to have a few short sentences describing what happened (what wasn't copied, etc). "
        "If certain files weren't copied, they should all be listed too. "
        "The goal is for someone to be able to easily read this and clean up the issues by hand. "
        "This summary should always start with\n\n"
        "Hello from The Dobinator, I seem to have encountered some issues while building this data drive. :(\n"
        "The issue was/The issues were...\n\n"
        "The summary should also all be in the first person as The Dobinator. "
        "This summary should be saved and formatted into a file in this folder called \"ISSUES.md\"."
    )
    
    logging.info("Sending prompt to LLM to summarize issues...")
    summary_llm.use(prompt)
    
    # After prompt, move ISSUES.md to root of the drive
    issues_md = os.path.join(dobdir_path, "ISSUES.md")
    root_issues_md = os.path.join(drive_path, "ISSUES.md")
    
    if os.path.exists(issues_md):
        try:
            # Overwrite if it already exists on the root
            if os.path.exists(root_issues_md):
                os.remove(root_issues_md)
            shutil.move(issues_md, root_issues_md)
            logging.info(f"Successfully moved ISSUES.md to {root_issues_md}")
        except Exception as e:
            logging.error(f"Failed to move ISSUES.md to root: {e}")
    else:
        logging.warning("LLM did not create ISSUES.md as requested.")
        
    logging.info("--- Finished summarizeIssues Process ---")

# ---------------------------------------------------------------------------
# Imagery verification (packfiles drives only)
# ---------------------------------------------------------------------------
# After the main build, a drive that arrived WITH a packfiles.txt is verified by
# having ARS regenerate packfiles (which lists what is actually on the drive) and
# confirming every imagery file the ORIGINAL packfiles.txt asked for is present.
# If some are missing, an LLM is given the misses and asked to produce a
# corrective mapping CSV, which is copied; this repeats up to FIX_LOOP_MAX_RUNS
# times before the drive is finally recorded as completed-but-not-verified.

# ARS regenerates packfiles.txt into its bin folder; the maintenance batch on the
# target drive launches the ARS program, which we kill after a short settle so the
# generated file is flushed and ARS is not left running.
ARS_PROCESS_NAMES = ("ars.exe",)
ARS_SETTLE_SECONDS = 25
FIX_LOOP_MAX_RUNS = 5
# Lines in a packfile that describe an imagery file start with this prefix.
IMAGERY_PREFIX = "data\\imagery\\"

# dobDir signal files exchanged between the verification steps and the LLMs:
#  * missedImagery.txt  — written by the imagery JUDGE; the precise list of
#                         imagery files still missing from the drive (the exact
#                         targets handed to the corrective LLM).
#  * couldNotFind.txt   — written by the corrective LLM; imagery files it
#                         confirmed are genuinely absent from the U drive.
MISSED_IMAGERY_FILE = "missedImagery.txt"
COULD_NOT_FIND_FILE = "couldNotFind.txt"

# The imagery JUDGE LLM. Small + fast (it only reasons over two short text lists),
# so it runs the quickest model with a modest context. It exists because exact
# string comparison can't tell "missing" from "present under a newer name" — copied
# files routinely have newer dates/versions than the original packfile entry, so a
# model has to judge "same product, different name". (matchFiles and the corrective
# LLMs use their own, larger models.)
JUDGE_LLM_MODEL = "openai/qwen/qwen3.6-27b"
JUDGE_LLM_CONTEXT = 10000


def _quit_ars():
    """Force-quit the ARS program (by image name, including child processes). Best-effort."""
    for name in ARS_PROCESS_NAMES:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/IM", name],
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logging.error(f"Failed to taskkill ARS process '{name}': {e}")


def _snapshot_root_entries(drive_path):
    """Capture the set of top-level names on the drive root (for scatter cleanup)."""
    try:
        return set(os.listdir(drive_path))
    except Exception as e:
        logging.error(f"Failed to snapshot root of {drive_path}: {e}")
        return set()


def _clean_root_scatter(drive_path, baseline_entries):
    """
    Remove files an LLM scattered onto the DRIVE ROOT during processing.

    The matchFiles / fix_loop agents run with the drive root as their working
    directory, so any scratch/notes/intermediate files they create (e.g.
    iv_matched.txt, missing_files.txt, geocode_mappings.txt) land at the root and
    would otherwise survive the dobDir cleanup. This removes only top-level FILES
    that appeared *after* `baseline_entries` was captured — it never touches
    directories (ARS, dobDir, System Volume Information), never touches files that
    were already present (the original packfiles.txt, etc.), and preserves
    ISSUES.md (the one intentional new root file).
    """
    try:
        current = set(os.listdir(drive_path))
    except Exception as e:
        logging.error(f"Failed to list root of {drive_path} for scatter cleanup: {e}")
        return
    for name in (current - baseline_entries):
        if name == "ISSUES.md":
            continue
        path = os.path.join(drive_path, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
                logging.info(f"Removed stray root file left by an LLM: {path}")
            except Exception as e:
                logging.error(f"Failed to remove stray root file {path}: {e}")


def generate_packfiles(drive_path):
    """
    Regenerate packfiles.txt on the drive being built and stash it in dobDir as
    verify_packfiles.txt for comparison.

    Launches DRIVE:\\ARS\\bin\\ars maintenance.bat (which starts the ARS program),
    waits ARS_SETTLE_SECONDS for ARS to write its packfiles.txt into DRIVE:\\ARS\\bin,
    quits ARS, then MOVES that packfiles.txt into dobDir\\verify_packfiles.txt
    (deleting any existing verify_packfiles.txt first).

    Returns the path to verify_packfiles.txt on success, or None on failure
    (missing batch file / ARS never produced a packfiles.txt). Reusable by both
    the initial verification (compare_packfiles) and fix_loop's re-checks.
    """
    status_mgr.update(status_number=12)
    dobdir_path = os.path.join(drive_path, "dobDir")
    bin_dir = os.path.join(drive_path, "ARS", "bin")
    maintenance_bat = os.path.join(bin_dir, "ars maintenance.bat")
    generated_packfiles = os.path.join(bin_dir, "packfiles.txt")
    verify_packfiles = os.path.join(dobdir_path, "verify_packfiles.txt")

    logging.info("--- Starting generate_packfiles Process ---")
    if not os.path.isfile(maintenance_bat):
        logging.error(f"ARS maintenance batch not found at {maintenance_bat}; cannot regenerate packfiles.")
        return None

    # Remove any stale generated packfiles so we know this run actually produced one.
    try:
        if os.path.exists(generated_packfiles):
            os.remove(generated_packfiles)
    except Exception as e:
        logging.warning(f"Could not remove stale {generated_packfiles}: {e}")

    # Launch the maintenance batch (starts the ARS program), let it settle, then quit ARS.
    logging.info(f"Launching ARS maintenance: {maintenance_bat}")
    proc = None
    try:
        proc = subprocess.Popen(
            ["cmd.exe", "/c", maintenance_bat],
            cwd=bin_dir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception as e:
        logging.error(f"Failed to launch ARS maintenance batch: {e}")
        return None

    logging.info(f"Waiting {ARS_SETTLE_SECONDS}s for ARS to generate packfiles...")
    time.sleep(ARS_SETTLE_SECONDS)

    logging.info("Quitting ARS...")
    _quit_ars()
    if proc is not None:
        _kill_process_tree(proc)

    if not os.path.exists(generated_packfiles):
        logging.error(f"ARS did not produce a packfiles.txt at {generated_packfiles}.")
        return None

    # Replace any prior verify_packfiles.txt and move the freshly generated one in.
    try:
        os.makedirs(dobdir_path, exist_ok=True)
        if os.path.exists(verify_packfiles):
            os.remove(verify_packfiles)
            logging.info(f"Deleted existing {verify_packfiles}")
        shutil.move(generated_packfiles, verify_packfiles)
        logging.info(f"SUCCESS: moved generated packfiles to {verify_packfiles}")
    except Exception as e:
        logging.error(f"Failed to move generated packfiles into dobDir: {e}")
        return None

    logging.info("--- Finished generate_packfiles Process ---")
    return verify_packfiles


def _read_imagery_lines(packfile_path):
    """Return the list of imagery entries (lines under data\\imagery\\) in a packfile."""
    entries = []
    if not packfile_path or not os.path.exists(packfile_path):
        return entries
    try:
        with open(packfile_path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                s = raw.strip()
                if not s:
                    continue
                norm = s.replace("/", "\\").lower()
                if norm.startswith(IMAGERY_PREFIX):
                    entries.append(s)
    except Exception as e:
        logging.error(f"Failed to read imagery lines from {packfile_path}: {e}")
    return entries


def _imagery_lines_in_text(text):
    """Extract the imagery entries (lines under data\\imagery\\) from arbitrary text."""
    out = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if s and s.replace("/", "\\").lower().startswith(IMAGERY_PREFIX):
            out.append(s)
    return out


def _write_missing_list(path, missing):
    """Write the precise missing-imagery list (one path per line) to `path`."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(missing) + ("\n" if missing else ""))
    except Exception as e:
        logging.error(f"Failed to write missing list {path}: {e}")


def _clear_could_not_find(drive_path):
    """Delete a stale couldNotFind.txt so each corrective run starts clean."""
    p = os.path.join(drive_path, "dobDir", COULD_NOT_FIND_FILE)
    try:
        if os.path.exists(p):
            os.remove(p)
    except Exception as e:
        logging.warning(f"Could not remove stale {p}: {e}")


def _read_could_not_find(drive_path):
    """Return the imagery files the corrective LLM reported as genuinely absent from U."""
    p = os.path.join(drive_path, "dobDir", COULD_NOT_FIND_FILE)
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return _imagery_lines_in_text(f.read())
    except Exception as e:
        logging.error(f"Failed to read {p}: {e}")
        return []


def _judge_missing_imagery(drive_path):
    """
    Determine which INTENDED imagery files are genuinely still missing from the
    drive and write that precise list to dobDir\\missedImagery.txt (one
    "data\\imagery\\..." path per line). Returns the list.

    This is the verification gate (idea #3). It can't be a plain string diff:
    copied files routinely carry a NEWER name than the original packfile entry
    (newer date/version/resolution wording), so only a model can decide
    "same product, different name". We use the small, fast JUDGE_LLM_MODEL for it.

    Fast path: if every intended path is already present verbatim, nothing is
    missing and no LLM is needed. Fallback: if the judge produces no usable output
    but the counts disagree, fall back to a deterministic name diff so the
    corrective stage still has a target list (the corrective LLM's no-substitute
    rules keep an over-reported target harmless).
    """
    status_mgr.update(status_number=12)
    dobdir_path = os.path.join(drive_path, "dobDir")
    original = os.path.join(drive_path, "packfiles.txt")
    verify = os.path.join(dobdir_path, "verify_packfiles.txt")
    missed_path = os.path.join(dobdir_path, MISSED_IMAGERY_FILE)

    intended = _read_imagery_lines(original)
    copied = _read_imagery_lines(verify)
    logging.info(f"Imagery judge: {len(intended)} intended vs {len(copied)} on-drive imagery entries.")

    # Fast, deterministic short-circuit: every intended path present verbatim.
    copied_lower = set(c.lower() for c in copied)
    if intended and all(i.lower() in copied_lower for i in intended):
        logging.info("Imagery judge: all intended files present verbatim; nothing missing.")
        _write_missing_list(missed_path, [])
        return []
    if not intended:
        logging.info("Imagery judge: packfiles lists no imagery; nothing to verify.")
        _write_missing_list(missed_path, [])
        return []

    # Remove any stale judge output so we can tell whether the judge wrote a fresh one.
    try:
        if os.path.exists(missed_path):
            os.remove(missed_path)
    except Exception:
        pass

    intended_block = "\n".join(intended)
    copied_block = "\n".join(copied) if copied else "(none)"
    prompt = (
        "You are a meticulous data-verification assistant helping confirm that a data drive received "
        "all of its imagery files. Do NOT copy, move, rename, or modify any files — your ONLY job is to "
        "compare two lists and write one short output file.\n\n"
        "LIST A is the set of imagery files this drive was SUPPOSED to contain (from the original "
        "packfile). LIST B is the set of imagery files ACTUALLY on the drive right now.\n\n"
        "A file in LIST A should be treated as PRESENT if LIST B contains the SAME imagery product, even "
        "when the filename is not identical. Filenames legitimately drift: a file on the drive may have a "
        "newer date, a newer version number, a different resolution token (e.g. 30cm vs 61cm), or an "
        "added/removed word such as \"naip\". Two entries are the SAME product when they clearly describe "
        "the same geographic coverage and the same kind of imagery (for example the same country / state / "
        "region and the same data type or chart), differing only in those date / version / resolution "
        "details.\n\n"
        "A file in LIST A is MISSING only when LIST B contains NO entry that plausibly represents that "
        "same product. When unsure whether two entries are the same product, lean towards treating it as "
        "PRESENT (do not flag a file as missing on a guess).\n\n"
        "LIST A — INTENDED:\n"
        f"{intended_block}\n\n"
        "LIST B — ON THE DRIVE NOW:\n"
        f"{copied_block}\n\n"
        "Go through LIST A one entry at a time and decide whether a matching product exists in LIST B. "
        f"Then write ONLY the MISSING LIST A entries to the file dobDir\\{MISSED_IMAGERY_FILE} (the dobDir "
        "folder is inside your current working directory). Write each missing file on its own line, copied "
        "EXACTLY as it appears in LIST A (the full \"data\\imagery\\...\" path). Write nothing else — no "
        "headers, numbering, commentary, or blank padding. If every LIST A file has a match in LIST B, "
        f"create dobDir\\{MISSED_IMAGERY_FILE} as an empty file."
    )
    logging.info(f"Running imagery judge (model={JUDGE_LLM_MODEL}, ctx={JUDGE_LLM_CONTEXT}).")
    judge_llm = LLM(working_directory=drive_path, model=JUDGE_LLM_MODEL, context_window=JUDGE_LLM_CONTEXT)
    judge_llm.use(prompt)

    missing = []
    judged = os.path.exists(missed_path)
    if judged:
        try:
            with open(missed_path, "r", encoding="utf-8", errors="replace") as f:
                missing = _imagery_lines_in_text(f.read())
        except Exception as e:
            logging.error(f"Failed to read judge output {missed_path}: {e}")
            judged = False

    if not judged:
        # Judge gave us nothing usable — fall back to a deterministic name diff so
        # the corrective stage still has a target list to work from.
        logging.warning("Imagery judge produced no usable output; falling back to a deterministic name diff.")
        missing = [i for i in intended if i.lower() not in copied_lower]
        _write_missing_list(missed_path, missing)

    logging.info(f"Imagery judge: {len(missing)} imagery file(s) still missing.")
    return missing


def compare_packfiles(drive_path):
    """
    Initial imagery verification. The imagery judge produces the precise list of
    still-missing imagery (dobDir\\missedImagery.txt). If nothing is missing the
    drive is verified; otherwise fix_loop(run 1) is started to recover the files.

    Returns (verified, missing_imagery) — see fix_loop.
    """
    logging.info("--- Starting compare_packfiles Process ---")
    missing = _judge_missing_imagery(drive_path)
    if not missing:
        logging.info("--- compare_packfiles: drive verified, no fix needed ---")
        return (True, [])
    logging.warning(f"compare_packfiles found {len(missing)} missing imagery file(s); entering fix_loop.")
    return fix_loop(drive_path, 1)


# Models used for the imagery-correction LLMs. Deliberately DIFFERENT from the
# initial matchFiles model (openai/qwen/qwen3.6-27b) so each stage varies the
# model: the first four correction passes use the larger qwen MoE; the fifth and
# final pass switches to gemma — changing variables to maximize the chance of a
# correct result. (matchFiles is intentionally left on its own model.)
FIX_LLM_MODEL = "openai/qwen/qwen3.6-35b-a3b"
FIX_LLM_CONTEXT = 40000
FINAL_FIX_LLM_MODEL = "openai/google/gemma-4-31b"
FINAL_FIX_LLM_CONTEXT = 10000


def _run_fix_llm(drive_path, run_number):
    """
    Spin up a fresh LLM on the drive root to produce dobDir\\extraMapping{n}.csv
    from missedImagery.txt, quoting the original matchFiles prompt as the previous
    agent's goal.

    Model varies by run: runs 1..(MAX-1) use FIX_LLM_MODEL @ FIX_LLM_CONTEXT, and
    the final run (MAX) uses FINAL_FIX_LLM_MODEL @ FINAL_FIX_LLM_CONTEXT.
    """
    status_mgr.update(status_number=13)
    if run_number >= FIX_LOOP_MAX_RUNS:
        model, context_window = FINAL_FIX_LLM_MODEL, FINAL_FIX_LLM_CONTEXT
    else:
        model, context_window = FIX_LLM_MODEL, FIX_LLM_CONTEXT
    logging.info(f"--- fix_loop run {run_number}: launching corrective LLM (model={model}, ctx={context_window}) ---")
    fix_llm = LLM(working_directory=drive_path, model=model, context_window=context_window)
    prompt = (
        "An AI agent, much like you, was just run on this drive with this as its prompt and goal:\n\n"
        "-------------------- PREVIOUS AGENT'S PROMPT --------------------\n"
        f"{MATCH_FILES_PROMPT}\n"
        "---\n\n"
        "It thought that it got all of the files but I found some discrepancies. You are being run on "
        "the root of the drive we are working on, and there is a subfolder called dobDir with a file in "
        f"it called {MISSED_IMAGERY_FILE}.\n\n"
        f"dobDir\\{MISSED_IMAGERY_FILE} contains the EXACT list of imagery files that are still missing "
        "from this drive — one \"data\\imagery\\...\" path per line. These, and ONLY these, are the files "
        "you must find on the U drive. (The list has already been narrowed down for you, accounting for "
        "files that are present under a newer name — so do not second-guess it; just find the listed "
        "files.) For each one, find its genuine source on the U drive and add it to a new mapping csv in "
        f"dobDir called extraMapping{run_number}.csv.\n\n"
        "CRITICAL RULES — read these carefully, they matter enormously:\n"
        f"1. OUTPUT FORMAT: The ONLY mapping file you create is dobDir\\extraMapping{run_number}.csv. It "
        "must be a real CSV with exactly two columns per row — the source path on the U drive, then the "
        "destination path on this drive — and NO header row. Do NOT write any notes, logs, or other "
        "intermediate/scratch output. If you absolutely must create a temporary file, it MUST live inside "
        "the dobDir folder — NEVER create any file at the root of the drive.\n"
        "2. NEVER RENAME A FILE: The destination filename must be EXACTLY, character-for-character, the "
        "same as the source filename you found on the U drive. Only the folder/location changes between "
        "source and destination — the filename itself must NEVER change. If the source is "
        "\"U:\\...\\foo_2026.esp\", the destination must also end in \"foo_2026.esp\".\n"
        "3. NEVER SUBSTITUTE A DIFFERENT FILE: Only add a row if you are CERTAIN the U-drive file is the "
        "genuine, correct match for the missing file (the same data product, just possibly a newer date). "
        "Do NOT fuzzy-match to a different file to fill a gap. Matching one state / region / county to "
        "another (for example a Texas chart to a Tennessee file), or one FAA chart to a different FAA "
        "chart, is strictly forbidden and is far worse than doing nothing.\n"
        "4. IF A FILE IS GENUINELY NOT ON U, REPORT IT: For any missing file that — after a careful, "
        "honest search of the imagery folders under U:\\ARS\\Data\\... — you are confident simply does "
        "NOT exist anywhere on the U drive, do TWO things: (a) leave it out of the CSV (never force or "
        f"guess a match), and (b) append its exact \"data\\imagery\\...\" line to a file called dobDir\\"
        f"{COULD_NOT_FIND_FILE} (one per line). Some files legitimately do not exist on U — recording them "
        f"in {COULD_NOT_FIND_FILE} tells us the file is truly unavailable rather than that you gave up. "
        "Only list a file there if you are confident it is genuinely absent; if you are merely unsure, "
        "leave it out of BOTH files so another attempt can try.\n\n"
        "Given all of this, your task is to slowly, carefully, with extreme precision find any errors that "
        "the initial agent could have caused and correct them. Read the initial prompt carefully so you "
        "don't make any errors. Try as hard as you can to get this perfect, but remember: it is far better "
        "to leave a file out (and report it) than to copy the wrong file. It matters a lot to me that you "
        "do this right and you have to nail it! PLEASE!!!"
    )
    logging.info(f"Sending corrective prompt to LLM (run {run_number}).")
    fix_llm.use(prompt)


def fix_loop(drive_path, run_number):
    """
    Attempt to recover missing imagery files, up to FIX_LOOP_MAX_RUNS times.

    run 1 (entered straight from compare_packfiles, with the judge's precise
      missedImagery.txt already written): ask the corrective LLM for
      extraMapping1.csv, copy it, then recurse to run 2.
    runs 2..(MAX-1): first re-verify (generate_packfiles + judge). If nothing is
      missing the drive is verified and we stop. Otherwise run the corrective LLM
      for extraMapping{n}.csv, copy it, then recurse to run n+1.
    run MAX (5): same start; if still missing, do a FINAL re-verify after the copy
      and return its result. This is the last attempt — a False here means the
      drive is recorded completed-but-not-verified.

    Early exit (idea #2): after any corrective run, if the LLM CONFIRMED one or
    more missing imagery files are genuinely absent from the U drive
    (couldNotFind.txt), no later model/run can recover them, so we stop immediately
    and record the drive unverified — rather than burning the remaining runs.

    Returns (verified, missing_imagery): `verified` is True/False; `missing_imagery`
    is the list of imagery files still not on the drive when it ends unverified
    (empty when verified) — surfaced to the operator in the WebUI.
    """
    logging.info(f"========== fix_loop run {run_number}/{FIX_LOOP_MAX_RUNS} ==========")

    # Every run after the first begins by re-checking whether the prior copy fixed
    # things (regenerate packfiles via ARS, then re-judge the missing set).
    if run_number > 1:
        if not generate_packfiles(drive_path):
            logging.warning("Could not regenerate packfiles during fix_loop; assuming verified to avoid blocking the drive.")
            return (True, [])
        if not _judge_missing_imagery(drive_path):
            logging.info(f"fix_loop run {run_number}: imagery now complete; drive verified.")
            return (True, [])

    # Produce and copy a corrective mapping for this run (and let the LLM record any
    # genuinely-absent files in couldNotFind.txt).
    _clear_could_not_find(drive_path)
    _run_fix_llm(drive_path, run_number)
    extra_csv = os.path.join(drive_path, "dobDir", f"extraMapping{run_number}.csv")
    _copy_from_mapping(drive_path, extra_csv, status_number=14, issues_filename=None)

    # Idea #2: a confirmed-absent file can never be recovered, so stop now and
    # report exactly those files as the ones unavailable on the source drive.
    could_not_find = _read_could_not_find(drive_path)
    if could_not_find:
        logging.warning(
            f"Corrective LLM confirmed {len(could_not_find)} imagery file(s) are genuinely absent from U; "
            "marking drive UNVERIFIED without further runs."
        )
        for f in could_not_find:
            logging.warning(f"  unavailable on U: {f}")
        return (False, could_not_find)

    if run_number >= FIX_LOOP_MAX_RUNS:
        # Final attempt: re-verify one last time after the copy.
        if not generate_packfiles(drive_path):
            logging.warning("Could not regenerate packfiles for the final check; assuming verified.")
            return (True, [])
        final_missing = _judge_missing_imagery(drive_path)
        verified = not final_missing
        logging.info(f"fix_loop final run complete; verified={verified}.")
        return (verified, [] if verified else final_missing)

    return fix_loop(drive_path, run_number + 1)


def verifySuccess(drive_path):
    """
    Two-part post-build verification:
      1. If mainCopy left an ISSUES.txt, summarize it (status 6); issues_found
         reflects this (unchanged behavior).
      2. Imagery verification: regenerate packfiles via ARS (generate_packfiles)
         and confirm every intended imagery file is present (compare_packfiles),
         recovering misses through fix_loop if needed; `verified` reflects the
         outcome. If ARS can't regenerate packfiles (e.g. the maintenance batch is
         missing) we skip verification and assume verified rather than blocking the
         drive on missing tooling.

    Returns (issues_found, verified, missing_imagery) — missing_imagery is the
    list of imagery files still unavailable when the drive ends unverified (empty
    otherwise), surfaced to the operator in the WebUI.
    """
    logging.info("--- Starting verifySuccess Process ---")
    dobdir_path = os.path.join(drive_path, "dobDir")
    issues_txt = os.path.join(dobdir_path, "ISSUES.txt")

    issues_found = False
    if os.path.exists(issues_txt):
        logging.warning("ISSUES.txt found! Running summarizeIssues.")
        issues_found = True
        summarizeIssues(drive_path)
    else:
        logging.info("No ISSUES.txt found. All copies were successful!")

    # --- Imagery verification (regenerate packfiles, compare, recover) ----------
    verified = True
    missing_imagery = []
    if generate_packfiles(drive_path):
        verified, missing_imagery = compare_packfiles(drive_path)
    else:
        logging.warning("Could not regenerate packfiles for verification; assuming verified.")

    logging.info(f"--- Finished verifySuccess Process (issues={issues_found}, verified={verified}, missing={len(missing_imagery)}) ---")
    return issues_found, verified, missing_imagery

def process_drive(drive_path):
    """Process a newly connected drive."""
    logging.info(f"========== Starting processing for newly detected drive: {drive_path} ==========")
    packfiles_path = os.path.join(drive_path, "packfiles.txt")
    dobdir_path = os.path.join(drive_path, "dobDir")

    logging.debug(f"Looking for packfiles.txt at: {packfiles_path}")
    
    # Check if packfiles.txt exists on the root of the drive. Drives WITHOUT a
    # packfiles.txt never reach process_drive — the monitoring loop routes them
    # to the country-drive flow (process_country_drive) only after the user
    # supplies a name + country in the WebUI. This guard is purely defensive in
    # case the file disappeared between detection and processing.
    if not os.path.exists(packfiles_path):
        logging.info(f"packfiles.txt NOT FOUND on {drive_path}. Skipping this drive.")
        return None

    logging.info(f"Found packfiles.txt on {drive_path}. Proceeding with processing.")
    status_mgr.update(status_number=1)
    
    if os.path.exists(dobdir_path):
        logging.info(f"Directory {dobdir_path} already exists. Deleting it first...")
        try:
            shutil.rmtree(dobdir_path)
            logging.info(f"SUCCESS: Deleted existing directory {dobdir_path}")
        except Exception as e:
            logging.error(f"FAILED to delete existing directory {dobdir_path}. Exception details: {e}")
            return (True, True, [])

    logging.info(f"Attempting to create dobDir on {drive_path}...")
    try:
        os.makedirs(dobdir_path)
        logging.info(f"SUCCESS: Created directory {dobdir_path}")
    except Exception as e:
        logging.error(f"FAILED to create directory {dobdir_path}. Exception details: {e}")
        return (True, True, [])

    # Snapshot the root now (dobDir + original packfiles + ARS-to-be) so we can
    # clean up any scratch files the LLM stages scatter onto the drive root later.
    root_baseline = _snapshot_root_entries(drive_path)

    # Initialize the workVars.csv file in the dobDir directory
    workvars_path = os.path.join(dobdir_path, "workVars.csv")
    work_vars = WorkVars(workvars_path)

    # Instantiate the LLM and run the classifyRegion function
    dobsy = LLM()
    classifyRegion(dobsy, drive_path, work_vars)
    
    # Run the file copy process
    copy_region_files(drive_path, work_vars)

    # Copy and extract the airport archive into ARS\data\airport
    copy_airport(drive_path)

    # Run the matchFiles process to find the rest of the files
    matchFiles(drive_path)
    
    # Run the mainCopy process
    mainCopy(drive_path)
    
    # Verify success: handle copy issues AND verify the imagery set is complete.
    issues_found, verified, missing_imagery = verifySuccess(drive_path)

    # Remove any scratch files the LLM stages scattered onto the drive root so the
    # finished drive only carries the real build output (+ ISSUES.md if relevant).
    _clean_root_scatter(drive_path, root_baseline)

    logging.info(f"Cleaning up {dobdir_path}...")
    try:
        shutil.rmtree(dobdir_path)
        logging.info(f"SUCCESS: Deleted directory {dobdir_path}")
    except Exception as e:
        logging.error(f"FAILED to delete directory {dobdir_path}. Exception details: {e}")

    logging.info(f"========== Finished initial processing for {drive_path} ==========")
    return (issues_found, verified, missing_imagery)


def initialize_and_format_disk(disk_number, label, expected_tb=0, serial=""):
    """
    Bring a whole physical disk to a clean state and lay down a single NTFS
    partition labeled `label`, returning the assigned drive path ("E:\\") or None.

    Unlike the old Format-Volume-by-letter approach (which only worked on an
    already-mounted, readable volume and could leave a drive RAW/uninitialized),
    this clears the disk, (re)initializes it GPT, creates a partition, assigns a
    letter, and quick-formats NTFS. It therefore handles EVERY starting state:
    brand-new/uninitialized disks, RAW disks, filesystems Windows can't read
    (e.g. APFS), exFAT/FAT, and NTFS.

    SAFETY: the PowerShell script refuses to touch a system/boot disk, and — when
    given — verifies the disk's size (±1 TB) and serial number still match what
    was detected, so a reused disk number can never wipe the wrong disk.
    """
    safe_label = (label or "DRIVE")[:32].replace("'", "''")  # NTFS labels max 32 chars
    safe_serial = (serial or "").replace("'", "''")
    ps = (
        "$ErrorActionPreference='Stop';"
        f"$n={int(disk_number)};"
        "$d=Get-Disk -Number $n -ErrorAction SilentlyContinue;"
        "if(-not $d){Write-Output 'ERR:no-disk';exit 3};"
        "if($d.IsSystem -or $d.IsBoot){Write-Output 'ERR:system-disk';exit 4};"
        "$tb=[math]::Round($d.Size/1000000000000);"
        f"if({int(expected_tb)} -gt 0 -and [math]::Abs($tb-{int(expected_tb)}) -gt 1){{Write-Output 'ERR:size-mismatch';exit 5}};"
        f"$want='{safe_serial}';"
        "if($want -ne '' -and \"$($d.SerialNumber)\".Trim() -ne $want){Write-Output 'ERR:serial-mismatch';exit 6};"
        "try{if($d.IsReadOnly){Set-Disk -Number $n -IsReadOnly $false}}catch{};"
        "try{if($d.IsOffline){Set-Disk -Number $n -IsOffline $false}}catch{};"
        "try{Clear-Disk -Number $n -RemoveData -RemoveOEM -Confirm:$false}catch{};"
        "$d=Get-Disk -Number $n;"
        "if($d.PartitionStyle -eq 'RAW'){Initialize-Disk -Number $n -PartitionStyle GPT};"
        "$p=New-Partition -DiskNumber $n -UseMaximumSize -AssignDriveLetter;"
        "Start-Sleep -Milliseconds 750;"
        f"Format-Volume -Partition $p -FileSystem NTFS -NewFileSystemLabel '{safe_label}' -Confirm:$false -Force | Out-Null;"
        "$L=(Get-Partition -DiskNumber $n | Where-Object {$_.DriveLetter -match '[A-Za-z]'} | Select-Object -First 1).DriveLetter;"
        "Write-Output \"OK:$L\""
    )
    logging.info(f"Initializing+formatting disk #{disk_number} as NTFS (label='{safe_label}', expectedTB={expected_tb}).")
    try:
        # 0x08000000 is CREATE_NO_WINDOW
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, creationflags=0x08000000, timeout=600,
        )
    except Exception as e:
        logging.error(f"Disk format subprocess failed for disk #{disk_number}: {e}")
        return None

    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    logging.info(f"Disk #{disk_number} format result: rc={result.returncode} stdout='{out}' stderr='{err}'")
    m = re.search(r"OK:([A-Za-z])", out)
    if result.returncode == 0 and m:
        path = f"{m.group(1).upper()}:\\"
        logging.info(f"SUCCESS: disk #{disk_number} formatted NTFS and mounted at {path}.")
        return path
    logging.error(f"Disk #{disk_number} did NOT format cleanly (rc={result.returncode}, out='{out}', err='{err}').")
    return None


def process_country_drive(job):
    """
    Process a blank drive (one that arrived WITHOUT packfiles.txt) after the user
    has supplied a Drive Name and Country in the WebUI.

    Steps:
      1. Initialize + NTFS-format the whole disk and apply the chosen name
         (status 9). This is what makes a brand-new/uninitialized/APFS/exFAT/FAT
         disk usable; the assigned drive letter is captured here.
      2. Determine the region purely from the chosen country: USA -> US ("u"),
         anything else -> International ("i"). No LLM is involved.
      3. Copy the regional base files (status 3, via copy_region_files).
      4. Copy + extract the airport archive into ARS\\data\\airport (status 7,
         via copy_airport) — same as the packfiles build.
      5. If the country is NOT the US, copy the three country-specific data sets
         (status 8, via copy_country_files).
      6. Clean up dobDir and report the drive completed.

    Returns (had_issues, verified, missing_imagery). Country drives have no
    packfiles, so they are always "assumed verified" (verified=True) with an empty
    missing_imagery list; had_issues is False on a clean completion or True if the
    drive could not be prepared/formatted.
    """
    iso = (job.get("iso") or "").upper()
    name = job.get("name") or "DRIVE"
    disk_number = job.get("disk")
    logging.info(f"========== Starting COUNTRY-DRIVE processing for disk #{disk_number} (name='{name}', iso='{iso}') ==========")

    # 1. Initialize + format the whole disk; capture the assigned drive letter.
    status_mgr.update(status_number=9)
    drive_path = initialize_and_format_disk(
        disk_number, name, expected_tb=job.get("sizeTB", 0), serial=job.get("serial", "")
    )
    if not drive_path:
        logging.error(f"Could not format disk #{disk_number}; aborting this build.")
        return (True, True, [])  # flag as completed-with-issues so the operator notices
    # Record the assigned path on the job so the worker can eject the right drive.
    job["path"] = drive_path

    # 2. dobDir + workVars for the base copy (temporary files live in dobDir).
    status_mgr.update(status_number=1)
    dobdir_path = os.path.join(drive_path, "dobDir")
    if os.path.exists(dobdir_path):
        logging.info(f"Directory {dobdir_path} already exists. Deleting it first...")
        try:
            shutil.rmtree(dobdir_path)
        except Exception as e:
            logging.error(f"FAILED to delete existing directory {dobdir_path}. Exception details: {e}")
            return (True, True, [])
    try:
        os.makedirs(dobdir_path)
        logging.info(f"SUCCESS: Created directory {dobdir_path}")
    except Exception as e:
        logging.error(f"FAILED to create directory {dobdir_path}. Exception details: {e}")
        return (True, True, [])

    work_vars = WorkVars(os.path.join(dobdir_path, "workVars.csv"))

    # 3. Region straight from the country code.
    region = "u" if iso == "USA" else "i"
    work_vars.remove_row("Region")
    work_vars.add_row("Region", region)
    logging.info(f"Country '{iso}' maps to region '{region}'.")

    # 4. Copy the regional base files (US gets US set, others get the international set).
    copy_region_files(drive_path, work_vars, status_number=3)

    # 5. Copy and extract the airport archive into ARS\data\airport (same as the
    #    packfiles build; ARS\data already exists from copy_region_files).
    copy_airport(drive_path)

    # 6. Non-US drives additionally get the country-specific files.
    if region != "u":
        copy_country_files(drive_path, iso)

    # 7. Clean up the temporary dobDir.
    logging.info(f"Cleaning up {dobdir_path}...")
    try:
        shutil.rmtree(dobdir_path)
        logging.info(f"SUCCESS: Deleted directory {dobdir_path}")
    except Exception as e:
        logging.error(f"FAILED to delete directory {dobdir_path}. Exception details: {e}")

    logging.info(f"========== Finished COUNTRY-DRIVE processing for {drive_path} ==========")
    return (False, True, [])


def _append_gitlog(message):
    """Append a timestamped line to the user-facing gitLog.log."""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        ts = datetime.datetime.now().strftime("%a %m/%d/%Y %H:%M:%S")
        with open(GITLOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts} - {message}\n")
    except Exception as e:
        logging.error(f"Failed to write {GITLOG_FILE}: {e}")


def ensure_keys_file():
    """Create configs/keys.json with a blank key slot if it does not already exist."""
    if os.path.exists(KEYS_FILE):
        return
    try:
        os.makedirs(CONFIGS_DIR, exist_ok=True)
        with open(KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(KEYS_FILE_TEMPLATE, f, indent=4)
        logging.info(
            f"Created blank keys file at {KEYS_FILE}. "
            f"Fill in '{GITHUB_PAT_LABEL}' before running."
        )
    except Exception as e:
        logging.error(f"Failed to create keys file {KEYS_FILE}: {e}")


def get_github_pat():
    """
    Ensure the keys file exists, then return the GitHub PAT it holds. Returns an
    empty string if the file is missing, unreadable, or the key slot is blank.
    """
    ensure_keys_file()
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get(GITHUB_PAT_LABEL, "")).strip()
    except Exception as e:
        logging.error(f"Failed to read keys file {KEYS_FILE}: {e}")
        return ""


def get_local_head_sha():
    """
    Return the local checked-out commit SHA (lowercase hex) of the working tree,
    or None if it can't be determined.

    Reads git's plumbing files directly (.git/HEAD -> loose ref or packed-refs)
    rather than shelling out to git.exe, because the watcher runs inside a
    logon-spawned process where git is frequently not on PATH (the same reason
    git_update.py uses find_git_executable). This is what lets the WebUI keep
    showing "update pending" after a power cycle: we compare this local SHA to
    the remote HEAD instead of only noticing pushes that happen while running.
    """
    git_dir = os.path.join(PROJECT_ROOT, ".git")
    try:
        with open(os.path.join(git_dir, "HEAD"), "r", encoding="utf-8") as f:
            head = f.read().strip()
    except Exception:
        return None

    # Detached HEAD: the file holds the SHA directly.
    if not head.startswith("ref:"):
        return head.lower() or None

    ref = head[4:].strip()  # e.g. "refs/heads/main"
    # 1) Loose ref file (.git/refs/heads/main).
    try:
        with open(os.path.join(git_dir, *ref.split("/")), "r", encoding="utf-8") as f:
            sha = f.read().strip()
        if sha:
            return sha.lower()
    except Exception:
        pass
    # 2) Packed refs (.git/packed-refs) — common right after a clone/reset.
    try:
        with open(os.path.join(git_dir, "packed-refs"), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("^"):
                    continue
                parts = line.split(" ", 1)
                if len(parts) == 2 and parts[1].strip() == ref:
                    return parts[0].strip().lower()
    except Exception:
        pass
    return None


class UpdateWatcher:
    """
    Polls GitHub for new commits using cheap HTTP conditional requests so the
    WebUI can show an "update available" indicator without burning the API
    rate limit.

    Approach (matches the rate-limit-free local watcher pattern):
      * First request has no validator -> GitHub returns 200 + an ETag. We
        store that ETag as our baseline AND compare the remote HEAD commit SHA
        to our LOCAL checked-out SHA. If they differ, an update was already
        pending before we started (e.g. the operator powered off without
        applying it), so we flag it immediately. This is the fix for the bug
        where power-cycling theDobinator hid a still-pending update.
      * Every later request sends the stored ETag back in If-None-Match.
          - 304 Not Modified  -> nothing changed, costs nothing.
          - 200 OK            -> a new push happened. We refresh the stored
                                 ETag and raise the update-available flag.

    The actual HTTP call runs on a short-lived daemon thread so a slow network
    never stalls the 1-second drive-detection loop.
    """

    def __init__(self, status_mgr, github_pat):
        self.status_mgr = status_mgr
        self.github_pat = github_pat
        self.etag = None
        self.update_available = False
        self._lock = threading.Lock()
        self._checking = False

    def trigger_check(self):
        """Kick off a non-blocking GitHub check (no-op if one is already running)."""
        if self.update_available:
            # Once we know an update is waiting there is nothing more to learn
            # until the program restarts and re-baselines.
            return
        with self._lock:
            if self._checking:
                return
            self._checking = True
        threading.Thread(target=self._run_check, daemon=True).start()

    def _run_check(self):
        try:
            self._check()
        except Exception as e:
            plog.debug(f"GitHub update check failed (non-fatal): {e}")
        finally:
            with self._lock:
                self._checking = False

    def _check(self):
        req = urllib.request.Request(GITHUB_API_URL)
        req.add_header("Authorization", f"Bearer {self.github_pat}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "TheDobinator-UpdateWatcher")
        if self.etag:
            req.add_header("If-None-Match", self.etag)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                new_etag = resp.headers.get("ETag")
                body = resp.read()  # drain the body (and parse the latest SHA)
                remote_sha = self._parse_latest_sha(body)
                if self.etag is None:
                    # Establish the ETag baseline, then decide availability by
                    # comparing the remote HEAD to our LOCAL checked-out commit.
                    # If we restarted while behind origin/main, local != remote
                    # and the update must still show as pending.
                    self.etag = new_etag
                    local_sha = get_local_head_sha()
                    plog.debug(
                        f"GitHub update watcher baseline: etag={new_etag} "
                        f"remote={remote_sha} local={local_sha}"
                    )
                    if remote_sha and local_sha and remote_sha.lower() != local_sha.lower():
                        plog.warning("Local commit is behind origin/main; an update is already pending.")
                        self._flag_update_available()
                else:
                    # 200 with a previously-known ETag => a genuinely new push.
                    self.etag = new_etag
                    self._flag_update_available()
        except urllib.error.HTTPError as e:
            if e.code == 304:
                plog.debug("GitHub update check: 304 Not Modified (up to date).")
            else:
                plog.warning(f"GitHub update check HTTP error {e.code}: {e.reason}")
        except Exception as e:
            plog.debug(f"GitHub update check network error (non-fatal): {e}")

    def _parse_latest_sha(self, body):
        """Pull the newest commit SHA out of the /commits?per_page=1 response."""
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
            if isinstance(data, list) and data:
                return str(data[0].get("sha", "")).strip() or None
        except Exception as e:
            plog.debug(f"Could not parse latest commit SHA: {e}")
        return None

    def _flag_update_available(self):
        """Raise the WebUI update indicator and decide if it needs a PC restart."""
        self.update_available = True
        self.status_mgr.set_update_available(True)
        plog.warning("A new version of theDobinator is available on GitHub.")
        # Decide whether this incoming update needs a full PC restart by reading
        # the remote reboot-required flag.
        reboot = self._fetch_reboot_required()
        self.status_mgr.set_reboot_required(reboot)
        if reboot:
            plog.warning("The available update is flagged as REQUIRING A PC RESTART.")

    def _fetch_reboot_required(self):
        """
        Read the remote configs/reboot_required.flag via the GitHub contents API
        (raw media type) and return True if it indicates a reboot is required.
        Fails safe to False (yellow button) on any error.
        """
        try:
            req = urllib.request.Request(GITHUB_FLAG_API_URL)
            req.add_header("Authorization", f"Bearer {self.github_pat}")
            req.add_header("Accept", "application/vnd.github.raw")
            req.add_header("X-GitHub-Api-Version", "2022-11-28")
            req.add_header("User-Agent", "TheDobinator-UpdateWatcher")
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace").strip().lower()
            return content in ("1", "true", "yes")
        except Exception as e:
            plog.debug(f"Could not read remote reboot flag (assuming no reboot needed): {e}")
            return False


def is_update_scheduled():
    """True if the user asked (via the WebUI) to apply an update after the current drive."""
    return os.path.exists(UPDATE_SCHEDULED_FLAG)


def scheduled_update_is_reboot():
    """
    True if the scheduled update is a reboot-update (the API wrote 'reboot' into
    the flag file). Any other content means a normal restart-the-bot update.
    """
    try:
        with open(UPDATE_SCHEDULED_FLAG, "r", encoding="utf-8") as f:
            return f.read().strip().lower() == "reboot"
    except Exception:
        return False


def clear_update_scheduled():
    """Remove the scheduled-update flag if present."""
    try:
        if os.path.exists(UPDATE_SCHEDULED_FLAG):
            os.remove(UPDATE_SCHEDULED_FLAG)
    except Exception as e:
        logging.error(f"Failed to clear scheduled-update flag: {e}")


def drain_queue(drive_queue):
    """Pull every remaining item out of the queue (without processing them)."""
    items = []
    while True:
        try:
            item = drive_queue.get_nowait()
        except queue.Empty:
            break
        if item is not None:
            items.append(item)
        drive_queue.task_done()
    return items


def save_queue(jobs):
    """Persist the not-yet-processed job dicts so they survive the update restart."""
    try:
        os.makedirs(os.path.dirname(SAVED_QUEUE_FILE), exist_ok=True)
        with open(SAVED_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(jobs), f)
        logging.info(f"Saved {len(jobs)} queued drive(s) for post-update resume.")
    except Exception as e:
        logging.error(f"Failed to save drive queue to {SAVED_QUEUE_FILE}: {e}")


def load_saved_queue():
    """Read and consume (delete) any saved drive queue from a prior update restart."""
    if not os.path.exists(SAVED_QUEUE_FILE):
        return []
    try:
        with open(SAVED_QUEUE_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception as e:
        logging.error(f"Failed to read saved drive queue {SAVED_QUEUE_FILE}: {e}")
        items = []
    try:
        os.remove(SAVED_QUEUE_FILE)
    except Exception as e:
        logging.error(f"Failed to delete saved drive queue {SAVED_QUEUE_FILE}: {e}")
    return items if isinstance(items, list) else []


def trigger_update(reboot=False):
    """
    Launch the git updater detached. git_update.py shuts this program down via
    quit.bat, pulls the new code, then either restarts it via dobWin.bat (normal)
    or — when reboot=True — clears the reboot flag and restarts the whole PC
    (git_update.py --reboot). The updater is started in its own detached process
    group so it is NOT killed when this program is terminated.
    """
    updater = os.path.join(PROJECT_ROOT, "configs", "git_updater", "git_update.py")
    if not os.path.exists(updater):
        logging.error(f"Cannot apply scheduled update: {updater} not found.")
        return
    args = [sys.executable, updater] + (["--reboot"] if reboot else [])
    logging.info(f"Launching {'reboot-' if reboot else ''}update via {updater}")
    try:
        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            subprocess.Popen(
                args,
                cwd=PROJECT_ROOT,
                creationflags=flags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                args,
                cwd=PROJECT_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
    except Exception as e:
        logging.error(f"Failed to launch updater: {e}", exc_info=True)


# Filesystems Windows can read/mount (and therefore could hold a packfiles.txt).
READABLE_FILESYSTEMS = {"NTFS", "EXFAT", "FAT", "FAT32"}


def scan_external_disks():
    """
    Enumerate external (non-system, non-boot) physical disks via PowerShell and
    return {disk_number: info}. Crucially this sees disks that GetLogicalDrives()
    can NOT — brand-new/uninitialized disks, RAW disks, and disks with a
    filesystem Windows can't read (e.g. APFS) have no drive letter at all.

    Each info dict: {number, sizeTB, letter ("E:\\" or None), fs (UPPER or None),
    style, serial}. `letter`/`fs` describe the first lettered, mountable volume on
    the disk (if any).

    Returns None on scan failure so callers can SKIP the iteration rather than
    wrongly conclude every disk was removed.
    """
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "$out=@();"
        "foreach($d in Get-Disk){"
        "  if($d.IsSystem -or $d.IsBoot){continue};"
        "  $letter=$null;$fs=$null;"
        "  foreach($p in (Get-Partition -DiskNumber $d.Number)){"
        "    if($p.DriveLetter -and ($p.DriveLetter -match '[A-Za-z]')){"
        "      $v=Get-Volume -Partition $p;"
        "      if($v){$letter=\"$($p.DriveLetter)\";$fs=\"$($v.FileSystemType)\";break}"
        "    }"
        "  };"
        "  $out+=[pscustomobject]@{Number=$d.Number;Size=[int64]$d.Size;"
        "PartitionStyle=\"$($d.PartitionStyle)\";SerialNumber=\"$($d.SerialNumber)\";"
        "Letter=$letter;FileSystem=$fs}"
        "};"
        "ConvertTo-Json -Compress -Depth 3 -InputObject @($out)"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, creationflags=0x08000000, timeout=60,
        )
    except Exception as e:
        plog.error(f"Disk scan failed to run: {e}")
        return None
    if result.returncode != 0:
        plog.error(f"Disk scan rc={result.returncode}: {(result.stderr or '').strip()}")
        return None
    raw = (result.stdout or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception as e:
        plog.error(f"Disk scan JSON parse failed: {e}; raw={raw[:300]}")
        return None
    if isinstance(data, dict):
        data = [data]

    disks = {}
    for item in data:
        try:
            num = int(item.get("Number"))
        except Exception:
            continue
        size = item.get("Size") or 0
        letter_char = item.get("Letter")
        fs = item.get("FileSystem")
        disks[num] = {
            "number": num,
            "sizeTB": int(round((size or 0) / 1_000_000_000_000)),
            "letter": (f"{letter_char}:\\" if letter_char else None),
            "fs": (str(fs).upper() if fs else None),
            "style": item.get("PartitionStyle"),
            "serial": (str(item.get("SerialNumber")).strip() if item.get("SerialNumber") else ""),
        }
    return disks


def classify_and_enqueue_disk(num, info, drive_queue):
    """
    Route a newly connected physical disk:
      * If it has a readable, lettered volume that contains packfiles.txt -> queue
        the full build immediately (unchanged behavior for prepared drives).
      * Otherwise (NTFS/exFAT/FAT with no packfiles, OR a RAW/uninitialized/foreign
        disk such as APFS or a brand-new drive) -> register it blank-awaiting so the
        WebUI prompts for a Drive Name + Country before it is formatted + built.
    """
    size_tb = info.get("sizeTB", 0)
    letter = info.get("letter")
    fs = info.get("fs")
    serial = info.get("serial", "")

    has_packfiles = bool(
        letter and fs in READABLE_FILESYSTEMS
        and os.path.exists(os.path.join(letter, "packfiles.txt"))
    )

    if has_packfiles:
        job = {
            "disk": num,
            "path": letter,
            "kind": "packfiles",
            "name": get_volume_name(letter),
            "sizeTB": size_tb,
            "iso": None,
            "serial": serial,
        }
        drive_manager.add_pending(job)
        drive_queue.put(job)
        plog.info(f"Disk #{num} ({letter}, {fs}) has packfiles.txt -> queued for full build (name='{job['name']}', {size_tb}TB).")
    else:
        drive_manager.add_blank(num, size_tb, serial)
        plog.info(f"Disk #{num} (letter={letter}, fs={fs}, {size_tb}TB) has no packfiles -> awaiting user input in WebUI.")


def consume_submissions(drive_queue):
    """
    Consume any blank-drive submissions written by the companion API into
    SUBMISSIONS_DIR. Each file is {token, name, country}. For each one still
    matching a blank-awaiting disk, build a country job, register it pending,
    and queue it for the worker (which formats + builds it).
    """
    if not os.path.isdir(SUBMISSIONS_DIR):
        return
    try:
        entries = sorted(os.listdir(SUBMISSIONS_DIR))
    except Exception as e:
        plog.error(f"Failed to list submissions dir {SUBMISSIONS_DIR}: {e}")
        return

    for fname in entries:
        fpath = os.path.join(SUBMISSIONS_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                sub = json.load(f)
        except Exception as e:
            plog.error(f"Failed to read submission {fpath}: {e}")
            try:
                os.remove(fpath)
            except Exception:
                pass
            continue
        # Consume the file regardless of outcome so it is never reprocessed.
        try:
            os.remove(fpath)
        except Exception as e:
            plog.error(f"Failed to delete submission {fpath}: {e}")

        token = str(sub.get("token", "")).strip()
        name = sanitize_drive_name(sub.get("name", ""))
        iso = str(sub.get("country", "")).strip().upper()

        if not (token and name and re.fullmatch(r"[A-Z]{3}", iso)):
            plog.warning(f"Ignoring malformed submission: {sub}")
            continue

        match = drive_manager.pop_blank_by_token(token)
        if not match:
            plog.warning(f"Submission token {token} no longer matches a connected blank disk; ignoring.")
            continue

        job = {
            "disk": match["disk"],
            "path": None,  # assigned by initialize_and_format_disk during processing
            "kind": "country",
            "name": name,
            "sizeTB": match["sizeTB"],
            "iso": iso,
            "serial": match.get("serial", ""),
        }
        drive_manager.add_pending(job)
        drive_queue.put(job)
        plog.warning(f"Blank disk #{match['disk']} submitted as '{name}' ({iso}) -> queued for build.")


def worker_thread(drive_queue, status_mgr):
    logging.info("Worker thread started. Waiting for drives...")
    while True:
        try:
            job = drive_queue.get()
            if job is None:  # Shutdown signal
                break

            drive_path = job.get("path")
            kind = job.get("kind", "packfiles")
            vol_name = job.get("name") or (get_volume_name(drive_path) if drive_path else "Drive")
            drive_manager.start_job(job)

            # For an already-lettered drive (packfiles build), if it was unplugged
            # while queued, drop it instead of processing a drive that's gone. A
            # country drive has no letter yet (path is None); its disk presence and
            # identity are re-verified inside initialize_and_format_disk.
            if kind != "country" and not (drive_path and os.path.exists(drive_path)):
                logging.warning(f"Queued drive {drive_path} is no longer connected; skipping it.")
                if drive_queue.empty():
                    current_state = status_mgr._read_data()
                    if current_state.get("StatusNumber", 0) not in [10, 11]:
                        status_mgr.update(status_number=0)
                drive_queue.task_done()
                continue

            logging.info(f"Worker picked up drive: {drive_path} (Name: {vol_name}, kind: {kind})")

            # Both processors update status numbers during their execution and
            # return either None (packfiles drive that had nothing to do) or a
            # (had_issues, verified, missing_imagery) tuple.
            if kind == "country":
                result = process_country_drive(job)
            else:
                result = process_drive(drive_path)

            # A country build assigns the drive letter during formatting, so read
            # the final path back off the job for the eject step.
            final_path = job.get("path") or drive_path

            if result is not None:
                had_issues, verified, missing_imagery = result
                # Record the drive: the verified flag (imagery completeness) and the
                # list of imagery still unavailable are stored in completedDrives.csv.
                status_mgr.add_completed_drive(vol_name, had_issues, verified, missing_imagery)

                # Set the final live status card. A drive that merely failed
                # imagery verification (no copy issues) still ends like any normal
                # completed drive (status 10) — the not-verified state is surfaced
                # in the completed-drives history, not the live card.
                if had_issues:
                    status_mgr.update(status_number=11)
                else:
                    status_mgr.update(status_number=10)

                # Eject the drive
                if final_path:
                    logging.info(f"Ejecting drive {final_path}...")
                    eject_drive(final_path)
            else:
                # If packfiles.txt wasn't found, it resets status if the queue is empty
                current_state = status_mgr._read_data()
                if drive_queue.empty() and current_state.get("StatusNumber", 0) not in [10, 11]:
                    status_mgr.update(status_number=0)

            drive_queue.task_done()

            # If the user scheduled an update to apply once the current drive
            # finished, do it now — before draining the rest of the queue. We
            # stash the still-pending drives, then launch the updater (which
            # stops and restarts this program). The saved queue is re-enqueued
            # automatically on the next startup.
            if is_update_scheduled():
                reboot = scheduled_update_is_reboot()
                logging.warning(f"Scheduled {'reboot-' if reboot else ''}update detected; applying now that the current drive is done.")
                remaining = drain_queue(drive_queue)
                save_queue(remaining)
                clear_update_scheduled()
                trigger_update(reboot=reboot)
                logging.info("Updater launched; worker thread exiting to await program restart.")
                return
        except Exception as e:
            logging.error(f"Error in worker thread: {e}", exc_info=True)


def main():
    # The GitHub PAT is mandatory. It is read from the gitignored configs/keys.json
    # (auto-created blank on first run). Without it, refuse to run and make the
    # reason loud in every log so it is impossible to miss.
    github_pat = get_github_pat()
    if not github_pat:
        msg = (
            f"No GitHub PAT found. Open '{KEYS_FILE}', paste your token into the "
            f"'{GITHUB_PAT_LABEL}' field, and restart. The Dobinator will NOT run "
            f"without it."
        )
        logging.critical(msg)
        _append_gitlog(msg)
        status_mgr.update(running=0)
        return

    # Reset transient run state, but DO NOT wipe the completed-drives history:
    # it now lives permanently in completedDrives.csv. Refresh the last-24h
    # view and clear any stale update indicator so a fresh launch starts clean.
    status_mgr.update(status_number=0, running=1)
    status_mgr.set_update_available(False)
    status_mgr.set_reboot_required(False)
    status_mgr.refresh_completed_drives()
    # Wipe any blank/pending drive lists left over in status.json by a previous
    # run or a hard reboot, so a stale popup can never survive a restart.
    drive_manager.reset()

    # Elevation matters: disk formatting and shutdown/reboot need admin rights.
    if is_admin():
        logging.info("Running elevated (administrator). Disk formatting + reboot are available.")
    else:
        logging.warning(
            "NOT elevated (administrator). Disk formatting (Clear-Disk/Format-Volume) and reboot "
            "updates WILL FAIL. Set the 'Dobinator Web API' scheduled task to 'Run with highest "
            "privileges' so the bot it launches inherits admin rights. See AGENTS.md section 5."
        )
    logging.info("Starting dobd.py drive monitor program...")

    drive_queue = queue.Queue()
    worker = threading.Thread(target=worker_thread, args=(drive_queue, status_mgr), daemon=True)
    worker.start()

    # Background watcher that polls GitHub for new commits (cheap ETag checks).
    update_watcher = UpdateWatcher(status_mgr, github_pat)
    poll_count = 0

    # Make sure the blank-drive submission inbox exists before we start polling.
    try:
        os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
    except Exception as e:
        logging.error(f"Failed to create submissions dir {SUBMISSIONS_DIR}: {e}")

    # Establish the baseline set of EXTERNAL physical disks already connected at
    # startup; these are ignored (only disks plugged in afterwards are processed),
    # which also protects every pre-existing disk from ever being formatted.
    # Detection is disk-based (not drive-letter based) so we can also see disks
    # that have no readable volume at all (uninitialized / RAW / APFS / brand new).
    known_disks = set()
    baseline_established = False
    initial_scan = None
    for attempt in range(3):
        initial_scan = scan_external_disks()
        if initial_scan is not None:
            break
        plog.warning(f"Initial disk scan failed (attempt {attempt + 1}/3); retrying...")
        time.sleep(2)
    if initial_scan is not None:
        known_disks = set(initial_scan.keys())
        baseline_established = True
        logging.info(f"Initial external disks (ignored as baseline): {sorted(known_disks) if known_disks else 'None'}")
    else:
        plog.critical("Could not scan disks at startup; baseline will be set on the first successful scan. "
                      "No drives will be processed until then.")

    # Resume any drives that were still queued when a scheduled update restarted
    # the program. Packfiles drives resume if their letter is back; country
    # drives resume if their disk is still present.
    current_letters = get_connected_drives()
    for job in load_saved_queue():
        if not isinstance(job, dict):
            continue
        kind = job.get("kind", "packfiles")
        path = job.get("path")
        disk = job.get("disk")
        still_here = (
            (kind != "country" and path and path in current_letters)
            or (kind == "country" and initial_scan is not None and disk in initial_scan)
        )
        if still_here:
            drive_manager.add_pending(job)
            drive_queue.put(job)
            logging.info(f"Resuming queued drive after update restart: {job}")
        else:
            logging.info(f"Saved drive {job} is no longer connected; skipping resume.")

    plog.info("Entering main monitoring loop. Waiting for new drives...")

    try:
        while True:
            poll_count += 1

            # Disk enumeration is heavier than a drive-letter check (it spawns
            # PowerShell), so run it every DISK_SCAN_EVERY iterations rather than
            # every second. Submissions are still consumed every iteration so the
            # WebUI Confirm button feels responsive.
            if poll_count % DISK_SCAN_EVERY == 0:
                scan = scan_external_disks()
                if scan is None:
                    plog.debug("Disk scan failed this cycle; leaving known set unchanged.")
                else:
                    current_disks = set(scan.keys())
                    if not baseline_established:
                        known_disks = current_disks
                        baseline_established = True
                        logging.info(f"Disk baseline established late: {sorted(known_disks) if known_disks else 'None'}")
                    else:
                        for num in (current_disks - known_disks):
                            info = scan[num]
                            plog.warning(f"--- NEW DISK DETECTED: #{num} ({info.get('letter')}, fs={info.get('fs')}, {info.get('sizeTB')}TB) ---")
                            classify_and_enqueue_disk(num, info, drive_queue)
                        for num in (known_disks - current_disks):
                            plog.warning(f"--- DISK REMOVED: #{num} ---")
                            # Stop tracking an unplugged disk: drop it from the
                            # blank-awaiting list (so its popup disappears) and the
                            # pending list (so it leaves the Pending Drives menu).
                            # A job already in the work queue is additionally skipped
                            # by the worker if the drive is gone.
                            drive_manager.remove_blank_by_disk(num)
                            drive_manager.remove_pending_by_disk(num)
                        known_disks = current_disks

            # Consume any blank-drive submissions the WebUI posted via the API.
            consume_submissions(drive_queue)

            # Reset status to 0 if no external disks are connected and queue is empty
            if not known_disks and drive_queue.empty():
                current_state = status_mgr._read_data()
                if current_state.get("StatusNumber", 0) != 0:
                    status_mgr.update(status_number=0)

            # Every 5th poll (~5 seconds) check GitHub for a newer version.
            if poll_count % GITHUB_CHECK_EVERY == 0:
                update_watcher.trigger_check()

            # Sleep briefly before checking again to prevent high CPU usage
            time.sleep(1)
            
    except KeyboardInterrupt:
        plog.info("Program stopped by user via KeyboardInterrupt.")
    except Exception as e:
        plog.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
    finally:
        # On a graceful exit, mark stopped and clear the drive lists so the WebUI
        # shows nothing pending. (A force-kill via quit.bat won't reach this, but
        # the WebUI also suppresses these lists whenever Running != 1.)
        status_mgr.update(running=0)
        status_mgr.set_drive_lists([], [])

if __name__ == "__main__":
    main()
