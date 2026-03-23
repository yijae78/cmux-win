import { describe, it, expect } from 'vitest';
import { parseKeyCombo, matchInput, DEFAULT_SHORTCUTS } from '../../../src/shared/shortcuts';

describe('parseKeyCombo', () => {
  it('parses Ctrl+D', () => {
    expect(parseKeyCombo('Ctrl+D')).toEqual({ ctrl: true, shift: false, alt: false, key: 'D' });
  });

  it('parses Ctrl+Shift+Enter', () => {
    expect(parseKeyCombo('Ctrl+Shift+Enter')).toEqual({
      ctrl: true,
      shift: true,
      alt: false,
      key: 'Enter',
    });
  });

  it('parses Ctrl+Alt+Left', () => {
    expect(parseKeyCombo('Ctrl+Alt+Left')).toEqual({
      ctrl: true,
      shift: false,
      alt: true,
      key: 'Left',
    });
  });
});

describe('matchInput', () => {
  it('finds matching shortcut', () => {
    const result = matchInput(
      { control: true, shift: false, alt: false, key: 'd' },
      DEFAULT_SHORTCUTS,
    );
    expect(result).toBe('splitRight');
  });

  it('returns null for no match', () => {
    const result = matchInput(
      { control: false, shift: false, alt: false, key: 'x' },
      DEFAULT_SHORTCUTS,
    );
    expect(result).toBeNull();
  });

  it('matches Ctrl+Shift+T as newSurface', () => {
    const result = matchInput(
      { control: true, shift: true, alt: false, key: 't' },
      DEFAULT_SHORTCUTS,
    );
    expect(result).toBe('newSurface');
  });
});

describe('DEFAULT_SHORTCUTS', () => {
  it('all shortcuts have unique keys', () => {
    const keys = DEFAULT_SHORTCUTS.map((s) => s.defaultKey);
    const unique = new Set(keys);
    expect(unique.size).toBe(keys.length);
  });

  it('all shortcuts have non-empty id and label', () => {
    for (const s of DEFAULT_SHORTCUTS) {
      expect(s.id.length).toBeGreaterThan(0);
      expect(s.label.length).toBeGreaterThan(0);
    }
  });
});
