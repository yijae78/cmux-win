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
    // R5: findRealClaude now uses direct fs.existsSync probing (no `where`).
    // It skips directories containing 'claude-wrapper.js' (marker for cmux wrapper).
    // execSyncFn parameter is kept for signature compat but unused.
    const execSync = vi.fn(); // unused but required by signature

    it('returns first existing candidate that is not our wrapper', () => {
      const existsSyncOrig = vi.spyOn(require('fs'), 'existsSync');
      // Simulate: npm global claude.cmd exists, no marker file
      existsSyncOrig.mockImplementation((p: string) => {
        const norm = p.replace(/\\/g, '/');
        if (norm.includes('npm/claude.cmd')) return true;
        if (norm.includes('npm/claude-wrapper.js')) return false;
        return false;
      });
      const result = findRealClaude('C:\\mydir', execSync);
      expect(result).toMatch(/npm.*claude\.cmd$/);
      existsSyncOrig.mockRestore();
    });

    it('skips candidates in wrapper directory (has claude-wrapper.js)', () => {
      const existsSyncOrig = vi.spyOn(require('fs'), 'existsSync');
      existsSyncOrig.mockImplementation((p: string) => {
        const norm = p.replace(/\\/g, '/');
        // First candidate exists but is our wrapper
        if (norm.includes('.local/bin/claude.exe')) return true;
        if (norm.includes('.local/bin/claude-wrapper.js')) return true;
        // Second candidate exists and is NOT our wrapper
        if (norm.includes('npm/claude.cmd')) return true;
        if (norm.includes('npm/claude-wrapper.js')) return false;
        return false;
      });
      const result = findRealClaude('C:\\mydir', execSync);
      expect(result).toMatch(/npm.*claude\.cmd$/);
      existsSyncOrig.mockRestore();
    });

    it('returns null when no candidates exist', () => {
      const existsSyncOrig = vi.spyOn(require('fs'), 'existsSync');
      existsSyncOrig.mockReturnValue(false);
      const result = findRealClaude('C:\\mydir', execSync);
      expect(result).toBeNull();
      existsSyncOrig.mockRestore();
    });

    it('returns null when all candidates are our wrapper', () => {
      const existsSyncOrig = vi.spyOn(require('fs'), 'existsSync');
      // All candidates exist but all have the marker file
      existsSyncOrig.mockReturnValue(true);
      const result = findRealClaude('C:\\mydir', execSync);
      expect(result).toBeNull();
      existsSyncOrig.mockRestore();
    });
  });
});
