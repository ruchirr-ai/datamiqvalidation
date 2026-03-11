import React, { useState, useRef, useEffect } from 'react';
import './Select.css';

interface SelectOption {
  value: string | number;
  label: string;
}

interface SearchableSelectProps {
  value: string | number;
  onChange: (value: string | number) => void;
  options: SelectOption[];
  className?: string;
  disabled?: boolean;
  placeholder?: string;
}

export const SearchableSelect: React.FC<SearchableSelectProps> = ({
  value,
  onChange,
  options,
  className = '',
  disabled = false,
  placeholder = 'Select...',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const selectRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedOption = options.find(opt => opt.value === value);

  const filtered = search
    ? options.filter(opt => opt.label.toLowerCase().includes(search.toLowerCase()))
    : options;

  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (selectRef.current && !selectRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && inputRef.current) inputRef.current.focus();
  }, [isOpen]);

  const handleSelect = (optionValue: string | number) => {
    onChange(optionValue);
    setIsOpen(false);
    setSearch('');
  };

  return (
    <div className={`custom-select ${disabled ? 'disabled' : ''} ${className}`} ref={selectRef}>
      <button
        type="button"
        className="custom-select-trigger"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
      >
        <span className="custom-select-trigger-content">
          <span>{selectedOption?.label || placeholder}</span>
        </span>
        <svg
          className={`custom-select-arrow ${isOpen ? 'open' : ''}`}
          width="12" height="12" viewBox="0 0 12 12"
          fill="none" stroke="currentColor" strokeWidth="2"
        >
          <path d="M3 4.5l3 3 3-3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {isOpen && !disabled && (
        <div className="custom-select-dropdown" style={{ minWidth: '220px' }}>
          <div style={{ padding: '4px 4px 2px' }}>
            <input
              ref={inputRef}
              type="text"
              className="searchable-select-input"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          {filtered.length === 0 ? (
            <div style={{ padding: '8px 12px', fontSize: '13px', color: '#9CA3AF' }}>No results</div>
          ) : (
            filtered.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`custom-select-option ${option.value === value ? 'selected' : ''}`}
                onClick={() => handleSelect(option.value)}
              >
                <span>{option.label}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
};
