// Shared configuration for the Drive Label portal.

// The companion API (drivelabel/label_api.py) runs on the SAME machine as this
// site, on its own port so it stays fully independent of theDobinator's API
// (which owns 5050). Both hostnames resolve to the same box, so we build the
// URL from whatever host the page was loaded from.
export const API_PORT = 5051;

// Sibling site. theDobinator's portal links here for label printing; this site
// links back there for drive builds.
export const DOBINATOR_URL = 'http://dobinator.c-nav.com/';

// Hardware choices, in the order the operators asked for. Recorded by
// driveLabelPrinter into the master records file; not printed on the label.
export const HARDWARE_OPTIONS = [
  'ARS600',
  'Getac',
  'GEAR700',
  'ARS300/400',
  'ARS500',
  'ARS750',
  'ARS700',
  'GEAR750',
  'ION',
  'GCS',
  'AIRSCAPE',
  'MC1',
  'Other',
];

export const PRINT_MODES = [
  { value: 'print',  label: 'Print & record serial', action: 'Print Label' },
  { value: 'test',   label: 'Test print (no record)', action: 'Test Print' },
  { value: 'render', label: 'Render PDF only (no print)', action: 'Render PDF' },
];

export const PRINT_SCALES = [
  { value: 'noscale', label: 'No scaling (exact size)' },
  { value: 'fit',     label: 'Fit' },
  { value: 'shrink',  label: 'Shrink' },
];

// Printer-side fallbacks, mirroring driveLabelPrinter's example label.json.
// Used only if GET /print-defaults can't be reached — the real values come from
// the installed C:\driveLabelPrinter\label.json.
//
// NOTE: intentionally no label-content defaults. Customer / Purpose / Box
// Serial / Hardware / Prepared By always start blank, even when label.json
// carries leftover values from a previous print.
export const PRINTER_FALLBACK_DEFAULTS = {
  printer_name: 'Brother QL-810W',
  cage_code: '5ET05',
  qr_url: 'churchillnavigation.com/specifications',
  copies: 1,
  label_media: '0.94" Dia',
  print_scale: 'noscale',
  master_records_path: 'Z:\\SerialNumbers\\SERIAL_NUMBERS.txt',
};

export const EMPTY_LABEL = {
  customer: '',
  purpose: '',
  box_serial: '',
  hardware: '',
  prepared_by: '',
};

// --- Secret admin unlock -----------------------------------------------------
// Five clicks on the brand mark inside this window reveals Mode + printer
// settings. Deliberately something nobody stumbles into: a single stray click
// does nothing, and the only hint (a small wiggle) doesn't appear until click
// three, by which point you're clearly poking at it on purpose.
export const UNLOCK_CLICKS = 5;
// Rolling window: the 5 clicks must span less than this. Generous enough to be
// comfortable on a phone, far too fast to happen by accident — a stray click a
// second apart never accumulates.
export const UNLOCK_WINDOW_MS = 3500;
export const UNLOCK_HINT_AT = 3;
export const ADMIN_STORAGE_KEY = 'drivelabel_admin_unlocked';
