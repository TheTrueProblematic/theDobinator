// Top-level controller: polls status.json, hands off to render.js,
// wires up the power button (which calls the companion API and re-polls fast).

import { fetchStatus, togglePower, applyUpdate, scheduleUpdate, applyUpdateReboot, scheduleUpdateReboot, submitDrive } from './api.js';
import { render } from './render.js';
import { COUNTRIES } from './countries.js';

const POLL_INTERVAL_MS = 1000;
const FAST_POLL_INTERVAL_MS = 250;
const FAST_POLL_DURATION_MS = 5000;

let lastState = null;
let pollHandle = null;
let fastPollHandle = null;
let fastPollUntil = 0;
let powerInFlight = false;
let updateInFlight = false;
let driveSubmitInFlight = false;

// --- Blank-drive prompt state ---
// `dismissedTokens` holds drives the user already confirmed (so we don't re-open
// their popup while the backend catches up). `currentPromptToken` is the drive
// the popup is currently showing, ensuring popups appear strictly one at a time.
const dismissedTokens = new Set();
let currentPromptToken = null;
// Set when the user closes the popup via its X (to reach the power button, etc.)
// without naming the drive. While true the popup won't auto-reopen; the topbar
// "name drives" button clears it to bring the popup back.
let promptHiddenByUser = false;

async function poll() {
  const state = await fetchStatus();
  if (render(state, lastState)) lastState = state;
  // The blank-drive popup is driven independently of render()'s change gate so
  // it always reflects the latest BlankDrives list.
  syncDrivePrompt(state);
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

// A drive is actively being worked when the program is running and the status
// is one of the in-progress steps (1–9, which includes the empty-drive region
// and base-copy steps 8 and 9). Idle/finished states (0, 10, 11) mean nothing
// is processing, so an update can be applied right away.
function isProcessing() {
  const s = lastState;
  return !!(s && s.Running === 1 && s.StatusNumber >= 1 && s.StatusNumber <= 9);
}

function closeUpdateModal() {
  document.getElementById('updateModal')?.classList.add('hidden');
}

// True when the available update is flagged as requiring a full PC restart.
function isRebootUpdate() {
  const s = lastState;
  return !!(s && (s.RebootRequired === 1 || s.RebootRequired === true));
}

// Reword the "can't update while processing" modal for the reboot case.
function setUpdateModalCopy(reboot) {
  const title = document.querySelector('#updateModal .modal-title');
  const body = document.querySelector('#updateModal .modal-body .subline');
  const scheduleBtn = document.getElementById('scheduleUpdateBtn');
  if (title) title.textContent = reboot ? 'Restart Required' : 'Update Available';
  if (body) {
    body.textContent = reboot
      ? 'This update requires restarting the PC, which can’t happen while a drive is processing. Schedule it to update + restart once processing completes?'
      : 'Update cannot be applied while drives are processing. Would you like to schedule this update for when processing completes?';
  }
  if (scheduleBtn) scheduleBtn.textContent = reboot ? 'Schedule restart' : 'Schedule';
}

async function handleUpdateClick() {
  const reboot = isRebootUpdate();
  if (isProcessing()) {
    // Can't update mid-process — offer to schedule it for when the drive is done.
    setUpdateModalCopy(reboot);
    document.getElementById('updateModal')?.classList.remove('hidden');
    return;
  }
  // Idle: apply immediately. A reboot-update needs explicit confirmation since
  // it restarts the whole machine.
  if (reboot && !confirm('This update requires restarting the PC.\n\nUpdate now and restart the computer?')) {
    return;
  }
  if (updateInFlight) return;
  updateInFlight = true;
  try {
    await (reboot ? applyUpdateReboot() : applyUpdate());
  } catch (err) {
    console.error('[Dobinator] apply update failed:', err);
    alert(
      'Could not start the update.\n\n' +
      'Check that the companion API (srvr_api.py) is running on port 5050.'
    );
  } finally {
    setTimeout(() => { updateInFlight = false; }, 800);
  }
}

async function handleScheduleUpdate() {
  if (updateInFlight) return;
  updateInFlight = true;
  try {
    await (isRebootUpdate() ? scheduleUpdateReboot() : scheduleUpdate());
    closeUpdateModal();
  } catch (err) {
    console.error('[Dobinator] schedule update failed:', err);
    alert(
      'Could not schedule the update.\n\n' +
      'Check that the companion API (srvr_api.py) is running on port 5050.'
    );
  } finally {
    setTimeout(() => { updateInFlight = false; }, 800);
  }
}

// ---------------------------------------------------------------------------
// Blank-drive prompt (one popup at a time, in detection order)
// ---------------------------------------------------------------------------

function sanitizeDriveName(raw) {
  // Trim leading/trailing whitespace; collapse internal whitespace to underscores.
  return String(raw || '').trim().replace(/\s+/g, '_');
}

function populateCountrySelect() {
  const select = document.getElementById('driveCountrySelect');
  if (!select || select.dataset.populated === '1') return;
  const opts = ['<option value="">Select a country…</option>'];
  for (const c of COUNTRIES) {
    opts.push(`<option value="${c.code}">${c.name} (${c.code})</option>`);
  }
  select.innerHTML = opts.join('');
  select.dataset.populated = '1';
}

function refreshConfirmState() {
  const nameInput = document.getElementById('driveNameInput');
  const select = document.getElementById('driveCountrySelect');
  const confirmBtn = document.getElementById('confirmDriveBtn');
  if (!nameInput || !select || !confirmBtn) return;
  const ready = sanitizeDriveName(nameInput.value).length > 0 && select.value !== '';
  confirmBtn.classList.toggle('is-ready', ready);
  confirmBtn.disabled = !ready;
}

function openDrivePrompt(drive) {
  const modal = document.getElementById('drivePromptModal');
  const title = document.getElementById('drivePromptTitle');
  const nameInput = document.getElementById('driveNameInput');
  const select = document.getElementById('driveCountrySelect');
  if (!modal || !title || !nameInput || !select) return;

  populateCountrySelect();
  const sizeTB = (typeof drive.sizeTB === 'number') ? drive.sizeTB : 0;
  title.textContent = `New ${sizeTB}TB Drive`;
  nameInput.value = '';
  select.value = '';
  currentPromptToken = drive.token;
  refreshConfirmState();
  modal.classList.remove('hidden');
  // Focus the name field for quick entry.
  setTimeout(() => nameInput.focus(), 50);
}

function closeDrivePrompt() {
  document.getElementById('drivePromptModal')?.classList.add('hidden');
  currentPromptToken = null;
}

// Close the popup without naming the drive (the X button). Keeps the drive in
// the awaiting list so it can be reopened; suppresses auto-reopen until the
// user clicks the "name drives" button.
function closeDrivePromptManually() {
  promptHiddenByUser = true;
  closeDrivePrompt();
}

// Reopen the naming popup for the next awaiting drive (the topbar tag button).
function reopenDrivePrompt() {
  promptHiddenByUser = false;
  if (lastState) syncDrivePrompt(lastState);
}

// Decide which blank-drive popup (if any) should be showing, given the latest
// state. Shows them strictly one at a time, in the order the backend reports.
function syncDrivePrompt(state) {
  // The popup only belongs while the bot is running. If it's stopped (power
  // off / quit / a stale reboot), close the popup and reset the manual-hide
  // flag so the next run starts clean.
  if (state.Running !== 1) {
    closeDrivePrompt();
    promptHiddenByUser = false;
    return;
  }

  const blanks = Array.isArray(state.BlankDrives) ? state.BlankDrives : [];
  const tokens = new Set(blanks.map(b => b.token));

  // Forget dismissals for drives that are gone (e.g. unplugged or fully
  // consumed), so a later re-insert with a fresh token prompts again.
  for (const t of [...dismissedTokens]) {
    if (!tokens.has(t)) dismissedTokens.delete(t);
  }

  // If the popup is open for a drive that's no longer waiting (e.g. it was
  // unplugged), close it immediately.
  if (currentPromptToken && !tokens.has(currentPromptToken)) {
    closeDrivePrompt();
  }

  // The user closed the popup on purpose — don't auto-reopen until they ask.
  if (promptHiddenByUser) return;

  const next = blanks.find(b => !dismissedTokens.has(b.token));
  if (!next) {
    if (currentPromptToken && dismissedTokens.has(currentPromptToken)) closeDrivePrompt();
    return;
  }
  if (currentPromptToken === next.token) return; // already showing this one
  if (currentPromptToken) return;                // another popup is open; wait
  openDrivePrompt(next);
}

async function handleConfirmDrive() {
  if (driveSubmitInFlight) return;
  const nameInput = document.getElementById('driveNameInput');
  const select = document.getElementById('driveCountrySelect');
  const confirmBtn = document.getElementById('confirmDriveBtn');
  if (!nameInput || !select || !confirmBtn || confirmBtn.disabled) return;

  const token = currentPromptToken;
  const name = sanitizeDriveName(nameInput.value);
  const country = select.value;
  if (!token || !name || !country) return;

  driveSubmitInFlight = true;
  try {
    await submitDrive({ token, name, country });
    dismissedTokens.add(token);
    closeDrivePrompt();
    startFastPolling();
  } catch (err) {
    console.error('[Dobinator] drive submission failed:', err);
    alert(
      'Could not submit the drive details.\n\n' +
      'Check that the companion API (srvr_api.py) is running on port 5050.'
    );
  } finally {
    setTimeout(() => { driveSubmitInFlight = false; }, 600);
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

    // --- Pending drives modal ---
    if (e.target.closest('#pendingBtn')) {
      document.getElementById('pendingModal')?.classList.remove('hidden');
    }
    if (
      e.target.closest('#closePendingBtn') ||
      e.target.closest('#pendingModalBackdrop')
    ) {
      document.getElementById('pendingModal')?.classList.add('hidden');
    }

    // --- New-drive prompt: confirm / close / reopen ---
    if (e.target.closest('#confirmDriveBtn')) handleConfirmDrive();
    if (e.target.closest('#closeDrivePromptBtn')) closeDrivePromptManually();
    if (e.target.closest('#nameDriveBtn')) reopenDrivePrompt();

    // --- Update flow ---
    const updateBtn = e.target.closest('#updateBtn');
    if (updateBtn) handleUpdateClick();

    const scheduleBtn = e.target.closest('#scheduleUpdateBtn');
    if (scheduleBtn) handleScheduleUpdate();

    if (
      e.target.closest('#cancelUpdateBtn') ||
      e.target.closest('#closeUpdateBtn') ||
      e.target.closest('#updateModalBackdrop')
    ) {
      closeUpdateModal();
    }
  });

  // Keep the New-Drive confirm button's enabled/white state in sync as the
  // user types a name or picks a country.
  document.addEventListener('input', (e) => {
    if (e.target.closest('#driveNameInput')) refreshConfirmState();
  });
  document.addEventListener('change', (e) => {
    if (e.target.closest('#driveCountrySelect')) refreshConfirmState();
  });
  // Enter in the name field confirms when ready.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.closest('#driveNameInput')) {
      e.preventDefault();
      handleConfirmDrive();
    }
  });
}

export async function start() {
  wireDelegatedEvents();
  populateCountrySelect();
  await poll();           // initial paint, no flicker
  startNormalPolling();
}

// Auto-start unless a test harness has set window.__DOB_NO_AUTOSTART = true
if (!window.__DOB_NO_AUTOSTART) start();
