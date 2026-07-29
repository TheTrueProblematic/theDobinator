import { UpdateIcon } from './Icons.jsx';

// Mirrors theDobinator's update indicator: hidden until an update is pending,
// amber normally, red when the update needs a full PC restart. Styled to this
// site's topbar (rounded square, matching the Build a Drive button) rather than
// the Dobinator's circle.
export default function UpdateButton({ reboot, onClick, busy }) {
  const label = reboot ? 'Restart required' : 'Update available';
  return (
    <button
      type="button"
      className={`icon-btn has-tip update-btn${reboot ? ' is-reboot' : ''}`}
      onClick={onClick}
      disabled={busy}
      aria-label={label}
    >
      <UpdateIcon />
      <span className="tip" role="tooltip">{label}</span>
    </button>
  );
}
