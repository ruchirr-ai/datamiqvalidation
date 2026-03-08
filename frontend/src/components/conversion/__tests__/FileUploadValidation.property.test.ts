// Feature: code-conversion-enhancements, Property 5: File upload validation
/**
 * Property test: Files with extension in {.txt, .sql, .csv, .json, .xml}
 * and size <= 5MB are accepted. All others are rejected.
 *
 * Validates: Requirements 8.2
 */
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';

const ALLOWED_EXTENSIONS = ['.txt', '.sql', '.csv', '.json', '.xml'];
const MAX_SIZE = 5 * 1024 * 1024; // 5MB

/** Pure validation function for file uploads */
export function validateFileUpload(filename: string, sizeBytes: number): boolean {
  const ext = filename.includes('.') ? filename.slice(filename.lastIndexOf('.')).toLowerCase() : '';
  return ALLOWED_EXTENSIONS.includes(ext) && sizeBytes <= MAX_SIZE && sizeBytes > 0;
}

const validExtArb = fc.constantFrom(...ALLOWED_EXTENSIONS);
const invalidExtArb = fc.constantFrom('.exe', '.bat', '.py', '.js', '.zip', '.tar', '.doc', '.pdf', '');
const validSizeArb = fc.integer({ min: 1, max: MAX_SIZE });
const oversizeArb = fc.integer({ min: MAX_SIZE + 1, max: MAX_SIZE * 3 });
const filenameBase = fc.string({ minLength: 1, maxLength: 20 }).filter(s => /^[a-z0-9_-]+$/.test(s));

describe('Property 5: File upload validation', () => {
  it('accepts valid extensions with valid size', () => {
    fc.assert(
      fc.property(filenameBase, validExtArb, validSizeArb, (base, ext, size) => {
        expect(validateFileUpload(base + ext, size)).toBe(true);
      }),
      { numRuns: 100 }
    );
  });

  it('rejects invalid extensions', () => {
    fc.assert(
      fc.property(filenameBase, invalidExtArb, validSizeArb, (base, ext, size) => {
        expect(validateFileUpload(base + ext, size)).toBe(false);
      }),
      { numRuns: 100 }
    );
  });

  it('rejects files exceeding 5MB', () => {
    fc.assert(
      fc.property(filenameBase, validExtArb, oversizeArb, (base, ext, size) => {
        expect(validateFileUpload(base + ext, size)).toBe(false);
      }),
      { numRuns: 100 }
    );
  });

  it('rejects zero-size files', () => {
    fc.assert(
      fc.property(filenameBase, validExtArb, (base, ext) => {
        expect(validateFileUpload(base + ext, 0)).toBe(false);
      }),
      { numRuns: 100 }
    );
  });
});
