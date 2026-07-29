// Inline SVG icons. Every one strokes/fills with `currentColor` so it inherits
// the surrounding text colour — which is also what keeps them legible when a
// dark-mode extension recolours the page.

const base = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': 'true',
  focusable: 'false',
};

export function LabelMark(props) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="2.25" />
    </svg>
  );
}

export function DriveIcon(props) {
  return (
    <svg {...base} {...props}>
      <rect x="2.5" y="6" width="19" height="12" rx="2.5" />
      <circle cx="16.5" cy="12" r="2.5" />
      <path d="M6 9.5h4M6 14.5h4" />
    </svg>
  );
}

export function PrinterIcon(props) {
  return (
    <svg {...base} {...props}>
      <path d="M6 9V2h12v7" />
      <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
      <rect x="6" y="14" width="12" height="8" rx="1" />
    </svg>
  );
}

export function CheckIcon(props) {
  return (
    <svg {...base} strokeWidth="2.4" {...props}>
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

export function AlertIcon(props) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v4.5" />
      <path d="M12 16h.01" />
    </svg>
  );
}

export function KeyIcon(props) {
  return (
    <svg {...base} {...props}>
      <circle cx="8" cy="15" r="4" />
      <path d="M10.9 12.1L20 3" />
      <path d="M16.5 6.5l2.5 2.5" />
    </svg>
  );
}

export function LockIcon(props) {
  return (
    <svg {...base} {...props}>
      <rect x="4.5" y="10.5" width="15" height="10" rx="2" />
      <path d="M8 10.5V7a4 4 0 0 1 8 0v3.5" />
    </svg>
  );
}

export function QrGlyph(props) {
  // Decorative stand-in for the real QR code on the label preview.
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false" {...props}>
      <path d="M3 3h7v7H3V3zm2 2v3h3V5H5zM14 3h7v7h-7V3zm2 2v3h3V5h-3zM3 14h7v7H3v-7zm2 2v3h3v-3H5z" />
      <path d="M14 14h2v2h-2v-2zm3 0h2v2h-2v-2zm2 2h2v2h-2v-2zm-5 3h2v2h-2v-2zm3 0h2v2h-2v-2z" />
    </svg>
  );
}
