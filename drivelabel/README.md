# Drive Label — `drivelabel.c-nav.com`

The label-printing portal. It used to be a modal inside theDobinator; it's now
its own site with its own URL, running on the same office PC.

Two things serve it:

1. **IIS** — a second website ("Drive Label"), also on port 80, told apart from
   theDobinator by its **host header**. Serves the static files in `site/`.
2. **`label_api.py`** — a small Python HTTP server on port **5051** that drives
   the separate `driveLabelPrinter` project. Started by Task Scheduler at logon.

theDobinator is untouched by all of this. Its portal keeps port 80 with no host
name (so `http://<box-ip>/` still lands there) and its API keeps port 5050.

---

## Layout

```
drivelabel/
├── README.md                -- (this file)
├── label_api.py             -- companion API, port 5051
├── start_label_api.bat      -- launcher invoked by Task Scheduler
├── setup_drivelabel.bat     -- one-shot host setup (IIS + firewall + task)
├── app/                     -- React source. NEVER served directly.
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── public/web.config    -- IIS config; copied into site/ by the build
│   └── src/
│       ├── main.jsx
│       ├── App.jsx          -- form state, submit, admin gating
│       ├── api.js           -- fetchPrintDefaults(), printLabel()
│       ├── constants.js     -- hardware list, fallbacks, unlock tuning
│       ├── styles.css       -- design tokens + the dark-extension rules
│       ├── useAdminUnlock.js-- the secret handshake
│       └── components/
└── site/                    -- BUILT OUTPUT. Committed. This is what IIS serves.
```

### Why `site/` is committed

The office PC has no Node and no build step. The Dobinator's git updater brings
the whole working tree up to date with `origin/main`, so the *finished* files
have to already be in the repo. `npm run build` is a developer-machine step; its
output is committed like any other source file.

**Never edit anything in `site/` directly** — the next build wipes it.

---

## Making a change to the site

On a machine with Node installed:

```bash
cd drivelabel/app && npm install && npm run build
```

That writes `drivelabel/site/`. Commit **both** the `app/` change and the
regenerated `site/` output in the same commit, or the office PC will serve the
old UI.

For a live dev loop with hot reload:

```bash
cd drivelabel/app && npm run dev
```

The dev server proxies nothing — it calls the API at
`http://<current-host>:5051`, so run `python drivelabel/label_api.py` alongside
it (from the repo root) to exercise the real print path.

---

## Host setup (once)

Run **`drivelabel\setup_drivelabel.bat`** as your normal user — it self-elevates.
It is idempotent, so re-running it after a code change is safe. It:

1. Creates the "Drive Label" IIS site, bound `http/*:80:drivelabel.c-nav.com`,
   physical path `…\theDobinator\drivelabel\site`.
2. Grants `IIS_IUSRS` read access to that folder.
3. Opens inbound TCP 5051 (Private/Domain profiles only).
4. Registers the **"Drive Label Web API"** scheduled task, at logon, 30s delay.
5. Starts it and verifies `http://localhost:5051/health` plus the site itself.

It checks the site through IIS with an explicit `Host:` header, so step 5 passes
even before DNS exists.

### DNS

`drivelabel.c-nav.com` needs to resolve to this PC. A CNAME onto the existing
Dobinator record is the least maintenance — it follows along if the box's IP
ever changes:

```
drivelabel.c-nav.com.  CNAME  dobinator.c-nav.com.
```

To test before the record exists, add a line to
`C:\Windows\System32\drivers\etc\hosts` on your own machine:

```
<box-ip>   drivelabel.c-nav.com
```

### Why the scheduled task runs as the logged-on user

Same reason `configs\api_setup.bat` does it for the Dobinator API, and it matters
more here: printing needs the operator's session. The Brother QL-810W is
installed per-user, and `master_records_path` defaults to the mapped `Z:` drive —
neither exists in session 0. A task set to "run whether user is logged on or
not" will fail to find the printer, the mapped drive, or both.

**Do not** switch this task to SYSTEM or to "highest privileges". It needs no
elevation: nothing here formats a disk or reboots the PC.

---

## API

| Method | Path              | Purpose |
|--------|-------------------|---------|
| `GET`  | `/health`         | Liveness. `{"ok": true, "service": "drivelabel_api"}` |
| `GET`  | `/print-defaults` | Reads `C:\driveLabelPrinter\label.json` so the admin-only printer settings match the box |
| `POST` | `/print-label`    | Validates, writes `logs/label_print.json`, runs driveLabelPrinter synchronously, returns the real result |

`driveLabelPrinter` is a **separate repo installed at `C:\driveLabelPrinter`**
(override with `DOB_LABEL_PRINTER_DIR`). We only ever *read* its `label.json` and
*invoke* its entry point — never modify anything under that folder.

Exit codes from driveLabelPrinter: `0` success, `2` print failure, `1`
config/other. Logs land in `logs/labelApi.log`.

The API also honours `LABEL_API_PORT` / `LABEL_API_HOST` if 5051 ever collides.
Change it in both places — the env var for the task, and `API_PORT` in
`app/src/constants.js` (then rebuild).

---

## The UI

**What operators see** is only the label content: Customer, Purpose, Box Serial,
Hardware (a dropdown), Prepared By. All five start **blank on every load** —
`label.json`'s `label` block is deliberately ignored so a previous print's values
can never go out by accident.

**What operators don't see** is Mode and all seven printer settings. Those are
pre-filled from `label.json` and submitted normally; they're just hidden.

### The secret admin menu

Five clicks on the brand mark (top-left circle) inside 3.5 seconds. A rolling
window, so five clicks a second apart never add up — you have to mean it. The
mark gives a small wiggle from the third click so a deliberate explorer knows
they're onto something.

Once unlocked it's remembered in `localStorage` per browser, and the panel's
**Lock** button hides it again (and resets Mode back to `print`). Tuning lives in
`app/src/constants.js` — `UNLOCK_CLICKS`, `UNLOCK_WINDOW_MS`, `UNLOCK_HINT_AT`.

This is obscurity, not security. Anyone who reads the JS can find it, and the API
accepts any valid body regardless. It exists to keep printer settings out of the
way of people who shouldn't casually change them — not to defend against someone
determined.

### Dark-mode extensions

Operators run Dark Reader, so `app/src/styles.css` opens with a documented set of
rules the whole stylesheet obeys — chiefly *every element that renders text
declares both its own `background-color` and its `color`*. Read that comment
block before adding UI. The verified numbers: no text pair below **4.78:1** in
light, **6.33:1** in dark, nothing conveying state by hue alone, no text over a
gradient or image, and no `opacity` used to de-emphasise text.

---

## Troubleshooting

**Site shows a 404 or a directory listing.**
The IIS physical path is wrong. It must point at `drivelabel\site`, not at
`drivelabel` or `drivelabel\app`. Re-run `setup_drivelabel.bat`.

**Both hostnames show theDobinator.**
The Host header binding didn't take. Check it:

```bash
C:\Windows\System32\inetsrv\appcmd.exe list site
```

The Drive Label site should read `bindings:http/*:80:drivelabel.c-nav.com`. If it
shows a blank host name, it's competing with theDobinator's catch-all binding.

**"Could not reach the print service on this machine."**
The API isn't up. Check in order:
- `curl http://localhost:5051/health` from the box
- Task Scheduler → "Drive Label Web API" → Last Run Result should be `0x0`
- `logs\labelApi.log` for a recent startup line
- The firewall rule for 5051 exists (only matters from another machine)

**"driveLabelPrinter not found at …"**
Exactly what it says — `C:\driveLabelPrinter\src\driveLabelPrinter.py` isn't
there. This is the error you get on a machine where the other project isn't
installed.

**Prints work when you run the API by hand but not via the task.**
The printer/mapped-drive session problem above. Confirm the task is
"Run only when user is logged on" as the operator account.

**Site serves a stale UI after an update.**
`site/web.config` disables caching, so this shouldn't happen. If it does, confirm
`web.config` actually made it into `site/` (it's copied from `app/public/` by the
build) and that the committed `site/assets/*` filenames match what
`site/index.html` references.
