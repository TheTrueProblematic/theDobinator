// Top-level controller: polls status.json, hands off to render.js,
// wires up the power button (which calls the companion API and re-polls fast).

import { fetchStatus, togglePower } from './api.js';
import { render } from './render.js';

const POLL_INTERVAL_MS = 1000;
const FAST_POLL_INTERVAL_MS = 250;
const FAST_POLL_DURATION_MS = 5000;

let lastState = null;
let pollHandle = null;
let fastPollHandle = null;
let fastPollUntil = 0;
let powerInFlight = false;

async function poll() {
  const state = await fetchStatus();
  if (render(state, lastState)) lastState = state;
}

function startNormalPolling() {
  if (pollHandle) clearInterval(pollHandle);
  pollHandle = setInterval(poll, POLL_INTERVAL_MS);
}

function startFastPolling() {
  fastPollUntil = Date.now() + FAST_POLL_DURATION_MS;
  if (fastPollHandle) clearInterval(fastPollHandle);
  fastPollHandle = setInterval(() => {
    if (Date.now() > fastPollUntil) {
      clearInterval(fastPollHandle);
      fastPollHandle = null;
      return;
    }
    poll();
  }, FAST_POLL_INTERVAL_MS);
}

async function handlePowerClick() {
  if (powerInFlight) return;
  const btn = document.getElementById('powerBtn');
  if (btn) btn.classList.add('is-busy');
  powerInFlight = true;
  try {
    await togglePower();
    startFastPolling();
  } catch (err) {
    console.error('[Dobinator] power toggle failed:', err);
    alert(
      'Could not reach the power endpoint.\n\n' +
      'Check that the companion API (srvr_api.py) is running on port 5050. ' +
      'See HostingInstructions.md for setup details.'
    );
  } finally {
    setTimeout(() => {
      if (btn) btn.classList.remove('is-busy');
      powerInFlight = false;
    }, 800);
  }
}

function wireDelegatedEvents() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('#powerBtn');
    if (btn) handlePowerClick();

    const historyBtn = e.target.closest('#historyBtn');
    if (historyBtn) {
      document.getElementById('historyModal')?.classList.remove('hidden');
    }

    const closeBtn = e.target.closest('#closeHistoryBtn');
    if (closeBtn) {
      document.getElementById('historyModal')?.classList.add('hidden');
    }
    
    const backdrop = e.target.closest('#modalBackdrop');
    if (backdrop) {
      document.getElementById('historyModal')?.classList.add('hidden');
    }
  });
}

export async function start() {
  wireDelegatedEvents();
  await poll();           // initial paint, no flicker
  startNormalPolling();
}

// Auto-start unless a test harness has set window.__DOB_NO_AUTOSTART = true
if (!window.__DOB_NO_AUTOSTART) start();
