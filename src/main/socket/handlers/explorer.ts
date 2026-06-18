import { BrowserWindow } from 'electron';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';
import { IPC_CHANNELS } from '../../../shared/ipc-channels';

export function registerExplorerHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  /**
   * explorer.open_folder — Open a folder in the file explorer and cd into it.
   * Params: { path: string, surfaceId?: string }
   */
  router.register('explorer.open_folder', (params) => {
    const p = params as { path: string; surfaceId?: string };
    if (!p?.path) throw new Error('path is required');

    // Normalize path
    const folderPath = path.resolve(p.path);

    // Validate folder exists
    if (!fs.existsSync(folderPath)) {
      throw new Error(`Folder not found: ${folderPath}`);
    }
    if (!fs.statSync(folderPath).isDirectory()) {
      throw new Error(`Not a directory: ${folderPath}`);
    }

    // Determine target surface
    const surfaceId = p.surfaceId || store.getState().focus.activeSurfaceId;

    // Send IPC to renderer to update explorer UI
    const wins = BrowserWindow.getAllWindows();
    for (const win of wins) {
      if (!win.isDestroyed()) {
        win.webContents.send(IPC_CHANNELS.OPEN_FOLDER, folderPath, surfaceId);
      }
    }

    return { ok: true, path: folderPath, surfaceId: surfaceId ?? null };
  });
}
