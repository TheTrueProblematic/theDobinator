import { useEffect } from 'react';
import { KeyIcon, CheckIcon, AlertIcon, UpdateIcon } from './Icons.jsx';

const ICONS = {
  key: KeyIcon,
  check: CheckIcon,
  alert: AlertIcon,
  update: UpdateIcon,
};

// Transient one-liner: admin unlocked, update started, update failed. Carries an
// icon as well as a tone so it doesn't rely on colour alone. Auto-dismisses so it
// never becomes furniture.
export default function Toast({ title, icon = 'check', tone = 'accent', onDone, ttlMs = 4200 }) {
  useEffect(() => {
    const t = setTimeout(onDone, ttlMs);
    return () => clearTimeout(t);
  }, [onDone, ttlMs, title]);

  const Icon = ICONS[icon] || CheckIcon;

  return (
    <div className={`toast is-${tone}`} role="status" aria-live="polite">
      <span className="toast-icon" aria-hidden="true"><Icon /></span>
      <span className="toast-title">{title}</span>
      <button type="button" className="toast-close" onClick={onDone} aria-label="Dismiss">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
             strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
