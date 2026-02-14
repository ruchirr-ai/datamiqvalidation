import React, { useState, useEffect } from 'react';
import { Plus } from 'lucide-react';
import { DatabaseTypeList } from '../components/fieldConfig/DatabaseTypeList';
import { FieldConfigItem } from '../components/fieldConfig/FieldConfigItem';
import { FieldConfigModal } from '../components/fieldConfig/FieldConfigModal';
import { Button, Alert } from '../components/ui';
import { DatabaseType, FieldConfiguration } from '../types/fieldConfig';
import { fieldConfigApi } from '../services/fieldConfigApi';
import './DatabaseFieldConfigPage.css';

export const DatabaseFieldConfigPage: React.FC = () => {
  const [selectedDatabaseType, setSelectedDatabaseType] = useState<DatabaseType>('mongodb');
  const [fields, setFields] = useState<FieldConfiguration[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<'add' | 'edit'>('add');
  const [editingField, setEditingField] = useState<FieldConfiguration | undefined>();
  
  // Confirmation dialog state
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // Load field configurations
  useEffect(() => {
    loadFields();
  }, [selectedDatabaseType]);

  const loadFields = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fieldConfigApi.getFieldConfigs(selectedDatabaseType);
      setFields(data.sort((a, b) => a.displayOrder - b.displayOrder));
    } catch (err) {
      setError('Failed to load field configurations');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = (fieldId: string) => {
    setConfirmDelete(fieldId);
  };

  const handleToggle = async (fieldId: string, enabled: boolean) => {
    try {
      const field = fields.find(f => f.id === fieldId);
      if (!field) return;

      const updatedField = await fieldConfigApi.updateFieldConfig(fieldId, {
        ...field,
        enabled,
      });
      
      setFields(fields.map(f => f.id === updatedField.id ? updatedField : f));
      showSuccess(`Field ${enabled ? 'enabled' : 'disabled'} successfully`);
    } catch (err) {
      setError('Failed to update field status');
      console.error(err);
    }
  };

  const confirmRemove = async () => {
    if (!confirmDelete) return;

    try {
      await fieldConfigApi.deleteFieldConfig(confirmDelete);
      setFields(fields.filter(f => f.id !== confirmDelete));
      showSuccess('Field removed successfully');
      setConfirmDelete(null);
    } catch (err) {
      setError('Failed to remove field');
      console.error(err);
    }
  };

  const handleAddField = () => {
    setEditingField(undefined);
    setModalMode('add');
    setIsModalOpen(true);
  };

  const handleLoadDefaults = async () => {
    try {
      setLoading(true);
      const result = await fieldConfigApi.seedDefaultConfigs(selectedDatabaseType);
      if (result.success) {
        showSuccess(`Loaded ${result.count} default fields`);
        await loadFields(); // Reload fields
      } else {
        setError(result.message || 'Failed to load default fields');
      }
    } catch (err: any) {
      setError(err.detail || 'Failed to load default fields');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleEditField = (fieldId: string) => {
    const field = fields.find(f => f.id === fieldId);
    if (field) {
      setEditingField(field);
      setModalMode('edit');
      setIsModalOpen(true);
    }
  };

  const handleSaveField = async (fieldData: Partial<FieldConfiguration>) => {
    try {
      if (modalMode === 'add') {
        const newField = await fieldConfigApi.createFieldConfig(
          selectedDatabaseType,
          fieldData as Omit<FieldConfiguration, 'id'>
        );
        setFields([...fields, newField].sort((a, b) => a.displayOrder - b.displayOrder));
        showSuccess('Field added successfully');
      } else if (editingField) {
        const updatedField = await fieldConfigApi.updateFieldConfig(editingField.id, fieldData);
        setFields(fields.map(f => f.id === updatedField.id ? updatedField : f)
          .sort((a, b) => a.displayOrder - b.displayOrder));
        showSuccess('Field updated successfully');
      }
      setIsModalOpen(false);
    } catch (err) {
      setError(modalMode === 'add' ? 'Failed to add field' : 'Failed to update field');
      console.error(err);
    }
  };

  const handleSaveConfiguration = async () => {
    try {
      // TODO: Implement save configuration API call
      showSuccess('Configuration saved successfully');
    } catch (err) {
      setError('Failed to save configuration');
      console.error(err);
    }
  };

  const showSuccess = (message: string) => {
    setSuccess(message);
    setTimeout(() => setSuccess(null), 3000);
  };

  return (
    <div className="database-field-config-page">
      <div className="page-header">
        <h1>Database Connection Field Configuration</h1>
        <p>Configure which fields appear when creating database connections</p>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert variant="success" onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      <div className="config-container">
        <DatabaseTypeList
          selectedType={selectedDatabaseType}
          onSelect={setSelectedDatabaseType}
        />

        <div className="config-content">
          {loading ? (
            <div className="loading-state">
              <div className="spinner" />
              <p>Loading field configurations...</p>
            </div>
          ) : fields.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📋</div>
              <h3>No fields configured yet</h3>
              <p>Load default fields or add your own custom fields</p>
              <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', marginTop: '16px' }}>
                <Button variant="primary" onClick={handleLoadDefaults}>
                  Load Default Fields
                </Button>
                <Button variant="outline" onClick={handleAddField}>
                  <Plus size={16} />
                  Add Custom Field
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="field-list-table">
                {fields.map(field => (
                  <FieldConfigItem
                    key={field.id}
                    field={field}
                    onEdit={handleEditField}
                    onRemove={handleRemove}
                    onToggle={handleToggle}
                  />
                ))}
                
                <div className="add-field-button-container">
                  <Button variant="primary" onClick={handleAddField}>
                    <Plus size={16} />
                    Add Field
                  </Button>
                </div>
              </div>
              
              <div className="config-footer">
                <button className="save-config-button" onClick={handleSaveConfiguration}>
                  Save Configuration
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      <FieldConfigModal
        isOpen={isModalOpen}
        mode={modalMode}
        field={editingField}
        databaseType={selectedDatabaseType}
        onSave={handleSaveField}
        onCancel={() => setIsModalOpen(false)}
      />

      {confirmDelete && (
        <div className="confirm-dialog-overlay" onClick={() => setConfirmDelete(null)}>
          <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Confirm Deletion</h3>
            <p>Are you sure you want to remove this field? This action cannot be undone.</p>
            <div className="confirm-actions">
              <Button variant="outline" onClick={() => setConfirmDelete(null)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={confirmRemove}>
                Remove Field
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
