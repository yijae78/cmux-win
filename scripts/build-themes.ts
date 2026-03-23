// scripts/build-themes.ts
/**
 * Build Ghostty -> xterm.js theme cache
 * Reads .ghostty theme files and outputs resources/themes/themes.json
 */
import fs from 'node:fs';
import path from 'node:path';

const THEMES_DIR = path.resolve('resources/themes/ghostty');
const OUTPUT_FILE = path.resolve('resources/themes/themes.json');

interface XTermTheme {
  name: string;
  foreground: string;
  background: string;
  cursor: string;
  cursorAccent?: string;
  selectionBackground?: string;
  black: string;
  red: string;
  green: string;
  yellow: string;
  blue: string;
  magenta: string;
  cyan: string;
  white: string;
  brightBlack: string;
  brightRed: string;
  brightGreen: string;
  brightYellow: string;
  brightBlue: string;
  brightMagenta: string;
  brightCyan: string;
  brightWhite: string;
}

function parseGhosttyTheme(content: string): Partial<XTermTheme> {
  const theme: Record<string, string> = {};
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const value = trimmed.slice(eqIdx + 1).trim();
    theme[key] = value;
  }
  return theme as unknown as Partial<XTermTheme>;
}

// Main
if (!fs.existsSync(THEMES_DIR)) {
  console.warn(`No ghostty themes directory at ${THEMES_DIR}, using existing themes.json`);
  process.exit(0);
}

const themes: Record<string, Partial<XTermTheme>> = {};
for (const file of fs.readdirSync(THEMES_DIR)) {
  if (!file.endsWith('.ghostty') && !file.endsWith('.txt')) continue;
  const content = fs.readFileSync(path.join(THEMES_DIR, file), 'utf8');
  const name = path.basename(file, path.extname(file));
  themes[name] = parseGhosttyTheme(content);
}

fs.writeFileSync(OUTPUT_FILE, JSON.stringify(themes, null, 2));
console.warn(`Built ${Object.keys(themes).length} themes -> ${OUTPUT_FILE}`);
