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
    name: 'Running=1, Status=7 shows copying airport files with spinner',
    state: { Running: 1, StatusNumber: 7 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 7); if (!r.passed) return r;
      if (!$(doc, '.spinner')) return fail('spinner missing');
      const card = $(doc, '.card');
      if (!/copying airport files/i.test(card.textContent)) return fail('expected "copying airport files" copy');
      if (!/unzipping/i.test(card.textContent)) return fail('expected "unzipping" copy');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=8 with 3/6 main files renders 50% country-files bar',
    state: { Running: 1, StatusNumber: 8, CompletedMainFiles: 3, TotalMainFiles: 6 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 8); if (!r.passed) return r;
      const card = $(doc, '.card');
      if (!/country files/i.test(card.textContent)) return fail('expected "country files" copy');
      const bar = $(doc, '[data-progress-bar]');
      if (!bar || bar.style.width !== '50%') {
        return fail(`expected 50% width, got "${bar && bar.style.width}"`);
      }
      const meta = $(doc, '[data-progress-meta]');
      if (!meta || !/3 of 6 files/.test(meta.textContent)) {
        return fail(`progress meta="${meta && meta.textContent}", expected "3 of 6 files"`);
      }
      return ok();
    },
  },

  {
    name: 'Running=1, Status=9 shows formatting drive with spinner and no progress bar',
    state: { Running: 1, StatusNumber: 9 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 9); if (!r.passed) return r;
      if (!$(doc, '.spinner')) return fail('spinner missing');
      const card = $(doc, '.card');
      if (!/formatting drive/i.test(card.textContent)) return fail('expected "formatting drive" copy');
      if ($(doc, '[data-progress-bar]')) return fail('formatting step should not show a progress bar');
      return ok();
    },
  },

  {
    name: 'Pending list renders drive names and rounded TB sizes',
    state: { Running: 1, StatusNumber: 0, PendingDrives: [
      { name: 'BasinElectric', sizeTB: 2 },
      { name: 'Swedish_NP', sizeTB: 1 },
    ] },
    check(doc) {
      const items = $$(doc, '#pendingList .pending-item');
      if (items.length !== 2) return fail(`expected 2 pending items, got ${items.length}`);
      const text = $(doc, '#pendingList').textContent;
      if (!/BasinElectric/.test(text)) return fail('expected BasinElectric in pending list');
      if (!/2 TB/.test(text)) return fail('expected "2 TB" size label');
      if (!/Swedish_NP/.test(text)) return fail('expected Swedish_NP in pending list');
      return ok();
    },
  },

  {
    name: 'Empty pending list shows a friendly placeholder',
    state: { Running: 1, StatusNumber: 0, PendingDrives: [] },
    check(doc) {
      const text = $(doc, '#pendingList')?.textContent || '';
      if (!/no drives waiting/i.test(text)) return fail('expected empty pending placeholder');
      return ok();
    },
  },

  {
    name: 'Blank drives awaiting input reveal the name-drives button + count',
    state: { Running: 1, StatusNumber: 0, BlankDrives: [
      { token: 'blk-1-E', sizeTB: 2 }, { token: 'blk-2-F', sizeTB: 4 },
    ] },
    check(doc) {
      const btn = $(doc, '#nameDriveBtn');
      if (!btn) return fail('name-drives button missing');
      if (!btn.classList.contains('is-visible')) return fail('name-drives button should be visible');
      const count = $(doc, '#nameDriveCount');
      if (!count || count.textContent !== '2') return fail(`expected count "2", got "${count && count.textContent}"`);
      return ok();
    },
  },

  {
    name: 'Stopped bot clears pending list/badge and hides the name-drives button',
    setupBefore: { Running: 1, StatusNumber: 0,
      PendingDrives: [{ name: 'BasinElectric', sizeTB: 2 }],
      BlankDrives: [{ token: 'blk-1-E', sizeTB: 2 }] },
    state: { Running: 0, StatusNumber: 0,
      PendingDrives: [{ name: 'BasinElectric', sizeTB: 2 }],
      BlankDrives: [{ token: 'blk-1-E', sizeTB: 2 }] },
    check(doc) {
      const count = $(doc, '#pendingCount');
      if (count && count.classList.contains('is-visible')) return fail('pending badge should be hidden when stopped');
      const nameBtn = $(doc, '#nameDriveBtn');
      if (nameBtn && nameBtn.classList.contains('is-visible')) return fail('name-drives button should be hidden when stopped');
      const text = $(doc, '#pendingList')?.textContent || '';
      if (!/no drives waiting/i.test(text)) return fail('pending list should be empty when stopped');
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
