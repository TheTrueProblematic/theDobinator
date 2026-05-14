// State-driven rendering for The Dobinator portal.
// Pure function of state -> DOM. Sets data attributes the test harness asserts on.

export const STATUS_LABELS = {
  0: 'Scanning for Drives',
  1: 'Preparing Drive',
  2: 'Identifying Region',
  3: 'Copying Base Files',
  4: 'Matching Specific Files',
  5: 'Copying Specific Files',
  6: 'Issues Detected',
  10: 'Drive Completed Successfully',
  11: 'Drive Completed — Errors Detected',
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

function spinnerHeadline(text) {
  return `
    <div class="eyebrow"><span class="eyebrow-dot"></span> Working</div>
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

    default:
      return {
        cardClass: '',
        inner: spinnerHeadline('Working') +
          `<p class="subline">Hang tight…</p>`
      };
  }
}

function renderOff(stage) {
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
    prev.CompletedMainFiles !== state.CompletedMainFiles;

  if (!changed) return false;

  // Connection error wins over everything.
  if (state._error) {
    renderError(stage, state);
    return true;
  }

  // Running=1 with no structural change but progress changed — update bar in place
  // for smoother animation rather than re-rendering the whole card.
  if (
    prev && !prev._error &&
    prev.Running === 1 && state.Running === 1 &&
    prev.StatusNumber === state.StatusNumber &&
    (state.StatusNumber === 3 || state.StatusNumber === 5)
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
