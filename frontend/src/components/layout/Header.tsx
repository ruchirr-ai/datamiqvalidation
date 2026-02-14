import React from 'react';
import './Header.css';

export interface HeaderProps {
  onMenuToggle?: () => void;
  showMenuButton?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onMenuToggle,
  showMenuButton = false
}) => {
  return (
    <header className="header">
      <div className="header__left">
        {showMenuButton && onMenuToggle && (
          <button
            className="header__menu-button"
            onClick={onMenuToggle}
            aria-label="Toggle menu"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path
                d="M3 12H21M3 6H21M3 18H21"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
        )}
        
        <div className="header__logo">
          <span className="header__logo-text">DataMIQ</span>
        </div>
      </div>

      <div className="header__right">
        {/* Additional header actions can be added here */}
      </div>
    </header>
  );
};
