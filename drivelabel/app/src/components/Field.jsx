// Form primitives. Each one owns a real <label for=…> so taps on the label move
// focus into the control, and every control declares its own background AND
// text colour in CSS (see the note at the top of styles.css).

export function TextField({ id, label, value, onChange, placeholder, type = 'text', inputMode, min, step, autoComplete = 'off' }) {
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>{label}</label>
      <input
        id={id}
        className="field-input"
        type={type}
        inputMode={inputMode}
        min={min}
        step={step}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        spellCheck="false"
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

export function SelectField({ id, label, value, onChange, options, placeholder }) {
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>{label}</label>
      <div className="select-wrap">
        <select
          id={id}
          className="field-input field-select"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((opt) => {
            const val = typeof opt === 'string' ? opt : opt.value;
            const text = typeof opt === 'string' ? opt : opt.label;
            return <option key={val} value={val}>{text}</option>;
          })}
        </select>
        <span className="select-chevron" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
               strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </span>
      </div>
    </div>
  );
}
