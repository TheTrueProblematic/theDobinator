import time
import datetime
import json
import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIGS_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(CONFIGS_DIR)
STATUS_FILE = os.path.join(PROJECT_ROOT, "srvr", "status.json")
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "gitLog.log")

def log_event(message):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"{now_str} - {message}\n"
    
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    existing_content = ""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        except Exception as e:
            print(f"Error reading {LOG_FILE}: {e}")
            
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(log_line + existing_content)
    except Exception as e:
        print(f"Error writing to {LOG_FILE}: {e}")

def is_busy():
    if not os.path.exists(STATUS_FILE):
        return False
    try:
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # If Running is 0, it's not busy.
            if data.get("Running", 0) == 0:
                return False
            # If Running is 1, check StatusNumber
            status = data.get("StatusNumber", 0)
            if status in [0, 10, 11]:
                return False
            return True
    except:
        return False

def do_update():
    if is_busy():
        log_event("System is busy. Skipped clone for today.")
        return
        
    print("System not busy. Initiating update process...")
    
    # 1. Shut down the Dobinator if it's running
    running = 0
    try:
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            running = data.get("Running", 0)
    except:
        pass
        
    was_running = False
    if running == 1:
        was_running = True
        quit_bat = os.path.join(PROJECT_ROOT, "src", "quit.bat")
        # CREATE_NO_WINDOW = 0x08000000
        subprocess.run(["cmd.exe", "/c", quit_bat], cwd=PROJECT_ROOT, creationflags=0x08000000)
        time.sleep(5) # wait for shutdown
        
    # 2. Get latest copy of main branch and merge into local version
    # "get the latest copy of the main branch from https://github.com/TheTrueProblematic/theDobinator.git and merge it into the local version."
    try:
        subprocess.run(["git", "pull", "origin", "main"], cwd=PROJECT_ROOT, creationflags=0x08000000)
        log_event("Cloned the latest version.")
    except Exception as e:
        log_event(f"Failed to clone the latest version: {e}")

    # 3. Start the program running again
    if was_running:
        dobwin_path = os.path.join(PROJECT_ROOT, "dobWin.bat")
        subprocess.run(["cmd.exe", "/c", dobwin_path], cwd=PROJECT_ROOT, creationflags=0x08000000)
        
if __name__ == "__main__":
    do_update()
