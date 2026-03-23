import { describe, it, expect, beforeEach, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Mock node-pty before importing the module under test
// ---------------------------------------------------------------------------
vi.mock('node-pty', () => ({
  spawn: vi.fn(() => ({
    pid: 1234,
    cols: 80,
    rows: 24,
    process: 'powershell.exe',
    onData: vi.fn((cb: (data: string) => void) => {
      setTimeout(() => cb('PS C:\\> '), 10);
      return { dispose: vi.fn() };
    }),
    onExit: vi.fn(() => ({ dispose: vi.fn() })),
    write: vi.fn(),
    resize: vi.fn(),
    kill: vi.fn(),
  })),
}));

import {
  PtyBridge,
  ALLOWED_SHELLS,
  shouldUseConpty,
  resolveShell,
} from '../../../src/main/terminal/pty-bridge';
import * as pty from 'node-pty';

describe('PtyBridge', () => {
  let bridge: PtyBridge;

  beforeEach(() => {
    vi.clearAllMocks();
    bridge = new PtyBridge();
  });

  // -------------------------------------------------------------------------
  // spawn
  // -------------------------------------------------------------------------
  describe('spawn', () => {
    it('returns pid and id', () => {
      const result = bridge.spawn({ shell: 'powershell' });
      expect(result.id).toMatch(/^pty-\d+$/);
      expect(result.pid).toBe(1234);
    });

    it('calls node-pty spawn with resolved shell', () => {
      bridge.spawn({ shell: 'powershell' });
      expect(pty.spawn).toHaveBeenCalledWith(
        'powershell.exe',
        [],
        expect.objectContaining({
          name: 'xterm-256color',
          cols: 80,
          rows: 24,
          useConpty: true,
        }),
      );
    });

    it('passes custom cols, rows, and cwd', () => {
      bridge.spawn({
        shell: 'cmd',
        cols: 120,
        rows: 40,
        cwd: 'C:\\Projects',
      });
      expect(pty.spawn).toHaveBeenCalledWith(
        'cmd.exe',
        [],
        expect.objectContaining({
          cols: 120,
          rows: 40,
          cwd: 'C:\\Projects',
        }),
      );
    });
  });

  // -------------------------------------------------------------------------
  // write
  // -------------------------------------------------------------------------
  describe('write', () => {
    it('calls pty.write with the data', () => {
      const { id } = bridge.spawn({ shell: 'powershell' });
      bridge.write(id, 'ls\r');
      const mockPty = (pty.spawn as ReturnType<typeof vi.fn>).mock.results[0]
        .value;
      expect(mockPty.write).toHaveBeenCalledWith('ls\r');
    });

    it('throws for unknown id', () => {
      expect(() => bridge.write('nope', 'x')).toThrow('PTY not found');
    });
  });

  // -------------------------------------------------------------------------
  // resize
  // -------------------------------------------------------------------------
  describe('resize', () => {
    it('calls pty.resize with cols and rows', () => {
      const { id } = bridge.spawn({ shell: 'powershell' });
      bridge.resize(id, 120, 40);
      const mockPty = (pty.spawn as ReturnType<typeof vi.fn>).mock.results[0]
        .value;
      expect(mockPty.resize).toHaveBeenCalledWith(120, 40);
    });

    it('throws for unknown id', () => {
      expect(() => bridge.resize('nope', 80, 24)).toThrow('PTY not found');
    });
  });

  // -------------------------------------------------------------------------
  // kill
  // -------------------------------------------------------------------------
  describe('kill', () => {
    it('removes instance from bridge', () => {
      const { id } = bridge.spawn({ shell: 'powershell' });
      expect(bridge.has(id)).toBe(true);
      bridge.kill(id);
      expect(bridge.has(id)).toBe(false);
    });

    it('calls pty.kill', () => {
      const { id } = bridge.spawn({ shell: 'powershell' });
      bridge.kill(id);
      const mockPty = (pty.spawn as ReturnType<typeof vi.fn>).mock.results[0]
        .value;
      expect(mockPty.kill).toHaveBeenCalled();
    });

    it('is idempotent for already-killed instance', () => {
      bridge.kill('nonexistent'); // should not throw
    });
  });

  // -------------------------------------------------------------------------
  // onData
  // -------------------------------------------------------------------------
  describe('onData', () => {
    it('callback receives data from pty', async () => {
      const { id } = bridge.spawn({ shell: 'powershell' });
      const received: string[] = [];

      bridge.onData(id, (data) => {
        received.push(data);
      });

      // Wait for the setTimeout in the mock to fire
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(received).toContain('PS C:\\> ');
    });

    it('throws for unknown id', () => {
      expect(() => bridge.onData('nope', () => {})).toThrow('PTY not found');
    });
  });

  // -------------------------------------------------------------------------
  // getAvailableShells
  // -------------------------------------------------------------------------
  describe('getAvailableShells', () => {
    it('returns array that always includes powershell', () => {
      const shells = bridge.getAvailableShells();
      expect(Array.isArray(shells)).toBe(true);
      expect(shells).toContain('powershell');
    });

    it('always includes cmd', () => {
      const shells = bridge.getAvailableShells();
      expect(shells).toContain('cmd');
    });
  });

  // -------------------------------------------------------------------------
  // BUG-21: Shell whitelist
  // -------------------------------------------------------------------------
  describe('BUG-21: shell whitelist', () => {
    it('throws "Shell not allowed" for disallowed shell', () => {
      expect(() => bridge.spawn({ shell: 'zsh' })).toThrow('Shell not allowed');
    });

    it('throws for path-traversal attempt', () => {
      expect(() =>
        bridge.spawn({ shell: '../../evil' }),
      ).toThrow('Shell not allowed');
    });

    it('allows all whitelisted shells', () => {
      for (const shell of ALLOWED_SHELLS) {
        // Should not throw (mocked pty.spawn always succeeds)
        expect(() => bridge.spawn({ shell })).not.toThrow();
      }
    });
  });

  // -------------------------------------------------------------------------
  // BUG-20: shouldUseConpty
  // -------------------------------------------------------------------------
  describe('BUG-20: shouldUseConpty', () => {
    it('returns false for Git Bash path', () => {
      expect(
        shouldUseConpty('C:\\Program Files\\Git\\bin\\bash.exe'),
      ).toBe(false);
    });

    it('returns false for git-bash variant paths', () => {
      expect(
        shouldUseConpty('C:\\Program Files (x86)\\Git\\bin\\bash.exe'),
      ).toBe(false);
    });

    it('returns true for powershell.exe', () => {
      expect(shouldUseConpty('powershell.exe')).toBe(true);
    });

    it('returns true for cmd.exe', () => {
      expect(shouldUseConpty('cmd.exe')).toBe(true);
    });

    it('returns true for wsl.exe', () => {
      expect(shouldUseConpty('wsl.exe')).toBe(true);
    });
  });

  // -------------------------------------------------------------------------
  // resolveShell
  // -------------------------------------------------------------------------
  describe('resolveShell', () => {
    it('maps powershell to powershell.exe', () => {
      expect(resolveShell('powershell')).toBe('powershell.exe');
    });

    it('maps cmd to cmd.exe', () => {
      expect(resolveShell('cmd')).toBe('cmd.exe');
    });

    it('maps wsl to wsl.exe', () => {
      expect(resolveShell('wsl')).toBe('wsl.exe');
    });

    it('maps bash to bash.exe', () => {
      expect(resolveShell('bash')).toBe('bash.exe');
    });

    it('returns input for unknown shell', () => {
      expect(resolveShell('fish')).toBe('fish');
    });
  });

  // -------------------------------------------------------------------------
  // has / getInstanceIds / killAll
  // -------------------------------------------------------------------------
  describe('instance management', () => {
    it('has returns true for spawned instance', () => {
      const { id } = bridge.spawn({ shell: 'powershell' });
      expect(bridge.has(id)).toBe(true);
    });

    it('has returns false for unknown id', () => {
      expect(bridge.has('nope')).toBe(false);
    });

    it('getInstanceIds returns all live ids', () => {
      const a = bridge.spawn({ shell: 'powershell' });
      const b = bridge.spawn({ shell: 'cmd' });
      const ids = bridge.getInstanceIds();
      expect(ids).toContain(a.id);
      expect(ids).toContain(b.id);
    });

    it('killAll removes all instances', () => {
      bridge.spawn({ shell: 'powershell' });
      bridge.spawn({ shell: 'cmd' });
      bridge.killAll();
      expect(bridge.getInstanceIds()).toHaveLength(0);
    });
  });
});
