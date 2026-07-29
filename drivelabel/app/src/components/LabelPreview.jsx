import { QrGlyph } from './Icons.jsx';

// A stylised stand-in for the round die-cut label, showing only the fields that
// actually get printed (Customer, Purpose, Box #, CAGE code, QR). Hardware and
// Prepared By are recorded to the master records file, not printed, so they're
// deliberately absent here — which doubles as a quiet explanation of why.
//
// The real artwork is rendered by driveLabelPrinter, so this is captioned as
// approximate; it's a sanity check on what you typed, not a proof.
export default function LabelPreview({ customer, purpose, boxSerial, cageCode }) {
  const has = (v) => Boolean(v && v.trim());

  return (
    <aside className="preview" aria-label="Label preview">
      <div className="preview-disc">
        <div className="preview-inner">
          <div className="preview-cage">{has(cageCode) ? cageCode.trim() : 'CAGE'}</div>

          <div className={`preview-customer${has(customer) ? '' : ' is-empty'}`}>
            {has(customer) ? customer.trim() : 'Customer'}
          </div>

          <div className={`preview-purpose${has(purpose) ? '' : ' is-empty'}`}>
            {has(purpose) ? purpose.trim() : 'Purpose'}
          </div>

          <div className="preview-foot">
            <QrGlyph className="preview-qr" />
            <span className={`preview-box${has(boxSerial) ? '' : ' is-empty'}`}>
              Box #{has(boxSerial) ? ` ${boxSerial.trim()}` : ''}
            </span>
          </div>
        </div>
      </div>
      <p className="preview-caption">Approximate preview</p>
    </aside>
  );
}
