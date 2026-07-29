import { DOBINATOR_URL } from '../constants.js';
import { LabelMark, DriveIcon, KeyIcon } from './Icons.jsx';

// The brand mark is also the secret admin trigger (see useAdminUnlock). It stays
// a real <button> so it's keyboard- and screen-reader-reachable, but it carries
// no visible hint until someone is clearly poking at it on purpose.
export default function TopBar({ onSecretClick, hinting, adminUnlocked }) {
  return (
    <header className="topbar">
      <div className="brand">
        <button
          type="button"
          className={`brand-mark${hinting ? ' is-hinting' : ''}${adminUnlocked ? ' is-unlocked' : ''}`}
          onClick={onSecretClick}
          aria-label="Drive Label"
        >
          <LabelMark />
          {adminUnlocked && (
            <span className="brand-badge" aria-hidden="true">
              <KeyIcon />
            </span>
          )}
        </button>
        <span className="brand-text">
          <span className="brand-name">Drive Label</span>
          <span className="brand-sub">Churchill Navigation</span>
        </span>
      </div>

      <div className="topbar-actions">
        <a
          className="icon-btn has-tip"
          href={DOBINATOR_URL}
          target="_blank"
          rel="noopener"
          aria-label="Build Drive"
        >
          <DriveIcon />
          <span className="tip" role="tooltip">Build Drive</span>
        </a>
      </div>
    </header>
  );
}
