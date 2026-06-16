import React, { useState, useEffect } from 'react';
import { Modal } from '../ui/Modal';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { Select } from '../ui/Select';
import { Database, Check, X, AlertCircle, ExternalLink, Zap } from 'lucide-react';
import { SiMongodb, SiAmazondocumentdb, SiPostgresql, SiMysql, SiOracle, SiGooglecloud, SiAmazonredshift, SiSap } from 'react-icons/si';
import { DynamicField } from '../fieldConfig/DynamicField';
import { fieldConfigApi } from '../../services/fieldConfigApi';
import { testConnection } from '../../services/api';
import { FieldConfiguration, DatabaseType } from '../../types/fieldConfig';
import { Db2Icon } from '../icons/Db2Icon';
import './CreateConnectionModal.css';

interface CreateConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  connectionType: 'source' | 'target';
  onSubmit: (data: ConnectionFormData) => void;
  initialData?: ConnectionFormData;
  isEditMode?: boolean;
}

export interface ConnectionFormData {
  name: string;
  type: 'source' | 'target';
  database: string;
  [key: string]: any; // Dynamic fields
}

export const CreateConnectionModal: React.FC<CreateConnectionModalProps> = ({
  isOpen,
  onClose,
  connectionType,
  onSubmit,
  initialData,
  isEditMode = false,
}) => {
  const [formData, setFormData] = useState<ConnectionFormData>(
    initialData || {
      name: '',
      type: connectionType,
      database: 'mongodb',
    }
  );

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showPassword, setShowPassword] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [testSuccess, setTestSuccess] = useState(false);
  const [showSuccessToast, setShowSuccessToast] = useState(false);
  const [showErrorToast, setShowErrorToast] = useState(false);
  const [fieldConfigs, setFieldConfigs] = useState<FieldConfiguration[]>([]);
  const [loadingFields, setLoadingFields] = useState(false);
  const [bqAuthMethod, setBqAuthMethod] = useState<'service_account' | 'wif'>('service_account');

  // Database options based on connection type
  const sourceDatabaseOptions = [
    { value: 'mongodb', label: 'MongoDB', icon: <SiMongodb size={16} /> },
    { value: 'documentdb', label: 'Amazon DocumentDB', icon: <SiAmazondocumentdb size={16} /> },
    { value: 'postgresql', label: 'PostgreSQL', icon: <SiPostgresql size={16} /> },
    { value: 'mysql', label: 'MySQL', icon: <SiMysql size={16} /> },
    { value: 'oracle', label: 'Oracle', icon: <SiOracle size={16} /> },
    { value: 'sqlserver', label: 'SQL Server', icon: <Database size={16} /> },
    { value: 'bigquery', label: 'BigQuery', icon: <SiGooglecloud size={16} /> },
    { value: 'clickhouse', label: 'ClickHouse', icon: <Zap size={16} /> },
    { value: 'sybase', label: 'SAP Sybase', icon: <SiSap size={16} /> },
    { value: 'db2', label: 'IBM Db2', icon: <Db2Icon size={16} /> },
  ];

  const targetDatabaseOptions = [
    { value: 'mongodb', label: 'MongoDB', icon: <SiMongodb size={16} /> },
    { value: 'documentdb', label: 'Amazon DocumentDB', icon: <SiAmazondocumentdb size={16} /> },
    { value: 'postgresql', label: 'PostgreSQL', icon: <SiPostgresql size={16} /> },
    { value: 'mysql', label: 'MySQL', icon: <SiMysql size={16} /> },
    { value: 'oracle', label: 'Oracle', icon: <SiOracle size={16} /> },
    { value: 'sqlserver', label: 'SQL Server', icon: <Database size={16} /> },
    { value: 'redshift', label: 'Amazon Redshift', icon: <SiAmazonredshift size={16} /> },
    { value: 'clickhouse', label: 'ClickHouse', icon: <Zap size={16} /> },
    { value: 'sybase', label: 'SAP Sybase', icon: <SiSap size={16} /> },
    { value: 'db2', label: 'IBM Db2', icon: <Db2Icon size={16} /> },
  ];

  const databaseOptions = connectionType === 'source' ? sourceDatabaseOptions : targetDatabaseOptions;

  // Load field configurations when database type changes
  useEffect(() => {
    const loadFieldConfigs = async () => {
      if (!formData.database) return;
      
      setLoadingFields(true);
      try {
        let configs = await fieldConfigApi.getFieldConfigs(formData.database as DatabaseType);
        
        // If no configs exist in database, seed defaults
        if (configs.length === 0) {
          console.log(`No field configs found for ${formData.database}, seeding defaults...`);
          try {
            await fieldConfigApi.seedDefaultConfigs(formData.database as DatabaseType);
            configs = await fieldConfigApi.getFieldConfigs(formData.database as DatabaseType);
          } catch (seedError) {
            console.error('Failed to seed default configs:', seedError);
            // If seeding fails, configs will remain empty array
            // The form will show no fields, which is better than breaking
          }
        }
        
        // Only show enabled fields, sorted by display order
        const enabledConfigs = configs
          .filter(config => config.enabled)
          .sort((a, b) => a.displayOrder - b.displayOrder);
        setFieldConfigs(enabledConfigs);
        
        // Initialize form data with default values or initial data
        if (!isEditMode || !initialData) {
          const newFormData: ConnectionFormData = {
            name: formData.name,
            type: connectionType,
            database: formData.database,
          };
          
          enabledConfigs.forEach(config => {
            if (config.defaultValue) {
              newFormData[config.name] = config.defaultValue;
            }
          });
          
          setFormData(newFormData);
        }
        setErrors({});
      } catch (error) {
        console.error('Failed to load field configurations:', error);
      } finally {
        setLoadingFields(false);
      }
    };

    loadFieldConfigs();
  }, [formData.database]);

  const handleChange = (field: string, value: string | boolean) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Connection name is required';
    }

    // Validate dynamic fields
    fieldConfigs.forEach(config => {
      if (config.required && !formData[config.name]) {
        newErrors[config.name] = `${config.label} is required`;
      }

      // Additional validation based on field type
      if (config.type === 'number' && formData[config.name]) {
        if (isNaN(Number(formData[config.name]))) {
          newErrors[config.name] = `${config.label} must be a number`;
        }
      }

      // Custom validation rules
      if (config.validation && formData[config.name]) {
        const value = formData[config.name];
        const { minLength, maxLength, min, max, pattern } = config.validation;

        if (minLength && value.length < minLength) {
          newErrors[config.name] = `${config.label} must be at least ${minLength} characters`;
        }

        if (maxLength && value.length > maxLength) {
          newErrors[config.name] = `${config.label} must be at most ${maxLength} characters`;
        }

        if (min !== undefined && Number(value) < min) {
          newErrors[config.name] = `${config.label} must be at least ${min}`;
        }

        if (max !== undefined && Number(value) > max) {
          newErrors[config.name] = `${config.label} must be at most ${max}`;
        }

        if (pattern) {
          const regex = new RegExp(pattern);
          if (!regex.test(value)) {
            newErrors[config.name] = `${config.label} format is invalid`;
          }
        }
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleTestConnection = async () => {
    if (!validateForm()) return;

    setIsTesting(true);
    setTestSuccess(false);
    setShowSuccessToast(false);
    setShowErrorToast(false);
    
    try {
      // Prepare connection parameters based on database type
      const connectionParams: Record<string, any> = {};
      
      // Extract all dynamic field values
      fieldConfigs.forEach(config => {
        if (config.type === 'checkbox') {
          // Always send checkbox values (even when unchecked)
          connectionParams[config.name] = formData[config.name] || 'false';
        } else if (formData[config.name]) {
          connectionParams[config.name] = formData[config.name];
        }
      });
      
      // Call the test connection API
      const response = await testConnection(formData.database, connectionParams);
      
      if (response.success) {
        setTestSuccess(true);
        setShowSuccessToast(true);
        // Auto-hide toast after 5 seconds
        setTimeout(() => setShowSuccessToast(false), 5000);
      } else {
        setTestSuccess(false);
        setShowErrorToast(true);
        setErrors({ ...errors, connection: response.message });
        // Auto-hide error toast after 5 seconds
        setTimeout(() => setShowErrorToast(false), 5000);
      }
    } catch (error: any) {
      console.error('Connection test failed:', error);
      setTestSuccess(false);
      setShowErrorToast(true);
      setErrors({ 
        ...errors, 
        connection: error.detail || error.message || 'Connection test failed. Please check your credentials.' 
      });
      // Auto-hide error toast after 5 seconds
      setTimeout(() => setShowErrorToast(false), 5000);
    } finally {
      setIsTesting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) return;

    // Require successful test before creating/updating connection
    if (!testSuccess) {
      setErrors({ 
        ...errors, 
        connection: `Please test the connection successfully before ${isEditMode ? 'updating' : 'creating'} it.` 
      });
      setShowErrorToast(true);
      setTimeout(() => setShowErrorToast(false), 5000);
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit(formData);
      onClose();
      // Reset form
      if (!isEditMode) {
        setFormData({
          name: '',
          type: connectionType,
          database: 'mongodb',
        });
        setFieldConfigs([]);
      }
      setTestSuccess(false);
    } catch (error) {
      console.error(`Failed to ${isEditMode ? 'update' : 'create'} connection:`, error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDatabaseChange = (value: string | number) => {
    const dbValue = String(value);
    setFormData((prev) => ({
      name: prev.name,
      type: prev.type,
      database: dbValue,
    }));
    // Clear test success when changing database type
    setTestSuccess(false);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`${isEditMode ? 'Update' : 'Create'} ${connectionType === 'source' ? 'Source' : 'Target'} Connection`}
      size="lg"
    >
      <form onSubmit={handleSubmit} className="connection-form">
        {showSuccessToast && (
          <div className="connection-toast connection-toast--success">
            <div className="connection-toast__content">
              <Check size={20} />
              <span>Connection successful</span>
            </div>
            <button
              type="button"
              className="connection-toast__close"
              onClick={() => setShowSuccessToast(false)}
              aria-label="Close notification"
            >
              <X size={16} />
            </button>
          </div>
        )}

        {showErrorToast && (
          <div className="connection-toast connection-toast--error">
            <div className="connection-toast__content">
              <AlertCircle size={20} />
              <span>Connection failed</span>
            </div>
            <button
              type="button"
              className="connection-toast__close"
              onClick={() => setShowErrorToast(false)}
              aria-label="Close notification"
            >
              <X size={16} />
            </button>
          </div>
        )}

        <div className="form-section">
          <div className="form-row">
            <Input
              label="Connection Name"
              placeholder="e.g., Production MongoDB"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              error={errors.name}
              fullWidth
              required
            />
          </div>

          <div className="form-row form-row--label-dropdown">
            <label className="form-label-inline">
              Data Source <span className="required">*</span>
            </label>
            <div className="database-type-wrapper">
              <Select
                value={formData.database}
                onChange={handleDatabaseChange}
                options={databaseOptions}
              />
              {formData.database && (
                <a
                  href="#"
                  className="database-doc-link"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => {
                    e.preventDefault();
                    // TODO: Open documentation for selected database
                    console.log(`Open docs for ${formData.database}`);
                  }}
                >
                  User permissions guide
                  <ExternalLink size={12} />
                </a>
              )}
            </div>
          </div>

          {/* Auth Method Tabs for BigQuery */}
          {formData.database === 'bigquery' && (
            <div className="form-row">
              <div style={{ display: 'flex', gap: '0', borderBottom: '2px solid var(--color-divider)', marginBottom: '16px' }}>
                <button
                  type="button"
                  onClick={() => { setBqAuthMethod('service_account'); handleChange('credentials_json', ''); }}
                  style={{
                    padding: '8px 16px',
                    fontSize: '13px',
                    fontWeight: bqAuthMethod === 'service_account' ? 600 : 400,
                    color: bqAuthMethod === 'service_account' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                    background: 'none',
                    border: 'none',
                    borderBottom: bqAuthMethod === 'service_account' ? '2px solid var(--color-primary)' : '2px solid transparent',
                    marginBottom: '-2px',
                    cursor: 'pointer',
                  }}
                >
                  Service Account Key
                </button>
                <button
                  type="button"
                  onClick={() => { setBqAuthMethod('wif'); handleChange('credentials_json', ''); }}
                  style={{
                    padding: '8px 16px',
                    fontSize: '13px',
                    fontWeight: bqAuthMethod === 'wif' ? 600 : 400,
                    color: bqAuthMethod === 'wif' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                    background: 'none',
                    border: 'none',
                    borderBottom: bqAuthMethod === 'wif' ? '2px solid var(--color-primary)' : '2px solid transparent',
                    marginBottom: '-2px',
                    cursor: 'pointer',
                  }}
                >
                  Workload Identity Federation
                </button>
              </div>
            </div>
          )}

          {/* Dynamic Fields */}
          {loadingFields ? (
            <div className="form-row">
              <div className="loading-fields">
                <div className="spinner"></div>
                <span>Loading fields...</span>
              </div>
            </div>
          ) : (
            <>
              {fieldConfigs.map((config) => {
                // For BigQuery WIF mode, override the credentials_json field appearance
                let displayConfig = config;
                if (formData.database === 'bigquery' && config.name === 'credentials_json') {
                  if (bqAuthMethod === 'wif') {
                    displayConfig = {
                      ...config,
                      label: 'WIF Configuration JSON',
                      placeholder: 'Paste Workload Identity Federation config JSON',
                      helpText: 'Generated by: gcloud iam workload-identity-pools create-cred-config ...',
                    };
                  } else {
                    displayConfig = {
                      ...config,
                      label: 'Service Account JSON',
                      placeholder: 'Paste service account JSON key',
                      helpText: 'Google Cloud service account credentials in JSON format',
                    };
                  }
                }
                // Hide dataset and location fields for WIF mode (not needed — assessment scans all datasets)
                if (formData.database === 'bigquery' && bqAuthMethod === 'wif' && (config.name === 'dataset' || config.name === 'location')) {
                  return null;
                }
                const isPasswordField = displayConfig.type === 'password';
                const isTextareaField = displayConfig.type === 'textarea';
                const isCheckboxField = config.type === 'checkbox';
                
                // Determine the row class based on field type
                let rowClass = 'form-row';
                if (!isCheckboxField && !isTextareaField) {
                  rowClass += ' form-row--two-cols';
                }
                
                return (
                  <div 
                    key={config.id} 
                    className={rowClass}
                  >
                    {isPasswordField ? (
                      <div className="password-field">
                        <Input
                          label={config.label + (config.required ? ' *' : '')}
                          type={showPassword ? 'text' : 'password'}
                          placeholder={config.placeholder}
                          value={formData[config.name] || ''}
                          onChange={(e) => handleChange(config.name, e.target.value)}
                          error={errors[config.name]}
                          fullWidth
                          required={config.required}
                        />
                        <button
                          type="button"
                          className="password-toggle"
                          onClick={() => setShowPassword(!showPassword)}
                          aria-label={showPassword ? 'Hide password' : 'Show password'}
                        >
                          <svg
                            width="20"
                            height="20"
                            viewBox="0 0 20 20"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.5"
                          >
                            {showPassword ? (
                              <>
                                <path d="M3 3l14 14M10 7a3 3 0 013 3" strokeLinecap="round" />
                                <path d="M4 10s2-5 6-5c1.5 0 2.8.6 3.8 1.5M16 10s-2 5-6 5c-1.5 0-2.8-.6-3.8-1.5" />
                              </>
                            ) : (
                              <>
                                <path d="M2 10s3-5 8-5 8 5 8 5-3 5-8 5-8-5-8-5z" />
                                <circle cx="10" cy="10" r="3" />
                              </>
                            )}
                          </svg>
                        </button>
                      </div>
                    ) : (
                      <DynamicField
                        config={displayConfig}
                        value={formData[config.name]}
                        onChange={(value) => handleChange(config.name, value)}
                        error={errors[config.name]}
                      />
                    )}
                  </div>
                );
              })}
            </>
          )}

        </div>

        <div className="form-actions">
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <div className="form-actions-right">
            <Button
              type="button"
              variant="secondary"
              onClick={handleTestConnection}
              loading={isTesting}
              disabled={isSubmitting}
            >
              Test Connection
            </Button>
            <Button type="submit" variant="primary" loading={isSubmitting} disabled={isTesting}>
              {isEditMode ? 'Update Connection' : 'Create Connection'}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
};
