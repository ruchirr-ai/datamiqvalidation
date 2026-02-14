import React from 'react';
import './Dropdown.css';

interface DropdownProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
  isOpen: boolean;
  onToggle: () => void;
  align?: 'left' | 'right';
  className?: string;
}

export const Dropdown: React.FC<DropdownProps> = ({
  trigger,
  children,
  isOpen,
  onToggle,
  align = 'right',
  className = '',
}) => {
  React.useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('.dropdown')) {
        onToggle();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onToggle]);

  return (
    <div className={`dropdown ${className}`}>
      <div onClick={onToggle}>{trigger}</div>
      {isOpen && (
        <div className={`dropdown-menu dropdown-menu--${align}`}>
          {children}
        </div>
      )}
    </div>
  );
};

interface DropdownItemProps {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}

export const DropdownItem: React.FC<DropdownItemProps> = ({
  children,
  onClick,
  className = '',
}) => {
  return (
    <button
      className={`dropdown-item ${className}`}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
};

interface DropdownDividerProps {
  className?: string;
}

export const DropdownDivider: React.FC<DropdownDividerProps> = ({
  className = '',
}) => {
  return <div className={`dropdown-divider ${className}`} />;
};
