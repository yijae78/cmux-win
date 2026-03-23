import { describe, it, expect } from 'vitest';
import { parseGhosttyTheme, ghosttyToXterm } from '../../../src/main/terminal/theme-parser';

describe('parseGhosttyTheme', () => {
  it('parses background and foreground', () => {
    const theme = parseGhosttyTheme('background = #282a36\nforeground = #f8f8f2');
    expect(theme.background).toBe('#282a36');
    expect(theme.foreground).toBe('#f8f8f2');
  });

  it('parses palette entries', () => {
    const theme = parseGhosttyTheme('palette = 0=#1d1f21\npalette = 1=#cc6666');
    expect(theme.palette[0]).toBe('#1d1f21');
    expect(theme.palette[1]).toBe('#cc6666');
  });

  it('parses cursor-color', () => {
    const theme = parseGhosttyTheme('cursor-color = #f8f8f2');
    expect(theme.cursor_color).toBe('#f8f8f2');
  });

  it('parses selection colors', () => {
    const theme = parseGhosttyTheme(
      'selection-background = #44475a\nselection-foreground = #f8f8f2',
    );
    expect(theme.selection_background).toBe('#44475a');
    expect(theme.selection_foreground).toBe('#f8f8f2');
  });

  it('skips comments and empty lines', () => {
    const theme = parseGhosttyTheme('# comment\n\nbackground = #000');
    expect(theme.background).toBe('#000');
  });

  it('uses defaults for missing fields', () => {
    const theme = parseGhosttyTheme('');
    expect(theme.background).toBe('#000000');
    expect(theme.foreground).toBe('#ffffff');
  });
});

describe('ghosttyToXterm', () => {
  it('maps palette 0 to black', () => {
    const result = ghosttyToXterm({
      palette: { 0: '#111' },
      background: '#000',
      foreground: '#fff',
    });
    expect(result.black).toBe('#111');
  });

  it('maps palette 1 to red', () => {
    const result = ghosttyToXterm({
      palette: { 1: '#f00' },
      background: '#000',
      foreground: '#fff',
    });
    expect(result.red).toBe('#f00');
  });

  it('maps palette 8 to brightBlack', () => {
    const result = ghosttyToXterm({
      palette: { 8: '#888' },
      background: '#000',
      foreground: '#fff',
    });
    expect(result.brightBlack).toBe('#888');
  });

  it('includes cursor and selection colors', () => {
    const result = ghosttyToXterm({
      palette: {},
      background: '#000',
      foreground: '#fff',
      cursor_color: '#ff0',
      selection_background: '#333',
      selection_foreground: '#eee',
    });
    expect(result.cursor).toBe('#ff0');
    expect(result.selectionBackground).toBe('#333');
    expect(result.selectionForeground).toBe('#eee');
  });

  it('handles empty palette', () => {
    const result = ghosttyToXterm({
      palette: {},
      background: '#000',
      foreground: '#fff',
    });
    expect(result.background).toBe('#000');
    expect(result.foreground).toBe('#fff');
    expect(result.black).toBeUndefined();
  });
});
