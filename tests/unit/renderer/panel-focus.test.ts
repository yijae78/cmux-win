import { describe, it, expect } from 'vitest';

/**
 * Pure-logic helpers extracted from usePanelFocus for testability.
 * We test the navigation algorithm directly without React hooks.
 */
import { resolveNextPanel, clampIndex } from '../../../src/renderer/hooks/usePanelFocus';

describe('panel-focus: resolveNextPanel', () => {
  const ids = ['p1', 'p2', 'p3', 'p4'];

  // ---------- right / down ----------
  it('moves right from first to second', () => {
    expect(resolveNextPanel(ids, 'p1', 'right')).toBe('p2');
  });

  it('moves down from first to second (alias for right)', () => {
    expect(resolveNextPanel(ids, 'p1', 'down')).toBe('p2');
  });

  it('wraps around right at end of list', () => {
    expect(resolveNextPanel(ids, 'p4', 'right')).toBe('p1');
  });

  // ---------- left / up ----------
  it('moves left from second to first', () => {
    expect(resolveNextPanel(ids, 'p2', 'left')).toBe('p1');
  });

  it('moves up from second to first (alias for left)', () => {
    expect(resolveNextPanel(ids, 'p2', 'up')).toBe('p1');
  });

  it('wraps around left at start of list', () => {
    expect(resolveNextPanel(ids, 'p1', 'left')).toBe('p4');
  });

  // ---------- boundary: single panel ----------
  it('returns the same panel when list has one element', () => {
    expect(resolveNextPanel(['only'], 'only', 'right')).toBe('only');
    expect(resolveNextPanel(['only'], 'only', 'left')).toBe('only');
  });

  // ---------- boundary: empty list ----------
  it('returns null for an empty panel list', () => {
    expect(resolveNextPanel([], 'p1', 'right')).toBeNull();
  });

  // ---------- boundary: unknown current panel ----------
  it('returns first panel when currentId is not in the list', () => {
    expect(resolveNextPanel(ids, 'unknown', 'right')).toBe('p1');
    expect(resolveNextPanel(ids, 'unknown', 'left')).toBe('p1');
  });

  // ---------- two panels ----------
  it('toggles between two panels going right', () => {
    expect(resolveNextPanel(['a', 'b'], 'a', 'right')).toBe('b');
    expect(resolveNextPanel(['a', 'b'], 'b', 'right')).toBe('a');
  });

  it('toggles between two panels going left', () => {
    expect(resolveNextPanel(['a', 'b'], 'a', 'left')).toBe('b');
    expect(resolveNextPanel(['a', 'b'], 'b', 'left')).toBe('a');
  });
});

describe('panel-focus: clampIndex', () => {
  it('clamps negative index to 0', () => {
    expect(clampIndex(-1, 5)).toBe(0);
  });

  it('clamps index above length to last', () => {
    expect(clampIndex(10, 5)).toBe(4);
  });

  it('returns same index when within bounds', () => {
    expect(clampIndex(2, 5)).toBe(2);
  });

  it('returns 0 for length 0 (edge)', () => {
    expect(clampIndex(0, 0)).toBe(0);
  });
});
