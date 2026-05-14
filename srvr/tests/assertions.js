// Assertion suite for the portal.
// Each entry: { name, state, check(doc) -> { passed, message } }
// `doc` is the preview iframe's document.

function $(doc, sel)  { return doc.querySelector(sel); }
function $$(doc, sel) { return Array.from(doc.querySelectorAll(sel)); }

function ok(msg)        { return { passed: true,  message: msg || 'ok' }; }
function fail(msg)      { return { passed: false, message: msg }; }
function expect(cond, ifPass, ifFail) { return cond ? ok(ifPass) : fail(ifFail); }

function bodyAttrs(doc, expectedRunning, expectedStatus) {
  const r = doc.body.dataset.running;
  const s = doc.body.dataset.status;
  if (r !== String(expectedRunning)) {
    return fail(`body data-running="${r}", expected "${expectedRunning}"`);
  }
  if (s !== String(expectedStatus)) {
    return fail(`body data-status="${s}", expected "${expectedStatus}"`);
  }
  return ok();
}

export const ASSERTIONS = [
  {
    name: 'Running=0 shows the OFF screen with no card',
    state: { Running: 0, StatusNumber: 0 },
    check(doc) {
      const r = bodyAttrs(doc, 0, 0); if (!r.passed) return r;
      if ($(doc, '.card')) return fail('status card should be hidden when Running=0');
      const off = $(doc, '[data-screen="off"]');
      if (!off) return fail('off-screen element missing');
      if (!/not running/i.test(off.textContent)) return fail('expected "not running" copy');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=0 shows scanning radar',
    state: { Running: 1, StatusNumber: 0 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 0); if (!r.passed) return r;
      const card = $(doc, '.card[data-screen="on"]');
      if (!card) return fail('status card missing');
      if (!$(doc, '.radar')) return fail('radar element missing for scanning state');
      if (!/scanning/i.test(card.textContent)) return fail('expected "scanning" copy');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=1 shows preparing copy with spinner',
    state: { Running: 1, StatusNumber: 1 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 1); if (!r.passed) return r;
      if (!$(doc, '.spinner')) return fail('spinner missing');
      if (!/preparing/i.test($(doc, '.card').textContent)) return fail('expected "preparing" copy');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=2 shows identifying region',
    state: { Running: 1, StatusNumber: 2 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 2); if (!r.passed) return r;
      if (!$(doc, '.spinner')) return fail('spinner missing');
      if (!/identifying region/i.test($(doc, '.card').textContent)) return fail('expected "identifying region" copy');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=3 with 7/10 base files renders 70% progress bar',
    state: { Running: 1, StatusNumber: 3, CompletedBaseFiles: 7, TotalBaseFiles: 10 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 3); if (!r.passed) return r;
      const bar = $(doc, '[data-progress-bar]');
      if (!bar) return fail('progress bar missing');
      const w = bar.style.width;
      if (w !== '70%') return fail(`progress bar width="${w}", expected "70%"`);
      const meta = $(doc, '[data-progress-meta]');
      if (!meta || !/7 of 10 files/.test(meta.textContent)) {
        return fail(`progress meta="${meta && meta.textContent}", expected "7 of 10 files"`);
      }
      return ok();
    },
  },

  {
    name: 'Running=1, Status=3 with -1/-1 shows preparing meta and 0% bar',
    state: { Running: 1, StatusNumber: 3, CompletedBaseFiles: -1, TotalBaseFiles: -1 },
    check(doc) {
      const bar = $(doc, '[data-progress-bar]');
      if (!bar) return fail('progress bar missing');
      if (bar.style.width !== '0%') return fail(`expected 0% width, got "${bar.style.width}"`);
      const meta = $(doc, '[data-progress-meta]');
      if (!meta || !/preparing/i.test(meta.textContent)) {
        return fail(`expected "preparing" meta, got "${meta && meta.textContent}"`);
      }
      return ok();
    },
  },

  {
    name: 'Running=1, Status=4 shows matching files',
    state: { Running: 1, StatusNumber: 4 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 4); if (!r.passed) return r;
      if (!/matching .*files/i.test($(doc, '.card').textContent)) return fail('expected "matching … files" copy');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=5 with 250/500 main files renders 50% progress bar',
    state: { Running: 1, StatusNumber: 5, CompletedMainFiles: 250, TotalMainFiles: 500 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 5); if (!r.passed) return r;
      const bar = $(doc, '[data-progress-bar]');
      if (!bar || bar.style.width !== '50%') {
        return fail(`expected 50% width, got "${bar && bar.style.width}"`);
      }
      const meta = $(doc, '[data-progress-meta]');
      if (!/250 of 500 files/.test(meta.textContent)) return fail('expected "250 of 500 files" meta');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=6 shows danger card with documentation copy',
    state: { Running: 1, StatusNumber: 6 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 6); if (!r.passed) return r;
      const card = $(doc, '.card.is-danger');
      if (!card) return fail('expected card with .is-danger class');
      if (!/issues detected/i.test(card.textContent)) return fail('expected "issues detected" copy');
      if (!/documentation/i.test(card.textContent)) return fail('expected "documentation" copy');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=10 shows green success card',
    state: { Running: 1, StatusNumber: 10 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 10); if (!r.passed) return r;
      const card = $(doc, '.card.is-success');
      if (!card) return fail('expected card with .is-success class');
      if (!/completed successfully/i.test(card.textContent)) return fail('expected "completed successfully" copy');
      if (!$(doc, '.status-icon.is-success')) return fail('expected success icon');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=11 shows orange warning card with ISSUES.md note',
    state: { Running: 1, StatusNumber: 11 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 11); if (!r.passed) return r;
      const card = $(doc, '.card.is-warning');
      if (!card) return fail('expected card with .is-warning class');
      if (!/errors detected/i.test(card.textContent)) return fail('expected "errors detected" copy');
      if (!/ISSUES\.md/.test(card.textContent)) return fail('expected ISSUES.md reference');
      return ok();
    },
  },

  {
    name: 'Power button is always present in topbar',
    state: { Running: 1, StatusNumber: 0 },
    check(doc) {
      if (!$(doc, '#powerBtn')) return fail('power button missing');
      return ok();
    },
  },

  {
    name: 'Switching Running=1 -> Running=0 hides the card',
    state: { Running: 0, StatusNumber: 0 },
    setupBefore: { Running: 1, StatusNumber: 5, CompletedMainFiles: 5, TotalMainFiles: 10 },
    check(doc) {
      if ($(doc, '.card')) return fail('card should be gone after Running flips to 0');
      if (!$(doc, '[data-screen="off"]')) return fail('off-screen should be visible');
      return ok();
    },
  },

  {
    name: 'Connection error renders error screen',
    state: { _error: true, _errorMessage: 'simulated network failure', Running: -1 },
    check(doc) {
      const err = $(doc, '[data-screen="error"]');
      if (!err) return fail('error screen missing');
      if (!/simulated network failure/.test(err.textContent)) return fail('expected error message rendered');
      return ok();
    },
  },
];
