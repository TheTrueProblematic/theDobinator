import os
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
# How many 1-second drive-poll iterations between GitHub checks (~5 seconds).
GITHUB_CHECK_EVERY = 5

# --- Secrets / keys file ---
# The GitHub fine-grained PAT is deliberately NOT stored in source (it would
# leak the moment the repo is pushed). It lives in configs/keys.json, which is
# gitignored. That file is auto-created with a blank key slot on first run, and
# the program refuses to run until the key has been filled in.
CONFIGS_DIR = os.path.join(PROJECT_ROOT, "configs")
KEYS_FILE = os.path.join(CONFIGS_DIR, "keys.json")
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
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

    def _read_data(self):
        data = {
            "StatusNumber": 0,
            "TotalBaseFiles": -1,
            "CompletedBaseFiles": -1,
            "TotalMainFiles": -1,
            "CompletedMainFiles": -1,
            "CompletedDrives": [],
            "UpdateAvailable": 0,
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
        data = self._read_data()
        new_val = 1 if available else 0
        if data.get("UpdateAvailable", 0) != new_val:
            data["UpdateAvailable"] = new_val
            self._write_data(data)

    def _load_recent_completed_drives(self, hours=24):
        """
        Read the permanent completedDrives.csv and return the entries that
        completed within the last `hours` hours, newest last. Each entry is a
        dict {name, issues, timestamp} matching what the WebUI consumes.
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
                    try:
                        ts = datetime.datetime.fromisoformat(ts_str)
                    except ValueError:
                        continue
                    if ts >= cutoff:
                        recent.append({"name": name, "issues": issues, "timestamp": ts_str})
        except Exception as e:
            logging.error(f"Failed to read {COMPLETED_DRIVES_CSV}: {e}")
        return recent

    def refresh_completed_drives(self):
        """Recompute the last-24h completed-drive list and store it in status.json."""
        recent = self._load_recent_completed_drives()
        data = self._read_data()
        data["CompletedDrives"] = recent
        self._write_data(data)

    def add_completed_drive(self, name, had_issues):
        """
        Permanently record a completed drive in completedDrives.csv (kept
        forever) and refresh the last-24h view exposed to the WebUI.
        """
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        try:
            os.makedirs(os.path.dirname(COMPLETED_DRIVES_CSV), exist_ok=True)
            with open(COMPLETED_DRIVES_CSV, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([ts, name, "1" if had_issues else "0"])
            logging.info(f"Recorded completed drive '{name}' (issues={bool(had_issues)}) at {ts}")
        except Exception as e:
            logging.error(f"Failed to append to {COMPLETED_DRIVES_CSV}: {e}")
        self.refresh_completed_drives()

status_mgr = StatusManager(STATUS_FILE)

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

def classifyRegionByName(llm_instance, drive_path, work_vars):
    """
    Region classification for drives that arrive WITHOUT a packfiles.txt.

    Unlike classifyRegion (which inspects packfiles.txt), an empty drive has
    nothing on it to read, so the only hint available is the drive's own name.
    We pull that name with Python (get_volume_name) and hand it to the LLM,
    asking it to decide US vs International and record its answer by creating
    either region-U.txt or region-I.txt on the root of the drive (contents = the
    drive name). The region file is intentionally left in place here;
    process_empty_drive removes it after the base files have been copied.
    """
    status_mgr.update(status_number=8)
    logging.info("--- Starting Region Classification (by drive name) ---")

    # Find the drive name in Python and feed it to the LLM via the prompt.
    drive_name = get_volume_name(drive_path)
    logging.info(f"Drive name used for region classification: '{drive_name}'")

    # ========================================================================
    # LLM PROMPT FOR REGION CLASSIFICATION (BY DRIVE NAME)
    # ========================================================================
    # The LLM runs with 'drive_path' as its working directory (the root of the
    # drive being processed). [DRIVE] is replaced with the drive name above.
    prompt = (
        "Your task is to identify if this drive is intended to be used by a customer inside the US or outside the US. "
        f"The name of the drive is {drive_name} and that should serve as your best hint. "
        "Below are a couple of drive names and their regions to serve as examples:\n"
        "BasinElectric -> US (we can tell this since Basin Electric is the name of a US utility company).\n"
        "CalNatGuard -> US (since it's california's national guard this is obvious)\n"
        "SwedishNP -> International (again it says Swedish so you can figure it out)\n"
        "NMGameFish -> US (NM stands for New Mexico)\n\n"
        "Some will be tricky and only be companies and some will be more clear. Once you have identified the region "
        "you will create a new file at the root of this drive called either region-I.txt (for international) or "
        "region-U.txt (for US). DO NOT CREATE ANY OTHER FILES WITH ANY OTHER NAMES! The contents of the text file "
        "should be just the drive name. "
    )
    # ========================================================================

    logging.info(f"Sending prompt to LLM: '{prompt}'")
    llm_instance.useLoc(prompt, drive_path)

    # The LLM signals the region by creating region-U.txt or region-I.txt on the
    # root of the drive. Detect which one it made and record it in workVars.
    region_u_path = os.path.join(drive_path, "region-U.txt")
    region_i_path = os.path.join(drive_path, "region-I.txt")

    region_determined = None
    if os.path.exists(region_u_path):
        region_determined = "U"
    elif os.path.exists(region_i_path):
        region_determined = "I"

    if region_determined:
        logging.info(f"LLM created region file. Region is: {region_determined}")
        work_vars.remove_row("Region")
        work_vars.add_row("Region", region_determined)
    else:
        logging.warning("LLM failed to create region-U.txt or region-I.txt to indicate region.")

    region_after = work_vars.get_data_by_name("Region")
    logging.info(f"Region AFTER LLM processing: {region_after}")
    logging.info("--- Finished Region Classification (by drive name) ---")

def copy_region_files(drive_path, work_vars, status_number=3):
    """
    Copies the appropriate files to the drive based on the identified region.

    `status_number` lets callers reflect a distinct WebUI step: the normal build
    reports step 3 ("Copying Base Files") while the empty-drive path reports
    step 9 (its own base-files-only copy) via copy_base_files.
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

def copy_base_files(drive_path, work_vars):
    """
    Copies the regional base files for an empty drive (one with no packfiles.txt).

    This is the empty-drive counterpart to copy_region_files: it performs the very
    same robocopy work, but reports its own WebUI status (step 9) so the user can
    clearly see that an empty drive is only receiving its regional base files.
    """
    logging.info("--- Starting Base File Copy Process (empty drive) ---")
    copy_region_files(drive_path, work_vars, status_number=9)
    logging.info("--- Finished Base File Copy Process (empty drive) ---")

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

def matchFiles(drive_path):
    """
    Instructs the AI on how to actually find the rest of the files.
    Creates a new LLM instance with the working directory on the root of the processing drive.
    """
    status_mgr.update(status_number=4)
    logging.info("--- Starting matchFiles Process ---")
    
    # Create a new LLM object with its working directory on the root of the drive
    match_llm = LLM(working_directory=drive_path)
    
    prompt = (
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

def mainCopy(drive_path):
    """
    Reads the mapping.csv created by matchFiles and copies the files using robocopy.
    Tracks total and completed files, and logs any errors to ISSUES.txt.
    """
    status_mgr.update(status_number=5)
    logging.info("--- Starting mainCopy Process ---")
    dobdir_path = os.path.join(drive_path, "dobDir")
    mapping_csv = os.path.join(dobdir_path, "mapping.csv")
    issues_txt = os.path.join(dobdir_path, "ISSUES.txt")
    
    if not os.path.exists(mapping_csv):
        logging.error(f"mapping.csv not found at {mapping_csv}. Cannot proceed with mainCopy.")
        return
        
    try:
        with open(mapping_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Remove empty rows and keep only those with at least source and destination
            rows = [row for row in reader if row and len(row) >= 2]
    except Exception as e:
        logging.error(f"Failed to read {mapping_csv}: {e}")
        return
        
    totalMainFiles = len(rows)
    completedMainFiles = 0
    status_mgr.update(total_main=totalMainFiles, comp_main=0)
    errors_encountered = []
    
    logging.info(f"Total items to copy (totalMainFiles): {totalMainFiles}")
    
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
            
    logging.info(f"mainCopy process completed. Successfully copied {completedMainFiles} out of {totalMainFiles} items.")
    
    if errors_encountered:
        logging.warning(f"Writing {len(errors_encountered)} errors to {issues_txt}")
        try:
            with open(issues_txt, 'w', encoding='utf-8') as f:
                f.write(f"Errors encountered during mainCopy on {time.strftime('%Y-%m-%d %H:%M:%S')}:\n")
                f.write("-" * 50 + "\n")
                for err in errors_encountered:
                    f.write(err + "\n")
        except Exception as e:
            logging.error(f"Failed to write to {issues_txt}: {e}")
            
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

def verifySuccess(drive_path):
    """
    Checks for ISSUES.txt and runs summarizeIssues if it exists.
    Returns True if issues were found, False otherwise.
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
        
    logging.info("--- Finished verifySuccess Process ---")
    return issues_found

def process_drive(drive_path):
    """Process a newly connected drive."""
    logging.info(f"========== Starting processing for newly detected drive: {drive_path} ==========")
    packfiles_path = os.path.join(drive_path, "packfiles.txt")
    dobdir_path = os.path.join(drive_path, "dobDir")

    logging.debug(f"Looking for packfiles.txt at: {packfiles_path}")
    
    # Check if packfiles.txt exists on the root of the drive. If it is missing,
    # this is an "empty" drive: rather than skip it, we hand off to the
    # process_empty_drive workflow which copies only the regional base files.
    if not os.path.exists(packfiles_path):
        logging.info(f"packfiles.txt NOT FOUND on {drive_path}. Switching to empty-drive processing.")
        return process_empty_drive(drive_path)

    logging.info(f"Found packfiles.txt on {drive_path}. Proceeding with processing.")
    status_mgr.update(status_number=1)
    
    if os.path.exists(dobdir_path):
        logging.info(f"Directory {dobdir_path} already exists. Deleting it first...")
        try:
            shutil.rmtree(dobdir_path)
            logging.info(f"SUCCESS: Deleted existing directory {dobdir_path}")
        except Exception as e:
            logging.error(f"FAILED to delete existing directory {dobdir_path}. Exception details: {e}")
            return True
            
    logging.info(f"Attempting to create dobDir on {drive_path}...")
    try:
        os.makedirs(dobdir_path)
        logging.info(f"SUCCESS: Created directory {dobdir_path}")
    except Exception as e:
        logging.error(f"FAILED to create directory {dobdir_path}. Exception details: {e}")
        return True
    
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
    
    # Verify success and handle issues
    issues_found = verifySuccess(drive_path)
    
    logging.info(f"Cleaning up {dobdir_path}...")
    try:
        shutil.rmtree(dobdir_path)
        logging.info(f"SUCCESS: Deleted directory {dobdir_path}")
    except Exception as e:
        logging.error(f"FAILED to delete directory {dobdir_path}. Exception details: {e}")
    
    logging.info(f"========== Finished initial processing for {drive_path} ==========")
    return issues_found


def process_empty_drive(drive_path):
    """
    Process a newly connected drive that has NO packfiles.txt on its root.

    Whereas process_drive builds a full data drive, an "empty" drive only gets the
    regional base files. Because there is no packfiles.txt to read the region from,
    the region is inferred by the LLM from the drive's NAME (classifyRegionByName).
    Once the base files are copied, BOTH dobDir and the region file the LLM created
    are deleted, and the drive is reported as completed exactly like a normal build.

    Returns False (no issues) on completion so the worker thread records it as a
    completed drive, or True if the drive could not even be prepared.
    """
    logging.info(f"========== Starting EMPTY-DRIVE processing for: {drive_path} ==========")
    status_mgr.update(status_number=1)
    dobdir_path = os.path.join(drive_path, "dobDir")

    # Same dobDir lifecycle as process_drive: temporary work files (workVars.csv,
    # the copy_files.bat reference) live in dobDir on the target drive.
    if os.path.exists(dobdir_path):
        logging.info(f"Directory {dobdir_path} already exists. Deleting it first...")
        try:
            shutil.rmtree(dobdir_path)
            logging.info(f"SUCCESS: Deleted existing directory {dobdir_path}")
        except Exception as e:
            logging.error(f"FAILED to delete existing directory {dobdir_path}. Exception details: {e}")
            return True

    logging.info(f"Attempting to create dobDir on {drive_path}...")
    try:
        os.makedirs(dobdir_path)
        logging.info(f"SUCCESS: Created directory {dobdir_path}")
    except Exception as e:
        logging.error(f"FAILED to create directory {dobdir_path}. Exception details: {e}")
        return True

    # Initialize the workVars.csv file in the dobDir directory
    workvars_path = os.path.join(dobdir_path, "workVars.csv")
    work_vars = WorkVars(workvars_path)

    # Identify the region from the drive's NAME, then copy the regional base files.
    dobsy = LLM()
    classifyRegionByName(dobsy, drive_path, work_vars)
    copy_base_files(drive_path, work_vars)

    # Clean up: remove dobDir AND the region file the LLM created on the root.
    logging.info(f"Cleaning up {dobdir_path}...")
    try:
        shutil.rmtree(dobdir_path)
        logging.info(f"SUCCESS: Deleted directory {dobdir_path}")
    except Exception as e:
        logging.error(f"FAILED to delete directory {dobdir_path}. Exception details: {e}")

    for region_file in ("region-U.txt", "region-I.txt"):
        region_path = os.path.join(drive_path, region_file)
        if os.path.exists(region_path):
            try:
                os.remove(region_path)
                logging.info(f"SUCCESS: Deleted region file {region_path}")
            except Exception as e:
                logging.error(f"FAILED to delete region file {region_path}. Exception details: {e}")

    logging.info(f"========== Finished EMPTY-DRIVE processing for {drive_path} ==========")
    return False


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


class UpdateWatcher:
    """
    Polls GitHub for new commits using cheap HTTP conditional requests so the
    WebUI can show an "update available" indicator without burning the API
    rate limit.

    Approach (matches the rate-limit-free local watcher pattern):
      * First request has no validator -> GitHub returns 200 + an ETag. We
        store that ETag as our baseline and do NOT flag an update (this is
        simply the version we are already running).
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
                resp.read()  # drain the body so the connection can be reused/closed
                if self.etag is None:
                    # Establish the baseline; this is the version we run now.
                    self.etag = new_etag
                    plog.debug(f"GitHub update watcher baseline ETag set: {new_etag}")
                else:
                    # 200 with a previously-known ETag => a genuinely new push.
                    self.etag = new_etag
                    self.update_available = True
                    self.status_mgr.set_update_available(True)
                    plog.warning("A new version of theDobinator is available on GitHub.")
        except urllib.error.HTTPError as e:
            if e.code == 304:
                plog.debug("GitHub update check: 304 Not Modified (up to date).")
            else:
                plog.warning(f"GitHub update check HTTP error {e.code}: {e.reason}")
        except Exception as e:
            plog.debug(f"GitHub update check network error (non-fatal): {e}")


def is_update_scheduled():
    """True if the user asked (via the WebUI) to apply an update after the current drive."""
    return os.path.exists(UPDATE_SCHEDULED_FLAG)


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


def save_queue(drive_paths):
    """Persist the not-yet-processed drives so they survive the update restart."""
    try:
        os.makedirs(os.path.dirname(SAVED_QUEUE_FILE), exist_ok=True)
        with open(SAVED_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(drive_paths), f)
        logging.info(f"Saved {len(drive_paths)} queued drive(s) for post-update resume.")
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


def trigger_update():
    """
    Launch the git updater detached. git_update.py shuts this program down via
    quit.bat, pulls the new code, then restarts it via dobWin.bat. The updater
    is started in its own detached process group so it is NOT killed when this
    program is terminated.
    """
    updater = os.path.join(PROJECT_ROOT, "configs", "git_updater", "git_update.py")
    if not os.path.exists(updater):
        logging.error(f"Cannot apply scheduled update: {updater} not found.")
        return
    logging.info(f"Launching scheduled update via {updater}")
    try:
        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            subprocess.Popen(
                [sys.executable, updater],
                cwd=PROJECT_ROOT,
                creationflags=flags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                [sys.executable, updater],
                cwd=PROJECT_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
    except Exception as e:
        logging.error(f"Failed to launch updater: {e}", exc_info=True)


def worker_thread(drive_queue, status_mgr):
    logging.info("Worker thread started. Waiting for drives...")
    while True:
        try:
            drive_path = drive_queue.get()
            if drive_path is None:  # Shutdown signal
                break
                
            vol_name = get_volume_name(drive_path)
            logging.info(f"Worker picked up drive: {drive_path} (Name: {vol_name})")
            
            # process_drive updates status numbers during its execution (1, 2, 3, etc.)
            had_issues = process_drive(drive_path)
            
            if had_issues is not None:
                # Add to completed drives
                status_mgr.add_completed_drive(vol_name, had_issues)
                
                # Set final status for this drive
                if had_issues:
                    status_mgr.update(status_number=11)
                else:
                    status_mgr.update(status_number=10)
                
                # Eject the drive
                logging.info(f"Ejecting drive {drive_path}...")
                eject_drive(drive_path)
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
                logging.warning("Scheduled update detected; applying now that the current drive is done.")
                remaining = drain_queue(drive_queue)
                save_queue(remaining)
                clear_update_scheduled()
                trigger_update()
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
    status_mgr.refresh_completed_drives()
    logging.info("Starting dobd.py drive monitor program...")

    drive_queue = queue.Queue()
    worker = threading.Thread(target=worker_thread, args=(drive_queue, status_mgr), daemon=True)
    worker.start()

    # Background watcher that polls GitHub for new commits (cheap ETag checks).
    update_watcher = UpdateWatcher(status_mgr, github_pat)
    poll_count = 0

    # Instantly add all currently connected drives to the known list
    logging.debug("Fetching initial list of connected drives...")
    known_drives = get_connected_drives()
    logging.info(f"Initial drives detected and added to ignore list: {', '.join(known_drives) if known_drives else 'None'}")

    # Resume any drives that were still queued when a scheduled update restarted
    # the program. They are enqueued directly (and marked known so the change
    # detector does not also re-add them).
    for drive in load_saved_queue():
        if os.path.exists(drive):
            known_drives.add(drive)
            drive_queue.put(drive)
            logging.info(f"Resuming queued drive after update restart: {drive}")
        else:
            logging.info(f"Saved drive {drive} is no longer connected; skipping resume.")

    plog.info("Entering main monitoring loop. Waiting for new drives...")

    try:
        while True:
            plog.debug("Polling for currently connected drives...")
            current_drives = get_connected_drives()

            # Find newly connected drives (in current but not in known)
            new_drives = current_drives - known_drives
            for drive in new_drives:
                plog.warning(f"--- NEW DRIVE DETECTED: {drive} ---")
                plog.debug(f"Adding {drive} to the internal ignore list and queue.")
                known_drives.add(drive)
                drive_queue.put(drive)

            # Find drives that were removed (in known but not in current)
            removed_drives = known_drives - current_drives
            for drive in removed_drives:
                plog.warning(f"--- DRIVE REMOVED: {drive} ---")
                plog.debug(f"Removing {drive} from the internal ignore list so it can be re-processed if inserted again.")
                known_drives.remove(drive)
                    
            # Reset status to 0 if no known drives are connected and queue is empty
            if not known_drives and drive_queue.empty():
                current_state = status_mgr._read_data()
                if current_state.get("StatusNumber", 0) != 0:
                    status_mgr.update(status_number=0)
                
            # Every 5th poll (~5 seconds) check GitHub for a newer version.
            poll_count += 1
            if poll_count % GITHUB_CHECK_EVERY == 0:
                update_watcher.trigger_check()

            # Sleep briefly before checking again to prevent high CPU usage
            time.sleep(1)
            
    except KeyboardInterrupt:
        plog.info("Program stopped by user via KeyboardInterrupt.")
    except Exception as e:
        plog.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
    finally:
        status_mgr.update(running=0)

if __name__ == "__main__":
    main()
