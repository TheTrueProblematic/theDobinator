# Hosting The Dobinator portal on IIS

This walks through setting up the portal end-to-end on a Windows box with a fixed local IP. Two things need to run on the machine:

1. **IIS** — serves the static portal files from this `srvr/` folder.
2. **Companion API** (`srvr_api.py`) — a tiny Python HTTP server on port 5050 that handles the power button. Started by Task Scheduler at boot.

Total setup time: ~15 minutes.

---

## 1. Prerequisites

Verify each of these before continuing.

- **Windows 10 / 11 / Server** with the IIS role enabled.
  - To enable IIS: Start → **Turn Windows features on or off** → check **Internet Information Services** → OK. Wait for it to install.
- **Python 3.8+** on `PATH`. (You already have this if `dobd.py` runs.)
  - Verify: open a Command Prompt and run `python --version`.
- The repo cloned somewhere predictable on the box — for the rest of these instructions we'll use `C:\theDobinator\` as the project root. **Substitute your actual path everywhere.**

---

## 2. Point IIS at the `srvr` folder

1. Open **IIS Manager** (Start → search "IIS Manager").
2. In the left tree, expand your server, right-click **Sites**, choose **Add Website…** (or edit "Default Web Site" if you prefer).
3. Fill in:
   - **Site name:** `Dobinator Portal`
   - **Physical path:** `C:\theDobinator\srvr`
   - **Binding:** Type `http`, IP address `All Unassigned` (or the box's fixed IP), Port `80`, Host name blank.
4. Click **OK**.
5. In the site's Features view, double-click **Default Document** and confirm `index.html` is in the list (it is by default).
6. **Test it.** From the same machine, open a browser and go to `http://localhost/`. You should see the Dobinator portal — black screen with "The Dobinator is not running" (because the daemon isn't running yet). From another machine on the LAN, browse to `http://<box-ip>/`.

If you get a 404 or directory listing instead of the page:
- Confirm the **Physical path** points at the `srvr` folder, not at the project root.
- Confirm `index.html`, `preview.html`, `test.html`, and `web.config` are present in that folder.

### Folder permissions

IIS runs as the built-in `IIS_IUSRS` group. It needs **Read** access to the `srvr` folder. This is usually inherited from the parent, but if you cloned the repo into a restricted location (like a user profile), grant `IIS_IUSRS` Read & Execute on the folder:

1. Right-click the `srvr` folder → **Properties** → **Security** tab → **Edit…** → **Add…**
2. Type `IIS_IUSRS`, click **Check Names**, **OK**.
3. Tick **Read & execute**, **List folder contents**, **Read**. **Apply**.

---

## 3. Set up the companion API (power button)

The portal's power button calls `http://<box-ip>:5050/power`, and that endpoint is served by `srvr_api.py`. We'll run it as a Scheduled Task that starts at boot.

### 3a. Smoke test it manually first

In a Command Prompt:

```bat
cd C:\theDobinator
python srvr\srvr_api.py
```

You should see something like:

```
2026-05-14 ... [INFO] dob_srvr_api starting on 0.0.0.0:5050 (project=C:\theDobinator)
2026-05-14 ... [INFO] dobWin.bat path: C:\theDobinator\dobWin.bat (exists=True)
```

In another window:

```bat
curl http://localhost:5050/health
```

Should return:

```json
{"ok": true, "service": "dob_srvr_api"}
```

`Ctrl+C` to stop it. If that worked, move on. If `dobWin.bat exists=False`, the path resolution is off — verify `srvr_api.py` is inside the `srvr/` folder and `dobWin.bat` is in the project root.

### 3b. Register it as a Scheduled Task

1. Open **Task Scheduler** (Start → "Task Scheduler").
2. **Action → Create Task…** (not "Create Basic Task" — we need the full dialog).
3. **General** tab:
   - **Name:** `Dobinator Web API`
   - **Description:** `Companion HTTP server for the Dobinator portal power button.`
   - Select **Run whether user is logged on or not**.
   - Check **Run with highest privileges**.
   - **Configure for:** your Windows version.
4. **Triggers** tab → **New…**
   - **Begin the task:** `At startup`
   - **Delay task for:** 30 seconds (gives the network stack a chance to come up).
   - **Enabled.** OK.
5. **Actions** tab → **New…**
   - **Action:** `Start a program`
   - **Program/script:** `C:\theDobinator\srvr\start_api.bat`
   - **Start in (optional):** `C:\theDobinator`
   - OK.
6. **Conditions** tab:
   - Uncheck **Start the task only if the computer is on AC power** (this is a server, not a laptop).
7. **Settings** tab:
   - Check **If the task fails, restart every** `1 minute`, attempt up to `3` times.
   - **If the running task does not end when requested, force it to stop.**
8. **OK.** It will ask for the password of the user the task runs as — provide it.

### 3c. Start it now (without rebooting)

Right-click the new `Dobinator Web API` task → **Run**. Then:

```bat
curl http://localhost:5050/health
```

Same response as before? Good.

You can also tail the log to verify it's alive:

```bat
type C:\theDobinator\srvr\srvr_api.log
```

---

## 4. Open the firewall

Both ports need inbound access from the LAN (not the public internet).

```powershell
# Run in an elevated PowerShell
New-NetFirewallRule -DisplayName "Dobinator HTTP (IIS)" `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80 -Profile Private,Domain

New-NetFirewallRule -DisplayName "Dobinator Web API" `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5050 -Profile Private,Domain
```

Adjust `-Profile` to match your network classification. **Do not** add `Public` unless you genuinely want this reachable from outside your LAN.

---

## 5. Verify everything end to end

From another machine on the LAN, browse to `http://<box-ip>/` and check:

1. **OFF state renders.** Black background, "The Dobinator is not running", white title top-left, white power button top-right.
2. **Power button toggles.** Click it. Within ~2 seconds the screen should flip to white background and either "Scanning for drives" (if no drive is plugged in) or one of the working states.
3. **Test suite passes.** Browse to `http://<box-ip>/test.html` and click **Run all assertions**. All ~14 checks should report PASS.

If any of those fail, see Troubleshooting below.

---

## 6. Updating the portal later

To deploy new versions of the portal:

1. `git pull` (or copy new files into `srvr/`).
2. IIS picks up changes immediately — no restart needed for HTML/CSS/JS.
3. If you change `srvr_api.py`, restart the scheduled task: Task Scheduler → right-click `Dobinator Web API` → **End**, then **Run**.
4. If you change `web.config`, IIS will detect it on the next request — no manual reload needed.

---

## Troubleshooting

**Portal shows "Can't reach status".**
The browser can't fetch `status.json`. Check:
- IIS site is started (IIS Manager → site → **Browse** in the right panel).
- `status.json` exists at the root of `srvr/`. If `dobd.py` has never run, the file is empty — that's fine, the portal handles it.
- Browser dev tools → Network tab — what's the actual response code? 404 means IIS path is wrong; 403 means a permissions issue.

**Power button shows "Could not reach the power endpoint" alert.**
The companion API isn't reachable. Check:
- Task Scheduler → `Dobinator Web API` → **Last Run Result** shows `(0x0)` (success). If it shows an error code, the bat file or Python failed to launch.
- `srvr_api.log` exists in `srvr/` and contains a recent startup line.
- `curl http://localhost:5050/health` from the box itself works.
- Firewall rule for 5050 is active.
- If accessing from another machine, the browser is hitting `http://<box-ip>:5050` — make sure the box IP is reachable.

**status.json shows stale values in the browser.**
IIS isn't honoring the no-cache headers. In browser dev tools, look at the `status.json` response headers — `Cache-Control: no-cache, no-store, must-revalidate` should be there. If not, `web.config` isn't being applied — confirm IIS has the URL Rewrite module installed and that the `web.config` is at the site root (`srvr/web.config`).

**Power button click does nothing visible.**
The API may be receiving the request fine but `dobWin.bat` is failing. Check `srvr_api.log` for a `power toggle requested:` line with `ok=False`. If it says `dobWin.bat not found`, your project root is misdetected — `srvr_api.py` assumes its parent folder is the project root. Verify the layout is `<project>/srvr/srvr_api.py` and `<project>/dobWin.bat`.

**Task fails immediately at boot.**
Most common cause: the task is configured to run as a user account that doesn't have a password set, or whose password expired. Re-open the task → **General** → re-enter the credentials. Also confirm `python` (or `pythonw`) is on the SYSTEM `PATH`, not just the user's — if it's only on your user PATH, the task will fail to find it when running as SYSTEM. Either add Python to system PATH or hard-code the python.exe path in `start_api.bat`.

**Different port for the companion API.**
Set the `DOB_API_PORT` environment variable. For Task Scheduler, edit the task → **Actions** → **Edit…** and add an environment variable via a wrapper bat that does `set DOB_API_PORT=5151 & start_api.bat`. Then update `API_PORT` in `srvr/assets/js/api.js` to match.

---

## File reference

```
srvr/
├── index.html              -- Main portal (what users see)
├── preview.html            -- Headless preview used by the test harness
├── test.html               -- Dev/test harness with mock controls
├── status.json             -- Written by dobd.py; read by the portal
├── web.config              -- IIS settings (no-cache for status.json, MIME types)
├── srvr_api.py             -- Companion HTTP server for /power
├── start_api.bat           -- Launcher invoked by Task Scheduler
├── HostingInstructions.md  -- (this file)
├── srvr_api.log            -- Created at first run; rotating log file
├── assets/
│   ├── css/styles.css      -- Theme + animations
│   └── js/
│       ├── api.js          -- fetchStatus(), togglePower()
│       ├── render.js       -- State -> DOM
│       ├── app.js          -- Polling loop + power-button wiring
│       └── test-harness.js -- Drives the preview iframe for tests
└── tests/
    └── assertions.js       -- Assertion suite (run from test.html)
```
