import { useCallback, useEffect, useMemo, useState } from 'react';

import TopBar from './components/TopBar.jsx';
import AdminPanel from './components/AdminPanel.jsx';
import LabelPreview from './components/LabelPreview.jsx';
import StatusBanner from './components/StatusBanner.jsx';
import Toast from './components/Toast.jsx';
import { TextField, SelectField } from './components/Field.jsx';
import { PrinterIcon } from './components/Icons.jsx';

import useAdminUnlock from './useAdminUnlock.js';
import { fetchPrintDefaults, printLabel } from './api.js';
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

  const admin = useAdminUnlock();

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

  const setLabelField = (key) => (value) => setLabel((prev) => ({ ...prev, [key]: value }));

  const clearLabel = useCallback(() => {
    setLabel(EMPTY_LABEL);
    setStatus({ kind: null, message: '' });
  }, []);

  const actionText = useMemo(
    () => PRINT_MODES.find((m) => m.value === mode)?.action ?? 'Print Label',
    [mode]
  );

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

  return (
    <div className="shell">
      <TopBar
        onSecretClick={admin.registerClick}
        hinting={admin.hinting}
        adminUnlocked={admin.unlocked}
      />

      <main className="wrap">
        <div className="intro">
          <h1 className="intro-title">Print a drive label</h1>
          <p className="intro-sub">Fill in the details, hit print, stick it on.</p>
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
              placeholder="e.g. Australia"
            />
            <TextField
              id="purpose"
              label="Purpose"
              value={label.purpose}
              onChange={setLabelField('purpose')}
              placeholder="e.g. Master"
            />
            <TextField
              id="boxSerial"
              label="Box Serial"
              value={label.box_serial}
              onChange={setLabelField('box_serial')}
              placeholder="e.g. 000000"
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
              placeholder="e.g. Max"
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

      <footer className="foot">
        <span>Drive Label</span>
        <span className="foot-dot" aria-hidden="true">·</span>
        <span>one round sticker at a time</span>
      </footer>

      {admin.justUnlocked && <Toast onDone={admin.clearJustUnlocked} />}
    </div>
  );
}
