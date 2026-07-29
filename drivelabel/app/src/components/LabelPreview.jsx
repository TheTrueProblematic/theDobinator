import { QrGlyph } from './Icons.jsx';

// Mirrors the real round die-cut label produced by driveLabelPrinter, laid out
// from a photo of an actual print:
//
//        SHOT          <- wordmark, centred at the top
//        OVER
//   Customer           <- left-aligned content block
//   Purpose
//   Box #: 000000
//   [QR]  2026-07-29   <- QR bottom-left, print date + CAGE stacked to its right
//         Cage
//         5ET05
//
// Only the fields that actually get printed appear here. Hardware and Prepared
// By are recorded to the master records file rather than printed, so their
// absence doubles as a quiet explanation of why.
//
// The wordmark, the print date and the "Cage" caption all come from the label
// template itself, not from the form — they're fixed here for the same reason.
export default function LabelPreview({ customer, purpose, boxSerial, cageCode }) {
  const has = (v) => Boolean(v && v.trim());
  const val = (v, fallback) => (has(v) ? v.trim() : fallback);

  // driveLabelPrinter stamps the day it prints. Built from local date parts
  // rather than toISOString() so an evening print doesn't show tomorrow.
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const printedDate = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

  return (
    <aside className="preview" aria-label="Label preview">
      <div className="preview-disc">
        <div className="preview-inner">
          <div className="preview-wordmark" aria-hidden="true">
            <span>SHOT</span>
            <span>OVER</span>
          </div>

          <div className="preview-lines">
            <div className={`preview-line preview-customer${has(customer) ? '' : ' is-empty'}`}>
              {val(customer, 'Customer')}
            </div>
            <div className={`preview-line preview-purpose${has(purpose) ? '' : ' is-empty'}`}>
              {val(purpose, 'Purpose')}
            </div>
            {/* "Box #:" is part of the printed template, so it stays at full
                strength; only the value greys out when nothing is entered. */}
            <div className="preview-line">
              <span>Box #:</span>{' '}
              <span className={has(boxSerial) ? undefined : 'is-empty'}>
                {val(boxSerial, '000000')}
              </span>
            </div>
          </div>

          <div className="preview-bottom">
            <QrGlyph className="preview-qr" />
            <div className="preview-meta">
              <span>{printedDate}</span>
              <span>Cage</span>
              <span className={has(cageCode) ? '' : 'is-empty'}>{val(cageCode, '—')}</span>
            </div>
          </div>
        </div>
      </div>
      <p className="preview-caption">Preview</p>
    </aside>
  );
}
