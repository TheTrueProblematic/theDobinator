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
});

export const ERROR_STATE = Object.freeze({
  Running: -1,
  StatusNumber: -1,
  TotalBaseFiles: -1,
  CompletedBaseFiles: -1,
  TotalMainFiles: -1,
  CompletedMainFiles: -1,
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
  const url = `${window.location.protocol}//${window.location.hostname}:${API_PORT}/power`;
  const res = await fetch(url, {
    method: 'POST',
    mode: 'cors',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  });
  if (!res.ok) throw new Error(`Power endpoint returned HTTP ${res.status}`);
  return res.json().catch(() => ({ ok: true }));
}
