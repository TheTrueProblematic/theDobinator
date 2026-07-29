// State-driven rendering for The Dobinator portal.
// Pure function of state -> DOM. Sets data attributes the test harness asserts on.

import { initScene, destroyScene } from './pixel-scene.js';

export const STATUS_LABELS = {
  0: 'Scanning for Drives',
  1: 'Preparing Drive',
  2: 'Identifying Region',
  3: 'Copying Base Files',
  4: 'Matching Specific Files',
  5: 'Copying Specific Files',
  6: 'Issues Detected',
  7: 'Copying Airport Files',
  8: 'Copying Country Files',
  9: 'Formatting Drive',
  10: 'Drive Completed Successfully',
  11: 'Drive Completed — Errors Detected',
  12: 'Verifying Imagery',
  13: 'Correcting Missed Imagery',
  14: 'Copying Corrected Imagery',
};

const ICONS = {
  power: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v10"/><path d="M5.6 6.4a8 8 0 1 0 12.8 0"/></svg>`,
  check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>`,
  warn: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>`,
  alert: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>`,
  spinner: '<span class="spinner" aria-hidden="true"></span>',
};

function esc(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function powerButtonHtml() {
  return `
    <button id="powerBtn" class="power-btn" aria-label="Toggle The Dobinator" title="Toggle The Dobinator">
      ${ICONS.power}
    </button>`;
}

export function brandHtml() {
  return `
    <span class="brand" aria-label="The Dobinator">
      <span class="brand-dot" aria-hidden="true"></span>
      The Dobinator
    </span>`;
}

function progressBlock(label, completed, total) {
  const safeTotal = (typeof total === 'number' && total > 0) ? total : 0;
  const safeDone = (typeof completed === 'number' && completed >= 0) ? completed : 0;
  const pct = safeTotal > 0 ? Math.min(100, Math.round((safeDone / safeTotal) * 1000) / 10) : 0;
  const meta = safeTotal > 0
    ? `${safeDone.toLocaleString()} of ${safeTotal.toLocaleString()} files`
    : 'preparing…';
  return `
    <div class="progress-wrap" data-progress-label="${esc(label)}">
      <div class="progress-track">
        <div class="progress-bar" data-progress-bar style="width: ${pct}%"></div>
      </div>
      <div class="progress-meta">
        <span data-progress-meta>${esc(meta)}</span>
        <span data-progress-pct>${pct}%</span>
      </div>
    </div>`;
}

// Extra detail for the imagery-verification stages (steps 12–14). Surfaces the
// current correction attempt (out of the max) and what's still being searched
// for — showing the actual filenames only when fewer than 3 remain (the backend
// enforces the same rule, sending names only for a short list), otherwise just
// the count so a long missing list never overwhelms the operator.
function verifyDetail(state) {
  const max = (typeof state.VerifyMaxRuns === 'number' && state.VerifyMaxRuns > 0)
    ? state.VerifyMaxRuns : 5;
  const run = (typeof state.VerifyRun === 'number' && state.VerifyRun > 0)
    ? state.VerifyRun : 0;
  const count = (typeof state.VerifyMissingCount === 'number' && state.VerifyMissingCount > 0)
    ? state.VerifyMissingCount : 0;
  const names = Array.isArray(state.VerifyMissing) ? state.VerifyMissing.filter(Boolean) : [];

  // Nothing meaningful to add yet (e.g. the very first verification pass before
  // any correction attempt) — fall back to just the stage's own copy.
  if (!run && !count) return '';

  let html = '<div class="verify-detail">';
  if (run) {
    html += `<div class="verify-attempt">Correction attempt ${run} of ${max}</div>`;
  }
  if (count) {
    if (names.length) {
      // Short list: name exactly what's left.
      html += `<div class="verify-missing">Still searching for ${count} file${count === 1 ? '' : 's'}:
        <ul class="verify-missing-list">
          ${names.map(f => `<li>${esc(f)}</li>`).join('')}
        </ul></div>`;
    } else {
      // 3+ outstanding: show the count only, not which ones.
      html += `<div class="verify-missing">Still searching for ${count} imagery files.</div>`;
    }
  }
  html += '</div>';
  return html;
}

function spinnerHeadline(text) {
  return `
    <h1 class="headline">
      ${ICONS.spinner}
      <span>${esc(text)}<span class="dots"><span>.</span><span>.</span><span>.</span></span></span>
    </h1>`;
}

function radarHeadline(text) {
  return `
    <div class="radar"><span class="radar-core"></span></div>
    <div class="eyebrow"><span class="eyebrow-dot"></span> Standing by</div>
    <h1 class="headline"><span>${esc(text)}<span class="dots"><span>.</span><span>.</span><span>.</span></span></span></h1>
    <p class="subline">Plug in a drive to begin.</p>`;
}

function screenForState(state) {
  const sn = state.StatusNumber;
  switch (sn) {
    case 0:
      return { cardClass: '', inner: radarHeadline(STATUS_LABELS[0]) };

    case 1:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[1]) +
          `<p class="subline">Getting things ready on the drive.</p>`
      };

    case 2:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[2]) +
          `<p class="subline">Figuring out which set of files this drive needs.<br/>
            <em class="hint">The AI is thinking — this may take a while.</em></p>`
      };

    case 3:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[3]) +
          progressBlock('base', state.CompletedBaseFiles, state.TotalBaseFiles) +
          `<p class="subline">Copying the baseline set for this region.</p>`
      };

    case 4:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[4]) +
          `<p class="subline">Working out where every file should go.<br/>
            <em class="hint">The AI is thinking — this may take a while.</em></p>`
      };

    case 5:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[5]) +
          progressBlock('main', state.CompletedMainFiles, state.TotalMainFiles) +
          `<p class="subline">Copying the rest of the files into place.</p>`
      };

    case 6:
      return {
        cardClass: 'is-danger',
        inner: `
          <div class="status-icon is-danger">${ICONS.alert}</div>
          <div class="eyebrow"><span class="eyebrow-dot"></span> Heads up</div>
          <h1 class="headline"><span>${esc(STATUS_LABELS[6])}</span></h1>
          <p class="subline">Creating documentation<span class="dots"><span>.</span><span>.</span><span>.</span></span><br/>
            Hold on while the details get written down. This may take a while.</p>` };

    case 7:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[7]) +
          `<p class="subline">Copying and unzipping the airport data set.</p>`
      };

    case 8:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[8]) +
          progressBlock('main', state.CompletedMainFiles, state.TotalMainFiles) +
          `<p class="subline">Copying the country-specific imagery, vector, and geocode sets.</p>`
      };

    case 9:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[9]) +
          `<p class="subline">Erasing and labeling the drive before the build begins.</p>`
      };

    case 10:
      return {
        cardClass: 'is-success',
        inner: `
          <div class="status-icon is-success">${ICONS.check}</div>
          <div class="eyebrow"><span class="eyebrow-dot"></span> All done</div>
          <h1 class="headline"><span>${esc(STATUS_LABELS[10])}</span></h1>
          <p class="subline">Safe to unplug. Pop in the next one whenever you're ready.</p>` };

    case 11:
      return {
        cardClass: 'is-warning',
        inner: `
          <div class="status-icon is-warning">${ICONS.warn}</div>
          <div class="eyebrow"><span class="eyebrow-dot"></span> Finished with notes</div>
          <h1 class="headline"><span>${esc(STATUS_LABELS[11])}</span></h1>
          <p class="subline">Check <strong>ISSUES.md</strong> at the root of the drive for details on what came up.</p>` };

    case 12:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[12]) +
          `<p class="subline">Regenerating the packfile and checking every imagery file made it onto the drive.</p>` +
          verifyDetail(state)
      };

    case 13:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[13]) +
          `<p class="subline">Some imagery files were missing — working out where to find them.<br/>
            <em class="hint">The AI is thinking — this may take a while.</em></p>` +
          verifyDetail(state)
      };

    case 14:
      return {
        cardClass: '',
        inner: spinnerHeadline(STATUS_LABELS[14]) +
          progressBlock('main', state.CompletedMainFiles, state.TotalMainFiles) +
          `<p class="subline">Copying the imagery files that were missed the first time.</p>` +
          verifyDetail(state)
      };

    default:
      return {
        cardClass: '',
        inner: spinnerHeadline('Working') +
          `<p class="subline">Hang tight…</p>`
      };
  }
}

function renderOff(stage) {
  destroyScene();
  stage.innerHTML = `
    <div class="off-screen fade-enter" data-screen="off">
      The Dobinator is not running
    </div>
    <div class="off-foot" data-screen="off-foot">Press the power button to start</div>`;
}

function renderError(stage, state) {
  stage.innerHTML = `
    <div class="error-screen fade-enter" data-screen="error">
      <div class="error-title">Can't reach status</div>
      <div>${esc(state._errorMessage || 'Unable to load status.json')}</div>
    </div>`;
}

function renderOn(stage, state) {
  initScene();
  const screen = screenForState(state);
  stage.innerHTML = `
    <div class="card ${screen.cardClass} fade-enter"
         data-screen="on"
         data-status="${esc(state.StatusNumber)}">
      ${screen.inner}
    </div>`;
}

// Top-level render. Returns true if it changed the DOM.
export function render(state, prev) {
  document.body.dataset.running = String(state.Running);
  document.body.dataset.status = String(state.StatusNumber);

  // Reflect update availability on every render (independent of the change
  // gate below) so the yellow update button appears/disappears immediately.
  const updateBtn = document.getElementById('updateBtn');
  if (updateBtn) {
    // NOT gated on state.Running any more. It used to be, because update state
    // came from the bot and was therefore meaningless while it was off — which
    // also meant a pending update was invisible exactly when it was safest to
    // apply. srvr_api.py's always-on watcher now owns this (app.js overlays it
    // onto the polled state), and git_update.py handles a not-running bot fine.
    const updateReady = state.UpdateAvailable === 1 || state.UpdateAvailable === true;
    const showUpdate = updateReady;
    updateBtn.classList.toggle('is-visible', showUpdate);
    // A reboot-required update turns the button red and changes its hover label.
    const rebootReady = state.RebootRequired === 1 || state.RebootRequired === true;
    const showReboot = showUpdate && rebootReady;
    updateBtn.classList.toggle('is-reboot', showReboot);
    const label = showReboot ? 'Restart required' : 'Update available';
    updateBtn.setAttribute('title', label);
    updateBtn.setAttribute('aria-label', showReboot ? 'Apply update and restart PC' : 'Apply available update');
  }

  // Pending + blank drive lists only make sense while the bot is running. When
  // it's stopped, treat them as empty so a power-off / quit clears the popup,
  // the count badge, and the Pending Drives menu immediately (and stale lists
  // from a hard reboot never linger). Handled on every render, independent of
  // the card-change gate below.
  const running = state.Running === 1;
  const pending = (running && Array.isArray(state.PendingDrives)) ? state.PendingDrives : [];
  const blanks = (running && Array.isArray(state.BlankDrives)) ? state.BlankDrives : [];

  const pendingCount = document.getElementById('pendingCount');
  if (pendingCount) {
    pendingCount.textContent = pending.length > 99 ? '99+' : String(pending.length);
    pendingCount.classList.toggle('is-visible', pending.length > 0);
  }

  // "Name pending drives" button: visible only while running and blank drives
  // are awaiting input, giving a way to reopen the naming popup after closing it.
  const nameBtn = document.getElementById('nameDriveBtn');
  if (nameBtn) {
    nameBtn.classList.toggle('is-visible', blanks.length > 0);
    const nameCount = document.getElementById('nameDriveCount');
    if (nameCount) {
      nameCount.textContent = blanks.length > 9 ? '9+' : String(blanks.length);
      nameCount.classList.toggle('is-visible', blanks.length > 0);
    }
  }

  // Keep the pending list in sync every render (it's tiny). Using the
  // running-gated list means it empties out the moment the bot stops.
  renderPending(pending);

  const stage = document.getElementById('stage');
  if (!stage) return false;

  const changed =
    !prev ||
    prev.Running !== state.Running ||
    prev.StatusNumber !== state.StatusNumber ||
    prev._error !== state._error ||
    prev.TotalBaseFiles !== state.TotalBaseFiles ||
    prev.CompletedBaseFiles !== state.CompletedBaseFiles ||
    prev.TotalMainFiles !== state.TotalMainFiles ||
    prev.CompletedMainFiles !== state.CompletedMainFiles ||
    prev.VerifyRun !== state.VerifyRun ||
    prev.VerifyMissingCount !== state.VerifyMissingCount ||
    JSON.stringify(prev.VerifyMissing) !== JSON.stringify(state.VerifyMissing) ||
    JSON.stringify(prev.CompletedDrives) !== JSON.stringify(state.CompletedDrives);

  if (!changed) return false;

  // Render history list if it changed
  if (!prev || JSON.stringify(prev.CompletedDrives) !== JSON.stringify(state.CompletedDrives)) {
    renderHistory(state.CompletedDrives);
  }

  // Connection error wins over everything.
  if (state._error) {
    destroyScene();
    renderError(stage, state);
    return true;
  }

  // Running=1 with no structural change but progress changed — update bar in place
  // for smoother animation rather than re-rendering the whole card.
  if (
    prev && !prev._error &&
    prev.Running === 1 && state.Running === 1 &&
    prev.StatusNumber === state.StatusNumber &&
    (state.StatusNumber === 3 || state.StatusNumber === 5 ||
     state.StatusNumber === 8 || state.StatusNumber === 14)
  ) {
    updateProgressInPlace(stage, state);
    return true;
  }

  if (state.Running === 1) renderOn(stage, state);
  else renderOff(stage);
  return true;
}

function updateProgressInPlace(stage, state) {
  const isBase = state.StatusNumber === 3;
  const total = isBase ? state.TotalBaseFiles : state.TotalMainFiles;
  const completed = isBase ? state.CompletedBaseFiles : state.CompletedMainFiles;
  const safeTotal = (typeof total === 'number' && total > 0) ? total : 0;
  const safeDone = (typeof completed === 'number' && completed >= 0) ? completed : 0;
  const pct = safeTotal > 0 ? Math.min(100, Math.round((safeDone / safeTotal) * 1000) / 10) : 0;
  const meta = safeTotal > 0
    ? `${safeDone.toLocaleString()} of ${safeTotal.toLocaleString()} files`
    : 'preparing…';

  const bar = stage.querySelector('[data-progress-bar]');
  const m = stage.querySelector('[data-progress-meta]');
  const p = stage.querySelector('[data-progress-pct]');
  if (bar) bar.style.width = `${pct}%`;
  if (m) m.textContent = meta;
  if (p) p.textContent = `${pct}%`;
}

function formatTimestamp(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString([], {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}

function renderPending(pendingDrives = []) {
  const list = document.getElementById('pendingList');
  if (!list) return;

  if (!pendingDrives || pendingDrives.length === 0) {
    list.innerHTML = `<div class="subline" style="text-align: center; margin-top: 0;">No drives waiting to be processed.</div>`;
    return;
  }

  list.innerHTML = pendingDrives.map(drive => {
    const name = esc(drive.name || 'Unnamed Drive');
    const size = (typeof drive.sizeTB === 'number') ? drive.sizeTB : 0;
    return `
      <div class="pending-item">
        <div class="pending-item-name">${name}</div>
        <div class="pending-item-size">${esc(size)} TB</div>
      </div>
    `;
  }).join('');
}

// --- "Clear completed" view filter ---------------------------------------
// Clearing the completed list is a per-browser view action: the drives stay in
// completedDrives.csv (and in status.json) forever, but we remember the newest
// timestamp the operator chose to clear and hide anything at or before it. Using
// the timestamp (not the name) as the cutoff keeps this correct even when two
// drives share the same name. ISO timestamps (fixed "YYYY-MM-DDTHH:MM:SS" form)
// compare correctly as plain strings.
const CLEARED_KEY = 'dob_completed_cleared_before';

function getClearedBefore() {
  try { return localStorage.getItem(CLEARED_KEY) || ''; } catch { return ''; }
}

function visibleCompletedDrives(completedDrives = []) {
  const cleared = getClearedBefore();
  return (completedDrives || []).filter(
    d => !cleared || !d.timestamp || String(d.timestamp) > cleared
  );
}

// Hide everything currently completed by remembering the newest timestamp, then
// re-render the (now empty) list. Called from the WebUI "Clear" button.
export function clearCompletedHistory(completedDrives = []) {
  const tss = (completedDrives || []).map(d => d.timestamp).filter(Boolean).sort();
  const marker = tss.length ? tss[tss.length - 1] : new Date().toISOString().slice(0, 19);
  try { localStorage.setItem(CLEARED_KEY, marker); } catch { /* ignore */ }
  renderHistory(completedDrives);
}

function renderHistory(completedDrives = []) {
  const list = document.getElementById('historyList');
  if (!list) return;

  const visible = visibleCompletedDrives(completedDrives);

  if (visible.length === 0) {
    list.innerHTML = `<div class="subline" style="text-align: center; margin-top: 0;">No drives completed in the last 24 hours.</div>`;
    return;
  }

  // Reverse the array to show most recent at the top
  const drives = [...visible].reverse();

  list.innerHTML = drives.map(drive => {
    // Coloring is driven by verification: verified drives are green, drives that
    // failed imagery verification are yellow with an explanatory note. Drives
    // without packfiles (and legacy rows) default to verified. A copy-issues
    // drive is also shown yellow, preserving the existing "Experienced Issues"
    // wording.
    const verified = drive.verified !== false;
    const hasIssues = !!drive.issues;
    const isWarning = !verified || hasIssues;
    const itemClass = isWarning ? 'is-warning' : 'is-success';
    const icon = isWarning ? ICONS.warn : ICONS.check;
    const label = hasIssues ? `${esc(drive.name)} Experienced Issues` : `${esc(drive.name)} Completed`;
    const when = formatTimestamp(drive.timestamp);

    // For a drive that failed imagery verification, show the note and — when we
    // know which files were unavailable on the source drive — a collapsible list
    // so the operator can tell a source-data gap from a bot miss without it
    // crowding the row.
    let note = '';
    if (!verified) {
      note = `<div class="history-item-note">Not all imagery files were found.</div>`;
      const missing = Array.isArray(drive.missingImagery) ? drive.missingImagery.filter(Boolean) : [];
      if (missing.length) {
        const n = missing.length;
        const summary = `${n} file${n === 1 ? '' : 's'} unavailable on the source drive`;
        note += `
          <details class="history-missing">
            <summary class="history-missing-summary">${esc(summary)}</summary>
            <ul class="history-missing-list">
              ${missing.map(f => `<li>${esc(f)}</li>`).join('')}
            </ul>
          </details>`;
      }
    }

    return `
      <div class="history-item ${itemClass}">
        <div class="history-item-icon">${icon}</div>
        <div class="history-item-body">
          <div class="history-item-text">${label}</div>
          ${note}
          ${when ? `<div class="history-item-time">${esc(when)}</div>` : ''}
        </div>
      </div>
    `;
  }).join('');
}
