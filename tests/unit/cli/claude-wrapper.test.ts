import { describe, it, expect, vi } from 'vitest';

// eslint-disable-next-line @typescript-eslint/no-require-imports
const {
  buildHookJson,
  shouldBypass,
  findRealClaude,
  BYPASS_SUBCOMMANDS,
} = require('../../../resources/bin/claude-wrapper-lib');

interface HookEntry {
  type: string;
  command: string;
  timeout: number;
  async?: boolean;
}

interface MatcherEntry {
  matcher: string;
  hooks: HookEntry[];
}

describe('claude-wrapper-lib', () => {
  describe('buildHookJson', () => {
    const hooks = buildHookJson('/path/to/cli.js');

    it('generates 6 hook events', () => {
      const keys = Object.keys(hooks.hooks);
      expect(keys).toEqual([
        'SessionStart',
        'Stop',
        'SessionEnd',
        'Notification',
        'UserPromptSubmit',
        'PreToolUse',
      ]);
    });

    it('SessionEnd has timeout 1', () => {
      const sessionEnd = hooks.hooks.SessionEnd[0].hooks[0];
      expect(sessionEnd.timeout).toBe(1);
    });

    it('PreToolUse has async true and timeout 5', () => {
      const preToolUse = hooks.hooks.PreToolUse[0].hooks[0];
      expect(preToolUse.async).toBe(true);
      expect(preToolUse.timeout).toBe(5);
    });

    it('all commands reference the CLI path', () => {
      for (const [, matchers] of Object.entries(hooks.hooks)) {
        for (const matcher of matchers as MatcherEntry[]) {
          for (const hook of matcher.hooks) {
            expect(hook.command).toContain('/path/to/cli.js');
            expect(hook.command).toContain('claude-hook');
          }
        }
      }
    });

    it('Stop has timeout 10', () => {
      const stop = hooks.hooks.Stop[0].hooks[0];
      expect(stop.timeout).toBe(10);
    });
  });

  describe('shouldBypass', () => {
    it('bypasses mcp subcommand', () => {
      expect(shouldBypass(['mcp'])).toBe(true);
    });

    it('bypasses config subcommand', () => {
      expect(shouldBypass(['config'])).toBe(true);
    });

    it('bypasses api-key subcommand', () => {
      expect(shouldBypass(['api-key'])).toBe(true);
    });

    it('does not bypass empty args', () => {
      expect(shouldBypass([])).toBe(false);
    });

    it('does not bypass unknown subcommands', () => {
      expect(shouldBypass(['chat'])).toBe(false);
      expect(shouldBypass(['--help'])).toBe(false);
    });

    it('has 5 bypass subcommands', () => {
      expect(BYPASS_SUBCOMMANDS).toHaveLength(5);
    });
  });

  describe('findRealClaude', () => {
    it('skips entries in own directory', () => {
      const execSync = vi.fn().mockReturnValue('C:\\app\\bin\\claude.exe\nC:\\other\\claude.exe\n');
      const result = findRealClaude('C:\\app\\bin', execSync);
      expect(result).toBe('C:\\other\\claude.exe');
    });

    it('returns first entry from different directory', () => {
      const execSync = vi.fn().mockReturnValue('C:\\dir1\\claude.exe\nC:\\dir2\\claude.exe\n');
      const result = findRealClaude('C:\\mydir', execSync);
      expect(result).toBe('C:\\dir1\\claude.exe');
    });

    it('returns null when where fails', () => {
      const execSync = vi.fn().mockImplementation(() => {
        throw new Error('not found');
      });
      const result = findRealClaude('C:\\mydir', execSync);
      expect(result).toBeNull();
    });

    it('returns null when all entries are in own directory', () => {
      const execSync = vi.fn().mockReturnValue('C:\\mydir\\claude.exe\n');
      const result = findRealClaude('C:\\mydir', execSync);
      expect(result).toBeNull();
    });

    it('skips empty lines', () => {
      const execSync = vi.fn().mockReturnValue('\n\nC:\\other\\claude.exe\n');
      const result = findRealClaude('C:\\mydir', execSync);
      expect(result).toBe('C:\\other\\claude.exe');
    });
  });
});
