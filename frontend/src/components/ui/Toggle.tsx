import React from 'react';
import './Toggle.css';

interface ToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  disabled?: boolean;
  label?: string;
  ariaLabel?: string;
}

export const Toggle: React.FC<ToggleProps> = ({
  enabled,
  onChange,
  disabled = false,
  label,
  ariaLabel,
}) => {
  const handleClick = () => {
    if (!disabled) {
      onChange(!enabled);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <div className="toggle-container">
      {label && <span className="toggle-label">{label}</span>}
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-label={ariaLabel || label || 'Toggle'}
        className={`toggle-switch ${enabled ? 'enabled' : ''} ${disabled ? 'disabled' : ''}`}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      >
        <span className="toggle-switch-handle" />
      </button>
    </div>
  );
};
