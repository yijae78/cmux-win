import { execSync } from 'node:child_process';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface SshTarget {
  host: string;
  port?: number;
  user?: string;
}

export type SshSessionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface SshSpawnArgs {
  shell: string;
  args: string[];
}

export interface SshSessionResult {
  ok: true;
  spawn: SshSpawnArgs;
}

export interface SshSessionError {
  ok: false;
  error: string;
}

// ---------------------------------------------------------------------------
// Reconnection config
// ---------------------------------------------------------------------------
const MAX_RETRIES = 5;
const BASE_DELAY_MS = 1000;

export interface ReconnectState {
  attempt: number;
  maxRetries: number;
  /** Next delay in ms, or null if max retries exhausted */
  nextDelayMs: number | null;
  status: SshSessionStatus;
}

/**
 * Compute the next reconnection state using exponential backoff.
 * Delays: 1s, 2s, 4s, 8s, 16s — max 5 retries.
 */
export function nextReconnectState(current: ReconnectState): ReconnectState {
  const nextAttempt = current.attempt + 1;
  if (nextAttempt > current.maxRetries) {
    return {
      attempt: nextAttempt,
      maxRetries: current.maxRetries,
      nextDelayMs: null,
      status: 'error',
    };
  }
  return {
    attempt: nextAttempt,
    maxRetries: current.maxRetries,
    nextDelayMs: BASE_DELAY_MS * Math.pow(2, nextAttempt - 1),
    status: 'connecting',
  };
}

export function initialReconnectState(): ReconnectState {
  return {
    attempt: 0,
    maxRetries: MAX_RETRIES,
    nextDelayMs: BASE_DELAY_MS,
    status: 'connecting',
  };
}

// ---------------------------------------------------------------------------
// Parse & build (existing logic, preserved)
// ---------------------------------------------------------------------------
export function parseSshTarget(target: string): SshTarget {
  const match = target.match(/^(?:([^@]+)@)?([^:]+)(?::(\d+))?$/);
  if (!match) throw new Error(`Invalid SSH target: ${target}`);
  return {
    user: match[1] || undefined,
    host: match[2],
    port: match[3] ? parseInt(match[3]) : undefined,
  };
}

export function buildSshCommand(target: SshTarget): SshSpawnArgs {
  const args: string[] = [];
  if (target.port) args.push('-p', String(target.port));
  if (target.user) args.push('-l', target.user);
  args.push(target.host);
  return { shell: 'ssh', args };
}

// ---------------------------------------------------------------------------
// createSshSession — check for ssh.exe and return spawn args
// ---------------------------------------------------------------------------

/**
 * Check if ssh.exe is available on the system PATH.
 */
function isSshAvailable(): boolean {
  try {
    execSync('where ssh', { stdio: 'pipe', windowsHide: true });
    return true;
  } catch {
    return false;
  }
}

/**
 * Create an SSH session by verifying ssh.exe exists and returning
 * spawn arguments suitable for node-pty.
 *
 * @param target - SSH target string (e.g. "user@host:port") or SshTarget object
 * @returns SshSessionResult with spawn args, or SshSessionError
 */
export function createSshSession(
  target: string | SshTarget,
): SshSessionResult | SshSessionError {
  // Check ssh availability
  if (!isSshAvailable()) {
    return {
      ok: false,
      error:
        'ssh.exe not found on PATH. Please install OpenSSH Client:\n' +
        'Settings > Apps > Optional Features > OpenSSH Client',
    };
  }

  // Parse target if string
  let sshTarget: SshTarget;
  try {
    sshTarget = typeof target === 'string' ? parseSshTarget(target) : target;
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : 'Invalid SSH target',
    };
  }

  // Build spawn args for node-pty
  const spawn = buildSshCommand(sshTarget);

  return { ok: true, spawn };
}
