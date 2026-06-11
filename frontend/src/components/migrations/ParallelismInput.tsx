/**
 * ParallelismInput component for configuring migration parallelism.
 * Caps parallelism at 8 for S3 Tables destinations and displays a warning
 * when the value exceeds 8.
 *
 * Requirements: 6.1, 6.2, 6.7
 */
import React, { useCallback, useMemo } from 'react';
import { Input } from '../ui';
import { IcebergDestinationType } from './steps/iceberg/validators';
import './ParallelismInput.css';

export interface ParallelismInputProps {
  /** Current parallelism value */
  value: number;
  /** Callback when value changes */
  onChange: (value: number) => void;
  /** The selected destination type */
  destinationType: IcebergDestinationType | null;
  /** Whether to show validation errors */
  showErrors?: boolean;
  /** Optional label override */
  label?: string;
}

/** Maximum parallelism for S3 Tables destinations */
const S3_TABLES_MAX_PARALLELISM = 8;

/** Maximum parallelism for standard S3 Iceberg destinations */
const STANDARD_S3_MAX_PARALLELISM = 16;

/** Default parallelism value */
const DEFAULT_PARALLELISM = 4;

/** Warning message for S3 Tables when parallelism exceeds 8 */
const S3_TABLES_WARNING_MESSAGE =
  'S3 Tables API has lower concurrency limits than standard S3. Parallelism above 8 may cause throttling errors and slower overall throughput.';

export const ParallelismInput: React.FC<ParallelismInputProps> = ({
  value,
  onChange,
  destinationType,
  showErrors = false,
  label = 'Parallelism',
}) => {
  const isS3Tables = destinationType === 'iceberg_s3_tables';
  const maxParallelism = isS3Tables ? S3_TABLES_MAX_PARALLELISM : STANDARD_S3_MAX_PARALLELISM;

  const showWarning = useMemo(() => {
    return isS3Tables && value > S3_TABLES_MAX_PARALLELISM;
  }, [isS3Tables, value]);

  const validationError = useMemo(() => {
    if (!showErrors) return '';
    if (value < 1) return 'Parallelism must be at least 1.';
    if (isS3Tables && value > S3_TABLES_MAX_PARALLELISM) {
      return `Parallelism must not exceed ${S3_TABLES_MAX_PARALLELISM} for S3 Tables destinations.`;
    }
    if (!isS3Tables && value > STANDARD_S3_MAX_PARALLELISM) {
      return `Parallelism must not exceed ${STANDARD_S3_MAX_PARALLELISM}.`;
    }
    return '';
  }, [value, isS3Tables, showErrors]);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const rawValue = parseInt(e.target.value, 10);
      if (isNaN(rawValue)) {
        onChange(DEFAULT_PARALLELISM);
        return;
      }
      // Cap the value at the max for S3 Tables
      if (isS3Tables && rawValue > S3_TABLES_MAX_PARALLELISM) {
        onChange(S3_TABLES_MAX_PARALLELISM);
        return;
      }
      onChange(rawValue);
    },
    [isS3Tables, onChange]
  );

  return (
    <div className="parallelism-input">
      <div className="form-section">
        <label className="form-label">{label}</label>
        <Input
          type="number"
          min={1}
          max={maxParallelism}
          value={value || DEFAULT_PARALLELISM}
          onChange={handleChange}
          aria-label={label}
          aria-invalid={!!validationError}
          aria-describedby={
            showWarning
              ? 'parallelism-warning'
              : validationError
                ? 'parallelism-error'
                : 'parallelism-help'
          }
        />
        {validationError && (
          <p className="form-error" role="alert" id="parallelism-error">
            {validationError}
          </p>
        )}
        <p className="form-help" id="parallelism-help">
          {isS3Tables
            ? `Number of concurrent tables to load (max ${S3_TABLES_MAX_PARALLELISM} for S3 Tables)`
            : `Number of concurrent tables to load (max ${STANDARD_S3_MAX_PARALLELISM})`}
        </p>
      </div>

      {showWarning && (
        <div className="parallelism-warning" id="parallelism-warning" role="alert">
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <path
              d="M8 1.5L1.5 13.5h13L8 1.5z"
              strokeLinejoin="round"
            />
            <path d="M8 6v3" strokeLinecap="round" />
            <circle cx="8" cy="11.5" r="0.5" fill="currentColor" stroke="none" />
          </svg>
          <span>{S3_TABLES_WARNING_MESSAGE}</span>
        </div>
      )}
    </div>
  );
};

export default ParallelismInput;
