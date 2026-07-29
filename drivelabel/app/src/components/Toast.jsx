import { useEffect } from 'react';
import { KeyIcon } from './Icons.jsx';

// One-shot confirmation that the secret handshake worked. Auto-dismisses so it
// never becomes furniture.
export default function Toast({ onDone, ttlMs = 4200 }) {
  useEffect(() => {
    const t = setTimeout(onDone, ttlMs);
    return () => clearTimeout(t);
  }, [onDone, ttlMs]);

  return (
    <div className="toast" role="status" aria-live="polite">
      <span className="toast-icon" aria-hidden="true"><KeyIcon /></span>
      <span className="toast-body">
        <strong className="toast-title">Admin mode unlocked</strong>
        <span className="toast-sub">Printer settings are yours. Be gentle.</span>
      </span>
      <button type="button" className="toast-close" onClick={onDone} aria-label="Dismiss">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
             strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
