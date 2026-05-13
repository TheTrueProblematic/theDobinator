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
* **Target Identification:** Only process drives that contain a specific marker file (`packfiles.txt`) on their root directory. If this file is not found, the drive should be ignored and the script must immediately return to the monitoring loop.
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

## 5. Living Document Policy
* **Knowledge Preservation:** If you discover a "gotcha", a repeated requirement, or a useful piece of project context that would benefit future agents, you must document it here immediately to ensure continuous knowledge preservation.
* **Open Interpreter Dependency Gotcha:** When calling `OpenInterpreter` from within a Python script (especially if `open-interpreter` was installed via `pipx`), Open Interpreter will attempt to use the script's `sys.executable` to spawn Jupyter kernels. If the system Python environment running the script does not have `ipykernel` installed, Open Interpreter will **hang silently forever** when asked to execute Python code. Always ensure `python -m pip install ipykernel` has been run on the host Python.
