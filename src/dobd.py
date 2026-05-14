import os
import time
import ctypes
import string
import logging
import csv
import shutil
import subprocess

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
RUN_SEPARATOR = "\n" + "="*50 + " END OF RUN " + "="*50 + "\n"

# Maintain the past 5 logs in dobLogPrev.log
if os.path.exists(LOG_FILE):
    try:
        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            last_run_log = f.read().strip()
            
        if last_run_log:
            prev_logs = []
            if os.path.exists(PREV_LOG_FILE):
                with open(PREV_LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    prev_logs = [log.strip() for log in content.split(RUN_SEPARATOR) if log.strip()]
            
            # Keep the last 4 logs, then add the most recent run
            prev_logs = prev_logs[-4:]
            prev_logs.append(last_run_log)
            
            with open(PREV_LOG_FILE, 'w', encoding='utf-8') as f:
                f.write(RUN_SEPARATOR.join(prev_logs) + RUN_SEPARATOR)
    except Exception as e:
        print(f"Failed to update previous logs: {e}")

# Configure logging to write to the file (resetting every run with mode='w')
# and also output to the console.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
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
        import sys
        import os

        # Try to import open-interpreter, with a fallback to the common pipx installation path
        try:
            from interpreter import OpenInterpreter
        except ImportError:
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

def copy_region_files(drive_path, work_vars):
    """
    Copies the appropriate files to the drive based on the identified region.
    """
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

    for cmd in commands:
        cmd_str = " ".join(cmd)
        logging.info(f"Running command: {cmd_str}")
        try:
            # 0x08000000 is CREATE_NO_WINDOW
            result = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
            if result.returncode >= 8:
                logging.error(f"Robocopy failed with exit code {result.returncode}: {result.stderr or result.stdout}")
            else:
                logging.info(f"Robocopy completed with exit code {result.returncode}")
        except Exception as e:
            logging.error(f"Failed to execute robocopy command: {e}")

    logging.info("--- Finished File Copy Process ---")

def matchFiles(drive_path):
    """
    Instructs the AI on how to actually find the rest of the files.
    Creates a new LLM instance with the working directory on the root of the processing drive.
    """
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
        "if applicable (see previous note)."
    )
    logging.info(f"Sending prompt to LLM in matchFiles: '{prompt}'")
    match_llm.use(prompt)
    
    logging.info("--- Finished matchFiles Process ---")

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
    if os.path.exists(dobdir_path):
        logging.info(f"Directory {dobdir_path} already exists. Deleting it first...")
        try:
            shutil.rmtree(dobdir_path)
            logging.info(f"SUCCESS: Deleted existing directory {dobdir_path}")
        except Exception as e:
            logging.error(f"FAILED to delete existing directory {dobdir_path}. Exception details: {e}")
            return
            
    logging.info(f"Attempting to create dobDir on {drive_path}...")
    try:
        os.makedirs(dobdir_path)
        logging.info(f"SUCCESS: Created directory {dobdir_path}")
    except Exception as e:
        logging.error(f"FAILED to create directory {dobdir_path}. Exception details: {e}")
        return

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
    
    # Run the file copy process
    copy_region_files(drive_path, work_vars)
    
    # Run the matchFiles process to find the rest of the files
    matchFiles(drive_path)
    
    logging.info(f"Cleaning up {dobdir_path}...")
    try:
        shutil.rmtree(dobdir_path)
        logging.info(f"SUCCESS: Deleted directory {dobdir_path}")
    except Exception as e:
        logging.error(f"FAILED to delete directory {dobdir_path}. Exception details: {e}")
    
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
