import { CheckIcon, AlertIcon } from './Icons.jsx';

// Result of the last print attempt. State is carried by an ICON plus wording as
// well as colour, so it still reads correctly if a dark-mode extension shifts
// the palette (and for anyone who can't separate the red from the green).
export default function StatusBanner({ kind, message, onClear }) {
  if (!kind) return null;

  return (
    <div className={`banner is-${kind}`} role="status" aria-live="polite">
      <span className="banner-icon" aria-hidden="true">
        {kind === 'success' && <CheckIcon />}
        {kind === 'error' && <AlertIcon />}
        {kind === 'pending' && <span className="spinner" />}
      </span>
      <span className="banner-text">{message}</span>
      {kind === 'success' && onClear && (
        <button type="button" className="ghost-btn banner-action" onClick={onClear}>
          Clear fields
        </button>
      )}
    </div>
  );
}
