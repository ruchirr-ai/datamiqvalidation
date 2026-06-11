/**
 * Tests for IcebergCustomStructureEditor
 * Covers: column definition editor, partition spec editor, sort order editor,
 * table properties editor, validation warnings.
 * Requirements: 4.9
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IcebergCustomStructureEditor } from '../IcebergCustomStructureEditor';
import type { CustomStructureValidation } from '../../../types/bqIceberg';

describe('IcebergCustomStructureEditor', () => {
  const mockOnSave = vi.fn();
  const mockOnCancel = vi.fn();
  const mockOnValidate = vi.fn();

  const defaultProps = {
    tableName: 'test_table',
    onSave: mockOnSave,
    onCancel: mockOnCancel,
    onValidate: mockOnValidate,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- Rendering ---

  it('renders with table name in title', () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);
    expect(screen.getByText('test_table')).toBeInTheDocument();
    expect(screen.getByText(/Define Custom Structure/)).toBeInTheDocument();
  });

  it('renders column definition section', () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);
    expect(screen.getByText('Column Definitions')).toBeInTheDocument();
    expect(screen.getByLabelText('Column 1 name')).toBeInTheDocument();
    expect(screen.getByLabelText('Column 1 type')).toBeInTheDocument();
    expect(screen.getByLabelText('Column 1 nullable')).toBeInTheDocument();
  });

  it('renders partition spec section', () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);
    expect(screen.getByText('Partition Spec')).toBeInTheDocument();
    expect(screen.getByText('Add Partition')).toBeInTheDocument();
  });

  it('renders sort order section', () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);
    expect(screen.getByText('Sort Order')).toBeInTheDocument();
    expect(screen.getByText('Add Sort Column')).toBeInTheDocument();
  });

  it('renders table properties section', () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);
    expect(screen.getByText('Table Properties')).toBeInTheDocument();
    expect(screen.getByLabelText('New property key')).toBeInTheDocument();
    expect(screen.getByLabelText('New property value')).toBeInTheDocument();
  });

  it('renders with existing columns when provided', () => {
    const existingColumns = [
      { name: 'id', iceberg_type: 'long', nullable: false },
      { name: 'name', iceberg_type: 'string', nullable: true },
    ];
    render(<IcebergCustomStructureEditor {...defaultProps} existingColumns={existingColumns} />);

    const nameInputs = screen.getAllByLabelText(/Column \d+ name/);
    expect(nameInputs).toHaveLength(2);
    expect(nameInputs[0]).toHaveValue('id');
    expect(nameInputs[1]).toHaveValue('name');
  });

  // --- Column Definition Editor ---

  it('adds a new column when Add Column is clicked', async () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);

    await userEvent.click(screen.getByText('Add Column'));

    const nameInputs = screen.getAllByLabelText(/Column \d+ name/);
    expect(nameInputs).toHaveLength(2);
  });

  it('removes a column when Remove is clicked', async () => {
    const existingColumns = [
      { name: 'id', iceberg_type: 'long', nullable: false },
      { name: 'name', iceberg_type: 'string', nullable: true },
    ];
    render(<IcebergCustomStructureEditor {...defaultProps} existingColumns={existingColumns} />);

    const removeButtons = screen.getAllByLabelText(/Remove column/);
    await userEvent.click(removeButtons[1]);

    const nameInputs = screen.getAllByLabelText(/Column \d+ name/);
    expect(nameInputs).toHaveLength(1);
    expect(nameInputs[0]).toHaveValue('id');
  });

  it('cannot remove the last column', () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);

    const removeButton = screen.getByLabelText('Remove column 1');
    expect(removeButton).toBeDisabled();
  });

  it('updates column name when typed', async () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);

    const nameInput = screen.getByLabelText('Column 1 name');
    await userEvent.type(nameInput, 'user_id');
    expect(nameInput).toHaveValue('user_id');
  });

  it('updates column type when selected', async () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);

    const typeSelect = screen.getByLabelText('Column 1 type');
    await userEvent.selectOptions(typeSelect, 'long');
    expect(typeSelect).toHaveValue('long');
  });

  it('toggles nullable checkbox', async () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);

    const checkbox = screen.getByLabelText('Column 1 nullable');
    expect(checkbox).toBeChecked(); // default is true
    await userEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
  });

  // --- Partition Spec Editor ---

  it('adds a partition when Add Partition is clicked', async () => {
    const existingColumns = [{ name: 'event_date', iceberg_type: 'date', nullable: true }];
    render(<IcebergCustomStructureEditor {...defaultProps} existingColumns={existingColumns} />);

    await userEvent.click(screen.getByText('Add Partition'));

    expect(screen.getByLabelText('Partition 1 column')).toBeInTheDocument();
    expect(screen.getByLabelText('Partition 1 transform')).toBeInTheDocument();
  });

  it('removes a partition when Remove is clicked', async () => {
    const existingColumns = [{ name: 'event_date', iceberg_type: 'date', nullable: true }];
    render(<IcebergCustomStructureEditor {...defaultProps} existingColumns={existingColumns} />);

    await userEvent.click(screen.getByText('Add Partition'));
    expect(screen.getByLabelText('Partition 1 column')).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText('Remove partition 1'));
    expect(screen.queryByLabelText('Partition 1 column')).not.toBeInTheDocument();
  });

  it('partition transform options include all valid transforms', async () => {
    const existingColumns = [{ name: 'col1', iceberg_type: 'date', nullable: true }];
    render(<IcebergCustomStructureEditor {...defaultProps} existingColumns={existingColumns} />);

    await userEvent.click(screen.getByText('Add Partition'));

    const transformSelect = screen.getByLabelText('Partition 1 transform');
    const options = Array.from(transformSelect.querySelectorAll('option')).map((o) => o.value);
    expect(options).toContain('identity');
    expect(options).toContain('day');
    expect(options).toContain('hour');
    expect(options).toContain('month');
    expect(options).toContain('year');
    expect(options).toContain('bucket');
    expect(options).toContain('truncate');
  });

  // --- Sort Order Editor ---

  it('adds a sort column when Add Sort Column is clicked', async () => {
    const existingColumns = [{ name: 'id', iceberg_type: 'long', nullable: false }];
    render(<IcebergCustomStructureEditor {...defaultProps} existingColumns={existingColumns} />);

    await userEvent.click(screen.getByText('Add Sort Column'));

    expect(screen.getByLabelText('Sort 1 column')).toBeInTheDocument();
    expect(screen.getByLabelText('Sort 1 direction')).toBeInTheDocument();
  });

  it('sort direction options are asc and desc', async () => {
    const existingColumns = [{ name: 'id', iceberg_type: 'long', nullable: false }];
    render(<IcebergCustomStructureEditor {...defaultProps} existingColumns={existingColumns} />);

    await userEvent.click(screen.getByText('Add Sort Column'));

    const dirSelect = screen.getByLabelText('Sort 1 direction');
    const options = Array.from(dirSelect.querySelectorAll('option')).map((o) => o.value);
    expect(options).toEqual(['asc', 'desc']);
  });

  // --- Table Properties Editor ---

  it('adds a property when key and value are provided', async () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);

    const keyInput = screen.getByLabelText('New property key');
    const valueInput = screen.getByLabelText('New property value');

    await userEvent.type(keyInput, 'write.format.default');
    await userEvent.type(valueInput, 'parquet');
    await userEvent.click(screen.getByText('Add'));

    expect(screen.getByText('write.format.default')).toBeInTheDocument();
    expect(screen.getByText('parquet')).toBeInTheDocument();
  });

  it('removes a property when Remove is clicked', async () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);

    // Add a property first
    await userEvent.type(screen.getByLabelText('New property key'), 'test.key');
    await userEvent.type(screen.getByLabelText('New property value'), 'test.value');
    await userEvent.click(screen.getByText('Add'));

    expect(screen.getByText('test.key')).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText('Remove property test.key'));
    expect(screen.queryByText('test.key')).not.toBeInTheDocument();
  });

  it('does not add property with empty key', async () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);

    await userEvent.type(screen.getByLabelText('New property value'), 'some-value');
    await userEvent.click(screen.getByText('Add'));

    // No property row should appear
    expect(screen.queryByText('some-value')).not.toBeInTheDocument();
  });

  // --- Validation ---

  it('calls onValidate and displays validation errors', async () => {
    const validationResult: CustomStructureValidation = {
      valid: false,
      warnings: ['Column count mismatch'],
      errors: ['Type incompatibility: cannot map STRING to long'],
    };
    mockOnValidate.mockResolvedValue(validationResult);

    render(<IcebergCustomStructureEditor {...defaultProps} />);

    await userEvent.click(screen.getByText('Validate'));

    await waitFor(() => {
      expect(screen.getByText('Type incompatibility: cannot map STRING to long')).toBeInTheDocument();
    });
    expect(screen.getByText('Column count mismatch')).toBeInTheDocument();
  });

  it('displays success message when validation passes', async () => {
    const validationResult: CustomStructureValidation = {
      valid: true,
      warnings: [],
      errors: [],
    };
    mockOnValidate.mockResolvedValue(validationResult);

    render(<IcebergCustomStructureEditor {...defaultProps} />);

    await userEvent.click(screen.getByText('Validate'));

    await waitFor(() => {
      expect(screen.getByText(/Structure is valid/)).toBeInTheDocument();
    });
  });

  it('displays validation warnings', async () => {
    const validationResult: CustomStructureValidation = {
      valid: true,
      warnings: ['Potential data loss: decimal precision reduced'],
      errors: [],
    };
    mockOnValidate.mockResolvedValue(validationResult);

    render(<IcebergCustomStructureEditor {...defaultProps} />);

    await userEvent.click(screen.getByText('Validate'));

    await waitFor(() => {
      expect(screen.getByText('Potential data loss: decimal precision reduced')).toBeInTheDocument();
    });
  });

  // --- Save and Cancel ---

  it('calls onSave with correct structure definition', async () => {
    const existingColumns = [
      { name: 'id', iceberg_type: 'long', nullable: false },
    ];
    render(<IcebergCustomStructureEditor {...defaultProps} existingColumns={existingColumns} />);

    await userEvent.click(screen.getByText('Save Custom Structure'));

    expect(mockOnSave).toHaveBeenCalledWith(
      expect.objectContaining({
        table_name: 'test_table',
        columns: [{ name: 'id', iceberg_type: 'long', nullable: false }],
        partition_spec: [],
        sort_order: [],
        properties: {},
      })
    );
  });

  it('Save button is disabled when column names are empty', () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);

    // Default state has one empty column name
    const saveButton = screen.getByText('Save Custom Structure');
    expect(saveButton).toBeDisabled();
  });

  it('calls onCancel when Cancel is clicked', async () => {
    render(<IcebergCustomStructureEditor {...defaultProps} />);

    await userEvent.click(screen.getByText('Cancel'));
    expect(mockOnCancel).toHaveBeenCalled();
  });
});
