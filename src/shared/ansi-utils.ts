/**
 * Comprehensive ANSI escape sequence stripping.
 * Handles CSI, OSC, DCS, charset, misc escapes, and C0 control characters.
 * Used by surface.read and bridge-watcher for clean text extraction from raw PTY output.
 */

const CSI_RE = /\x1B\[[0-9;?]*[a-zA-Z]/g;

const OSC_RE = /\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)/g;

const DCS_RE = /\x1BP[^\x1B]*\x1B\\/g;

const CHARSET_RE = /\x1B[()][0-9A-B]/g;

const MISC_ESC_RE = /\x1B[>=<N~}{F|7-8]/g;

const C0_RE = /[\x00-\x08\x0B-\x0C\x0E-\x1F]/g;

export function stripAnsiEscapes(s: string): string {
  return s
    .replace(OSC_RE, '')
    .replace(DCS_RE, '')
    .replace(CSI_RE, '')
    .replace(CHARSET_RE, '')
    .replace(MISC_ESC_RE, '')
    .replace(C0_RE, '');
}
