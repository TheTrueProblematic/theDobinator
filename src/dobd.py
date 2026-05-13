import os
import time
import ctypes
import string
import logging
import csv

# --- Logging Setup ---
# Find the project root by going up one level from the 'src' directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

# Ensure the logs directory exists
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LOG_FILE = os.path.join(LOGS_DIR, "dobLog.log")

# Configure logging to write to the file (resetting every run with mode='w')
# and also output to the console.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'),
        logging.StreamHandler()
    ]
)

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


class LLM:
    """
    A class to interact with a remote LLM using OpenInterpreter.
    Each instance maintains its own context and conversation history separately.
    """
    def __init__(self, ip_address="192.168.11.65", port=1234, working_directory=None, 
                 model="openai/qwen/qwen3.6-27b", context_window=40000, api_key="fake_key", max_tokens=4096):
        self.ip_address = ip_address
        self.port = port
        self.working_directory = working_directory
        self.model = model
        self.context_window = context_window
        self.api_key = api_key
        self.max_tokens = max_tokens
        
        # Try to import open-interpreter, with a fallback to the common pipx installation path
        try:
            from interpreter import OpenInterpreter
        except ImportError:
            import sys
            import os
            # Expand ~ to the user's home directory to find the pipx environment
            pipx_path = os.path.expanduser(r"~\pipx\venvs\open-interpreter\Lib\site-packages")
            if os.path.exists(pipx_path) and pipx_path not in sys.path:
                sys.path.append(pipx_path)
            
            try:
                from interpreter import OpenInterpreter
            except ImportError:
                logging.error("Failed to import 'interpreter'. Ensure Open Interpreter is installed (e.g., via pipx or in the current environment).")
                raise

        # Initialize an isolated OpenInterpreter instance to keep conversation history separate
        self.interpreter = OpenInterpreter()
        self.interpreter.llm.api_base = f"http://{self.ip_address}:{self.port}/v1"
        self.interpreter.llm.model = self.model
        self.interpreter.llm.api_key = self.api_key
        self.interpreter.llm.context_window = self.context_window
        self.interpreter.llm.max_tokens = self.max_tokens
        self.interpreter.auto_run = True  # Avoids prompting for user confirmation, similar to -y
        
        if hasattr(self.interpreter.llm, 'temperature'):
            self.interpreter.llm.temperature = 0

        logging.debug(f"LLM instance initialized using model {self.model} at {self.interpreter.llm.api_base}")

    def use(self, prompt):
        """Runs the prompt in the working directory set during initialization."""
        if not self.working_directory:
            logging.warning("No working directory set for LLM instance. Using current directory.")
            return self.useLoc(prompt, os.getcwd())
        return self.useLoc(prompt, self.working_directory)

    def useLoc(self, prompt, directory):
        """Runs the prompt in the specified directory."""
        original_cwd = os.getcwd()
        
        # Validate and change to the specified directory
        if directory and os.path.exists(directory):
            os.chdir(directory)
            logging.debug(f"LLM executing in directory: {directory}")
        else:
            logging.error(f"Directory {directory} does not exist. Cannot execute prompt.")
            return None
            
        try:
            logging.info(f"LLM executing prompt: '{prompt}'")
            # The interpreter.chat method handles the execution and conversation history
            response = self.interpreter.chat(prompt)
            return response
        except Exception as e:
            logging.error(f"LLM encountered an error during execution: {e}", exc_info=True)
            return None
        finally:
            # Always revert back to the original working directory
            if directory and os.path.exists(directory):
                os.chdir(original_cwd)
                logging.debug(f"LLM restored directory to: {original_cwd}")



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

def classifyRegion(llm_instance, drive_path, work_vars):
    """
    Uses the provided LLM instance to classify the region of the drive.
    The LLM has access to the drive and is instructed to update the Region variable 
    in the dobDir/workVars.csv file based on its findings.
    """
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
        "Look at the packfiles.txt file on the drive and determine the region it belongs to (US or International)."
        "Once determined, update the 'Region' row in the 'dobDir/workVars.csv' file to be a single letter (U for US or I for International)."
        "For context, it is currently set to X but it should be changed to U or I depending on your findings."
        "Do not output any other text, only the letter U or I."
    )
    # ========================================================================
    
    logging.info(f"Sending prompt to LLM: '{prompt}'")
    llm_instance.useLoc(prompt, drive_path)
    
    # Read the region value again to log the result
    region_after = work_vars.get_data_by_name("Region")
    logging.info(f"Region AFTER LLM processing: {region_after}")
    logging.info("--- Finished Region Classification ---")

def process_drive(drive_path):
    """Process a newly connected drive."""
    logging.info(f"========== Starting processing for newly detected drive: {drive_path} ==========")
    packfiles_path = os.path.join(drive_path, "packfiles.txt")
    dobdir_path = os.path.join(drive_path, "dobDir")

    logging.debug(f"Looking for packfiles.txt at: {packfiles_path}")
    
    # Check if packfiles.txt exists on the root of the drive
    if not os.path.exists(packfiles_path):
        logging.info(f"packfiles.txt NOT FOUND on {drive_path}. Skipping this drive.")
        return

    logging.info(f"Found packfiles.txt on {drive_path}. Proceeding with processing.")
    
    # Create the dobDir folder on the root of the drive
    logging.debug(f"Checking if dobDir exists at: {dobdir_path}")
    if not os.path.exists(dobdir_path):
        logging.info(f"dobDir does not exist on {drive_path}. Attempting to create it...")
        try:
            os.makedirs(dobdir_path)
            logging.info(f"SUCCESS: Created directory {dobdir_path}")
        except Exception as e:
            logging.error(f"FAILED to create directory {dobdir_path}. Exception details: {e}")
            return
    else:
        logging.info(f"Directory {dobdir_path} already exists. No creation necessary.")

    # ========================================================================
    # CLEAR COMMENT MARKER FOR FURTHER PROCESSING
    # ========================================================================
    # This is where the rest of the functions that the program runs for 
    # this drive will be placed. 
    # ========================================================================
    logging.debug(f"Reached placeholder for further processing on {drive_path}.")
    
    # Initialize the workVars.csv file in the dobDir directory
    workvars_path = os.path.join(dobdir_path, "workVars.csv")
    work_vars = WorkVars(workvars_path)
    
    # Instantiate the LLM and run the classifyRegion function
    dobsy = LLM()
    classifyRegion(dobsy, drive_path, work_vars)
    
    logging.info(f"========== Finished initial processing for {drive_path} ==========")


def main():
    logging.info("Starting dobd.py drive monitor program...")
    
    # Instantly add all currently connected drives to the known list
    # This ephemeral list starts fresh every time the program runs
    logging.debug("Fetching initial list of connected drives...")
    known_drives = get_connected_drives()
    logging.info(f"Initial drives detected and added to ignore list: {', '.join(known_drives) if known_drives else 'None'}")
    
    logging.info("Entering main monitoring loop. Waiting for new drives...")
    
    try:
        while True:
            logging.debug("Polling for currently connected drives...")
            current_drives = get_connected_drives()
            
            # Find newly connected drives (in current but not in known)
            new_drives = current_drives - known_drives
            for drive in new_drives:
                logging.warning(f"--- NEW DRIVE DETECTED: {drive} ---")
                logging.debug(f"Adding {drive} to the internal ignore list.")
                known_drives.add(drive)
                
                # Transition to processing function
                process_drive(drive)
                
                logging.info("Returning to main monitoring loop.")
                
            # Find drives that were removed (in known but not in current)
            removed_drives = known_drives - current_drives
            for drive in removed_drives:
                logging.warning(f"--- DRIVE REMOVED: {drive} ---")
                logging.debug(f"Removing {drive} from the internal ignore list so it can be re-processed if inserted again.")
                known_drives.remove(drive)
                
            # Sleep briefly before checking again to prevent high CPU usage
            time.sleep(2)
            
    except KeyboardInterrupt:
        logging.info("Program stopped by user via KeyboardInterrupt.")
    except Exception as e:
        logging.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)

if __name__ == "__main__":
    main()
