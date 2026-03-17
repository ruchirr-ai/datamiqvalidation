/**
 * Property-based test for formatTableSummary accuracy
 *
 * Property 3: Table Summary Accuracy
 * For any non-negative integers (passed, failed, errors), the formatTableSummary function
 * must include exactly the non-zero categories with correct counts and omit zero-count categories.
 *
 * Validates: Requirements 3.1, 3.2, 3.3
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import fc from 'fast-check';
import { formatTableSummary } from '../ValidationDashboardPage';

describe('Property 3: Table Summary Accuracy', () => {
  /**
   * **Validates: Requirements 3.1, 3.2, 3.3**
   */
  it('includes exactly the non-zero categories with correct counts and omits zero-count categories', () => {
    fc.assert(
      fc.property(fc.nat(), fc.nat(), fc.nat(), (passed, failed, errors) => {
        const { container } = render(formatTableSummary(passed, failed, errors));

        const passedEl = container.querySelector('.summary-passed');
        const failedEl = container.querySelector('.summary-failed');
        const errorEl = container.querySelector('.summary-error');
        const noneEl = container.querySelector('.summary-none');

        // Non-zero categories must be present with correct counts
        if (passed > 0) {
          expect(passedEl).not.toBeNull();
          expect(passedEl!.textContent).toBe(`${passed} Passed`);
        } else {
          expect(passedEl).toBeNull();
        }

        if (failed > 0) {
          expect(failedEl).not.toBeNull();
          expect(failedEl!.textContent).toBe(`${failed} Failed`);
        } else {
          expect(failedEl).toBeNull();
        }

        if (errors > 0) {
          expect(errorEl).not.toBeNull();
          expect(errorEl!.textContent).toBe(`${errors} Errors`);
        } else {
          expect(errorEl).toBeNull();
        }

        // When all zero, show dash
        if (passed === 0 && failed === 0 && errors === 0) {
          expect(noneEl).not.toBeNull();
          expect(noneEl!.textContent).toBe('—');
        } else {
          expect(noneEl).toBeNull();
        }

        // Count of rendered category spans must equal count of non-zero inputs
        const nonZeroCount = [passed, failed, errors].filter((n) => n > 0).length;
        const renderedCount = [passedEl, failedEl, errorEl].filter(Boolean).length;
        expect(renderedCount).toBe(nonZeroCount);
      }),
      { numRuns: 200 }
    );
  });
});
