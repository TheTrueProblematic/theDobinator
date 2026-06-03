# TheDobinator - Agent Policies & Guidelines

This document outlines the core policies, design patterns, and operational knowledge for any AI agents working on "theDobinator" project. 

## 1. Project Context & Tone
* **True Purpose:** The project automates the copying of files and setup processes for data drive builds.
* **Thematic Tone:** When writing user-facing documentation (like the README), maintain a serious, ironic tone suggesting that the robot is using AI to replace "Garrett 'Ace' Dobson."

## 2. Drive Monitoring & State Management
* **Ephemeral State:** The list of "known" or "ignored" drives must be stored in memory (e.g., a Python `set()`) so that the state resets completely every time the program restarts.
* **Startup Behavior:** The program must instantly fetch all connected drives upon startup and add them to the ignore list. It should only ever process drives that are connected *after* the script has begun running.
* **Re-insertion Processing:** If a drive is removed, it must be detected and removed from the internal ignore list. This ensures that if the same drive is re-inserted, it will be treated as a "new" connection and processed again.
* **Efficiency:** The main monitoring loop should poll frequently (e.g., every 2 seconds) using efficient OS-level calls (like `ctypes.windll.kernel32.GetLogicalDrives()` on Windows) rather than aggressive file-system scanning.

## 3. Drive Processing Logic (`dobd.py`)
* **Target Identification & Routing (`handle_new_drive`):** On detection, a drive is routed by whether it has a `packfiles.txt` on its root. **With** it → queued immediately for the full build via `process_drive()`. **Without** it (a "blank" drive) → registered in `DriveManager` as *blank-awaiting* and surfaced in the WebUI as a popup; it is **not** processed until the user supplies a Drive Name + Country. Both kinds appear in the WebUI "Pending Drives" list (blank drives only after they've been submitted).
* **Drive job model & `DriveManager`:** Queue items are job dicts `{path, kind: "packfiles"|"country", name, sizeTB, iso}`. `DriveManager` (thread-safe) tracks two lists published to `status.json` for the WebUI: `BlankDrives` (`{token, sizeTB}`, awaiting input — each `token` is unique so popups serialize correctly even if a drive letter is reused) and `PendingDrives` (`{name, sizeTB}`, queued but not started).
* **Blank-drive submission IPC:** The WebUI popup POSTs `{token, name, country}` to the companion API's `/submit-drive`, which drops a JSON file into `logs/submissions/`. The monitor loop's `consume_submissions()` validates it, builds a `country` job, and queues it. The user-entered name is sanitized (trim + internal whitespace → underscores) on **both** sides.
* **Country-Drive Workflow (`process_country_drive`):** No LLM. (1) Quick-format the drive as NTFS and apply the chosen name (`format_drive`, status 9). (2) Region straight from the country: `USA` → US (`"u"`), anything else → International (`"i"`). (3) Copy regional base files (`copy_region_files`, status 3). (4) Non-US only: copy the three country-specific sets keyed on the ISO Alpha-3 code (`copy_country_files`, status 8 — imagery file(s) `<iso>_*` from `…\imagery\GLOBAL\COUNTRIES`, the `<iso>` vector folder from `…\vector\Baseline`, and the `<iso>` geocode folder from `…\geocode`). (5) Clean up `dobDir`; report completed.
* **WebUI Status Numbers:** Full build uses steps 1–7; the country-drive path adds step 9 ("Formatting Drive") and step 8 ("Copying Country Files", whose progress bar reuses the *main* file counters). Steps 1–9 are all "processing" (see `isProcessing` in `app.js`); 0 is idle and 10/11 are terminal. `copy_region_files` accepts a `status_number` arg (defaults to step 3).
* **`status.json` concurrency:** It is now written from multiple threads (worker + monitor loop), so `StatusManager` guards every read-modify-write with an `RLock`.
* **Initial Actions:** When a target drive is identified, the first action is to create a `dobDir` directory on the root of the drive.
* **Modularity:** Any new processing functions should be called from within the explicitly marked comment section in the `process_drive()` function to keep the script organized.
* **Temporary Files:** If the python file ever needs to make any temporary files, it must put them in the `dobDir` directory on the target drive.

## 4. Logging & Verbose Tracking Policy
* **Log Location:** All logs must be written to `logs/dobLog.log` at the root of the project.
* **Auto-Resetting:** The log file must reset on every run. Use the file handler mode `'w'` (overwrite) instead of `'a'` (append).
* **Verbosity Requirement:** Logging must be *extremely* verbose to ensure any problems can be easily diagnosed. Use the standard Python `logging` module and output to both the file and the console.
* **Severity Levels:**
    * `DEBUG`: Use for highly verbose tracing, variable tracking, polling loop updates, path checking, and internal state modifications.
    * `INFO`: Use for standard operational steps, program startup/shutdown, and confirming processing checkpoints.
    * `WARNING`: Use strictly for alerting when physical drive changes occur (a new drive is detected or a drive is removed).
    * `ERROR/CRITICAL`: Use for exceptions, failed folder creations, and stack traces.
* **Per-Thread / Per-Program Log Separation (going forward):** Every new Python thread, and every new standalone Python file/program added to the project, must write to its **own dedicated log file** in `logs/` (e.g. `logs/<name>.log`) with a matching `logs/<name>Prev.log` that keeps the last 5 runs — the same rule applied to `dobLogPrev.log`. Do **not** funnel a new thread's output into `dobLog.log`; keep each concern in its own file so the main log stays readable.
    * **Precedent:** The polling process (the drive-scanning loop in `main()` plus the GitHub `UpdateWatcher`) logs to `logs/pollingLog.log` / `logs/pollingLogPrev.log` via a dedicated `logging.getLogger("dobinator.polling")` (referenced as `plog`) configured with `propagate = False` so its records never reach `dobLog.log`. The rest of the bot keeps using the root logger → `dobLog.log`.
    * **Rotation:** Use the shared `rotate_prev_log(log_file, prev_log_file)` helper for the `*Prev.log` roll-over so every log behaves identically. Apply the same `LessNoiseFilter` to new handlers, and add the shared console `stream_handler` to the new logger so nothing disappears from the live console.

## 5. Living Document Policy
* **Knowledge Preservation:** If you discover a "gotcha", a repeated requirement, or a useful piece of project context that would benefit future agents, you must document it here immediately to ensure continuous knowledge preservation.
* **Open Interpreter Dependency Gotcha:** When calling `OpenInterpreter` from within a Python script (especially if `open-interpreter` was installed via `pipx`), Open Interpreter will attempt to use the script's `sys.executable` to spawn Jupyter kernels. If the system Python environment running the script does not have `ipykernel` installed, Open Interpreter will **hang silently forever** when asked to execute Python code. Always ensure `python -m pip install ipykernel` has been run on the host Python.

## 6. Background Git Updater Architecture & History
* **Goal:** Automate pulling the latest `main` from `https://github.com/TheTrueProblematic/theDobinator.git` daily at 5:00 AM. The updater must (1) skip the run if the program is mid-task, (2) cleanly shut down the program via `src/quit.bat`, (3) bring the working tree to match `origin/main`, and (4) relaunch via `dobWin.bat`.
* **Components:**
    * `configs/git_setup.bat` — Run once by `configs/win_setup.bat`. Installs Git via `winget` if missing, refreshes PATH, registers `PROJECT_ROOT` as a `safe.directory` globally, kills stale watchers, creates the `Dobinator Git Updater` scheduled task (on-logon), and starts `dobGit.vbs` immediately.
    * `configs/dobGit.vbs` — Long-running watcher. Resolves `pythonw.exe` from a list of standard install locations (PATH is unreliable when launched from `wscript` at logon), then loops forever: sleep until the next 5:00 AM, run `git_update.py`, log the exit code, repeat. Errors inside the loop are swallowed (`On Error Resume Next`) so a single bad day does not kill the watcher.
    * `configs/git_updater/git_update.py` — The actual update logic.
    * `configs/dobGitManual.bat` — Manual trigger; runs `git_update.py` directly and pauses so the operator can inspect results.
* **Why the Git approach kept "silently succeeding" but not updating:** Two compounding bugs in the prior implementation.
    1. `subprocess.run("git init", shell=True, ...)` had **no return-code check**. Only the final `git reset --hard` was checked. If `git.exe` was unresolvable from PATH (very common when launched by `wscript`->`pythonw` on logon — winget puts Git on user-PATH which a logon-task environment may not inherit), every preceding step failed silently and the final reset failed with a generic non-zero, mis-attributed to "no changes".
    2. `git remote add origin` fails on a second run because the remote already exists, but again, the failure was unchecked. Newer Git versions also refuse to operate on directories with "dubious ownership" (exit 128) — easy to hit when the project was unzipped/copied by a different user than the one running the scheduled task.
* **Current (working) design — must be preserved:**
    * `find_git_executable()` locates `git.exe` via `shutil.which` and a fallback list of typical Git-for-Windows install locations. Never trust PATH.
    * `run_git()` is the only way to call git: list-arg form (NEVER `shell=True`), `stdin=DEVNULL`, both stdout and stderr captured and **fully logged**, return-code checked by default, with `GIT_TERMINAL_PROMPT=0` set so any credential prompt fails fast instead of hanging the daemon.
    * `_ensure_safe_directory()` adds `PROJECT_ROOT` to global `safe.directory` on every run (idempotent).
    * `_is_valid_repo()` uses `git rev-parse --is-inside-work-tree` — relying on the presence of a `.git` folder is not sufficient (a partial/corrupt `.git` from an earlier failed init looks "present").
    * If not a valid repo, `_initialize_repo()` wipes any stale `.git`, runs `git init --initial-branch main`, sets local identity, and adds origin.
    * If it is a valid repo, `_ensure_remote_url()` rewrites origin's URL when it disagrees with `REPO_URL`.
    * After `git fetch --prune origin main`, the tree is brought up to date with `git reset --hard origin/main`. If that fails because of conflicting untracked files (paths present locally as untracked but tracked in origin), `_resolve_untracked_conflicts()` deletes only those specific files and the reset is retried once. Files matched by `.gitignore` (logs, `srvr/status.json`, `.DS_Store`) are always left alone — that's a property of `reset --hard`.
* **Do NOT regress to:** `shell=True`, `git pull` without explicit fetch+reset, skipping return-code checks on the early git commands, or the ZIP-download approach (it cannot delete files that were removed upstream, so the working tree drifts).
