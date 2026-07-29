import { TextField, SelectField } from './Field.jsx';
import { KeyIcon, LockIcon } from './Icons.jsx';
import { PRINT_MODES, PRINT_SCALES } from '../constants.js';

// Everything in here is hidden until the secret handshake. These values come
// pre-filled from the box's installed driveLabelPrinter label.json, so a normal
// operator never needs to see — or be able to break — them.
export default function AdminPanel({ mode, setMode, printer, setPrinter, onLock, defaultsSource }) {
  const set = (key) => (value) => setPrinter({ ...printer, [key]: value });

  return (
    <section className="admin" aria-label="Administrator settings">
      <div className="admin-head">
        <span className="admin-title">
          <KeyIcon className="admin-title-icon" />
          Admin
        </span>
        <button type="button" className="ghost-btn" onClick={onLock}>
          <LockIcon />
          Lock
        </button>
      </div>

      <p className="admin-note">
        {defaultsSource === 'live'
          ? 'Loaded from the printer configuration on this machine.'
          : 'Could not read the printer configuration — showing built-in fallbacks.'}
      </p>

      <SelectField
        id="mode"
        label="Mode"
        value={mode}
        onChange={setMode}
        options={PRINT_MODES}
      />

      <div className="admin-divider" role="presentation" />

      <TextField
        id="printerName"
        label="Printer Name"
        value={printer.printer_name}
        onChange={set('printer_name')}
        placeholder="Brother QL-810W"
      />
      <TextField
        id="cageCode"
        label="CAGE Code"
        value={printer.cage_code}
        onChange={set('cage_code')}
        placeholder="5ET05"
      />
      <TextField
        id="qrUrl"
        label="QR URL"
        value={printer.qr_url}
        onChange={set('qr_url')}
        placeholder="churchillnavigation.com/specifications"
      />
      <TextField
        id="copies"
        label="Copies"
        type="number"
        inputMode="numeric"
        min="1"
        step="1"
        value={printer.copies}
        onChange={set('copies')}
      />
      <TextField
        id="labelMedia"
        label="Label Media"
        value={printer.label_media}
        onChange={set('label_media')}
        placeholder={'0.94" Dia'}
      />
      <SelectField
        id="printScale"
        label="Print Scale"
        value={printer.print_scale}
        onChange={set('print_scale')}
        options={PRINT_SCALES}
      />
      <TextField
        id="masterPath"
        label="Master Records Path"
        value={printer.master_records_path}
        onChange={set('master_records_path')}
        placeholder="Z:\SerialNumbers\SERIAL_NUMBERS.txt"
      />
    </section>
  );
}
