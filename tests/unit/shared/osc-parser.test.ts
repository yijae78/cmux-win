import { describe, it, expect } from 'vitest';
import { parseOsc133P, parseOsc7 } from '../../../src/shared/osc-parser';

describe('parseOsc133P', () => {
  it('parses git_branch without dirty', () => {
    expect(parseOsc133P('P;k=git_branch;v=main')).toEqual({ gitBranch: 'main', gitDirty: false });
  });

  it('parses git_branch with dirty marker', () => {
    expect(parseOsc133P('P;k=git_branch;v=feature/x*')).toEqual({
      gitBranch: 'feature/x',
      gitDirty: true,
    });
  });

  it('ignores unknown keys', () => {
    expect(parseOsc133P('P;k=unknown;v=test')).toEqual({});
  });

  it('returns empty for non-P data', () => {
    expect(parseOsc133P('A')).toEqual({});
  });

  it('returns empty for empty string', () => {
    expect(parseOsc133P('')).toEqual({});
  });
});

describe('parseOsc7', () => {
  it('extracts CWD from file URL', () => {
    expect(parseOsc7('file://localhost/c/Users/test')).toBe('/c/Users/test');
  });

  it('handles URL-encoded spaces', () => {
    expect(parseOsc7('file://localhost/c/My%20Project')).toBe('/c/My Project');
  });

  it('returns null for invalid URL', () => {
    expect(parseOsc7('not a url')).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(parseOsc7('')).toBeNull();
  });
});
