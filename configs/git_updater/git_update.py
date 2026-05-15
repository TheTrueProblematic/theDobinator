import os
import json
import subprocess
import datetime
import time
import logging
import urllib.request
import zipfile
import io
import shutil
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIGS_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(CONFIGS_DIR)
LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "gitLog.log")

# Setup super verbose logging
VERBOSE_LOG_DIR = os.path.join(CONFIGS_DIR, "logs")
os.makedirs(VERBOSE_LOG_DIR, exist_ok=True)
VERBOSE_LOG_FILE = os.path.join(VERBOSE_LOG_DIR, "update.log")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(VERBOSE_LOG_FILE, mode='w'),
        logging.StreamHandler()
    ]
)

def log_event(message):
    timestamp = datetime.datetime.now().strftime("%a %m/%d/%Y %H:%M:%S.%f")[:-4]
    log_entry = f"{timestamp} - {message}\n"
    logging.info(f"Main Log Event: {message}")
    
    # Prepend to the main log file
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            existing_logs = f.read()
    else:
        existing_logs = ""
        
    with open(LOG_FILE, 'w') as f:
        f.write(log_entry + existing_logs)

def is_busy():
    status_file = os.path.join(PROJECT_ROOT, "srvr", "status.json")
    logging.debug(f"Checking if system is busy at {status_file}")
    if not os.path.exists(status_file):
        logging.debug("status.json does not exist. System is not busy.")
        return False
        
    try:
        with open(status_file, 'r') as f:
            data = json.load(f)
            
        running = data.get("Running", 0)
        status_num = data.get("StatusNumber", 0)
        logging.debug(f"Parsed status: Running={running}, StatusNumber={status_num}")
        
        if running == 0:
            logging.debug("Running is 0, system is not busy.")
            return False
            
        # Idle states
        if status_num in [0, 10, 11]:
            logging.debug(f"Status is idle ({status_num}), system is not busy.")
            return False
            
        logging.debug(f"System is busy. StatusNumber={status_num}")
        return True
    except Exception as e:
        logging.error(f"Error reading status.json: {e}")
        return False

def is_running():
    status_file = os.path.join(PROJECT_ROOT, "srvr", "status.json")
    if not os.path.exists(status_file):
        return False
        
    try:
        with open(status_file, 'r') as f:
            data = json.load(f)
        return data.get("Running", 0) == 1
    except Exception:
        return False

def do_update():
    logging.info("Starting do_update process...")
    
    if is_busy():
        logging.info("System determined as busy. Aborting update.")
        log_event("System is busy. Skipped clone for today.")
        return

    logging.info("System not busy. Initiating update process...")

    if is_running():
        logging.info("System was running. Initiating shutdown via quit.bat...")
        quit_path = os.path.join(PROJECT_ROOT, "src", "quit.bat")
        # Pass \r\n to bypass any pause command at the end of the bat file
        logging.debug(f"Running subprocess: {quit_path}")
        result = subprocess.run(f'cmd.exe /c "{quit_path}"', shell=True, cwd=PROJECT_ROOT, creationflags=0x08000000, input=b"\r\n", capture_output=True)
        logging.debug(f"quit.bat output: {result.stdout}")
        logging.debug(f"quit.bat stderr: {result.stderr}")
        
        logging.info("Sleeping 5 seconds to ensure shutdown completes...")
        time.sleep(5)
    else:
        logging.info("System was not running. Skipping shutdown step.")
        
    # 2. Get latest copy of main branch via ZIP download
    logging.info("Downloading latest repository ZIP from GitHub...")
    # Add a timestamp query parameter to explicitly bust GitHub's CDN cache!
    cache_buster = int(time.time())
    zip_url = f"https://github.com/TheTrueProblematic/theDobinator/archive/refs/heads/main.zip?t={cache_buster}"
    
    try:
        req = urllib.request.Request(zip_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            zip_content = response.read()
        
        logging.info("Download complete. Extracting files...")
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zip_ref:
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_ref.extractall(temp_dir)
                
                # GitHub ZIPs extract into a single top-level folder (e.g., theDobinator-main)
                extracted_items = os.listdir(temp_dir)
                if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_dir, extracted_items[0])):
                    extracted_root = os.path.join(temp_dir, extracted_items[0])
                else:
                    extracted_root = temp_dir
                
                # Copy files directly over the local ones
                logging.info(f"Applying new files from {extracted_root} to {PROJECT_ROOT}...")
                copied_items = []
                for item in os.listdir(extracted_root):
                    s = os.path.join(extracted_root, item)
                    d = os.path.join(PROJECT_ROOT, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                        copied_items.append(f"[DIR] {item}")
                    else:
                        shutil.copy2(s, d)
                        copied_items.append(f"[FILE] {item}")
                        
                logging.info(f"Successfully applied {len(copied_items)} items: {', '.join(copied_items)}")
                        
        logging.info("ZIP download and extraction completed successfully.")
        log_event("Downloaded and applied the latest version.")
    except Exception as e:
        logging.error(f"Exception during download/extraction: {e}")
        log_event(f"Failed to apply the latest version: {e}")

    # 3. Start the program running again
    logging.info("Initiating startup via dobWin.bat unconditionally...")
    dobwin_path = os.path.join(PROJECT_ROOT, "dobWin.bat")
    logging.debug(f"Running subprocess: {dobwin_path}")
    try:
        # dobWin.bat toggles the program.
        result = subprocess.run(f'cmd.exe /c "{dobwin_path}"', shell=True, cwd=PROJECT_ROOT, creationflags=0x08000000, input=b"\r\n", capture_output=True)
        logging.debug(f"dobWin.bat output: {result.stdout}")
        logging.debug(f"dobWin.bat stderr: {result.stderr}")
    except Exception as e:
        logging.error(f"Failed to start dobWin.bat: {e}")
        
    logging.info("do_update process completed.")
        
if __name__ == "__main__":
    try:
        do_update()
    except Exception as e:
        logging.critical(f"Unhandled exception in git_update.py: {e}", exc_info=True)
