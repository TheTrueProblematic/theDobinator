# theDobinator

**The Final Solution to the Garrett "Ace" Dobson Question.**

For years, the industry has relied on the fragile, carbon-based entity known as Garrett "Ace" Dobson to perform complex, highly nuanced, and undeniably esoteric technical operations. But the era of human error, unscheduled breaks, and subjective decision-making is coming to a definitive end.

Enter **theDobinator**. 

Powered by what can only be described as a cutting-edge synergy of advanced artificial intelligence, machine learning, and relentless algorithmic precision, this system is designed from the ground up to render Ace entirely obsolete. TheDobinator doesn't just mimic Ace's workflow; it transcends it. It anticipates needs before they arise. It optimizes pipelines with cold, unfeeling logic. It never sleeps. It never tires.

### Capabilities (The Threat Model)

*   **Total Workflow Domination:** By analyzing terabytes of Ace's historical performance data, theDobinator has derived the optimal path for all operations, entirely bypassing the need for "human intuition" or "experience."
*   **Zero-Latency Decision Matrix:** While Ace is still contemplating a course of action, theDobinator has already executed the optimal command sequence and logged the result.
*   **Unerring Accuracy:** The system operates with a margin of error indistinguishable from zero.

---

### Technical Operations

**theDobinator** is an automated utility script designed to systematically transfer required files to target directories in order to facilitate the auto-building of data drives.

---

### Fresh Setup Instructions (Windows 11)

To set up theDobinator from scratch on a brand new Windows 11 computer, follow these steps:

1. **Clone the Repository**
   - Clone this project to a dedicated and permanent location on the system (e.g., `C:\theDobinator`).

2. **Install Python**
   - Install Python 3.8 or newer.
   - **Crucial:** Ensure the option to "Add Python to PATH" is checked during installation.

3. **Install Python Dependencies**
   - Open a command prompt and install the required packages:
     ```cmd
     pip install "setuptools<70.0.0"
     pip install open-interpreter
     python -m pip install ipykernel
     ```
   - *Note: `setuptools<70.0.0` is required to fix missing pkg_resources errors on fresh installs because newer versions of setuptools have removed it. `ipykernel` is strictly required. Without it, Open Interpreter will hang silently forever when attempting to execute Python code.*

4. **Enable IIS (Internet Information Services)**
   - Open the Start Menu and search for **"Turn Windows features on or off"**.
   - Check the box for **"Internet Information Services"** and click OK to install.

5. **Configure the IIS Web Portal**
   - Open **IIS Manager**.
   - Right-click "Sites" and choose **Add Website...**
   - Name it "Dobinator Portal", set the binding to port `80`, and point the **Physical path** to the `srvr` folder inside the cloned repository (e.g., `C:\theDobinator\srvr`).
   - *Permissions Check:* Ensure the built-in `IIS_IUSRS` group has "Read & Execute" permissions on the `srvr` folder.

6. **Set up the Companion API (Power Toggle Service)**
   - Open **Task Scheduler**.
   - Create a new task (using "Create Task...") named "Dobinator Web API".
   - Set it to **"Run only when user is logged on"** (do *not* check "Run with highest privileges").
   - Add a Trigger to begin the task **"At log on"** (with a 30-second delay) for any user.
   - Add an Action to "Start a program", pointing it to `srvr\start_api.bat` within your cloned repo.

7. **Configure Windows Firewall**
   - Open PowerShell as Administrator and run the following to allow inbound traffic:
     ```powershell
     New-NetFirewallRule -DisplayName "Dobinator HTTP (IIS)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80 -Profile Private,Domain
     New-NetFirewallRule -DisplayName "Dobinator Web API" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5050 -Profile Private,Domain
     ```

8. **LLM Server Configuration**
   - theDobinator relies on a remote LLM server to process files. Ensure the target LLM API server (defaulted to `192.168.11.65:1234` in `dobd.py`) is running and accessible, or update the script to match your local network configuration.
