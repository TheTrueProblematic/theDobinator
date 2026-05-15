import time
import datetime
import json
import os
import subprocess
import logging

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIGS_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(CONFIGS_DIR)
STATUS_FILE = os.path.join(PROJECT_ROOT, "srvr", "status.json")
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "gitLog.log")

# Setup super verbose logging
VERBOSE_LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(VERBOSE_LOG_DIR, exist_ok=True)
VERBOSE_LOG_FILE = os.path.join(VERBOSE_LOG_DIR, "update.log")

logging.basicConfig(
    filename=VERBOSE_LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def log_event(message):
    logging.info(f"Main Log Event: {message}")
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"{now_str} - {message}\n"
    
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    existing_content = ""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        except Exception as e:
            logging.error(f"Error reading {LOG_FILE}: {e}")
            
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(log_line + existing_content)
    except Exception as e:
        logging.error(f"Error writing to {LOG_FILE}: {e}")

def is_busy():
    logging.debug(f"Checking if system is busy at {STATUS_FILE}")
    if not os.path.exists(STATUS_FILE):
        logging.debug("Status file does not exist, assuming not busy.")
        return False
    try:
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            running = data.get("Running", 0)
            status = data.get("StatusNumber", 0)
            logging.debug(f"Parsed status: Running={running}, StatusNumber={status}")
            
            # If Running is 0, it's not busy.
            if running == 0:
                logging.debug("Running is 0, system is not busy.")
                return False
            # If Running is 1, check StatusNumber
            if status in [0, 10, 11]:
                logging.debug("Status is idle (0, 10, 11), system is not busy.")
                return False
            logging.debug("System is busy processing files.")
            return True
    except Exception as e:
        logging.error(f"Failed to parse status file: {e}")
        return False

def do_update():
    logging.info("Starting do_update process...")
    if is_busy():
        logging.info("System determined as busy. Aborting update.")
        log_event("System is busy. Skipped clone for today.")
        return
        
    logging.info("System not busy. Initiating update process...")
    
    # 1. Shut down the Dobinator if it's running
    running = 0
    try:
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            running = data.get("Running", 0)
    except Exception as e:
        logging.error(f"Failed to read Running status: {e}")
        pass
        
    was_running = False
    if running == 1:
        logging.info("System was running. Initiating shutdown via quit.bat...")
        was_running = True
        quit_bat = os.path.join(PROJECT_ROOT, "src", "quit.bat")
        # CREATE_NO_WINDOW = 0x08000000
        # By piping \r\n to stdin, we bypass the 'pause' command at the end of quit.bat
        logging.debug(f"Running subprocess: {quit_bat}")
        result = subprocess.run(["cmd.exe", "/c", quit_bat], cwd=PROJECT_ROOT, creationflags=0x08000000, input=b"\r\n", capture_output=True)
        logging.debug(f"quit.bat output: {result.stdout}")
        logging.debug(f"quit.bat stderr: {result.stderr}")
        logging.info("Sleeping 5 seconds to ensure shutdown completes...")
        time.sleep(5) # wait for shutdown
    else:
        logging.info("System was not running. Skipping shutdown step.")
        
    # 2. Get latest copy of main branch and merge into local version
    logging.info("Running git pull origin main...")
    try:
        # Using shell=True and a string command helps locate git in PATH on Windows
        result = subprocess.run("git pull origin main", shell=True, cwd=PROJECT_ROOT, creationflags=0x08000000, capture_output=True, text=True)
        logging.debug(f"git pull output: {result.stdout}")
        logging.debug(f"git pull stderr: {result.stderr}")
        if result.returncode == 0:
            logging.info("Git pull completed successfully.")
            log_event("Cloned the latest version.")
        else:
            logging.error(f"Git pull failed with exit code {result.returncode}")
            log_event(f"Failed to clone the latest version (exit code {result.returncode})")
    except Exception as e:
        logging.error(f"Exception during git pull: {e}")
        log_event(f"Failed to clone the latest version: {e}")

    # 3. Start the program running again
    logging.info("Initiating startup via dobWin.bat unconditionally...")
    dobwin_path = os.path.join(PROJECT_ROOT, "dobWin.bat")
    logging.debug(f"Running subprocess: {dobwin_path}")
    try:
        # dobWin.bat toggles the program. Since we ensured it's off (or it was already off), this will turn it on.
        result = subprocess.run(f'cmd.exe /c "{dobwin_path}"', shell=True, cwd=PROJECT_ROOT, creationflags=0x08000000, input=b"\r\n", capture_output=True)
        logging.debug(f"dobWin.bat output: {result.stdout}")
        logging.debug(f"dobWin.bat stderr: {result.stderr}")
    except Exception as e:
        logging.error(f"Failed to start dobWin.bat: {e}")
        
    logging.info("do_update process completed.")
        
if __name__ == "__main__":
    do_update()
