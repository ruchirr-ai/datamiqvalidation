/**
 * Iceberg Destination Selection Step for the Migration Wizard.
 * Allows users to select between "Apache Iceberg on S3" and "AWS S3 Tables (Managed Iceberg)"
 * and configure the appropriate fields for each sub-type.
 *
 * Requirements: 1.1, 1.2, 1.3, 1.6, 9.1, 9.2, 9.5
 */
import React, { useState, useCallback } from 'react';
import { Input, Select } from '../../../ui';
import {
  AWS_REGIONS,
  IcebergConfigData,
  IcebergDestinationType,
  IcebergValidationErrors,
  validateIcebergConfig,
} from './validators';
import './IcebergDestinationStep.css';

export interface IcebergDestinationStepProps {
  config: IcebergConfigData;
  onChange: (updates: Partial<IcebergConfigData>) => void;
  /** Number of source tables selected (for summary panel) */
  selectedTableCount?: number;
  /** Whether to show validation errors */
  showErrors?: boolean;
}

const REGION_OPTIONS = [
  { value: '', label: 'Select AWS region' },
  ...AWS_REGIONS.map(r => ({ value: r.value, label: `${r.value} - ${r.label}` })),
];

export const IcebergDestinationStep: React.FC<IcebergDestinationStepProps> = ({
  config,
  onChange,
  selectedTableCount = 0,
  showErrors = false,
}) => {
  const [errors, setErrors] = useState<IcebergValidationErrors>({});
  const [showSummary, setShowSummary] = useState(false);

  const handleValidate = useCallback(() => {
    const validationErrors = validateIcebergConfig(config);
    setErrors(validationErrors);
    const isValid = Object.keys(validationErrors).length === 0;
    if (isValid) {
      setShowSummary(true);
    }
    return isValid;
  }, [config]);

  const displayErrors = showErrors ? errors : {};

  // Re-validate on blur for individual fields
  const handleBlurValidate = useCallback(() => {
    if (showErrors) {
      const validationErrors = validateIcebergConfig(config);
      setErrors(validationErrors);
    }
  }, [config, showErrors]);

  const handleDestinationSelect = (type: IcebergDestinationType) => {
    onChange({ destinationType: type });
    setShowSummary(false);
  };

  const handleFieldChange = (updates: Partial<IcebergConfigData>) => {
    onChange(updates);
    setShowSummary(false);
  };

  return (
    <div className="iceberg-destination-step">
      {/* Destination Type Selection Cards */}
      <div className="destination-cards" role="radiogroup" aria-label="Select Iceberg destination type">
        {/* Amazon Redshift card (existing, shown for context) */}
        <div
          className="destination-card disabled"
          aria-disabled="true"
        >
          <div className="destination-card-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="3" y="3" width="18" height="18" rx="3" />
              <path d="M7 8h10M7 12h10M7 16h6" strokeLinecap="round" />
            </svg>
          </div>
          <div className="destination-card-content">
            <h4>Amazon Redshift</h4>
            <p>Load data into a Redshift cluster</p>
          </div>
        </div>

        {/* Apache Iceberg card */}
        <div
          className={`destination-card ${config.destinationType ? 'selected' : ''}`}
          onClick={() => handleDestinationSelect(config.destinationType || 'iceberg_s3')}
          role="radio"
          aria-checked={!!config.destinationType}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              handleDestinationSelect(config.destinationType || 'iceberg_s3');
            }
          }}
        >
          <div className="destination-card-icon iceberg">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 2L3 9l3 11h12l3-11L12 2z" strokeLinejoin="round" />
              <path d="M12 2v20M3 9h18" strokeLinecap="round" />
            </svg>
          </div>
          <div className="destination-card-content">
            <h4>Apache Iceberg</h4>
            <p>Open table format on S3 with Glue catalog</p>
          </div>
          {config.destinationType && (
            <div className="destination-card-check" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 8l3.5 3.5L13 5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          )}
        </div>
      </div>

      {displayErrors.destinationType && (
        <p className="form-error" role="alert">{displayErrors.destinationType}</p>
      )}

      {/* Sub-type selection (only shown when Iceberg is selected) */}
      {config.destinationType && (
        <div className="iceberg-subtype-section">
          <label className="form-label">Storage Type</label>
          <div className="subtype-toggle" role="radiogroup" aria-label="Select Iceberg storage type">
            <button
              type="button"
              className={`subtype-option ${config.destinationType === 'iceberg_s3' ? 'active' : ''}`}
              onClick={() => handleFieldChange({ destinationType: 'iceberg_s3' })}
              role="radio"
              aria-checked={config.destinationType === 'iceberg_s3'}
            >
              <span className="subtype-label">Standard S3</span>
              <span className="subtype-desc">General-purpose S3 bucket</span>
            </button>
            <button
              type="button"
              className={`subtype-option ${config.destinationType === 'iceberg_s3_tables' ? 'active' : ''}`}
              onClick={() => handleFieldChange({ destinationType: 'iceberg_s3_tables' })}
              role="radio"
              aria-checked={config.destinationType === 'iceberg_s3_tables'}
            >
              <span className="subtype-label">AWS S3 Tables</span>
              <span className="subtype-desc">Managed Iceberg storage</span>
            </button>
          </div>

          {/* Dynamic configuration fields */}
          <div className="iceberg-config-fields">
            {config.destinationType === 'iceberg_s3' && (
              <>
                <div className="form-section">
                  <label className="form-label">
                    S3 Bucket Name <span className="required">*</span>
                  </label>
                  <Input
                    type="text"
                    placeholder="my-iceberg-bucket"
                    value={config.s3Bucket}
                    onChange={(e) => handleFieldChange({ s3Bucket: e.target.value })}
                    onBlur={handleBlurValidate}
                    aria-invalid={!!displayErrors.s3Bucket}
                  />
                  {displayErrors.s3Bucket && (
                    <p className="form-error" role="alert">{displayErrors.s3Bucket}</p>
                  )}
                  <p className="form-help">Bucket where Iceberg data files will be stored</p>
                </div>

                <div className="form-section">
                  <label className="form-label">S3 Path Prefix</label>
                  <Input
                    type="text"
                    placeholder="iceberg/tables"
                    value={config.s3PathPrefix}
                    onChange={(e) => handleFieldChange({ s3PathPrefix: e.target.value })}
                    onBlur={handleBlurValidate}
                    aria-invalid={!!displayErrors.s3PathPrefix}
                  />
                  {displayErrors.s3PathPrefix && (
                    <p className="form-error" role="alert">{displayErrors.s3PathPrefix}</p>
                  )}
                  <p className="form-help">Optional path prefix within the bucket (0-512 characters)</p>
                </div>
              </>
            )}

            {config.destinationType === 'iceberg_s3_tables' && (
              <div className="form-section">
                <label className="form-label">
                  Table Bucket ARN <span className="required">*</span>
                </label>
                <Input
                  type="text"
                  placeholder="arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
                  value={config.tableBucketArn}
                  onChange={(e) => handleFieldChange({ tableBucketArn: e.target.value })}
                  onBlur={handleBlurValidate}
                  aria-invalid={!!displayErrors.tableBucketArn}
                />
                {displayErrors.tableBucketArn && (
                  <p className="form-error" role="alert">{displayErrors.tableBucketArn}</p>
                )}
                <p className="form-help">ARN of your S3 Tables bucket</p>
              </div>
            )}

            {/* Common fields */}
            <div className="form-row">
              <div className="form-section">
                <label className="form-label">
                  AWS Region <span className="required">*</span>
                </label>
                <Select
                  value={config.awsRegion}
                  onChange={(value) => handleFieldChange({ awsRegion: String(value) })}
                  options={REGION_OPTIONS}
                />
                {displayErrors.awsRegion && (
                  <p className="form-error" role="alert">{displayErrors.awsRegion}</p>
                )}
              </div>

              <div className="form-section">
                <label className="form-label">
                  Glue Database Name <span className="required">*</span>
                </label>
                <Input
                  type="text"
                  placeholder="my_iceberg_db"
                  value={config.glueDatabaseName}
                  onChange={(e) => handleFieldChange({ glueDatabaseName: e.target.value })}
                  onBlur={handleBlurValidate}
                  aria-invalid={!!displayErrors.glueDatabaseName}
                />
                {displayErrors.glueDatabaseName && (
                  <p className="form-error" role="alert">{displayErrors.glueDatabaseName}</p>
                )}
                <p className="form-help">Lowercase letters, numbers, and underscores (1-255 chars)</p>
              </div>
            </div>

            {/* Authentication section */}
            <div className="auth-section">
              <div className="auth-header">
                <h4>AWS Authentication</h4>
                <div className="auth-toggle">
                  <button
                    type="button"
                    className={`auth-method-btn ${!config.useIamRole ? 'active' : ''}`}
                    onClick={() => handleFieldChange({ useIamRole: false })}
                  >
                    Access Keys
                  </button>
                  <button
                    type="button"
                    className={`auth-method-btn ${config.useIamRole ? 'active' : ''}`}
                    onClick={() => handleFieldChange({ useIamRole: true })}
                  >
                    IAM Role
                  </button>
                </div>
              </div>

              {config.useIamRole ? (
                <div className="form-section">
                  <label className="form-label">
                    IAM Role ARN <span className="required">*</span>
                  </label>
                  <Input
                    type="text"
                    placeholder="arn:aws:iam::123456789012:role/DataMIQIcebergRole"
                    value={config.awsRoleArn}
                    onChange={(e) => handleFieldChange({ awsRoleArn: e.target.value })}
                    onBlur={handleBlurValidate}
                    aria-invalid={!!displayErrors.awsRoleArn}
                  />
                  {displayErrors.awsRoleArn && (
                    <p className="form-error" role="alert">{displayErrors.awsRoleArn}</p>
                  )}
                  <p className="form-help">
                    The system will assume this role via STS for S3, Glue, and Athena access
                  </p>
                </div>
              ) : (
                <>
                  <div className="form-section">
                    <label className="form-label">
                      AWS Access Key ID <span className="required">*</span>
                    </label>
                    <Input
                      type="text"
                      placeholder="AKIAIOSFODNN7EXAMPLE"
                      value={config.awsAccessKeyId}
                      onChange={(e) => handleFieldChange({ awsAccessKeyId: e.target.value })}
                      onBlur={handleBlurValidate}
                      aria-invalid={!!displayErrors.awsAccessKeyId}
                    />
                    {displayErrors.awsAccessKeyId && (
                      <p className="form-error" role="alert">{displayErrors.awsAccessKeyId}</p>
                    )}
                  </div>
                  <div className="form-section">
                    <label className="form-label">
                      AWS Secret Access Key <span className="required">*</span>
                    </label>
                    <Input
                      type="password"
                      placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                      value={config.awsSecretAccessKey}
                      onChange={(e) => handleFieldChange({ awsSecretAccessKey: e.target.value })}
                      onBlur={handleBlurValidate}
                      aria-invalid={!!displayErrors.awsSecretAccessKey}
                    />
                    {displayErrors.awsSecretAccessKey && (
                      <p className="form-error" role="alert">{displayErrors.awsSecretAccessKey}</p>
                    )}
                    <p className="form-help">Will be encrypted via KMS before storage</p>
                  </div>
                </>
              )}
            </div>

            {/* Validate & Show Summary button */}
            <div className="iceberg-actions">
              <button
                type="button"
                className="btn-validate"
                onClick={handleValidate}
              >
                Validate Configuration
              </button>
            </div>
          </div>

          {/* Summary Panel */}
          {showSummary && Object.keys(errors).length === 0 && (
            <div className="iceberg-summary-panel" role="region" aria-label="Configuration summary">
              <h4>Configuration Summary</h4>
              <div className="summary-grid">
                <div className="summary-item">
                  <span className="summary-label">Destination Type</span>
                  <span className="summary-value">
                    {config.destinationType === 'iceberg_s3' ? 'Apache Iceberg on S3' : 'AWS S3 Tables (Managed)'}
                  </span>
                </div>
                {config.destinationType === 'iceberg_s3' && (
                  <div className="summary-item">
                    <span className="summary-label">S3 Bucket</span>
                    <span className="summary-value">{config.s3Bucket}</span>
                  </div>
                )}
                {config.destinationType === 'iceberg_s3_tables' && (
                  <div className="summary-item">
                    <span className="summary-label">Table Bucket ARN</span>
                    <span className="summary-value summary-value--mono">{config.tableBucketArn}</span>
                  </div>
                )}
                <div className="summary-item">
                  <span className="summary-label">Glue Database</span>
                  <span className="summary-value">{config.glueDatabaseName}</span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">AWS Region</span>
                  <span className="summary-value">{config.awsRegion}</span>
                </div>
                <div className="summary-item">
                  <span className="summary-label">Authentication</span>
                  <span className="summary-value">{config.useIamRole ? 'IAM Role' : 'Access Keys'}</span>
                </div>
                {selectedTableCount > 0 && (
                  <div className="summary-item">
                    <span className="summary-label">Source Tables</span>
                    <span className="summary-value">{selectedTableCount} table(s) selected</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
