/**
 * MaintenanceConfigForm component for S3 Tables maintenance settings.
 * Displays fields for target file size, min snapshots to keep, and max snapshot age.
 * Only shown when destination type is `iceberg_s3_tables`.
 *
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
 */
import React, { useState, useCallback } from 'react';
import { Input } from '../ui';
import type { MaintenanceConfig } from '../../types/bqIceberg';
import './MaintenanceConfigForm.css';

export interface MaintenanceConfigFormProps {
  /** Current maintenance config values */
  config: MaintenanceConfig;
  /** Callback when config values change */
  onChange: (config: MaintenanceConfig) => void;
  /** The selected destination type */
  destinationType: string;
  /** Whether to show validation errors immediately */
  showErrors?: boolean;
}

export interface MaintenanceConfigErrors {
  target_file_size_mb?: string;
  min_snapshots_to_keep?: string;
  max_snapshot_age_hours?: string;
}

/** Default maintenance config values per Req 4.2 */
export const DEFAULT_MAINTENANCE_CONFIG: MaintenanceConfig = {
  target_file_size_mb: 512,
  min_snapshots_to_keep: 30,
  max_snapshot_age_hours: 720,
};

/**
 * Validates maintenance config values per Req 4.3 and 4.4.
 * Returns an object with error messages for invalid fields.
 */
export function validateMaintenanceConfig(config: MaintenanceConfig): MaintenanceConfigErrors {
  const errors: MaintenanceConfigErrors = {};

  // Target file size validation (Req 4.4)
  if (config.target_file_size_mb === 0 || isNaN(config.target_file_size_mb)) {
    errors.target_file_size_mb = 'Target file size is required.';
  } else if (config.target_file_size_mb < 64 || config.target_file_size_mb > 512) {
    errors.target_file_size_mb = 'Target file size must be between 64 MB and 512 MB.';
  }

  // Min snapshots to keep validation (Req 4.3)
  if (isNaN(config.min_snapshots_to_keep) || config.min_snapshots_to_keep <= 0) {
    errors.min_snapshots_to_keep = 'Minimum snapshots to keep must be a positive integer.';
  }

  // Max snapshot age hours validation (Req 4.3)
  if (isNaN(config.max_snapshot_age_hours) || config.max_snapshot_age_hours <= 0) {
    errors.max_snapshot_age_hours = 'Maximum snapshot age must be a positive integer.';
  }

  return errors;
}

export const MaintenanceConfigForm: React.FC<MaintenanceConfigFormProps> = ({
  config,
  onChange,
  destinationType,
  showErrors = false,
}) => {
  const [errors, setErrors] = useState<MaintenanceConfigErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  // Only render for S3 Tables destinations (Req 4.5)
  if (destinationType !== 'iceberg_s3_tables') {
    return null;
  }

  const validate = useCallback(() => {
    const validationErrors = validateMaintenanceConfig(config);
    setErrors(validationErrors);
    return validationErrors;
  }, [config]);

  const handleBlur = (field: keyof MaintenanceConfig) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
    validate();
  };

  const handleChange = (field: keyof MaintenanceConfig, value: string) => {
    const numValue = value === '' ? 0 : parseInt(value, 10);
    onChange({ ...config, [field]: isNaN(numValue) ? 0 : numValue });
  };

  // Show errors for fields that have been touched or when showErrors is true
  const getFieldError = (field: keyof MaintenanceConfig): string | undefined => {
    if (showErrors || touched[field]) {
      return errors[field];
    }
    return undefined;
  };

  // Re-validate when showErrors changes
  React.useEffect(() => {
    if (showErrors) {
      validate();
    }
  }, [showErrors, validate]);

  return (
    <div className="maintenance-config-form" role="group" aria-labelledby="maintenance-config-title">
      <div className="maintenance-config-header">
        <h4 id="maintenance-config-title">Table Maintenance Settings</h4>
        <p className="maintenance-config-description">
          Configure S3 Tables compaction and snapshot management settings.
        </p>
      </div>

      <div className="maintenance-config-fields">
        {/* Target File Size */}
        <div className="form-section">
          <label className="form-label" htmlFor="target-file-size">
            Target File Size (MB) <span className="required">*</span>
          </label>
          <Input
            id="target-file-size"
            type="number"
            min={64}
            max={512}
            value={config.target_file_size_mb || ''}
            onChange={(e) => handleChange('target_file_size_mb', e.target.value)}
            onBlur={() => handleBlur('target_file_size_mb')}
            placeholder="512"
            aria-invalid={!!getFieldError('target_file_size_mb')}
            aria-describedby="target-file-size-help"
          />
          {getFieldError('target_file_size_mb') && (
            <p className="form-error" role="alert">
              {getFieldError('target_file_size_mb')}
            </p>
          )}
          <p className="form-help" id="target-file-size-help">
            Target size for compacted files (64–512 MB)
          </p>
        </div>

        {/* Min Snapshots to Keep */}
        <div className="form-section">
          <label className="form-label" htmlFor="min-snapshots">
            Min Snapshots to Keep <span className="required">*</span>
          </label>
          <Input
            id="min-snapshots"
            type="number"
            min={1}
            value={config.min_snapshots_to_keep || ''}
            onChange={(e) => handleChange('min_snapshots_to_keep', e.target.value)}
            onBlur={() => handleBlur('min_snapshots_to_keep')}
            placeholder="30"
            aria-invalid={!!getFieldError('min_snapshots_to_keep')}
            aria-describedby="min-snapshots-help"
          />
          {getFieldError('min_snapshots_to_keep') && (
            <p className="form-error" role="alert">
              {getFieldError('min_snapshots_to_keep')}
            </p>
          )}
          <p className="form-help" id="min-snapshots-help">
            Minimum number of table snapshots to retain
          </p>
        </div>

        {/* Max Snapshot Age Hours */}
        <div className="form-section">
          <label className="form-label" htmlFor="max-snapshot-age">
            Max Snapshot Age (hours) <span className="required">*</span>
          </label>
          <Input
            id="max-snapshot-age"
            type="number"
            min={1}
            value={config.max_snapshot_age_hours || ''}
            onChange={(e) => handleChange('max_snapshot_age_hours', e.target.value)}
            onBlur={() => handleBlur('max_snapshot_age_hours')}
            placeholder="720"
            aria-invalid={!!getFieldError('max_snapshot_age_hours')}
            aria-describedby="max-snapshot-age-help"
          />
          {getFieldError('max_snapshot_age_hours') && (
            <p className="form-error" role="alert">
              {getFieldError('max_snapshot_age_hours')}
            </p>
          )}
          <p className="form-help" id="max-snapshot-age-help">
            Maximum age of snapshots before cleanup (in hours)
          </p>
        </div>
      </div>
    </div>
  );
};
