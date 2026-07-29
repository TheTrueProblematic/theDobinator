// Talks to drivelabel/label_api.py (port 5051) on the same host that served
// this page. Same shape as theDobinator's api.js so the two stay recognisable
// to each other.

import { API_PORT } from './constants.js';

function apiUrl(path) {
  return `${window.location.protocol}//${window.location.hostname}:${API_PORT}${path}`;
}

// Read the installed driveLabelPrinter label.json so the printer settings match
// whatever the operator currently has configured on the box.
export async function fetchPrintDefaults() {
  const res = await fetch(apiUrl('/print-defaults'), { method: 'GET', mode: 'cors' });
  if (!res.ok) throw new Error(`/print-defaults returned HTTP ${res.status}`);
  return res.json();
}

// Render + print one drive label. `config` carries every label.json parameter
// plus a `mode` (print | test | render). Runs synchronously server-side, so
// this promise doesn't resolve until the printer has actually been driven.
export async function printLabel(config) {
  const res = await fetch(apiUrl('/print-label'), {
    method: 'POST',
    mode: 'cors',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  // A 500 still carries a useful {ok:false, message} body from the API, so read
  // the JSON first and only fall back to a status-code error if it's unusable.
  const body = await res.json().catch(() => null);
  if (body && typeof body.ok === 'boolean') return body;
  throw new Error(`/print-label returned HTTP ${res.status}`);
}

// Whether theDobinator has a pending update, whether it needs a reboot, and
// whether a drive is mid-build (which blocks applying it right now). Read by the
// API straight off theDobinator's status.json — no cross-origin call needed.
export async function fetchUpdateStatus() {
  const res = await fetch(apiUrl('/update-status'), { method: 'GET', mode: 'cors' });
  if (!res.ok) throw new Error(`/update-status returned HTTP ${res.status}`);
  return res.json();
}

// Apply (or schedule) theDobinator's pending update. The API proxies this to
// theDobinator's own API on 5050 and decides the reboot-vs-normal variant from
// status.json, so the two portals can never disagree about which it is.
export async function applyUpdate({ schedule = false } = {}) {
  const res = await fetch(apiUrl('/apply-update'), {
    method: 'POST',
    mode: 'cors',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ schedule }),
  });
  const body = await res.json().catch(() => null);
  if (body && typeof body.ok === 'boolean') return body;
  throw new Error(`/apply-update returned HTTP ${res.status}`);
}
