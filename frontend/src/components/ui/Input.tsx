import React from 'react';
import './Input.css';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  icon?: React.ReactNode;
  fullWidth?: boolean;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  icon,
  fullWidth = false,
  className = '',
  id,
  ...props
}) => {
  const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`;
  const hasError = Boolean(error);

  const containerClasses = [
    'input-container',
    fullWidth && 'input-container--full-width',
    className
  ].filter(Boolean).join(' ');

  const inputClasses = [
    'input',
    hasError && 'input--error',
    icon && 'input--with-icon'
  ].filter(Boolean).join(' ');

  return (
    <div className={containerClasses}>
      <div className="input__wrapper">
        {label && (
          <label htmlFor={inputId} className="input__label">
            {label}
          </label>
        )}
        
        {icon && (
          <span className="input__icon" aria-hidden="true">
            {icon}
          </span>
        )}
        
        <input
          id={inputId}
          className={inputClasses}
          aria-invalid={hasError}
          aria-describedby={
            error ? `${inputId}-error` : helperText ? `${inputId}-helper` : undefined
          }
          {...props}
        />
      </div>
      
      {error && (
        <span id={`${inputId}-error`} className="input__error" role="alert">
          {error}
        </span>
      )}
      
      {helperText && !error && (
        <span id={`${inputId}-helper`} className="input__helper">
          {helperText}
        </span>
      )}
    </div>
  );
};
