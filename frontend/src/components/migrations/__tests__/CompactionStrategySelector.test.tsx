/**
 * Tests for CompactionStrategySelector component
 * Covers: strategy selection, sort column management, descriptions display,
 * recommendation display, validation errors.
 * Requirements: 3.1, 3.2, 3.3, 3.4, 3.7
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CompactionStrategySelector } from '../CompactionStrategySelector';
import type { CompactionConfig } from '../../../types/bqIceberg';

// Sample data
const sampleAvailableColumns = ['order_date', 'customer_id', 'product_id', 'amount', 'created_at'];

const defaultConfig: CompactionConfig = {
  strategy: 'binpack',
  sort_columns: [],
};

const sortConfig: CompactionConfig = {
  strategy: 'sort',
  sort_columns: ['order_date'],
};

const configWithRecommendation: CompactionConfig = {
  strategy: 'binpack',
  sort_columns: [],
  recommended_strategy: 'sort',
  recommended_sort_columns: ['order_date', 'customer_id'],
};

describe('CompactionStrategySelector', () => {
  let mockOnChange: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockOnChange = vi.fn();
  });

  // --- Rendering ---

  it('renders the compaction strategy label', () => {
    render(
      <CompactionStrategySelector
        config={defaultConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );
    expect(screen.getByText('Compaction Strategy')).toBeInTheDocument();
  });

  it('renders the strategy dropdown with current value', () => {
    render(
      <CompactionStrategySelector
        config={defaultConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );
    expect(screen.getByText('Binpack')).toBeInTheDocument();
  });

  it('renders all three strategy descriptions', () => {
    render(
      <CompactionStrategySelector
        config={defaultConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );
    expect(
      screen.getByText('Combines small files without reordering (best for append-heavy workloads)')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Reorders data by specified columns (best for range queries on specific columns)')
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Interleaves multiple columns (best for queries filtering on multiple columns simultaneously)'
      )
    ).toBeInTheDocument();
  });

  // --- Strategy Selection ---

  it('calls onChange with new strategy when strategy is changed', async () => {
    const user = userEvent.setup();
    render(
      <CompactionStrategySelector
        config={defaultConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    // Open the dropdown
    const trigger = screen.getByText('Binpack');
    await user.click(trigger);

    // Select Sort
    const sortOption = screen.getByText('Sort');
    await user.click(sortOption);

    expect(mockOnChange).toHaveBeenCalledWith({
      ...defaultConfig,
      strategy: 'sort',
      sort_columns: [],
    });
  });

  it('clears sort columns when switching to binpack', async () => {
    const user = userEvent.setup();
    render(
      <CompactionStrategySelector
        config={sortConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    // Open the dropdown
    const trigger = screen.getByText('Sort');
    await user.click(trigger);

    // Select Binpack
    const binpackOption = screen.getByText('Binpack');
    await user.click(binpackOption);

    expect(mockOnChange).toHaveBeenCalledWith({
      ...sortConfig,
      strategy: 'binpack',
      sort_columns: [],
    });
  });

  // --- Sort Columns (shown for sort and z-order) ---

  it('does not show sort columns input when strategy is binpack', () => {
    render(
      <CompactionStrategySelector
        config={defaultConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );
    expect(screen.queryByText('Sort Columns')).not.toBeInTheDocument();
  });

  it('shows sort columns input when strategy is sort', () => {
    render(
      <CompactionStrategySelector
        config={sortConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );
    expect(screen.getByText('Sort Columns')).toBeInTheDocument();
  });

  it('shows sort columns input when strategy is z-order', () => {
    const zOrderConfig: CompactionConfig = {
      strategy: 'z-order',
      sort_columns: ['order_date'],
    };
    render(
      <CompactionStrategySelector
        config={zOrderConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );
    expect(screen.getByText('Sort Columns')).toBeInTheDocument();
  });

  it('adds a sort column via manual text input', async () => {
    const user = userEvent.setup();
    const config: CompactionConfig = { strategy: 'sort', sort_columns: [] };
    render(
      <CompactionStrategySelector
        config={config}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    const input = screen.getByLabelText('Sort column name');
    await user.type(input, 'customer_id');
    await user.click(screen.getByLabelText('Add sort column'));

    expect(mockOnChange).toHaveBeenCalledWith({
      ...config,
      sort_columns: ['customer_id'],
    });
  });

  it('adds a sort column via Enter key', async () => {
    const user = userEvent.setup();
    const config: CompactionConfig = { strategy: 'sort', sort_columns: [] };
    render(
      <CompactionStrategySelector
        config={config}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    const input = screen.getByLabelText('Sort column name');
    await user.type(input, 'order_date{Enter}');

    expect(mockOnChange).toHaveBeenCalledWith({
      ...config,
      sort_columns: ['order_date'],
    });
  });

  it('shows error when adding a column not in schema', async () => {
    const user = userEvent.setup();
    const config: CompactionConfig = { strategy: 'sort', sort_columns: [] };
    render(
      <CompactionStrategySelector
        config={config}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    const input = screen.getByLabelText('Sort column name');
    await user.type(input, 'nonexistent_col{Enter}');

    expect(
      screen.getByText('Column "nonexistent_col" does not exist in the table schema.')
    ).toBeInTheDocument();
    expect(mockOnChange).not.toHaveBeenCalled();
  });

  it('shows error when adding a duplicate column', async () => {
    const user = userEvent.setup();
    render(
      <CompactionStrategySelector
        config={sortConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    const input = screen.getByLabelText('Sort column name');
    await user.type(input, 'order_date{Enter}');

    expect(screen.getByText('Column "order_date" is already added.')).toBeInTheDocument();
    expect(mockOnChange).not.toHaveBeenCalled();
  });

  it('removes a sort column when remove button is clicked', async () => {
    const user = userEvent.setup();
    const config: CompactionConfig = {
      strategy: 'sort',
      sort_columns: ['order_date', 'customer_id'],
    };
    render(
      <CompactionStrategySelector
        config={config}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    const removeBtn = screen.getByLabelText('Remove column order_date');
    await user.click(removeBtn);

    expect(mockOnChange).toHaveBeenCalledWith({
      ...config,
      sort_columns: ['customer_id'],
    });
  });

  it('displays selected sort columns with order numbers', () => {
    const config: CompactionConfig = {
      strategy: 'sort',
      sort_columns: ['order_date', 'customer_id'],
    };
    render(
      <CompactionStrategySelector
        config={config}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('order_date')).toBeInTheDocument();
    expect(screen.getByText('customer_id')).toBeInTheDocument();
  });

  // --- Recommendation Display ---

  it('shows recommendation when source has clustering columns', () => {
    render(
      <CompactionStrategySelector
        config={configWithRecommendation}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    expect(screen.getByText(/Recommended:/)).toBeInTheDocument();
    expect(screen.getByText('sort')).toBeInTheDocument();
    expect(screen.getByText('order_date, customer_id')).toBeInTheDocument();
    expect(screen.getByText(/source has clustering columns/)).toBeInTheDocument();
  });

  it('does not show recommendation when no clustering columns', () => {
    render(
      <CompactionStrategySelector
        config={defaultConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    expect(screen.queryByText(/Recommended:/)).not.toBeInTheDocument();
  });

  // --- Validation ---

  it('shows validation error when sort columns are empty and showErrors is true', () => {
    const config: CompactionConfig = { strategy: 'sort', sort_columns: [] };
    render(
      <CompactionStrategySelector
        config={config}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
        showErrors={true}
      />
    );

    expect(
      screen.getByText('At least one sort column is required for this strategy.')
    ).toBeInTheDocument();
  });

  it('does not show validation error when showErrors is false', () => {
    const config: CompactionConfig = { strategy: 'sort', sort_columns: [] };
    render(
      <CompactionStrategySelector
        config={config}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
        showErrors={false}
      />
    );

    expect(
      screen.queryByText('At least one sort column is required for this strategy.')
    ).not.toBeInTheDocument();
  });

  it('does not show validation error when sort columns are provided', () => {
    render(
      <CompactionStrategySelector
        config={sortConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
        showErrors={true}
      />
    );

    expect(
      screen.queryByText('At least one sort column is required for this strategy.')
    ).not.toBeInTheDocument();
  });

  // --- Active description highlighting ---

  it('highlights the active strategy description', () => {
    const { container } = render(
      <CompactionStrategySelector
        config={defaultConfig}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    const activeDescription = container.querySelector(
      '.compaction-strategy-selector__description--active'
    );
    expect(activeDescription).toBeInTheDocument();
    expect(activeDescription).toHaveTextContent('Binpack:');
  });

  // --- Add button disabled state ---

  it('disables add button when input is empty', () => {
    const config: CompactionConfig = { strategy: 'sort', sort_columns: [] };
    render(
      <CompactionStrategySelector
        config={config}
        onChange={mockOnChange}
        availableColumns={sampleAvailableColumns}
      />
    );

    const addBtn = screen.getByLabelText('Add sort column');
    expect(addBtn).toBeDisabled();
  });
});
