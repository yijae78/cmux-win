import { describe, it, expect } from 'vitest';
import {
  extractScrollback,
  MAX_SCROLLBACK_LINES,
  MAX_SCROLLBACK_BYTES,
  isScrollbackWithinLimits,
  type MinimalBuffer,
} from '../../../src/shared/scrollback-utils';

function createMockBuffer(lines: string[]): MinimalBuffer {
  return {
    length: lines.length,
    getLine(index: number) {
      if (index < 0 || index >= lines.length) return undefined;
      return { translateToString: (_trimRight?: boolean) => lines[index] };
    },
  };
}

describe('extractScrollback', () => {
  it('extracts all lines from small buffer', () => {
    const buffer = createMockBuffer(['line1', 'line2', 'line3']);
    expect(extractScrollback(buffer)).toBe('line1\nline2\nline3');
  });

  it('limits to MAX_SCROLLBACK_LINES', () => {
    const lines = Array.from({ length: MAX_SCROLLBACK_LINES + 100 }, (_, i) => `line${i}`);
    const buffer = createMockBuffer(lines);
    const result = extractScrollback(buffer);
    const resultLines = result.split('\n');
    expect(resultLines.length).toBeLessThanOrEqual(MAX_SCROLLBACK_LINES);
  });

  it('limits to MAX_SCROLLBACK_BYTES', () => {
    // Create lines that total > 1MB
    const bigLine = 'x'.repeat(10000);
    const lines = Array.from({ length: 200 }, () => bigLine); // 2MB total
    const buffer = createMockBuffer(lines);
    const result = extractScrollback(buffer);
    expect(result.length).toBeLessThanOrEqual(MAX_SCROLLBACK_BYTES);
  });

  it('handles empty buffer', () => {
    const buffer = createMockBuffer([]);
    expect(extractScrollback(buffer)).toBe('');
  });

  it('handles undefined getLine results', () => {
    const buffer: MinimalBuffer = {
      length: 3,
      getLine(index) {
        if (index === 1) return undefined;
        return { translateToString: () => `line${index}` };
      },
    };
    expect(extractScrollback(buffer)).toBe('line0\nline2');
  });
});

describe('isScrollbackWithinLimits', () => {
  it('returns true for small text', () => {
    expect(isScrollbackWithinLimits('hello')).toBe(true);
  });

  it('returns false for text exceeding limit', () => {
    expect(isScrollbackWithinLimits('x'.repeat(MAX_SCROLLBACK_BYTES + 1))).toBe(false);
  });
});
