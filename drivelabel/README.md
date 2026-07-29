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
| `GET`  | `/update-status`  | Whether theDobinator has a pending update, needs a reboot for it, and is mid-build |
| `POST` | `/apply-update`   | Applies or schedules that update, by proxying to theDobinator's API on 5050 |

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

### The label preview

The round disc next to the form reproduces the **real** printed label, laid out
from a photo of an actual print:

```
      SHOT            <- wordmark, centred at the top
      OVER
 Customer             <- left-aligned content block
 Purpose
 Box #: 000000
 [QR]  2026-07-29     <- QR bottom-left, print date + CAGE stacked to its right
       Cage
       5ET05
```

Only printed fields appear. Hardware and Prepared By go to the master records
file rather than onto the label, so leaving them out doubles as an explanation of
why. The wordmark, the date and the "Cage" caption come from driveLabelPrinter's
own template, so they're fixed in `LabelPreview.jsx` rather than driven by the
form; the date is stamped from local date parts (not `toISOString()`, which would
show tomorrow on an evening print).

**If the printed label's layout ever changes, this has to change with it** — it's
the one place in this repo that duplicates driveLabelPrinter's design. Geometry is
verified against the circle: with a two-line Customer (the worst case) every
corner still clears the die-cut ring by ~5px. If you add a line or grow a font,
re-check that, because content near the bottom-left corner of the QR is what runs
out of room first.

### The secret admin menu

Two gates:

1. **The handshake** — five clicks on the brand mark (top-left square) inside 3.5
   seconds. A rolling window, so five clicks a second apart never add up; you have
   to mean it. The mark gives a small wiggle from the third click so a deliberate
   explorer knows they're onto something.
2. **The password** — clearing the handshake opens a prompt. A wrong entry shows
   an inline error and clears the field; the panel stays hidden.

Once unlocked it's remembered in `localStorage` per browser (no password on
reload), and the panel's **Lock** button hides it again and resets Mode back to
`print`. Tuning lives in `app/src/constants.js` — `UNLOCK_CLICKS`,
`UNLOCK_WINDOW_MS`, `UNLOCK_HINT_AT`, `ADMIN_PASSWORD`.

**⚠️ This is obscurity, not security.** The password is checked in the browser, so
it ships inside the JS bundle and anyone who opens devtools can read it — and the
API accepts any valid body whether or not it was ever entered. It exists to keep
printer settings out of the way of people who shouldn't casually change them. If
these settings ever need genuine protection, that has to move server-side into
`label_api.py`.

### The update button

The topbar carries the same pending-update indicator theDobinator's portal does:
hidden until an update exists, amber normally, red when the update needs a full PC
restart. It follows the same rules, too — mid-build it offers to schedule the
update instead of applying it, and a reboot-update asks for confirmation first.

It works without any cross-origin calls to the other site:

- **State** comes from `GET /update-status`, which reads `logs/update_state.json`
  off disk. That file is published by **`srvr_api.py`'s always-on update
  watcher** — not by the bot — which is what makes the badge correct whether or
  not theDobinator is powered on. (It used to read `UpdateAvailable` out of
  `srvr/status.json`, which only says anything useful while the bot is running;
  that's why this badge used to go stale and then vanish the moment the bot
  started.) `processing` still comes from `status.json`, since that genuinely is
  bot state. Same repo either way, so no CORS headers were needed on
  theDobinator's `web.config`.
- **Actions** go through `POST /apply-update`, which proxies to theDobinator's own
  API on `127.0.0.1:5050`. The update logic is not duplicated here.

The reboot-vs-normal decision is made **server-side** from `status.json`, not
taken from the request body, so the two portals can never disagree about which
kind of update is pending. `/apply-update` also refuses to apply immediately while
a drive is processing, independently of what the UI allows.

Polling is every 15s (`UPDATE_POLL_MS`) — this is a badge, not the Dobinator's
live drive progress, so it doesn't need per-second updates. A failed poll hides
the button rather than showing one that can't work.

### Colour

The accent is SHOTOVER orange, `#fb8333`. Two things to know before using it:

- **`--accent-fg` is near-black, not white.** White on `#fb8333` is only 2.5:1;
  `#101114` is 7.6:1. So filled accent buttons carry dark text.
- **`--accent-ink` exists for text.** The orange is too light to use as a text
  colour on a light background (2.5:1 on white), so anything rendering the accent
  as *text or an icon* uses `--accent-ink` — a darkened orange in light mode, and
  the plain orange in dark mode where it already has 6.4:1. If you add accent-
  coloured text, use `--accent-ink`; `--accent` is for fills, borders and rings.

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
