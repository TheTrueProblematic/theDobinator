"""
git_update.py - Robust background updater for theDobinator.

Triggered by dobGit.vbs (or dobGitManual.bat) on a Windows host where the
project lives under C:\\theDobinator. Pulls the latest main from
https://github.com/TheTrueProblematic/theDobinator.git and resets the working
tree to match. Files in .gitignore (logs, srvr/status.json, etc.) are left
alone.

Design notes for future agents:
* Uses an absolute path to git.exe found via shutil.which() with fallbacks
  to common Windows install locations. PATH is NOT trusted because this
  script is typically launched by wscript->pythonw on logon with a sparse
  environment.
* All subprocess calls use list-arg form (NO shell=True), capture stdout
  and stderr, redirect stdin to DEVNULL, and verify returncode. The earlier
  silent-failure regression was caused by shell=True + missing returncode
  checks on the early git commands (init / remote add / fetch).
* Configures GIT_TERMINAL_PROMPT=0 so any auth prompt fails fast instead
  of hanging the daemon.
* Marks PROJECT_ROOT as safe.directory to dodge Git's "dubious ownership"
  refusal (exit 128) that newer Git versions enforce.
* If reset --hard fails because untracked working-tree files conflict with
  incoming tracked files, the conflicting untracked files are removed and
  the reset is retried once.
"""

import os
import sys
import json
import shutil
import subprocess
import datetime
import time
import logging

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIGS_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(CONFIGS_DIR)

REPO_URL = "https://github.com/TheTrueProblematic/theDobinator.git"
BRANCH = "main"

VERBOSE_LOG_DIR = os.path.join(CONFIGS_DIR, "logs")
os.makedirs(VERBOSE_LOG_DIR, exist_ok=True)
VERBOSE_LOG_FILE = os.path.join(VERBOSE_LOG_DIR, "update.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(VERBOSE_LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

MAIN_LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "gitLog.log")

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def log_event(message):
    """Prepend a one-line event to the user-facing gitLog.log."""
    timestamp = datetime.datetime.now().strftime("%a %m/%d/%Y %H:%M:%S.%f")[:-4]
    entry = f"{timestamp} - {message}\n"
    logging.info(f"[MAIN LOG] {message}")

    os.makedirs(os.path.dirname(MAIN_LOG_FILE), exist_ok=True)
    existing = ""
    if os.path.exists(MAIN_LOG_FILE):
        try:
            with open(MAIN_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                existing = f.read()
        except Exception as e:
            logging.error(f"Could not read existing gitLog.log: {e}")
    try:
        with open(MAIN_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(entry + existing)
    except Exception as e:
        logging.error(f"Could not write gitLog.log: {e}")


def find_git_executable():
    """Locate git on disk. PATH may be sparse when launched from wscript."""
    on_path = shutil.which("git")
    if on_path:
        logging.info(f"Found git on PATH: {on_path}")
        return on_path

    candidates = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\git.exe"),
        os.path.expandvars(r"%ProgramFiles%\Git\cmd\git.exe"),
        os.path.expandvars(r"%ProgramFiles%\Git\bin\git.exe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            logging.info(f"Found git at fallback location: {path}")
            return path

    logging.critical(
        "git executable not found. Looked on PATH and the standard "
        "Git-for-Windows install locations."
    )
    return None


def run_git(git_exe, args, cwd, check=True, timeout=300):
    """
    Run a git subcommand. List-arg form, no shell, stdin closed, output
    captured. Returns the CompletedProcess. Raises RuntimeError on
    non-zero exit when check=True.
    """
    cmd = [git_exe, *args]
    display = " ".join(cmd)
    logging.info(f"[GIT EXEC] {display}   (cwd={cwd})")

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as e:
        logging.critical(f"[GIT FAIL] subprocess raised for {display}: {e}", exc_info=True)
        raise

    stdout = result.stdout.decode("utf-8", errors="replace").strip()
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    logging.info(f"[GIT EXIT] {result.returncode}  for: {display}")
    if stdout:
        logging.info(f"[GIT STDOUT]\n{stdout}")
    if stderr:
        logging.info(f"[GIT STDERR]\n{stderr}")

    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed with exit code {result.returncode}: {stderr or stdout}"
        )

    result._stdout_text = stdout
    result._stderr_text = stderr
    return result


def is_busy():
    status_file = os.path.join(PROJECT_ROOT, "srvr", "status.json")
    logging.debug(f"Checking busy status at {status_file}")
    if not os.path.exists(status_file):
        logging.debug("status.json missing - treating as NOT busy.")
        return False
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        running = data.get("Running", 0)
        status_num = data.get("StatusNumber", 0)
        logging.debug(f"status.json -> Running={running}, StatusNumber={status_num}")
        if running == 0:
            return False
        if status_num in (0, 10, 11):
            return False
        return True
    except Exception as e:
        logging.error(f"Error reading status.json: {e}")
        return False


def is_running():
    status_file = os.path.join(PROJECT_ROOT, "srvr", "status.json")
    if not os.path.exists(status_file):
        return False
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("Running", 0) == 1
    except Exception:
        return False


def shutdown_program():
    quit_path = os.path.join(PROJECT_ROOT, "src", "quit.bat")
    if not os.path.exists(quit_path):
        logging.warning(f"quit.bat not found at {quit_path}; skipping shutdown.")
        return
    logging.info(f"Running quit.bat at {quit_path}")
    try:
        # Pipe a newline via `input` to satisfy the `pause` at the end of the
        # .bat without hanging. Do NOT also pass stdin= - the two are mutually
        # exclusive and `subprocess.run` raises ValueError if both are given.
        result = subprocess.run(
            ["cmd.exe", "/c", quit_path],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            input=b"\r\n",
            timeout=60,
            creationflags=CREATE_NO_WINDOW,
        )
        logging.debug(f"quit.bat exit={result.returncode}")
        if result.stdout:
            logging.debug(f"quit.bat stdout: {result.stdout.decode('utf-8', 'replace').strip()}")
        if result.stderr:
            logging.debug(f"quit.bat stderr: {result.stderr.decode('utf-8', 'replace').strip()}")
    except Exception as e:
        logging.error(f"quit.bat raised: {e}", exc_info=True)


def startup_program():
    dobwin_path = os.path.join(PROJECT_ROOT, "dobWin.bat")
    if not os.path.exists(dobwin_path):
        logging.warning(f"dobWin.bat not found at {dobwin_path}; skipping startup.")
        return
    logging.info(f"Running dobWin.bat at {dobwin_path}")
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", dobwin_path],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            input=b"\r\n",
            timeout=60,
            creationflags=CREATE_NO_WINDOW,
        )
        logging.debug(f"dobWin.bat exit={result.returncode}")
        if result.stdout:
            logging.debug(f"dobWin.bat stdout: {result.stdout.decode('utf-8', 'replace').strip()}")
        if result.stderr:
            logging.debug(f"dobWin.bat stderr: {result.stderr.decode('utf-8', 'replace').strip()}")
    except Exception as e:
        logging.error(f"dobWin.bat raised: {e}", exc_info=True)


def _is_valid_repo(git_exe):
    r = run_git(git_exe, ["rev-parse", "--is-inside-work-tree"], PROJECT_ROOT, check=False)
    return r.returncode == 0 and r._stdout_text == "true"


def _ensure_safe_directory(git_exe):
    safe_path = PROJECT_ROOT.replace("\\", "/")
    run_git(
        git_exe,
        ["config", "--global", "--add", "safe.directory", safe_path],
        PROJECT_ROOT,
        check=False,
    )


def _initialize_repo(git_exe):
    """Set up PROJECT_ROOT as a fresh git working tree pointing at origin/main."""
    logging.info("Initializing fresh git repository in PROJECT_ROOT.")

    bad_git_dir = os.path.join(PROJECT_ROOT, ".git")
    if os.path.isdir(bad_git_dir):
        logging.info(f"Removing stale .git folder at {bad_git_dir}")
        try:
            shutil.rmtree(bad_git_dir)
        except Exception as e:
            logging.error(f"Could not remove stale .git folder: {e}")
            raise

    run_git(git_exe, ["init"], PROJECT_ROOT)
    run_git(
        git_exe,
        ["symbolic-ref", "HEAD", f"refs/heads/{BRANCH}"],
        PROJECT_ROOT,
        check=False,
    )
    run_git(git_exe, ["config", "user.email", "updater@thedobinator.local"], PROJECT_ROOT)
    run_git(git_exe, ["config", "user.name", "Dobinator Auto-Updater"], PROJECT_ROOT)
    run_git(git_exe, ["remote", "add", "origin", REPO_URL], PROJECT_ROOT)


def _ensure_remote_url(git_exe):
    r = run_git(git_exe, ["remote", "get-url", "origin"], PROJECT_ROOT, check=False)
    current = r._stdout_text if r.returncode == 0 else ""
    if current == REPO_URL:
        logging.info(f"origin URL already correct: {current}")
        return
    if current:
        logging.info(f"Updating origin URL from '{current}' to '{REPO_URL}'")
        run_git(git_exe, ["remote", "set-url", "origin", REPO_URL], PROJECT_ROOT)
    else:
        logging.info(f"Adding origin URL '{REPO_URL}'")
        run_git(git_exe, ["remote", "add", "origin", REPO_URL], PROJECT_ROOT)


def _resolve_untracked_conflicts(git_exe):
    """
    Remove local untracked files that exist in origin/<BRANCH>'s tree so the
    next reset --hard can checkout them without complaint.
    """
    r = run_git(
        git_exe,
        ["ls-tree", "-r", "--name-only", f"origin/{BRANCH}"],
        PROJECT_ROOT,
        check=False,
    )
    if r.returncode != 0:
        logging.warning("Could not enumerate origin tree; skipping untracked cleanup.")
        return

    tracked_paths = [line for line in r._stdout_text.splitlines() if line.strip()]
    removed = []
    for rel in tracked_paths:
        abs_path = os.path.join(PROJECT_ROOT, rel.replace("/", os.sep))
        if not os.path.exists(abs_path):
            continue
        check = run_git(
            git_exe,
            ["ls-files", "--error-unmatch", "--", rel],
            PROJECT_ROOT,
            check=False,
        )
        if check.returncode != 0:
            try:
                os.remove(abs_path)
                removed.append(rel)
            except Exception as e:
                logging.warning(f"Could not remove conflicting untracked file {rel}: {e}")
    if removed:
        sample = removed[:20]
        suffix = "..." if len(removed) > 20 else ""
        logging.info(f"Removed {len(removed)} conflicting untracked files: {sample}{suffix}")
    else:
        logging.info("No conflicting untracked files needed removal.")


def do_git_update(git_exe):
    """Fetch origin/main and hard-reset the working tree onto it."""
    logging.info(f"PROJECT_ROOT contents at start: {sorted(os.listdir(PROJECT_ROOT))}")

    _ensure_safe_directory(git_exe)

    if not _is_valid_repo(git_exe):
        _initialize_repo(git_exe)
    else:
        logging.info("Existing git repository detected; verifying origin URL.")
        _ensure_remote_url(git_exe)

    logging.info(f"Fetching origin/{BRANCH}...")
    run_git(git_exe, ["fetch", "--prune", "origin", BRANCH], PROJECT_ROOT)

    r_before = run_git(
        git_exe, ["rev-parse", "--verify", "--short", "HEAD"], PROJECT_ROOT, check=False
    )
    before_sha = r_before._stdout_text if r_before.returncode == 0 else "(none)"

    r_after = run_git(
        git_exe, ["rev-parse", "--short", f"origin/{BRANCH}"], PROJECT_ROOT
    )
    after_sha = r_after._stdout_text

    logging.info(f"HEAD ({before_sha}) vs origin/{BRANCH} ({after_sha})")

    logging.info(f"Resetting working tree to origin/{BRANCH}...")
    first_try = run_git(
        git_exe, ["reset", "--hard", f"origin/{BRANCH}"], PROJECT_ROOT, check=False
    )
    if first_try.returncode != 0:
        logging.warning(
            f"Initial reset --hard failed: {first_try._stderr_text}. "
            "Cleaning conflicting untracked files and retrying."
        )
        _resolve_untracked_conflicts(git_exe)
        run_git(git_exe, ["reset", "--hard", f"origin/{BRANCH}"], PROJECT_ROOT)

    run_git(
        git_exe,
        ["branch", "--set-upstream-to", f"origin/{BRANCH}", BRANCH],
        PROJECT_ROOT,
        check=False,
    )

    r_final = run_git(git_exe, ["rev-parse", "--short", "HEAD"], PROJECT_ROOT)
    final_sha = r_final._stdout_text
    logging.info(f"Update complete. HEAD is now at {final_sha}.")
    return before_sha, final_sha


def do_update():
    logging.info("=" * 64)
    logging.info(f"git_update.py starting at {datetime.datetime.now().isoformat()}")
    logging.info(f"SCRIPT_DIR    = {SCRIPT_DIR}")
    logging.info(f"CONFIGS_DIR   = {CONFIGS_DIR}")
    logging.info(f"PROJECT_ROOT  = {PROJECT_ROOT}")
    logging.info(f"REPO_URL      = {REPO_URL}")
    logging.info(f"BRANCH        = {BRANCH}")
    logging.info(f"Python exe    = {sys.executable}")
    logging.info(f"OS / platform = {sys.platform}")
    logging.info("=" * 64)

    if is_busy():
        logging.info("System is busy. Skipping today's update.")
        log_event("System busy. Skipped update.")
        return

    git_exe = find_git_executable()
    if not git_exe:
        log_event("Update failed: git.exe could not be located on this system.")
        return

    was_running = is_running()
    if was_running:
        logging.info("Program is currently running; shutting it down first.")
        shutdown_program()
        time.sleep(5)
    else:
        logging.info("Program is not running; no shutdown needed.")

    try:
        before_sha, after_sha = do_git_update(git_exe)
        if before_sha == after_sha and before_sha != "(none)":
            log_event(f"Already up to date at {after_sha}.")
        else:
            log_event(f"Updated working tree: {before_sha} -> {after_sha}.")
    except Exception as e:
        logging.critical(f"Update failed: {e}", exc_info=True)
        log_event(f"Update failed: {e}")
    finally:
        logging.info("Restarting the program via dobWin.bat.")
        startup_program()
        logging.info("git_update.py finished.")


if __name__ == "__main__":
    try:
        do_update()
    except Exception as e:
        logging.critical(f"Unhandled exception in git_update.py: {e}", exc_info=True)
