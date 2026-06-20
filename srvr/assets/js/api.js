// Status fetch + power-toggle helpers.
// The companion API runs on the same host as IIS, port 5050.

export const API_PORT = 5050;
export const STATUS_URL = 'status.json';

const DEFAULT_STATE = Object.freeze({
  Running: 0,
  StatusNumber: 0,
  TotalBaseFiles: -1,
  CompletedBaseFiles: -1,
  TotalMainFiles: -1,
  CompletedMainFiles: -1,
  CompletedDrives: [],
  BlankDrives: [],
  PendingDrives: [],
  UpdateAvailable: 0,
  RebootRequired: 0,
  // Imagery-verification detail (steps 12–14) — must be listed here or
  // normalizeState() would strip these keys before render.js ever sees them.
  VerifyRun: 0,
  VerifyMaxRuns: 5,
  VerifyMissingCount: 0,
  VerifyMissing: [],
});

export const ERROR_STATE = Object.freeze({
  Running: -1,
  StatusNumber: -1,
  TotalBaseFiles: -1,
  CompletedBaseFiles: -1,
  TotalMainFiles: -1,
  CompletedMainFiles: -1,
  CompletedDrives: [],
  BlankDrives: [],
  PendingDrives: [],
  UpdateAvailable: 0,
  RebootRequired: 0,
  VerifyRun: 0,
  VerifyMaxRuns: 5,
  VerifyMissingCount: 0,
  VerifyMissing: [],
  _error: true,
});

export function normalizeState(raw) {
  if (!raw || typeof raw !== 'object') return { ...DEFAULT_STATE };
  const merged = { ...DEFAULT_STATE };
  for (const key of Object.keys(DEFAULT_STATE)) {
    if (raw[key] !== undefined && raw[key] !== null) merged[key] = raw[key];
  }
  return merged;
}

export async function fetchStatus() {
  try {
    const res = await fetch(`${STATUS_URL}?t=${Date.now()}`, {
      cache: 'no-store',
      headers: { 'Cache-Control': 'no-cache' },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = (await res.text()).trim();
    if (!text) return { ...DEFAULT_STATE };
    return normalizeState(JSON.parse(text));
  } catch (err) {
    return { ...ERROR_STATE, _errorMessage: String(err && err.message || err) };
  }
}

export async function togglePower() {
  return postToApi('/power');
}

// Apply an available update immediately (only valid when no drive is processing).
export async function applyUpdate() {
  return postToApi('/update');
}

// Schedule an available update to be applied once the current drive finishes.
export async function scheduleUpdate() {
  return postToApi('/schedule-update');
}

// Apply a reboot-required update now (pull, clear flag, restart the PC).
export async function applyUpdateReboot() {
  return postToApi('/update-reboot');
}

// Schedule a reboot-required update for once the current drive finishes.
export async function scheduleUpdateReboot() {
  return postToApi('/schedule-update-reboot');
}

// Submit a blank drive's user-supplied Drive Name + Country (ISO Alpha-3).
export async function submitDrive({ token, name, country }) {
  return postToApi('/submit-drive', { token, name, country });
}

// Fetch the installed driveLabelPrinter label.json so the Print Label form can
// be pre-filled with the operator's current values.
export async function fetchPrintDefaults() {
  const url = `${window.location.protocol}//${window.location.hostname}:${API_PORT}/print-defaults`;
  const res = await fetch(url, { method: 'GET', mode: 'cors' });
  if (!res.ok) throw new Error(`/print-defaults returned HTTP ${res.status}`);
  return res.json();
}

// Render + print one drive label via the driveLabelPrinter project. `config`
// carries every label.json parameter plus a `mode` (print | test | render).
export async function printLabel(config) {
  return postToApi('/print-label', config);
}

async function postToApi(path, body = {}) {
  const url = `${window.location.protocol}//${window.location.hostname}:${API_PORT}${path}`;
  const res = await fetch(url, {
    method: 'POST',
    mode: 'cors',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} endpoint returned HTTP ${res.status}`);
  return res.json().catch(() => ({ ok: true }));
}
