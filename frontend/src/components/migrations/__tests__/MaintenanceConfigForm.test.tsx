/**
 * Tests for MaintenanceConfigForm component.
 * Covers: rendering, validation, conditional display, default values.
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  MaintenanceConfigForm,
  DEFAULT_MAINTENANCE_CONFIG,
  validateMaintenanceConfig,
} from '../MaintenanceConfigForm';
import type { MaintenanceConfig } from '../../../types/bqIceberg';

describe('MaintenanceConfigForm', () => {
  const defaultProps = {
    config: { ...DEFAULT_MAINTENANCE_CONFIG },
    onChange: vi.fn(),
    destinationType: 'iceberg_s3_tables',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Conditional Rendering (Req 4.5) ---

  it('renders when destination type is iceberg_s3_tables', () => {
    render(<MaintenanceConfigForm {...defaultProps} />);
    expect(screen.getByText('Table Maintenance Settings')).toBeInTheDocument();
  });

  it('does not render when destination type is iceberg_s3', () => {
    const { container } = render(
      <MaintenanceConfigForm {...defaultProps} destinationType="iceberg_s3" />
    );
    expect(container.firstChild).toBeNull();
  });

  it('does not render when destination type is empty', () => {
    const { container } = render(
      <MaintenanceConfigForm {...defaultProps} destinationType="" />
    );
    expect(container.firstChild).toBeNull();
  });

  // --- Field Rendering (Req 4.1) ---

  it('renders target file size field with label and help text', () => {
    render(<MaintenanceConfigForm {...defaultProps} />);
    expect(screen.getByLabelText(/Target File Size/)).toBeInTheDocument();
    expect(screen.getByText(/Target size for compacted files/)).toBeInTheDocument();
  });

  it('renders min snapshots to keep field with label and help text', () => {
    render(<MaintenanceConfigForm {...defaultProps} />);
    expect(screen.getByLabelText(/Min Snapshots to Keep/)).toBeInTheDocument();
    expect(screen.getByText(/Minimum number of table snapshots/)).toBeInTheDocument();
  });

  it('renders max snapshot age field with label and help text', () => {
    render(<MaintenanceConfigForm {...defaultProps} />);
    expect(screen.getByLabelText(/Max Snapshot Age/)).toBeInTheDocument();
    expect(screen.getByText(/Maximum age of snapshots/)).toBeInTheDocument();
  });

  // --- Default Values (Req 4.2) ---

  it('displays default values: 512, 30, 720', () => {
    render(<MaintenanceConfigForm {...defaultProps} />);
    const fileSizeInput = screen.getByLabelText(/Target File Size/) as HTMLInputElement;
    const snapshotsInput = screen.getByLabelText(/Min Snapshots to Keep/) as HTMLInputElement;
    const ageInput = screen.getByLabelText(/Max Snapshot Age/) as HTMLInputElement;

    expect(fileSizeInput.value).toBe('512');
    expect(snapshotsInput.value).toBe('30');
    expect(ageInput.value).toBe('720');
  });

  it('DEFAULT_MAINTENANCE_CONFIG has correct values', () => {
    expect(DEFAULT_MAINTENANCE_CONFIG.target_file_size_mb).toBe(512);
    expect(DEFAULT_MAINTENANCE_CONFIG.min_snapshots_to_keep).toBe(30);
    expect(DEFAULT_MAINTENANCE_CONFIG.max_snapshot_age_hours).toBe(720);
  });

  // --- onChange Callback ---

  it('calls onChange when target file size changes', () => {
    const onChange = vi.fn();
    render(<MaintenanceConfigForm {...defaultProps} onChange={onChange} />);

    const input = screen.getByLabelText(/Target File Size/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: '256' } });

    expect(onChange).toHaveBeenCalledWith({
      ...DEFAULT_MAINTENANCE_CONFIG,
      target_file_size_mb: 256,
    });
  });

  it('calls onChange when min snapshots changes', () => {
    const onChange = vi.fn();
    render(<MaintenanceConfigForm {...defaultProps} onChange={onChange} />);

    const input = screen.getByLabelText(/Min Snapshots to Keep/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: '50' } });

    expect(onChange).toHaveBeenCalledWith({
      ...DEFAULT_MAINTENANCE_CONFIG,
      min_snapshots_to_keep: 50,
    });
  });

  it('calls onChange when max snapshot age changes', () => {
    const onChange = vi.fn();
    render(<MaintenanceConfigForm {...defaultProps} onChange={onChange} />);

    const input = screen.getByLabelText(/Max Snapshot Age/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: '1440' } });

    expect(onChange).toHaveBeenCalledWith({
      ...DEFAULT_MAINTENANCE_CONFIG,
      max_snapshot_age_hours: 1440,
    });
  });

  // --- Validation (Req 4.3, 4.4) ---

  it('shows error when target file size is 0 (empty)', () => {
    const config: MaintenanceConfig = {
      target_file_size_mb: 0,
      min_snapshots_to_keep: 30,
      max_snapshot_age_hours: 720,
    };
    render(
      <MaintenanceConfigForm {...defaultProps} config={config} showErrors={true} />
    );
    expect(screen.getByText('Target file size is required.')).toBeInTheDocument();
  });

  it('shows error when target file size is below 64', () => {
    const config: MaintenanceConfig = {
      target_file_size_mb: 32,
      min_snapshots_to_keep: 30,
      max_snapshot_age_hours: 720,
    };
    render(
      <MaintenanceConfigForm {...defaultProps} config={config} showErrors={true} />
    );
    expect(
      screen.getByText('Target file size must be between 64 MB and 512 MB.')
    ).toBeInTheDocument();
  });

  it('shows error when target file size is above 512', () => {
    const config: MaintenanceConfig = {
      target_file_size_mb: 1024,
      min_snapshots_to_keep: 30,
      max_snapshot_age_hours: 720,
    };
    render(
      <MaintenanceConfigForm {...defaultProps} config={config} showErrors={true} />
    );
    expect(
      screen.getByText('Target file size must be between 64 MB and 512 MB.')
    ).toBeInTheDocument();
  });

  it('shows error when min snapshots is 0 or negative', () => {
    const config: MaintenanceConfig = {
      target_file_size_mb: 512,
      min_snapshots_to_keep: 0,
      max_snapshot_age_hours: 720,
    };
    render(
      <MaintenanceConfigForm {...defaultProps} config={config} showErrors={true} />
    );
    expect(
      screen.getByText('Minimum snapshots to keep must be a positive integer.')
    ).toBeInTheDocument();
  });

  it('shows error when max snapshot age is 0 or negative', () => {
    const config: MaintenanceConfig = {
      target_file_size_mb: 512,
      min_snapshots_to_keep: 30,
      max_snapshot_age_hours: 0,
    };
    render(
      <MaintenanceConfigForm {...defaultProps} config={config} showErrors={true} />
    );
    expect(
      screen.getByText('Maximum snapshot age must be a positive integer.')
    ).toBeInTheDocument();
  });

  it('shows no errors for valid config', () => {
    render(
      <MaintenanceConfigForm {...defaultProps} showErrors={true} />
    );
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows validation errors on blur', async () => {
    const config: MaintenanceConfig = {
      target_file_size_mb: 10,
      min_snapshots_to_keep: 30,
      max_snapshot_age_hours: 720,
    };
    render(<MaintenanceConfigForm {...defaultProps} config={config} />);

    const input = screen.getByLabelText(/Target File Size/);
    fireEvent.blur(input);

    expect(
      screen.getByText('Target file size must be between 64 MB and 512 MB.')
    ).toBeInTheDocument();
  });

  // --- Accessibility ---

  it('has proper aria-labelledby on the form group', () => {
    render(<MaintenanceConfigForm {...defaultProps} />);
    const group = screen.getByRole('group');
    expect(group).toHaveAttribute('aria-labelledby', 'maintenance-config-title');
  });

  it('marks invalid fields with aria-invalid', () => {
    const config: MaintenanceConfig = {
      target_file_size_mb: 10,
      min_snapshots_to_keep: 30,
      max_snapshot_age_hours: 720,
    };
    render(
      <MaintenanceConfigForm {...defaultProps} config={config} showErrors={true} />
    );
    const input = screen.getByLabelText(/Target File Size/);
    expect(input).toHaveAttribute('aria-invalid', 'true');
  });
});

// --- validateMaintenanceConfig unit tests ---

describe('validateMaintenanceConfig', () => {
  it('returns no errors for valid config', () => {
    const errors = validateMaintenanceConfig({
      target_file_size_mb: 256,
      min_snapshots_to_keep: 10,
      max_snapshot_age_hours: 48,
    });
    expect(errors).toEqual({});
  });

  it('returns error for target_file_size_mb = 0', () => {
    const errors = validateMaintenanceConfig({
      target_file_size_mb: 0,
      min_snapshots_to_keep: 10,
      max_snapshot_age_hours: 48,
    });
    expect(errors.target_file_size_mb).toBe('Target file size is required.');
  });

  it('returns error for target_file_size_mb below 64', () => {
    const errors = validateMaintenanceConfig({
      target_file_size_mb: 63,
      min_snapshots_to_keep: 10,
      max_snapshot_age_hours: 48,
    });
    expect(errors.target_file_size_mb).toBe(
      'Target file size must be between 64 MB and 512 MB.'
    );
  });

  it('returns error for target_file_size_mb above 512', () => {
    const errors = validateMaintenanceConfig({
      target_file_size_mb: 513,
      min_snapshots_to_keep: 10,
      max_snapshot_age_hours: 48,
    });
    expect(errors.target_file_size_mb).toBe(
      'Target file size must be between 64 MB and 512 MB.'
    );
  });

  it('accepts target_file_size_mb at boundaries (64 and 512)', () => {
    expect(
      validateMaintenanceConfig({
        target_file_size_mb: 64,
        min_snapshots_to_keep: 1,
        max_snapshot_age_hours: 1,
      })
    ).toEqual({});

    expect(
      validateMaintenanceConfig({
        target_file_size_mb: 512,
        min_snapshots_to_keep: 1,
        max_snapshot_age_hours: 1,
      })
    ).toEqual({});
  });

  it('returns error for min_snapshots_to_keep <= 0', () => {
    const errors = validateMaintenanceConfig({
      target_file_size_mb: 256,
      min_snapshots_to_keep: 0,
      max_snapshot_age_hours: 48,
    });
    expect(errors.min_snapshots_to_keep).toBe(
      'Minimum snapshots to keep must be a positive integer.'
    );
  });

  it('returns error for max_snapshot_age_hours <= 0', () => {
    const errors = validateMaintenanceConfig({
      target_file_size_mb: 256,
      min_snapshots_to_keep: 10,
      max_snapshot_age_hours: -1,
    });
    expect(errors.max_snapshot_age_hours).toBe(
      'Maximum snapshot age must be a positive integer.'
    );
  });

  it('returns multiple errors when multiple fields are invalid', () => {
    const errors = validateMaintenanceConfig({
      target_file_size_mb: 0,
      min_snapshots_to_keep: 0,
      max_snapshot_age_hours: 0,
    });
    expect(errors.target_file_size_mb).toBeDefined();
    expect(errors.min_snapshots_to_keep).toBeDefined();
    expect(errors.max_snapshot_age_hours).toBeDefined();
  });
});
