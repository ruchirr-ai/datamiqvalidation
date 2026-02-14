import React from 'react';
import './Alert.css';

export interface AlertProps {
  children: React.ReactNode;
  variant?: 'success' | 'warning' | 'error' | 'info';
  title?: string;
  onClose?: () => void;
  className?: string;
}

export const Alert: React.FC<AlertProps> = ({
  children,
  variant = 'info',
  title,
  onClose,
  className = ''
}) => {
  const classes = [
    'alert',
    `alert--${variant}`,
    className
  ].filter(Boolean).join(' ');

  return (
    <div className={classes} role="alert">
      <div className="alert__content">
        {title && <div className="alert__title">{title}</div>}
        <div className="alert__message">{children}</div>
      </div>
      
      {onClose && (
        <button
          className="alert__close"
          onClick={onClose}
          aria-label="Close alert"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M12 4L4 12M4 4L12 12"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>
      )}
    </div>
  );
};
