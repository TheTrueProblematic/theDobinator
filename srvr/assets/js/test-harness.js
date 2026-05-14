// Test harness: drives the preview iframe with mock states and runs assertions.

import { STATUS_LABELS } from './render.js';

// Dynamic import so each "Run all assertions" pulls a fresh copy and we
// never stare at a cached old version while iterating on the test suite.
async function loadAssertions() {
  const mod = await import(`../../tests/assertions.js?t=${Date.now()}`);
  return mod.ASSERTIONS;
}

const STATE_BUTTONS = [
  { sn: 0,  label: '0 · Scanning' },
  { sn: 1,  label: '1 · Preparing' },
  { sn: 2,  label: '2 · Region' },
  { sn: 3,  label: '3 · Region copy' },
  { sn: 4,  label: '4 · Matching' },
  { sn: 5,  label: '5 · File copy' },
  { sn: 6,  label: '6 · Issues' },
  { sn: 10, label: '10 · Success' },
  { sn: 11, label: '11 · Errors' },
];

const state = {
  Running: 1,
  StatusNumber: 0,
  TotalBaseFiles: 100,
  CompletedBaseFiles: 25,
  TotalMainFiles: 1000,
  CompletedMainFiles: 350,
};

let iframe;
let activeBtn = null;

function $(sel) { return document.querySelector(sel); }

function applyStateToPreview(s) {
  if (!iframe || !iframe.contentWindow) return;
  // Direct call is faster + more predictable than postMessage.
  if (typeof iframe.contentWindow.applyState === 'function') {
    iframe.contentWindow.applyState(s);
  } else {
    iframe.contentWindow.postMessage({ type: 'setState', state: s }, '*');
  }
}

function pushState() { applyStateToPreview(state); }

function buildStateButtons() {
  const container = $('#statusButtons');
  container.innerHTML = '';
  for (const { sn, label } of STATE_BUTTONS) {
    const btn = document.createElement('button');
    btn.className = 'test-btn';
    btn.dataset.sn = sn;
    btn.textContent = label;
    btn.title = STATUS_LABELS[sn];
    btn.addEventListener('click', () => {
      state.StatusNumber = sn;
      setActive(btn);
      pushState();
    });
    container.appendChild(btn);
  }
  setActive(container.querySelector('[data-sn="0"]'));
}

function setActive(btn) {
  if (activeBtn) activeBtn.classList.remove('is-active');
  activeBtn = btn;
  if (btn) btn.classList.add('is-active');
}

function buildToggle() {
  const wrap = $('#runningToggle');
  wrap.innerHTML = '';
  [['Running', 1], ['Stopped', 0]].forEach(([label, val]) => {
    const btn = document.createElement('button');
    btn.className = 'test-btn' + (state.Running === val ? ' is-active' : '');
    btn.textContent = label;
    btn.addEventListener('click', () => {
      state.Running = val;
      buildToggle();
      pushState();
    });
    wrap.appendChild(btn);
  });
}

function buildSliders() {
  const sliders = [
    { key: 'CompletedBaseFiles', max: () => state.TotalBaseFiles, label: 'Completed base files' },
    { key: 'TotalBaseFiles',     max: () => 1000,                  label: 'Total base files' },
    { key: 'CompletedMainFiles', max: () => state.TotalMainFiles, label: 'Completed main files' },
    { key: 'TotalMainFiles',     max: () => 5000,                  label: 'Total main files' },
  ];
  const wrap = $('#sliders');
  wrap.innerHTML = '';
  for (const s of sliders) {
    const row = document.createElement('div');
    const lbl = document.createElement('div');
    lbl.className = 'test-label';
    const labelText = document.createElement('span'); labelText.textContent = s.label;
    const valueText = document.createElement('span'); valueText.textContent = state[s.key];
    lbl.appendChild(labelText); lbl.appendChild(valueText);

    const input = document.createElement('input');
    input.type = 'range';
    input.className = 'test-slider';
    input.min = -1;
    input.max = s.max();
    input.value = state[s.key];
    input.addEventListener('input', () => {
      state[s.key] = parseInt(input.value, 10);
      valueText.textContent = state[s.key];
      pushState();
    });

    row.appendChild(lbl);
    row.appendChild(input);
    wrap.appendChild(row);
  }
}

function buildPresets() {
  const presets = [
    { label: 'Off', state: { Running: 0, StatusNumber: 0 } },
    { label: 'Connection error', state: { _error: true, _errorMessage: 'fetch failed (mock)', Running: -1 } },
    { label: 'Mid base copy', state: { Running: 1, StatusNumber: 3, CompletedBaseFiles: 50, TotalBaseFiles: 100 } },
    { label: 'Mid main copy', state: { Running: 1, StatusNumber: 5, CompletedMainFiles: 1234, TotalMainFiles: 5000 } },
  ];
  const wrap = $('#presets');
  wrap.innerHTML = '';
  for (const p of presets) {
    const btn = document.createElement('button');
    btn.className = 'test-btn';
    btn.textContent = p.label;
    btn.addEventListener('click', () => applyStateToPreview(p.state));
    wrap.appendChild(btn);
  }
}

async function runAll() {
  const out = $('#testResults');
  out.innerHTML = '<div>Running…</div>';

  let passed = 0, failed = 0;
  const lines = [];
  const assertions = await loadAssertions();

  for (const a of assertions) {
    if (a.setupBefore) {
      applyStateToPreview(a.setupBefore);
      await waitFrame();
    }
    applyStateToPreview(a.state);
    await waitFrame();
    let result;
    try {
      result = a.check(iframe.contentDocument);
    } catch (err) {
      result = { passed: false, message: 'threw: ' + (err && err.message || err) };
    }
    if (result.passed) {
      passed++;
      lines.push(`<div class="pass">PASS · ${escapeHtml(a.name)}</div>`);
    } else {
      failed++;
      lines.push(`<div class="fail">FAIL · ${escapeHtml(a.name)}<br/>&nbsp;&nbsp;&nbsp;${escapeHtml(result.message)}</div>`);
    }
  }

  lines.push(`<div class="summary ${failed === 0 ? 'pass' : 'fail'}">
    ${passed}/${passed + failed} passed${failed > 0 ? ` · ${failed} failing` : ''}</div>`);
  out.innerHTML = lines.join('');

  // Reset preview to whatever the controls say
  pushState();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
}

function waitFrame() {
  return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
}

function init() {
  iframe = $('#previewFrame');
  buildStateButtons();
  buildToggle();
  buildSliders();
  buildPresets();
  $('#runAssertions').addEventListener('click', runAll);

  // Wait for iframe ready, then push initial state
  if (iframe.contentDocument && iframe.contentDocument.readyState === 'complete'
      && iframe.contentWindow.applyState) {
    pushState();
  } else {
    iframe.addEventListener('load', () => setTimeout(pushState, 50));
  }
  window.addEventListener('message', (e) => {
    if (e.data && e.data.type === 'preview-ready') pushState();
  });
}

document.addEventListener('DOMContentLoaded', init);
