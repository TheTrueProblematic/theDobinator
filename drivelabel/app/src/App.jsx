import { useCallback, useEffect, useMemo, useState } from 'react';

import TopBar from './components/TopBar.jsx';
import AdminPanel from './components/AdminPanel.jsx';
import LabelPreview from './components/LabelPreview.jsx';
import StatusBanner from './components/StatusBanner.jsx';
import Toast from './components/Toast.jsx';
import Modal from './components/Modal.jsx';
import PasswordDialog from './components/PasswordDialog.jsx';
import { TextField, SelectField } from './components/Field.jsx';
import { PrinterIcon } from './components/Icons.jsx';

import useAdminUnlock from './useAdminUnlock.js';
import useUpdateStatus from './useUpdateStatus.js';
import { fetchPrintDefaults, printLabel, applyUpdate } from './api.js';
import {
  EMPTY_LABEL,
  HARDWARE_OPTIONS,
  PRINTER_FALLBACK_DEFAULTS,
  PRINT_MODES,
} from './constants.js';

// Printer-side state is kept as strings so every control stays cleanly
// controlled; `copies` is parsed back to an int at submit time.
function printerStateFrom(defaults) {
  const d = defaults || {};
  const pick = (key) => {
    const v = d[key];
    return v === undefined || v === null || v === '' ? PRINTER_FALLBACK_DEFAULTS[key] : v;
  };
  const copies = Number.parseInt(d.copies, 10);
  return {
    printer_name: String(pick('printer_name')),
    cage_code: String(pick('cage_code')),
    qr_url: String(pick('qr_url')),
    copies: String(Number.isFinite(copies) && copies >= 1 ? copies : 1),
    label_media: String(pick('label_media')),
    print_scale: String(pick('print_scale')),
    master_records_path: String(pick('master_records_path')),
  };
}

export default function App() {
  const [label, setLabel] = useState(EMPTY_LABEL);
  const [printer, setPrinter] = useState(() => printerStateFrom(null));
  const [mode, setMode] = useState('print');
  const [defaultsSource, setDefaultsSource] = useState('fallback');
  const [status, setStatus] = useState({ kind: null, message: '' });
  const [inFlight, setInFlight] = useState(false);
  const [toast, setToast] = useState(null);
  // null | 'schedule' | 'reboot' — which update confirmation is showing.
  const [updatePrompt, setUpdatePrompt] = useState(null);
  const [updateBusy, setUpdateBusy] = useState(false);

  const admin = useAdminUnlock();
  const update = useUpdateStatus();

  // Pull the operator's real printer configuration off the box. Label content is
  // deliberately NOT seeded from it — those fields always start blank.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetchPrintDefaults();
        if (!alive) return;
        if (res && res.defaults) {
          setPrinter(printerStateFrom(res.defaults));
          setDefaultsSource('live');
        }
      } catch (err) {
        console.warn('[drivelabel] could not load printer defaults; using fallbacks:', err);
        if (alive) setDefaultsSource('fallback');
      }
    })();
    return () => { alive = false; };
  }, []);

  // Surface the admin unlock as a toast, then reset the one-shot flag.
  useEffect(() => {
    if (!admin.justUnlocked) return;
    setToast({ title: 'Admin mode unlocked', icon: 'key', tone: 'accent' });
    admin.clearJustUnlocked();
  }, [admin.justUnlocked, admin.clearJustUnlocked]);

  // Stable identity matters: Toast restarts its auto-dismiss timer whenever
  // onDone changes, so an inline arrow here would keep the toast alive for as
  // long as the operator kept typing.
  const dismissToast = useCallback(() => setToast(null), []);

  const setLabelField = (key) => (value) => setLabel((prev) => ({ ...prev, [key]: value }));

  const clearLabel = useCallback(() => {
    setLabel(EMPTY_LABEL);
    setStatus({ kind: null, message: '' });
  }, []);

  const actionText = useMemo(
    () => PRINT_MODES.find((m) => m.value === mode)?.action ?? 'Print Label',
    [mode]
  );

  // --- Update flow ---------------------------------------------------------
  // Mirrors theDobinator's rules: can't apply mid-build (offer to schedule it
  // instead), and a reboot-update needs explicit confirmation because it
  // restarts the whole PC.

  const runUpdate = useCallback(async (schedule) => {
    setUpdateBusy(true);
    setUpdatePrompt(null);
    try {
      const res = await applyUpdate({ schedule });
      setToast(
        res && res.ok
          ? {
              title: schedule ? 'Update scheduled' : 'Update started',
              icon: 'update',
              tone: 'accent',
            }
          : {
              title: (res && res.message) || 'Could not start the update.',
              icon: 'alert',
              tone: 'danger',
            }
      );
    } catch (err) {
      console.error('[drivelabel] update failed:', err);
      setToast({ title: 'Could not reach the update service.', icon: 'alert', tone: 'danger' });
    } finally {
      setUpdateBusy(false);
      update.refresh();
    }
  }, [update]);

  function handleUpdateClick() {
    if (updateBusy) return;
    if (update.status.processing) { setUpdatePrompt('schedule'); return; }
    if (update.status.reboot) { setUpdatePrompt('reboot'); return; }
    runUpdate(false);
  }

  // --- Print ---------------------------------------------------------------

  async function handleSubmit(e) {
    e.preventDefault();
    if (inFlight) return;

    const copies = Number.parseInt(printer.copies, 10);

    // Mirrors the API's own validation. These fields live behind the admin
    // handshake and are pre-filled, so a normal operator can't trip this —
    // but if they somehow do, say where to go and fix it.
    if (!printer.printer_name.trim() || !printer.cage_code.trim() || !printer.qr_url.trim()) {
      setStatus({
        kind: 'error',
        message: 'Printer name, CAGE code, and QR URL are all required. Ask an admin to check the printer settings.',
      });
      return;
    }
    if (!Number.isFinite(copies) || copies < 1) {
      setStatus({ kind: 'error', message: 'Copies must be a whole number of at least 1.' });
      return;
    }

    setInFlight(true);
    setStatus({ kind: 'pending', message: 'Sending to the label printer…' });
    try {
      const res = await printLabel({
        mode,
        printer_name: printer.printer_name.trim(),
        cage_code: printer.cage_code.trim(),
        qr_url: printer.qr_url.trim(),
        copies,
        label_media: printer.label_media.trim(),
        print_scale: printer.print_scale || 'noscale',
        master_records_path: printer.master_records_path.trim(),
        label: {
          customer: label.customer.trim(),
          purpose: label.purpose.trim(),
          hardware: label.hardware.trim(),
          prepared_by: label.prepared_by.trim(),
          box_serial: label.box_serial.trim(),
        },
      });
      if (res && res.ok) {
        setStatus({ kind: 'success', message: res.message || 'Label printed.' });
      } else {
        setStatus({
          kind: 'error',
          message: (res && res.message) || 'The label printer reported a failure.',
        });
      }
    } catch (err) {
      console.error('[drivelabel] print failed:', err);
      setStatus({
        kind: 'error',
        message: 'Could not reach the print service on this machine. Check that the Drive Label API is running on port 5051.',
      });
    } finally {
      setInFlight(false);
    }
  }

  const promptCopy = updatePrompt === 'schedule'
    ? {
        title: update.status.reboot ? 'Restart Required' : 'Update Available',
        body: update.status.reboot
          ? 'This update requires restarting the PC, which can’t happen while a drive is processing. Schedule it to update and restart once processing completes?'
          : 'The update can’t be applied while a drive is processing. Schedule it for when processing completes?',
        confirm: update.status.reboot ? 'Schedule restart' : 'Schedule',
        schedule: true,
      }
    : {
        title: 'Restart Required',
        body: 'This update requires restarting the PC. Update now and restart?',
        confirm: 'Update and restart',
        schedule: false,
      };

  return (
    <div className="shell">
      <TopBar
        onSecretClick={admin.registerClick}
        hinting={admin.hinting}
        adminUnlocked={admin.unlocked}
        updateAvailable={update.status.available}
        updateReboot={update.status.reboot}
        updateBusy={updateBusy}
        onUpdateClick={handleUpdateClick}
      />

      <main className="wrap">
        <div className="intro">
          <h1 className="intro-title">Print a drive label</h1>
        </div>

        <div className="layout">
          {/* Preview sits first in the DOM so it leads on mobile; the desktop
              grid reorders it to the right-hand rail. */}
          <div className="preview-col">
            <LabelPreview
              customer={label.customer}
              purpose={label.purpose}
              boxSerial={label.box_serial}
              cageCode={printer.cage_code}
            />
          </div>

          <form className="form-col card" onSubmit={handleSubmit} noValidate>
            <TextField
              id="customer"
              label="Customer"
              value={label.customer}
              onChange={setLabelField('customer')}
              placeholder="e.g. Texas DPS"
            />
            <TextField
              id="purpose"
              label="Purpose"
              value={label.purpose}
              onChange={setLabelField('purpose')}
              placeholder="e.g. DATA DRIVE"
            />
            <TextField
              id="boxSerial"
              label="Box Serial"
              value={label.box_serial}
              onChange={setLabelField('box_serial')}
              placeholder="e.g. 190000"
            />
            <SelectField
              id="hardware"
              label="Hardware"
              value={label.hardware}
              onChange={setLabelField('hardware')}
              options={HARDWARE_OPTIONS}
              placeholder="Select hardware…"
            />
            <TextField
              id="preparedBy"
              label="Prepared By"
              value={label.prepared_by}
              onChange={setLabelField('prepared_by')}
              placeholder="e.g. Garrett"
            />

            {admin.unlocked && (
              <AdminPanel
                mode={mode}
                setMode={setMode}
                printer={printer}
                setPrinter={setPrinter}
                onLock={() => { admin.lock(); setMode('print'); }}
                defaultsSource={defaultsSource}
              />
            )}

            <StatusBanner
              kind={status.kind}
              message={status.message}
              onClear={clearLabel}
            />

            <button type="submit" className="print-btn" disabled={inFlight}>
              <PrinterIcon className="print-btn-icon" />
              <span>{inFlight ? 'Printing…' : actionText}</span>
            </button>
          </form>
        </div>
      </main>

      {admin.asking && (
        <PasswordDialog
          onSubmit={admin.submitPassword}
          onCancel={admin.cancelPassword}
          error={admin.authError}
        />
      )}

      {updatePrompt && (
        <Modal
          title={promptCopy.title}
          onClose={() => setUpdatePrompt(null)}
          labelledBy="updatePromptTitle"
          footer={
            <>
              <button type="button" className="ghost-btn dialog-btn"
                      onClick={() => setUpdatePrompt(null)}>
                Cancel
              </button>
              <button type="button" className="print-btn dialog-btn-primary"
                      onClick={() => runUpdate(promptCopy.schedule)}>
                {promptCopy.confirm}
              </button>
            </>
          }
        >
          <p className="dialog-text">{promptCopy.body}</p>
        </Modal>
      )}

      {toast && (
        <Toast
          title={toast.title}
          icon={toast.icon}
          tone={toast.tone}
          onDone={dismissToast}
        />
      )}
    </div>
  );
}
