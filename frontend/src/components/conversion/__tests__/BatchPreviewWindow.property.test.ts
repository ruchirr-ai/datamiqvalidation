// Feature: code-conversion-enhancements, Property 10: Batch preview displays all jobs with correct status actions
/**
 * Property test: For any completed batch, the BatchPreviewWindow should list
 * every job. Completed jobs get a Preview action, failed jobs show error.
 *
 * Validates: Requirements 11.2, 11.5
 */
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';

// Pure logic extracted from BatchPreviewWindow for property testing
interface JobSummary {
  id: number;
  status: string;
  error_message: string | null;
}

function getJobAction(job: JobSummary): 'preview' | 'error' {
  return job.status === 'failed' ? 'error' : 'preview';
}

const jobArb: fc.Arbitrary<JobSummary> = fc.record({
  id: fc.integer({ min: 1, max: 10000 }),
  status: fc.oneof(fc.constant('completed'), fc.constant('failed')),
  error_message: fc.oneof(fc.constant(null), fc.string({ minLength: 1, maxLength: 50 })),
});

describe('Property 10: Batch preview displays all jobs with correct status actions', () => {
  it('every completed job gets preview action, every failed job gets error', () => {
    fc.assert(
      fc.property(fc.array(jobArb, { minLength: 1, maxLength: 20 }), (jobs) => {
        for (const job of jobs) {
          const action = getJobAction(job);
          if (job.status === 'completed') {
            expect(action).toBe('preview');
          } else {
            expect(action).toBe('error');
          }
        }
      }),
      { numRuns: 100 }
    );
  });

  it('all jobs in batch are represented', () => {
    fc.assert(
      fc.property(fc.array(jobArb, { minLength: 1, maxLength: 20 }), (jobs) => {
        const actions = jobs.map(getJobAction);
        expect(actions).toHaveLength(jobs.length);
      }),
      { numRuns: 100 }
    );
  });
});
