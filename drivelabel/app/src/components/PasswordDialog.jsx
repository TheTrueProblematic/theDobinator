import { useState } from 'react';
import Modal from './Modal.jsx';
import { AlertIcon } from './Icons.jsx';

// Second gate after the click handshake. The check itself lives in
// useAdminUnlock; see the warning on ADMIN_PASSWORD in constants.js about what
// this does and does not protect.
export default function PasswordDialog({ onSubmit, onCancel, error }) {
  const [value, setValue] = useState('');

  function handleSubmit(e) {
    e.preventDefault();
    // onSubmit returns false on a wrong password — clear the field so the next
    // attempt starts fresh, and leave the dialog open with the error showing.
    if (!onSubmit(value)) setValue('');
  }

  return (
    <Modal title="Admin access" onClose={onCancel} labelledBy="adminAccessTitle">
      <form onSubmit={handleSubmit} className="dialog-form">
        <div className="field">
          <label className="field-label" htmlFor="adminPassword">Password</label>
          <input
            id="adminPassword"
            className="field-input"
            type="password"
            autoComplete="current-password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </div>

        {error && (
          <p className="dialog-error" role="alert">
            <AlertIcon className="dialog-error-icon" />
            {error}
          </p>
        )}

        <div className="modal-footer">
          <button type="button" className="ghost-btn dialog-btn" onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="print-btn dialog-btn-primary">
            Unlock
          </button>
        </div>
      </form>
    </Modal>
  );
}
