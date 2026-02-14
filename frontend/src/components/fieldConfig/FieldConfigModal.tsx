import React, { useState, useEffect } from 'react';
import { Modal, Input, Select, Button, Toggle } from '../ui';
import { FieldConfiguration, FieldType, DatabaseType } from '../../types/fieldConfig';
import './FieldConfigModal.css';

interface FieldConfigModalProps {
  isOpen: boolean;
  mode: 'add' | 'edit';
  field?: FieldConfiguration;
  databaseType: DatabaseType;
  onSave: (field: Partial<FieldConfiguration>) => void;
  onCancel: () => void;
}

export const FieldConfigModal: React.FC<FieldConfigModalProps> = ({
  isOpen,
  mode,
  field,
  databaseType,
  onSave,
  onCancel,
}) => {
  const [formData, setFormData] = useState({
    name: '',
    label: '',
    type: 'text' as FieldType,
    required: false,
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (field && mode === 'edit') {
      setFormData({
        name: field.name,
        label: field.label,
        type: field.type,
        required: field.required,
      });
    } else {
      // Reset for add mode
      setFormData({
        name: '',
        label: '',
        type: 'text',
        required: false,
      });
    }
    setErrors({});
  }, [field, mode, isOpen]);

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Field name is required';
    }

    if (!formData.label.trim()) {
      newErrors.label = 'Field label is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) {
      return;
    }

    const fieldData: Partial<FieldConfiguration> = {
      name: formData.name.trim(),
      label: formData.label.trim(),
      type: formData.type,
      required: formData.required,
      enabled: field?.enabled ?? true,
      databaseType,
      displayOrder: field?.displayOrder ?? 1,
      placeholder: field?.placeholder,
      defaultValue: field?.defaultValue,
      helpText: field?.helpText,
      validation: field?.validation,
    };

    onSave(fieldData);
  };

  return (
    <Modal isOpen={isOpen} onClose={onCancel} title={mode === 'add' ? 'Add Field Configuration' : 'Edit Field Configuration'}>
      <form onSubmit={handleSubmit} className="field-config-form">
        <div className="form-row">
          <Input
            label="Field Name *"
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            error={errors.name}
            placeholder="e.g., host, port, database"
            fullWidth
          />
        </div>

        <div className="form-row">
          <Input
            label="Field Label *"
            type="text"
            value={formData.label}
            onChange={(e) => setFormData({ ...formData, label: e.target.value })}
            error={errors.label}
            placeholder="e.g., Host, Port, Database"
            fullWidth
          />
        </div>

        <div className="form-row">
          <div className="form-field">
            <label htmlFor="field-type">Field Type *</label>
            <Select
              value={formData.type}
              onChange={(value) => setFormData({ ...formData, type: value as FieldType })}
              options={[
                { value: 'text', label: 'Text' },
                { value: 'number', label: 'Number' },
                { value: 'password', label: 'Password' },
                { value: 'select', label: 'Select' },
                { value: 'checkbox', label: 'Checkbox' },
              ]}
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-field-toggle">
            <label htmlFor="required-field">Required Field</label>
            <Toggle
              enabled={formData.required}
              onChange={(enabled) => setFormData({ ...formData, required: enabled })}
              ariaLabel="Toggle required field"
            />
          </div>
        </div>

        <div className="modal-actions">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" variant="primary">
            {mode === 'add' ? 'Add Field' : 'Save Changes'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};
