import { describe, it, expect } from 'vitest';

/**
 * Phase 4-1: stripAnsi + isAgentIdle logic tests.
 * These replicate the functions from cmux-mcp-server.ts to test independently.
 */

function stripAnsi(str: string): string {
  return str
    .replace(/\x1B\[[0-9;?]*[a-zA-Z]/g, '')
    .replace(/\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)/g, '')
    .replace(/\x1BP[^\x1B]*\x1B\\/g, '')
    .replace(/\x1B[()][0-9A-B]/g, '')
    .replace(/\x1B[>=<N~}{F|7-8]/g, '')
    .replace(/[\x00-\x08\x0B-\x0C\x0E-\x1F]/g, '');
}

const IDLE_PATTERNS: Record<string, string[]> = {
  gemini: ['Type your message', 'Enter your prompt', 'What can I help'],
  codex: ['What would you like', 'Enter a prompt'],
  claude: ['❯ ', '> '],
};

function isAgentIdle(screenText: string, agentType: string): boolean {
  const clean = stripAnsi(screenText);
  const lines = clean.split('\n').filter((l) => l.trim().length > 0);
  const tail = lines.slice(-3).join('\n');
  const patterns = IDLE_PATTERNS[agentType.toLowerCase()] || [];
  return patterns.some((p) => tail.includes(p));
}

describe('stripAnsi', () => {
  it('removes CSI color codes', () => {
    expect(stripAnsi('\x1B[31mred\x1B[0m')).toBe('red');
  });

  it('removes CSI with ? private mode', () => {
    expect(stripAnsi('\x1B[?25hvisible')).toBe('visible');
  });

  it('removes OSC sequences (BEL terminator)', () => {
    expect(stripAnsi('\x1B]0;title\x07text')).toBe('text');
  });

  it('removes OSC sequences (ST terminator)', () => {
    expect(stripAnsi('\x1B]7;file://localhost/path\x1B\\text')).toBe('text');
  });

  it('removes DCS sequences', () => {
    expect(stripAnsi('\x1BPsome-data\x1B\\after')).toBe('after');
  });

  it('removes charset designations', () => {
    expect(stripAnsi('\x1B(Btext')).toBe('text');
  });

  it('removes C0 control characters', () => {
    expect(stripAnsi('hello\x01\x02world')).toBe('helloworld');
  });

  it('preserves normal text, newlines, and tabs', () => {
    expect(stripAnsi('hello\nworld\ttab')).toBe('hello\nworld\ttab');
  });

  it('handles complex mixed sequences', () => {
    const input = '\x1B[1;32m❯ \x1B[0m\x1B]133;A\x07prompt text\x1B[?25h';
    expect(stripAnsi(input)).toBe('❯ prompt text');
  });
});

describe('isAgentIdle', () => {
  it('detects Claude idle prompt (❯)', () => {
    expect(isAgentIdle('some output\n❯ ', 'claude')).toBe(true);
  });

  it('detects Claude idle prompt (>)', () => {
    expect(isAgentIdle('line1\nline2\n> ', 'claude')).toBe(true);
  });

  it('does NOT detect > in middle of output (M1 fix)', () => {
    // '> ' appears at line 1 but last 3 lines don't contain it
    const text = '> quoted text\nline2\nline3\nline4\nline5';
    expect(isAgentIdle(text, 'claude')).toBe(false);
  });

  it('detects Gemini idle prompt', () => {
    expect(isAgentIdle('output\nType your message', 'gemini')).toBe(true);
  });

  it('detects Codex idle prompt', () => {
    expect(isAgentIdle('result\nWhat would you like', 'codex')).toBe(true);
  });

  it('returns false for unknown agent type', () => {
    expect(isAgentIdle('any text', 'unknown')).toBe(false);
  });

  it('returns false when agent is actively outputting', () => {
    expect(isAgentIdle('Writing file...\nProcessing...\nAlmost done...', 'claude')).toBe(false);
  });

  it('strips ANSI before checking', () => {
    expect(isAgentIdle('\x1B[32m❯ \x1B[0m', 'claude')).toBe(true);
  });
});
