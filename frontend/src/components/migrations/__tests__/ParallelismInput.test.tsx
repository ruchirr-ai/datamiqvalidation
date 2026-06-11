/**
 * Tests for ParallelismInput component.
 * Requirements: 6.1, 6.2, 6.7
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ParallelismInput } from '../ParallelismInput';

describe('ParallelismInput', () => {
  describe('Rendering', () => {
    it('renders with default label "Parallelism"', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={4} onChange={onChange} destinationType="iceberg_s3" />
      );

      expect(screen.getByText('Parallelism')).toBeInTheDocument();
    });

    it('renders with custom label', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput
          value={4}
          onChange={onChange}
          destinationType="iceberg_s3"
          label="Load Parallelism"
        />
      );

      expect(screen.getByText('Load Parallelism')).toBeInTheDocument();
    });

    it('renders the input with the provided value', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={6} onChange={onChange} destinationType="iceberg_s3" />
      );

      const input = screen.getByRole('spinbutton');
      expect(input).toHaveValue(6);
    });

    it('shows max 8 help text for S3 Tables destinations', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={4} onChange={onChange} destinationType="iceberg_s3_tables" />
      );

      expect(screen.getByText(/max 8 for S3 Tables/)).toBeInTheDocument();
    });

    it('shows max 16 help text for standard S3 destinations', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={4} onChange={onChange} destinationType="iceberg_s3" />
      );

      expect(screen.getByText(/max 16/)).toBeInTheDocument();
    });
  });

  describe('S3 Tables parallelism cap at 8 (Req 6.1, 6.7)', () => {
    it('caps value at 8 when user enters value > 8 for S3 Tables', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const { rerender } = render(
        <ParallelismInput value={4} onChange={onChange} destinationType="iceberg_s3_tables" />
      );

      const input = screen.getByRole('spinbutton');
      // Simulate a change event with value 12 directly
      await user.clear(input);
      // After clear, the component calls onChange with default (4)
      // Rerender with a value > 8 to simulate the user trying to set 12
      rerender(
        <ParallelismInput value={12} onChange={onChange} destinationType="iceberg_s3_tables" />
      );

      // Trigger a change event with value > 8
      await user.clear(input);
      await user.type(input, '9');

      // The onChange should be called with 8 (capped)
      expect(onChange).toHaveBeenCalledWith(8);
    });

    it('allows values up to 8 for S3 Tables', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={8} onChange={onChange} destinationType="iceberg_s3_tables" />
      );

      const input = screen.getByRole('spinbutton');
      // Value 8 should be displayed without capping
      expect(input).toHaveValue(8);
    });

    it('allows values up to 16 for standard S3', () => {
      const onChange = vi.fn();
      // Render with value=16 directly - standard S3 should not cap it
      render(
        <ParallelismInput value={16} onChange={onChange} destinationType="iceberg_s3" />
      );

      const input = screen.getByRole('spinbutton');
      // Value 16 should be displayed without capping
      expect(input).toHaveValue(16);
      // No warning should be shown for standard S3
      expect(
        screen.queryByText(/S3 Tables API has lower concurrency limits/)
      ).not.toBeInTheDocument();
    });

    it('sets max attribute to 8 for S3 Tables', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={4} onChange={onChange} destinationType="iceberg_s3_tables" />
      );

      const input = screen.getByRole('spinbutton');
      expect(input).toHaveAttribute('max', '8');
    });

    it('sets max attribute to 16 for standard S3', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={4} onChange={onChange} destinationType="iceberg_s3" />
      );

      const input = screen.getByRole('spinbutton');
      expect(input).toHaveAttribute('max', '16');
    });
  });

  describe('Warning message display (Req 6.2)', () => {
    it('shows warning when value exceeds 8 for S3 Tables', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={10} onChange={onChange} destinationType="iceberg_s3_tables" />
      );

      expect(
        screen.getByText(
          'S3 Tables API has lower concurrency limits than standard S3. Parallelism above 8 may cause throttling errors and slower overall throughput.'
        )
      ).toBeInTheDocument();
    });

    it('does not show warning when value is 8 or less for S3 Tables', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={8} onChange={onChange} destinationType="iceberg_s3_tables" />
      );

      expect(
        screen.queryByText(/S3 Tables API has lower concurrency limits/)
      ).not.toBeInTheDocument();
    });

    it('does not show warning for standard S3 even with high parallelism', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={12} onChange={onChange} destinationType="iceberg_s3" />
      );

      expect(
        screen.queryByText(/S3 Tables API has lower concurrency limits/)
      ).not.toBeInTheDocument();
    });

    it('warning has role="alert" for accessibility', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={10} onChange={onChange} destinationType="iceberg_s3_tables" />
      );

      const warning = screen.getByRole('alert');
      expect(warning).toHaveClass('parallelism-warning');
    });
  });

  describe('Validation errors', () => {
    it('shows error when value < 1 and showErrors is true', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput
          value={0}
          onChange={onChange}
          destinationType="iceberg_s3"
          showErrors
        />
      );

      expect(screen.getByText('Parallelism must be at least 1.')).toBeInTheDocument();
    });

    it('shows error when value > 8 for S3 Tables and showErrors is true', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput
          value={10}
          onChange={onChange}
          destinationType="iceberg_s3_tables"
          showErrors
        />
      );

      expect(
        screen.getByText('Parallelism must not exceed 8 for S3 Tables destinations.')
      ).toBeInTheDocument();
    });

    it('shows error when value > 16 for standard S3 and showErrors is true', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput
          value={20}
          onChange={onChange}
          destinationType="iceberg_s3"
          showErrors
        />
      );

      expect(screen.getByText('Parallelism must not exceed 16.')).toBeInTheDocument();
    });

    it('does not show errors when showErrors is false', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput
          value={0}
          onChange={onChange}
          destinationType="iceberg_s3"
          showErrors={false}
        />
      );

      expect(screen.queryByText(/Parallelism must be at least/)).not.toBeInTheDocument();
    });
  });

  describe('Edge cases', () => {
    it('handles null destination type gracefully', () => {
      const onChange = vi.fn();
      render(
        <ParallelismInput value={4} onChange={onChange} destinationType={null} />
      );

      // Should render with standard S3 max (16)
      const input = screen.getByRole('spinbutton');
      expect(input).toHaveAttribute('max', '16');
    });

    it('uses default value of 4 when value is NaN', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(
        <ParallelismInput value={4} onChange={onChange} destinationType="iceberg_s3" />
      );

      const input = screen.getByRole('spinbutton');
      await user.clear(input);

      // Clearing triggers onChange with default
      expect(onChange).toHaveBeenCalledWith(4);
    });
  });
});
