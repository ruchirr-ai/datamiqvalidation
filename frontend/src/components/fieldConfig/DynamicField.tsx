import React from 'react';
import { Input } from '../ui';
import { FieldConfiguration } from '../../types/fieldConfig';

interface DynamicFieldProps {
  config: FieldConfiguration;
  value: any;
  onChange: (value: any) => void;
  error?: string;
}

export const DynamicField: React.FC<DynamicFieldProps> = ({
  config,
  value,
  onChange,
  error,
}) => {
  const handleChange = (newValue: any) => {
    onChange(newValue);
  };

  switch (config.type) {
    case 'text':
      return (
        <Input
          label={config.label}
          type="text"
          value={value || ''}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={config.placeholder}
          error={error}
          fullWidth
          required={config.required}
        />
      );

    case 'password':
      // Password fields are handled separately in the parent component
      // to support the show/hide toggle
      return (
        <Input
          label={config.label}
          type="password"
          value={value || ''}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={config.placeholder}
          error={error}
          fullWidth
          required={config.required}
        />
      );

    case 'number':
      return (
        <Input
          label={config.label}
          type="number"
          value={value || ''}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={config.placeholder}
          error={error}
          fullWidth
          required={config.required}
        />
      );

    case 'checkbox':
      return (
        <div className="checkbox-field">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={value === 'true' || value === true}
              onChange={(e) => handleChange(e.target.checked)}
              className="checkbox-input"
            />
            <span className="checkbox-text">
              {config.label}
              {config.required && <span className="required"> *</span>}
            </span>
          </label>
          {config.helpText && (
            <span className="help-text">{config.helpText}</span>
          )}
          {error && <span className="error-text">{error}</span>}
        </div>
      );

    case 'textarea':
      return (
        <div className="textarea-field">
          <label className="form-label">
            {config.label}
            {config.required && <span className="required"> *</span>}
          </label>
          <textarea
            value={value || ''}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={config.placeholder}
            className={`textarea-input ${error ? 'textarea-input--error' : ''}`}
            rows={6}
            required={config.required}
          />
          {config.helpText && (
            <span className="help-text">{config.helpText}</span>
          )}
          {error && <span className="error-text">{error}</span>}
        </div>
      );

    case 'select':
      // For select fields, we would need to define options in the field config
      // For now, returning a basic select
      return (
        <Input
          label={config.label}
          type="text"
          value={value || ''}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={config.placeholder}
          error={error}
          fullWidth
          required={config.required}
        />
      );

    default:
      return null;
  }
};
