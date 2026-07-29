import { DOBINATOR_URL } from '../constants.js';
import { LabelMark, DriveIcon, KeyIcon } from './Icons.jsx';
import UpdateButton from './UpdateButton.jsx';

// The brand mark is also the secret admin trigger (see useAdminUnlock). It stays
// a real <button> so it's keyboard- and screen-reader-reachable, but it carries
// no visible hint until someone is clearly poking at it on purpose.
export default function TopBar({
  onSecretClick,
  hinting,
  adminUnlocked,
  updateAvailable,
  updateReboot,
  updateBusy,
  onUpdateClick,
}) {
  return (
    <header className="topbar">
      <div className="brand">
        <button
          type="button"
          className={`brand-mark${hinting ? ' is-hinting' : ''}${adminUnlocked ? ' is-unlocked' : ''}`}
          onClick={onSecretClick}
          aria-label="Drive Label Printer"
        >
          <LabelMark />
          {adminUnlocked && (
            <span className="brand-badge" aria-hidden="true">
              <KeyIcon />
            </span>
          )}
        </button>
        <span className="brand-text">
          <span className="brand-name">Drive Label Printer</span>
          <span className="brand-sub">SHOTOVER</span>
        </span>
      </div>

      <div className="topbar-actions">
        {updateAvailable && (
          <UpdateButton reboot={updateReboot} busy={updateBusy} onClick={onUpdateClick} />
        )}
        {/* Navigates in this tab on purpose: the two sites are a pair operators
            bounce between, and opening a new tab each way piled them up. */}
        <a
          className="icon-btn has-tip"
          href={DOBINATOR_URL}
          aria-label="Build a Drive"
        >
          <DriveIcon />
          <span className="tip" role="tooltip">Build a Drive</span>
        </a>
      </div>
    </header>
  );
}
