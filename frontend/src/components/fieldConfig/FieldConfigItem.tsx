import React from 'react';
import { X } from 'lucide-react';
import { PencilSquareIcon } from '@heroicons/react/24/outline';
import { FieldConfiguration } from '../../types/fieldConfig';
import './FieldConfigItem.css';

interface FieldConfigItemProps {
  field: FieldConfiguration;
  onEdit: (fieldId: string) => void;
  onRemove: (fieldId: string) => void;
  onToggle: (fieldId: string, enabled: boolean) => void;
}

export const FieldConfigItem: React.FC<FieldConfigItemProps> = ({
  field,
  onEdit,
  onRemove,
  onToggle,
}) => {
  const getFieldTypeLabel = (type: string): string => {
    const labels: Record<string, string> = {
      text: 'Text',
      number: 'Number',
      password: 'Password',
      select: 'Select',
      checkbox: 'Checkbox',
      textarea: 'Text Area',
    };
    return labels[type] || type;
  };

  const handleToggle = () => {
    onToggle(field.id, !field.enabled);
  };

  return (
    <div className="field-config-row">
      <div className="field-config-info">
        <span className="field-config-name">{field.label}</span>
        <span className="field-config-type">{getFieldTypeLabel(field.type)}</span>
      </div>
      <div className="field-config-actions">
        <label className="field-config-checkbox">
          <input
            type="checkbox"
            checked={field.enabled}
            onChange={handleToggle}
            aria-label={`${field.enabled ? 'Disable' : 'Enable'} ${field.label}`}
          />
          <span className="checkbox-custom" />
        </label>
        <button
          className="field-config-edit"
          onClick={() => onEdit(field.id)}
          aria-label={`Edit ${field.label}`}
        >
          <PencilSquareIcon className="icon-16" />
        </button>
        <button
          className="field-config-remove"
          onClick={() => onRemove(field.id)}
          aria-label={`Remove ${field.label}`}
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
};
