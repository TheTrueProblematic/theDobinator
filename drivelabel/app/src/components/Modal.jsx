import { useEffect, useRef } from 'react';

// Small shared dialog: backdrop click and Escape both close, focus moves inside
// on open and returns to whatever was focused before on close. Used by the admin
// password prompt and the update confirmation.
export default function Modal({ title, onClose, children, footer, labelledBy = 'modalTitle' }) {
  const panelRef = useRef(null);
  const returnFocusTo = useRef(null);

  useEffect(() => {
    returnFocusTo.current = document.activeElement;

    const onKeyDown = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); }
    };
    document.addEventListener('keydown', onKeyDown);

    // Focus the first control in the dialog so keyboard users land inside it.
    const first = panelRef.current?.querySelector('input, button, select, textarea');
    first?.focus();

    return () => {
      document.removeEventListener('keydown', onKeyDown);
      const back = returnFocusTo.current;
      if (back && typeof back.focus === 'function') back.focus();
    };
  }, [onClose]);

  return (
    <div className="modal">
      <div className="modal-backdrop" onClick={onClose} />
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        ref={panelRef}
      >
        <h2 className="modal-title" id={labelledBy}>{title}</h2>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
