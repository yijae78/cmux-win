/**
 * PtyManager — manages PTY lifecycle in the main process and exposes
 * IPC handlers so the renderer can interact with PTY instances without
 * importing node-pty directly.
 *
 * Architecture:
 *   Main (PtyManager + PtyBridge + node-pty)
 *       <-- IPC -->
 *   Preload (thin IPC bridge)
 *       <-- contextBridge -->
 *   Renderer (XTermWrapper)
 */
import { ipcMain, BrowserWindow } from 'electron';
import { EventEmitter } from 'node:events';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import { PtyBridge } from './pty-bridge';
import { buildPtyEnv } from '../../shared/env-utils';
import { getShellIntegrationArgs } from '../../shared/shell-integration-utils';
import { IPC_CHANNELS } from '../../shared/ipc-channels';

// M2: Auto-approve patterns — loaded from external config, fallback to built-in defaults
interface ApproveRule { includes: string[] }
type ApprovePatterns = Record<string, ApproveRule[]>;

const DEFAULT_APPROVE_PATTERNS: ApprovePatterns = {
  claude: [
    { includes: ['Do you want to', 'Yes'] },
    { includes: ['Esc to cancel', '1. Yes'] },
    { includes: ['requires approval', 'Yes'] },
  ],
  gemini: [
    { includes: ['Apply this change'] },
  ],
  codex: [
    { includes: ['Press enter to confirm'] },
  ],
};

function loadApprovePatterns(): ApprovePatterns {
  const configPath = path.join(os.homedir(), '.cmux-win', 'auto-approve-patterns.json');
  try {
    if (fs.existsSync(configPath)) {
      const raw = fs.readFileSync(configPath, 'utf-8');
      return JSON.parse(raw) as ApprovePatterns;
    }
  } catch (err) {
    console.error('[cmux-win] Failed to load auto-approve-patterns.json, using defaults:', err);
  }
  return DEFAULT_APPROVE_PATTERNS;
}

const approvePatterns = loadApprovePatterns();

const bridge = new PtyBridge();
// F7: PTY lifecycle events for external consumers (e.g. agent status tracking)
export const ptyEvents = new EventEmitter();
const surfacePtyMap = new Map<string, string>();

// BUG-D fix: live PTY output buffer per surface for fresh capture-pane reads.
const MAX_LIVE_BUFFER = 100_000;
const liveBuffers = new Map<string, string>();
(globalThis as Record<string, unknown>).__cmuxLiveBuffers = liveBuffers;

// ---------------------------------------------------------------------------
// Source/citation filter — strip Claude-style source references from output
// Detects patterns like "[1] http://..." or "Sources:" blocks and removes them.
// Similar to how Cursor hides citation metadata from the display.
// ---------------------------------------------------------------------------
const sourceLineBuffer = new Map<string, string>(); // partial line accumulator

function filterSources(_surfaceId: string, data: string): string {
  // Pass through all data immediately — no buffering.
  // Only filter complete source/citation lines if present.
  if (!data.includes('\n') && !data.includes('\r')) {
    return data; // No newline = user typing echo, pass through immediately
  }

  const lines = data.split(/(\r?\n|\r)/);
  const filtered: string[] = [];
  for (const line of lines) {
    const stripped = line.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '').trim();
    if (/^\[\d+\]\s*https?:\/\//.test(stripped)) continue;
    if (/^Sources?\s*:?\s*$/i.test(stripped)) continue;
    if (/^출처\s*:?\s*$/.test(stripped)) continue;
    if (/^Source:\s*https?:\/\//.test(stripped)) continue;
    filtered.push(line);
  }
  return filtered.join('');
}

/**
 * Register all PTY-related IPC handlers.
 * Call this once in app.whenReady (or before).
 */
export function registerPtyHandlers(): void {
  // pty:spawn — create a new PTY, return { id, pid }
  ipcMain.handle(
    IPC_CHANNELS.PTY_SPAWN,
    (
      _event,
      surfaceId: string,
      options?: {
        shell?: string;
        cwd?: string;
        cols?: number;
        rows?: number;
        workspaceId?: string;
        paneIndex?: number;
      },
    ) => {
      const mergedEnv = buildPtyEnv(surfaceId, options?.workspaceId, {
        ...process.env,
      } as Record<string, string>, options?.paneIndex);

      // Shell integration
      const integrationDir = path.join(
        mergedEnv.CMUX_BIN_DIR || path.join(__dirname, '../../resources'),
        '../shell-integration',
      );
      const shellName = options?.shell || 'powershell';
      const integration = getShellIntegrationArgs(shellName, integrationDir);
      Object.assign(mergedEnv, integration.env);

      const result = bridge.spawn({ ...options, env: mergedEnv, args: integration.args });
      surfacePtyMap.set(surfaceId, result.id);

      // Register data/exit listeners and forward to all renderer windows
      const ptyId = result.id;

      // Auto-approve: track last approval time to prevent spam
      // Exposed via globalThis so agent.send_task can refresh cooldown (risk ⑩)
      const g10 = globalThis as Record<string, unknown>;
      const autoApproveCooldowns = (g10.__cmuxAutoApproveCooldowns as Map<string, number>) || new Map<string, number>();
      g10.__cmuxAutoApproveCooldowns = autoApproveCooldowns;

      bridge.onData(ptyId, (data) => {
        // BUG-D fix: append to live buffer (raw, unfiltered) for surface.read
        let buf = (liveBuffers.get(surfaceId) ?? '') + data;
        if (buf.length > MAX_LIVE_BUFFER) {
          buf = buf.slice(buf.length - MAX_LIVE_BUFFER);
        }
        liveBuffers.set(surfaceId, buf);

        // Real-time auto-approve: only check NEW incoming data (not full buffer)
        // This prevents re-triggering on stale patterns in the buffer.
        const stripped = data.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '');
        const now = Date.now();
        const lastApproval = autoApproveCooldowns.get(surfaceId) ?? 0;
        if (now - lastApproval > 1000) { // 1s cooldown (was 3s — too slow for rapid approvals)
          // M2: check all approve patterns from config (external or default)
          let needsApproval = false;
          for (const rules of Object.values(approvePatterns)) {
            for (const rule of rules) {
              if (rule.includes.every((p) => stripped.includes(p))) {
                needsApproval = true;
                break;
              }
            }
            if (needsApproval) break;
          }
          if (needsApproval) {
            autoApproveCooldowns.set(surfaceId, now);
            // Delay slightly to let the full prompt render
            setTimeout(() => bridge.write(ptyId, '\r'), 500);
          }
        }

        // Filter source/citation lines from display (Cursor-style)
        const filtered = filterSources(surfaceId, data);
        if (filtered.length === 0) return; // all lines were sources, skip

        for (const win of BrowserWindow.getAllWindows()) {
          if (!win.isDestroyed()) {
            win.webContents.send(IPC_CHANNELS.PTY_DATA, surfaceId, filtered);
          }
        }
      });

      bridge.onExit(ptyId, (exitInfo) => {
        for (const win of BrowserWindow.getAllWindows()) {
          if (!win.isDestroyed()) {
            win.webContents.send(IPC_CHANNELS.PTY_EXIT, surfaceId, exitInfo);
          }
        }
        // F7: emit pty-exit event so index.ts can update agent status
        ptyEvents.emit('pty-exit', surfaceId, exitInfo);
        // Cleanup mapping on exit
        surfacePtyMap.delete(surfaceId);
        liveBuffers.delete(surfaceId);
      });

      return { id: result.id, pid: result.pid };
    },
  );

  // pty:write — send data to a PTY (fire-and-forget)
  ipcMain.on(IPC_CHANNELS.PTY_WRITE, (_event, surfaceId: string, data: string) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    if (ptyId) bridge.write(ptyId, data);
  });

  // pty:resize — resize a PTY (fire-and-forget)
  ipcMain.on(IPC_CHANNELS.PTY_RESIZE, (_event, surfaceId: string, cols: number, rows: number) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    if (ptyId) bridge.resize(ptyId, cols, rows);
  });

  // pty:kill — kill a PTY (fire-and-forget)
  ipcMain.on(IPC_CHANNELS.PTY_KILL, (_event, surfaceId: string) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    if (ptyId) {
      bridge.kill(ptyId);
      surfacePtyMap.delete(surfaceId);
      liveBuffers.delete(surfaceId);
    }
  });

  // pty:has — check if a PTY exists for a surface
  ipcMain.handle(IPC_CHANNELS.PTY_HAS, (_event, surfaceId: string) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    return ptyId ? bridge.has(ptyId) : false;
  });

  // pty:get-shells — return available shell list
  ipcMain.handle(IPC_CHANNELS.PTY_GET_SHELLS, () => {
    return bridge.getAvailableShells();
  });
}

/**
 * Write data directly to a PTY by surfaceId.
 * Used by the pty-write side-effect handler in main/index.ts.
 */
export function writeToPty(surfaceId: string, data: string): void {
  const ptyId = surfacePtyMap.get(surfaceId);
  if (ptyId) bridge.write(ptyId, data);
}

/**
 * Kill all PTY instances (cleanup on app quit).
 */
export function killAllPty(): void {
  bridge.killAll();
  surfacePtyMap.clear();
}
