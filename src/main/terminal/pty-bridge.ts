/**
 * PtyBridge — manages node-pty instances for terminal surfaces.
 *
 * IMPORTANT: This file must NOT import from 'electron'.
 * It is a pure Node.js module so it can be tested without Electron.
 */
import * as pty from 'node-pty';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';

// ---------------------------------------------------------------------------
// BUG-21: Shell whitelist — only allow known shells
// ---------------------------------------------------------------------------
export const ALLOWED_SHELLS = new Set([
  'powershell',
  'cmd',
  'wsl',
  'git-bash',
  'powershell.exe',
  'cmd.exe',
  'wsl.exe',
  'bash.exe',
  'bash',
]);

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface PtySpawnOptions {
  shell?: string;
  cwd?: string;
  cols?: number;
  rows?: number;
  env?: Record<string, string>;
  args?: string[];
}

export interface PtyInstance {
  id: string;
  pid: number;
  process: string;
  pty: pty.IPty;
}

// ---------------------------------------------------------------------------
// BUG-20: ConPTY detection
// ---------------------------------------------------------------------------

/**
 * Git Bash must use winpty (conpty causes issues), WSL and everything else
 * should use conpty.
 */
export function shouldUseConpty(resolvedShell: string): boolean {
  const lower = resolvedShell.toLowerCase();
  // Git Bash paths contain 'git' and 'bash' — use winpty
  if (lower.includes('git') && lower.includes('bash')) {
    return false;
  }
  // Bare 'bash' that lives under Git install directory
  if (lower.includes('git') && lower.endsWith('bash.exe')) {
    return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Shell resolution
// ---------------------------------------------------------------------------

/**
 * Map friendly shell names to their executable paths on Windows.
 */
export function resolveShell(shell: string): string {
  switch (shell) {
    case 'powershell':
    case 'powershell.exe':
      return 'powershell.exe';

    case 'cmd':
    case 'cmd.exe':
      return 'cmd.exe';

    case 'wsl':
    case 'wsl.exe':
      return 'wsl.exe';

    case 'bash':
    case 'bash.exe':
      return 'bash.exe';

    case 'git-bash': {
      // Try common Git Bash locations
      const candidates = [
        path.join(
          process.env['PROGRAMFILES'] ?? 'C:\\Program Files',
          'Git',
          'bin',
          'bash.exe',
        ),
        path.join(
          process.env['PROGRAMFILES(X86)'] ?? 'C:\\Program Files (x86)',
          'Git',
          'bin',
          'bash.exe',
        ),
        path.join(
          process.env['LOCALAPPDATA'] ?? '',
          'Programs',
          'Git',
          'bin',
          'bash.exe',
        ),
      ];
      for (const candidate of candidates) {
        if (candidate && fs.existsSync(candidate)) {
          return candidate;
        }
      }
      // Fallback — let the OS PATH resolve it
      return 'bash.exe';
    }

    default:
      return shell;
  }
}

// ---------------------------------------------------------------------------
// PtyBridge class
// ---------------------------------------------------------------------------

let nextId = 1;

export class PtyBridge {
  private instances = new Map<string, PtyInstance>();

  /**
   * Spawn a new PTY process.
   */
  spawn(options: PtySpawnOptions = {}): { id: string; pid: number } {
    const shellName = options.shell ?? 'powershell';

    // BUG-21: validate against whitelist
    if (!ALLOWED_SHELLS.has(shellName)) {
      throw new Error(`Shell not allowed: ${shellName}`);
    }

    const resolvedShell = resolveShell(shellName);
    const useConpty = shouldUseConpty(resolvedShell);
    const cols = options.cols ?? 80;
    const rows = options.rows ?? 24;
    const cwd = options.cwd ?? os.homedir();

    const env = {
      ...process.env,
      ...options.env,
    } as Record<string, string>;

    const ptyProcess = pty.spawn(resolvedShell, options.args ?? [], {
      name: 'xterm-256color',
      cols,
      rows,
      cwd,
      env,
      useConpty,
    });

    const id = `pty-${nextId++}`;
    const instance: PtyInstance = {
      id,
      pid: ptyProcess.pid,
      process: ptyProcess.process,
      pty: ptyProcess,
    };

    this.instances.set(id, instance);

    return { id, pid: ptyProcess.pid };
  }

  /**
   * Write data to a PTY instance.
   */
  write(id: string, data: string): void {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    instance.pty.write(data);
  }

  /**
   * Resize a PTY instance.
   */
  resize(id: string, cols: number, rows: number): void {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    instance.pty.resize(cols, rows);
  }

  /**
   * Kill a PTY instance and remove it from the map.
   */
  kill(id: string): void {
    const instance = this.instances.get(id);
    if (!instance) {
      return; // Already gone — idempotent
    }
    try {
      instance.pty.kill();
    } catch (err) {
      // node-pty ConPTY can throw "AttachConsole failed" on Windows when
      // the console process has already exited. Safe to ignore.
      console.warn(`[PtyBridge] kill(${id}) error (ignored):`, (err as Error).message);
    }
    this.instances.delete(id);
  }

  /**
   * Check whether a PTY instance exists.
   */
  has(id: string): boolean {
    return this.instances.has(id);
  }

  /**
   * Subscribe to data output from a PTY instance.
   */
  onData(id: string, callback: (data: string) => void): { dispose: () => void } {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    return instance.pty.onData(callback);
  }

  /**
   * Subscribe to exit events from a PTY instance.
   */
  onExit(
    id: string,
    callback: (e: { exitCode: number; signal?: number }) => void,
  ): { dispose: () => void } {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    return instance.pty.onExit(callback);
  }

  /**
   * Return the list of shell names available on this system.
   * Always includes 'powershell' and 'cmd'. Adds 'wsl' and 'git-bash' if detected.
   */
  getAvailableShells(): string[] {
    const shells: string[] = ['powershell', 'cmd'];

    // Check for WSL
    try {
      const wslPath = path.join(
        process.env['SYSTEMROOT'] ?? 'C:\\Windows',
        'System32',
        'wsl.exe',
      );
      if (fs.existsSync(wslPath)) {
        shells.push('wsl');
      }
    } catch {
      // Ignore
    }

    // Check for Git Bash
    const gitBashCandidates = [
      path.join(
        process.env['PROGRAMFILES'] ?? 'C:\\Program Files',
        'Git',
        'bin',
        'bash.exe',
      ),
      path.join(
        process.env['PROGRAMFILES(X86)'] ?? 'C:\\Program Files (x86)',
        'Git',
        'bin',
        'bash.exe',
      ),
      path.join(
        process.env['LOCALAPPDATA'] ?? '',
        'Programs',
        'Git',
        'bin',
        'bash.exe',
      ),
    ];
    for (const candidate of gitBashCandidates) {
      if (candidate && fs.existsSync(candidate)) {
        shells.push('git-bash');
        break;
      }
    }

    return shells;
  }

  /**
   * Get all active instance IDs.
   */
  getInstanceIds(): string[] {
    return Array.from(this.instances.keys());
  }

  /**
   * Kill all instances (cleanup on app quit).
   */
  killAll(): void {
    for (const id of this.instances.keys()) {
      this.kill(id);
    }
  }
}
