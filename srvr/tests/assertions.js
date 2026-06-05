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
    name: 'Update available (no reboot) shows yellow update button, not red',
    state: { Running: 1, StatusNumber: 0, UpdateAvailable: 1, RebootRequired: 0 },
    check(doc) {
      const b = $(doc, '#updateBtn');
      if (!b) return fail('update button missing');
      if (!b.classList.contains('is-visible')) return fail('update button should be visible');
      if (b.classList.contains('is-reboot')) return fail('should NOT be red when no reboot required');
      if (!/update available/i.test(b.getAttribute('title') || '')) return fail('expected "Update available" title');
      return ok();
    },
  },

  {
    name: 'Reboot-required update shows red button with "Restart required"',
    state: { Running: 1, StatusNumber: 0, UpdateAvailable: 1, RebootRequired: 1 },
    check(doc) {
      const b = $(doc, '#updateBtn');
      if (!b) return fail('update button missing');
      if (!b.classList.contains('is-visible')) return fail('update button should be visible');
      if (!b.classList.contains('is-reboot')) return fail('expected red is-reboot class');
      if (!/restart required/i.test(b.getAttribute('title') || '')) return fail('expected "Restart required" title');
      return ok();
    },
  },

  {
    name: 'Update button hidden when not running even if update available',
    state: { Running: 0, StatusNumber: 0, UpdateAvailable: 1, RebootRequired: 1 },
    check(doc) {
      const b = $(doc, '#updateBtn');
      if (b && b.classList.contains('is-visible')) return fail('update button should be hidden when stopped');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=12 shows verifying imagery with spinner',
    state: { Running: 1, StatusNumber: 12 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 12); if (!r.passed) return r;
      if (!$(doc, '.spinner')) return fail('spinner missing');
      if (!/verifying imagery/i.test($(doc, '.card').textContent)) return fail('expected "verifying imagery" copy');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=13 shows correcting missed imagery',
    state: { Running: 1, StatusNumber: 13 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 13); if (!r.passed) return r;
      if (!/correcting missed imagery/i.test($(doc, '.card').textContent)) return fail('expected "correcting missed imagery" copy');
      return ok();
    },
  },

  {
    name: 'Running=1, Status=14 with 2/4 main files renders 50% corrected-copy bar',
    state: { Running: 1, StatusNumber: 14, CompletedMainFiles: 2, TotalMainFiles: 4 },
    check(doc) {
      const r = bodyAttrs(doc, 1, 14); if (!r.passed) return r;
      if (!/corrected imagery/i.test($(doc, '.card').textContent)) return fail('expected "corrected imagery" copy');
      const bar = $(doc, '[data-progress-bar]');
      if (!bar || bar.style.width !== '50%') return fail(`expected 50% width, got "${bar && bar.style.width}"`);
      return ok();
    },
  },

  {
    name: 'Verify detail: correction run with <3 missing shows attempt count + filenames',
    state: {
      Running: 1, StatusNumber: 13, VerifyRun: 2, VerifyMaxRuns: 5,
      VerifyMissingCount: 2,
      VerifyMissing: ['usa_tx_houston.ecw', 'usa_ca_fresno.ecw'],
    },
    check(doc) {
      const detail = $(doc, '.verify-detail');
      if (!detail) return fail('expected .verify-detail block');
      if (!/attempt\s+2\s+of\s+5/i.test(detail.textContent)) return fail('expected "attempt 2 of 5"');
      const items = $$(doc, '.verify-missing-list li').map(li => li.textContent);
      if (items.length !== 2) return fail(`expected 2 listed files, got ${items.length}`);
      if (!items.includes('usa_tx_houston.ecw') || !items.includes('usa_ca_fresno.ecw')) {
        return fail(`missing expected filenames, got ${JSON.stringify(items)}`);
      }
      return ok();
    },
  },

  {
    name: 'Verify detail: 3+ missing shows the count only, never the filenames',
    state: {
      Running: 1, StatusNumber: 13, VerifyRun: 4, VerifyMaxRuns: 5,
      VerifyMissingCount: 12,
      VerifyMissing: [],   // backend withholds names when 3+ remain
    },
    check(doc) {
      const detail = $(doc, '.verify-detail');
      if (!detail) return fail('expected .verify-detail block');
      if (!/attempt\s+4\s+of\s+5/i.test(detail.textContent)) return fail('expected "attempt 4 of 5"');
      if (!/12\s+imagery files/i.test(detail.textContent)) return fail('expected "12 imagery files" count');
      if ($(doc, '.verify-missing-list')) return fail('filenames must NOT be listed when 3+ are missing');
      return ok();
    },
  },

  {
    name: 'Verify detail: initial verify pass (no run, none flagged) adds no detail block',
    state: { Running: 1, StatusNumber: 12, VerifyRun: 0, VerifyMissingCount: 0, VerifyMissing: [] },
    check(doc) {
      if (!/verifying imagery/i.test($(doc, '.card').textContent)) return fail('expected "verifying imagery" copy');
      if ($(doc, '.verify-detail')) return fail('verify-detail should be absent during the initial pass');
      return ok();
    },
  },

  {
    name: 'Completed history: verified drive is green, unverified is yellow with note',
    state: { Running: 1, StatusNumber: 0, CompletedDrives: [
      { name: 'GreenDrive', issues: false, verified: true, timestamp: '2099-12-31T10:00:00' },
      { name: 'YellowDrive', issues: false, verified: false, timestamp: '2099-12-31T11:00:00' },
    ] },
    check(doc) {
      const items = $$(doc, '#historyList .history-item');
      if (items.length !== 2) return fail(`expected 2 history items, got ${items.length}`);
      // List is reversed (last array entry shown first), so YellowDrive is item 0.
      const yellow = items[0];
      const green = items[1];
      if (!yellow.classList.contains('is-warning')) return fail('unverified drive should be is-warning (yellow)');
      if (!/not all imagery files were found/i.test(yellow.textContent)) return fail('expected missing-imagery note');
      if (!green.classList.contains('is-success')) return fail('verified drive should be is-success (green)');
      if (/not all imagery/i.test(green.textContent)) return fail('verified drive must not show the note');
      return ok();
    },
  },

  {
    name: 'Completed history: unverified drive lists its unavailable imagery files',
    state: { Running: 1, StatusNumber: 0, CompletedDrives: [
      { name: 'GapDrive', issues: false, verified: false,
        missingImagery: ['usa_faa_ifr_enr_gom_vertical_flight_ref_2025-04-17_37m.esp'],
        timestamp: '2099-12-31T13:00:00' },
    ] },
    check(doc) {
      const item = $(doc, '#historyList .history-item');
      if (!item || !item.classList.contains('is-warning')) return fail('expected a yellow history item');
      if (!/not all imagery files were found/i.test(item.textContent)) return fail('expected the imagery note');
      const summary = $(doc, '#historyList .history-missing-summary');
      if (!summary) return fail('expected a missing-imagery disclosure summary');
      if (!/1 file unavailable on the source drive/i.test(summary.textContent)) {
        return fail(`expected singular "1 file unavailable" summary, got "${summary.textContent}"`);
      }
      const items = $$(doc, '#historyList .history-missing-list li');
      if (items.length !== 1) return fail(`expected 1 missing-file entry, got ${items.length}`);
      if (!/gom_vertical_flight_ref/.test(items[0].textContent)) return fail('expected the gom filename listed');
      return ok();
    },
  },

  {
    name: 'Completed history: verified drive shows no missing-imagery disclosure',
    state: { Running: 1, StatusNumber: 0, CompletedDrives: [
      { name: 'CleanDrive', issues: false, verified: true, missingImagery: [],
        timestamp: '2099-12-31T14:00:00' },
    ] },
    check(doc) {
      if ($(doc, '#historyList .history-missing')) return fail('verified drive must not show a missing-imagery disclosure');
      const item = $(doc, '#historyList .history-item');
      if (!item || !item.classList.contains('is-success')) return fail('expected a green history item');
      return ok();
    },
  },

  {
    name: 'Completed history: two drives with the same name both render without error',
    state: { Running: 1, StatusNumber: 0, CompletedDrives: [
      { name: 'SameName', issues: false, verified: true, timestamp: '2099-12-31T10:00:00' },
      { name: 'SameName', issues: false, verified: false, timestamp: '2099-12-31T11:00:00' },
    ] },
    check(doc) {
      const items = $$(doc, '#historyList .history-item');
      if (items.length !== 2) return fail(`expected 2 history items for duplicate names, got ${items.length}`);
      if (!items[0].classList.contains('is-warning')) return fail('the unverified SameName should be yellow');
      if (!items[1].classList.contains('is-success')) return fail('the verified SameName should be green');
      return ok();
    },
  },

  {
    name: 'Completed history: legacy entries with no verified flag default to green',
    state: { Running: 1, StatusNumber: 0, CompletedDrives: [
      { name: 'LegacyDrive', issues: false, timestamp: '2099-12-31T09:00:00' },
    ] },
    check(doc) {
      const item = $(doc, '#historyList .history-item');
      if (!item) return fail('legacy history item missing');
      if (!item.classList.contains('is-success')) return fail('legacy drive (no verified flag) should default to green');
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
