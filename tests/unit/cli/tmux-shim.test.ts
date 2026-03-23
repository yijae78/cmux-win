import { describe, it, expect } from 'vitest';

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { convertTmuxKeys } = require('../../../resources/bin/tmux-shim');

describe('tmux-shim', () => {
  describe('convertTmuxKeys', () => {
    it('converts Enter to \\n', () => {
      expect(convertTmuxKeys(['Enter'])).toBe('\n');
    });

    it('converts Space to space', () => {
      expect(convertTmuxKeys(['Space'])).toBe(' ');
    });

    it('converts Tab to \\t', () => {
      expect(convertTmuxKeys(['Tab'])).toBe('\t');
    });

    it('converts Escape to \\x1b', () => {
      expect(convertTmuxKeys(['Escape'])).toBe('\x1b');
    });

    it('converts C-c to \\x03', () => {
      expect(convertTmuxKeys(['C-c'])).toBe('\x03');
    });

    it('converts C-d to \\x04', () => {
      expect(convertTmuxKeys(['C-d'])).toBe('\x04');
    });

    it('passes through normal text', () => {
      expect(convertTmuxKeys(['hello'])).toBe('hello');
    });

    it('joins multiple args', () => {
      expect(convertTmuxKeys(['ls', 'Space', '-la', 'Enter'])).toBe('ls -la\n');
    });

    it('handles mixed keys and text', () => {
      expect(convertTmuxKeys(['echo', 'Space', 'hello', 'Enter'])).toBe('echo hello\n');
    });
  });
});
