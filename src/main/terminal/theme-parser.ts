export interface GhosttyTheme {
  palette: Record<number, string>;
  background: string;
  foreground: string;
  cursor_color?: string;
  selection_background?: string;
  selection_foreground?: string;
}

const ANSI_TO_XTERM: Record<number, string> = {
  0: 'black',
  1: 'red',
  2: 'green',
  3: 'yellow',
  4: 'blue',
  5: 'magenta',
  6: 'cyan',
  7: 'white',
  8: 'brightBlack',
  9: 'brightRed',
  10: 'brightGreen',
  11: 'brightYellow',
  12: 'brightBlue',
  13: 'brightMagenta',
  14: 'brightCyan',
  15: 'brightWhite',
};

export function parseGhosttyTheme(content: string): GhosttyTheme {
  const theme: GhosttyTheme = {
    palette: {},
    background: '#000000',
    foreground: '#ffffff',
  };
  for (const rawLine of content.split('\n')) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eqIdx = line.indexOf('=');
    if (eqIdx === -1) continue;
    const key = line.slice(0, eqIdx).trim();
    const value = line.slice(eqIdx + 1).trim();
    if (key === 'palette') {
      const innerEq = value.indexOf('=');
      if (innerEq !== -1) {
        const idx = parseInt(value.slice(0, innerEq));
        const color = value.slice(innerEq + 1);
        if (!isNaN(idx)) theme.palette[idx] = color;
      }
    } else if (key === 'background') theme.background = value;
    else if (key === 'foreground') theme.foreground = value;
    else if (key === 'cursor-color') theme.cursor_color = value;
    else if (key === 'selection-background') theme.selection_background = value;
    else if (key === 'selection-foreground') theme.selection_foreground = value;
  }
  return theme;
}

export function ghosttyToXterm(ghostty: GhosttyTheme): Record<string, string> {
  const result: Record<string, string> = {
    background: ghostty.background,
    foreground: ghostty.foreground,
  };
  if (ghostty.cursor_color) result.cursor = ghostty.cursor_color;
  if (ghostty.selection_background) result.selectionBackground = ghostty.selection_background;
  if (ghostty.selection_foreground) result.selectionForeground = ghostty.selection_foreground;
  for (const [index, color] of Object.entries(ghostty.palette)) {
    const xtermKey = ANSI_TO_XTERM[Number(index)];
    if (xtermKey) result[xtermKey] = color;
  }
  return result;
}
