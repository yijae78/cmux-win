/**
 * Unified preload script — exposes cmuxIpc, cmuxWindowId, ptyBridge, and cmuxWin
 * namespaces to the renderer via contextBridge.
 *
 * This file imports from 'electron' and runs in the preload context.
 * PTY operations are handled via IPC to the main process (node-pty runs there).
 */
import { contextBridge, ipcRenderer } from 'electron';
import { IPC_CHANNELS } from '../shared/ipc-channels';

// ---------------------------------------------------------------------------
// cmuxIpc — store dispatch / query / subscribe
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('cmuxIpc', {
  dispatch(action: unknown) {
    return ipcRenderer.invoke(IPC_CHANNELS.DISPATCH, action);
  },

  queryState(query: { slice: string }) {
    return ipcRenderer.invoke(IPC_CHANNELS.QUERY_STATE, query);
  },

  getInitialState() {
    return ipcRenderer.invoke(IPC_CHANNELS.GET_INITIAL_STATE);
  },

  onStateUpdate(callback: (slice: string, data: unknown) => void) {
    const handler = (_event: Electron.IpcRendererEvent, slice: string, data: unknown) => {
      callback(slice, data);
    };
    ipcRenderer.on(IPC_CHANNELS.STATE_UPDATE, handler);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.STATE_UPDATE, handler);
    };
  },
});

// ---------------------------------------------------------------------------
// cmuxWindowId (BUG-8) — receive windowId from main
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('cmuxWindowId', {
  onWindowId(callback: (id: string) => void) {
    const handler = (_event: Electron.IpcRendererEvent, id: string) => {
      callback(id);
    };
    ipcRenderer.on(IPC_CHANNELS.WINDOW_ID, handler);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.WINDOW_ID, handler);
    };
  },
});

// ---------------------------------------------------------------------------
// ptyBridge — terminal PTY operations via IPC to main process
// node-pty runs in the main process; preload is a thin IPC bridge only.
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('ptyBridge', {
  async spawn(
    surfaceId: string,
    options?: {
      shell?: string;
      cwd?: string;
      cols?: number;
      rows?: number;
      workspaceId?: string;
    },
  ): Promise<{ id: string; pid: number }> {
    return ipcRenderer.invoke(IPC_CHANNELS.PTY_SPAWN, surfaceId, options);
  },

  write(surfaceId: string, data: string) {
    ipcRenderer.send(IPC_CHANNELS.PTY_WRITE, surfaceId, data);
  },

  resize(surfaceId: string, cols: number, rows: number) {
    ipcRenderer.send(IPC_CHANNELS.PTY_RESIZE, surfaceId, cols, rows);
  },

  kill(surfaceId: string) {
    ipcRenderer.send(IPC_CHANNELS.PTY_KILL, surfaceId);
  },

  async has(surfaceId: string): Promise<boolean> {
    return ipcRenderer.invoke(IPC_CHANNELS.PTY_HAS, surfaceId);
  },

  onData(surfaceId: string, callback: (data: string) => void) {
    const handler = (_e: Electron.IpcRendererEvent, sid: string, data: string) => {
      if (sid === surfaceId) callback(data);
    };
    ipcRenderer.on(IPC_CHANNELS.PTY_DATA, handler);
    return { dispose: () => ipcRenderer.removeListener(IPC_CHANNELS.PTY_DATA, handler) };
  },

  onExit(surfaceId: string, callback: (e: { exitCode: number; signal?: number }) => void) {
    const handler = (
      _e: Electron.IpcRendererEvent,
      sid: string,
      exitInfo: { exitCode: number; signal?: number },
    ) => {
      if (sid === surfaceId) callback(exitInfo);
    };
    ipcRenderer.on(IPC_CHANNELS.PTY_EXIT, handler);
    return { dispose: () => ipcRenderer.removeListener(IPC_CHANNELS.PTY_EXIT, handler) };
  },

  async getAvailableShells(): Promise<string[]> {
    return ipcRenderer.invoke(IPC_CHANNELS.PTY_GET_SHELLS);
  },
});

// ---------------------------------------------------------------------------
// cmuxShortcut — receive shortcut from main (P2-BUG-1: before-input-event)
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('cmuxShortcut', {
  onShortcut(callback: (id: string) => void) {
    const handler = (_e: Electron.IpcRendererEvent, id: string) => callback(id);
    ipcRenderer.on(IPC_CHANNELS.SHORTCUT, handler);
    return () => ipcRenderer.removeListener(IPC_CHANNELS.SHORTCUT, handler);
  },
});

// ---------------------------------------------------------------------------
// cmuxBrowser — browser automation IPC (Main↔Renderer bridge)
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('cmuxBrowser', {
  onExecuteRequest(callback: (requestId: string, surfaceId: string, code: string) => void) {
    const handler = (
      _e: Electron.IpcRendererEvent,
      requestId: string,
      surfaceId: string,
      code: string,
    ) => {
      callback(requestId, surfaceId, code);
    };
    ipcRenderer.on(IPC_CHANNELS.BROWSER_EXECUTE, handler);
    return () => {
      ipcRenderer.removeListener(IPC_CHANNELS.BROWSER_EXECUTE, handler);
    };
  },

  sendExecuteResult(requestId: string, result: unknown, error?: string) {
    ipcRenderer.send(IPC_CHANNELS.BROWSER_EXECUTE_RESULT, requestId, result, error);
  },
});

// ---------------------------------------------------------------------------
// cmuxScrollback — scrollback persistence (push save + pull load)
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('cmuxScrollback', {
  saveScrollback(surfaceId: string, content: string) {
    ipcRenderer.send(IPC_CHANNELS.SCROLLBACK_SAVE, surfaceId, content);
  },
  loadScrollback(surfaceId: string): Promise<string | null> {
    return ipcRenderer.invoke(IPC_CHANNELS.SCROLLBACK_LOAD, surfaceId);
  },
});

// ---------------------------------------------------------------------------
// cmuxFile — file read IPC for markdown viewer etc.
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('cmuxFile', {
  readFile(filePath: string): Promise<{ content: string } | { error: string }> {
    return ipcRenderer.invoke(IPC_CHANNELS.FILE_READ, filePath);
  },
  listDirectory(
    dirPath: string,
  ): Promise<{ entries: Array<{ name: string; isDirectory: boolean; path: string }> } | { error: string }> {
    return ipcRenderer.invoke(IPC_CHANNELS.FILE_LIST_DIR, dirPath);
  },
  openFolderDialog(): Promise<{ path: string } | { cancelled: true }> {
    return ipcRenderer.invoke(IPC_CHANNELS.DIALOG_OPEN_FOLDER);
  },
});

// ---------------------------------------------------------------------------
// cmuxWin — platform info + window controls
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('cmuxWin', {
  platform: process.platform,
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),
});
