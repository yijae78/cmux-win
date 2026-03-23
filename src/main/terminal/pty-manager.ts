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
import path from 'node:path';
import { PtyBridge } from './pty-bridge';
import { buildPtyEnv } from '../../shared/env-utils';
import { getShellIntegrationArgs } from '../../shared/shell-integration-utils';
import { IPC_CHANNELS } from '../../shared/ipc-channels';

const bridge = new PtyBridge();
const surfacePtyMap = new Map<string, string>();

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
      },
    ) => {
      const mergedEnv = buildPtyEnv(surfaceId, options?.workspaceId, {
        ...process.env,
      } as Record<string, string>);

      // Shell integration
      const integrationDir = path.join(
        mergedEnv.CMUX_BIN_DIR || path.join(__dirname, '../../resources'),
        '../shell-integration',
      );
      const shellName = options?.shell || 'powershell';
      const integration = getShellIntegrationArgs(shellName, integrationDir);
      Object.assign(mergedEnv, integration.env);

      const result = bridge.spawn({ ...options, env: mergedEnv });
      surfacePtyMap.set(surfaceId, result.id);

      // Register data/exit listeners and forward to all renderer windows
      const ptyId = result.id;

      bridge.onData(ptyId, (data) => {
        for (const win of BrowserWindow.getAllWindows()) {
          if (!win.isDestroyed()) {
            win.webContents.send(IPC_CHANNELS.PTY_DATA, surfaceId, data);
          }
        }
      });

      bridge.onExit(ptyId, (exitInfo) => {
        for (const win of BrowserWindow.getAllWindows()) {
          if (!win.isDestroyed()) {
            win.webContents.send(IPC_CHANNELS.PTY_EXIT, surfaceId, exitInfo);
          }
        }
        // Cleanup mapping on exit
        surfacePtyMap.delete(surfaceId);
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
