/**
 * cmux-win main process entry point.
 *
 * Initialization order:
 * 1. Load persisted state (clear windows array for fresh session)
 * 2. Create AppStateStore
 * 3. Register 5 middleware (validation, side-effects, persistence, ipc-broadcast, audit-log)
 * 4. Register IPC handlers
 * 5. Set up side-effect listener (pty-write forwarding)
 * 6. Create socket router + register all 8 handler categories
 * 7. app.whenReady: start socket server, create window (async), adoptOrphanWorkspaces
 * 8. window-all-closed: dispose persistence, stop socket, quit
 *
 * BUG-16: ipcMain imported for history IPC handlers (also used in handlers.ts).
 * BUG-16: No RecoveryManager import (Phase 1 deferred).
 * BUG-14: Persisted state loaded with windows cleared.
 * BUG-22: createWindow returns Promise, await it, adoptOrphanWorkspaces AFTER await.
 * BUG-12: SideEffectsMiddleware with callback that calls store.emit('side-effect', effect).
 */
import { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } from 'electron';

// Catch uncaught exceptions from node-pty ConPTY (AttachConsole failed, etc.)
// to prevent the entire app from crashing when a terminal is closed.
process.on('uncaughtException', (err) => {
  if (err.message?.includes('AttachConsole')) {
    console.warn('[cmux-win] ConPTY AttachConsole error (ignored):', err.message);
    return; // swallow — not fatal
  }
  console.error('[cmux-win] Uncaught exception:', err);
  // Re-throw non-ConPTY errors so they still crash as expected
  throw err;
});
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import type { AppState } from '../shared/types';
import { DEFAULT_SOCKET_PORT, SESSION_SAVE_DEBOUNCE_MS } from '../shared/constants';
import { IPC_CHANNELS } from '../shared/ipc-channels';
import { AppStateStore } from './sot/store';
import { loadPersistedState, migrateState } from './sot/migrations/index';
import { ValidationMiddleware } from './sot/middleware/validation';
import { SideEffectsMiddleware } from './sot/middleware/side-effects';
import { PersistenceMiddleware } from './sot/middleware/persistence';
import { IpcBroadcastMiddleware } from './sot/middleware/ipc-broadcast';
import { AuditLogMiddleware } from './sot/middleware/audit-log';
import { registerIpcHandlers } from './ipc/handlers';
import { WindowManager } from './window/window-manager';
import { JsonRpcRouter } from './socket/router';
import { SocketApiServer } from './socket/server';
import { registerSystemHandlers } from './socket/handlers/system';
import { registerWindowHandlers } from './socket/handlers/window';
import { registerWorkspaceHandlers } from './socket/handlers/workspace';
import { registerPanelHandlers } from './socket/handlers/panel';
import { registerSurfaceHandlers } from './socket/handlers/surface';
import { registerAgentHandlers } from './socket/handlers/agent';
import { registerNotificationHandlers } from './socket/handlers/notification';
import { registerSettingsHandlers } from './socket/handlers/settings';
import { registerBrowserHandlers } from './socket/handlers/browser';
import { attachShortcutInterceptor } from './shortcuts/shortcut-interceptor';
import { checkPidStatus } from '../shared/pid-utils';
import { HistoryDb } from './browser/history-db';
import { createTelemetryConfig } from './telemetry/telemetry-manager';
import { createUpdateConfig, initAutoUpdater } from './updates/update-manager';
import { registerPtyHandlers, writeToPty, killAllPty } from './terminal/pty-manager';
import { showToast } from './notifications/windows-toast';
import { computeUnreadCount, formatTrayTitle } from './notifications/tray-manager';

// ---------------------------------------------------------------------------
// 1. Load persisted state (BUG-14: clear windows for fresh session)
// ---------------------------------------------------------------------------
const sessionFilePath = path.join(app.getPath('appData'), 'cmux-win', 'session.json');
const debugLogPath = path.join(app.getPath('temp'), 'cmux-win-debug.log');

let initialState: AppState | undefined;
let lastWindowGeometry: { x: number; y: number; width: number; height: number } | undefined;
const persisted = loadPersistedState(sessionFilePath);
if (persisted) {
  const migrated = migrateState(persisted, sessionFilePath);
  // BUG-14: Save last window geometry before clearing
  lastWindowGeometry = migrated.state.windows[0]?.geometry;
  // BUG-14: Clear transient state — windows, agents, workspaces, panels, surfaces
  // Every app start begins fresh with one workspace created by App.tsx
  initialState = {
    ...migrated.state,
    windows: [],
    agents: [],
    workspaces: [],
    panels: [],
    surfaces: [],
  };
}

// ---------------------------------------------------------------------------
// Scrollback persistence
// ---------------------------------------------------------------------------
const scrollbackPath = path.join(
  process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'),
  'cmux-win',
  'scrollback.json',
);
const scrollbackStore = new Map<string, string>();
// R6: expose scrollbackStore globally so surface.read handler can access it
(globalThis as Record<string, unknown>).__cmuxScrollbackStore = scrollbackStore;
let scrollbackSaveTimer: ReturnType<typeof setTimeout> | null = null;

// Load on startup
try {
  const raw = fs.readFileSync(scrollbackPath, 'utf8');
  const data = JSON.parse(raw) as Record<string, string>;
  for (const [k, v] of Object.entries(data)) scrollbackStore.set(k, v);
} catch {
  /* file missing or corrupted — start fresh */
}

// ---------------------------------------------------------------------------
// 2. Create store
// ---------------------------------------------------------------------------
const store = new AppStateStore(initialState);

// ---------------------------------------------------------------------------
// 3. Register 5 middleware
// ---------------------------------------------------------------------------
const validationMw = new ValidationMiddleware();
// BUG-12: SideEffectsMiddleware with callback forwarding to store EventEmitter
const sideEffectsMw = new SideEffectsMiddleware((effect) => {
  store.emit('side-effect', effect);
});
const persistenceMw = new PersistenceMiddleware(sessionFilePath, SESSION_SAVE_DEBOUNCE_MS);
const ipcBroadcastMw = new IpcBroadcastMiddleware();
const auditLogMw = new AuditLogMiddleware(debugLogPath);

store.use(validationMw);
store.use(sideEffectsMw);
store.use(persistenceMw);
store.use(ipcBroadcastMw);
store.use(auditLogMw);

// ---------------------------------------------------------------------------
// 4. Register IPC handlers + PTY handlers (node-pty in main process)
// ---------------------------------------------------------------------------
registerIpcHandlers(store);
registerPtyHandlers();

// ---------------------------------------------------------------------------
// Window control IPC (frameless window — custom titlebar buttons)
// ---------------------------------------------------------------------------
ipcMain.on('window:minimize', (event) => {
  BrowserWindow.fromWebContents(event.sender)?.minimize();
});
ipcMain.on('window:maximize', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (win?.isMaximized()) win.unmaximize();
  else win?.maximize();
});
ipcMain.on('window:close', (event) => {
  BrowserWindow.fromWebContents(event.sender)?.close();
});

// ---------------------------------------------------------------------------
// 5. Side-effect listener: write directly to PTY in main process
// ---------------------------------------------------------------------------
const windowManager = new WindowManager();

// Module-level tray reference for side-effect handler (assigned in app.whenReady)
let appTray: Tray | null = null;

store.on('side-effect', (effect: { type: string; surfaceId?: string; text?: string; title?: string; body?: string; workspaceId?: string }) => {
  if (effect.type === 'pty-write' && effect.surfaceId && effect.text !== undefined) {
    writeToPty(effect.surfaceId, effect.text);
  }

  // Task 32: Show native Windows toast on notification.create and update tray badge
  if (effect.type === 'notification-created') {
    const title = (effect.title as string) || 'cmux-win';
    const body = (effect.body as string) || '';
    showToast(title, body);

    // Update tray title with unread badge count
    if (appTray) {
      const unread = computeUnreadCount(store.getState().notifications);
      appTray.setToolTip(formatTrayTitle(unread));
    }
  }
});

// ---------------------------------------------------------------------------
// 6. Create socket router + register all 8 handler categories
// ---------------------------------------------------------------------------
const router = new JsonRpcRouter();
registerSystemHandlers(router, store);
registerWindowHandlers(router, store);
registerWorkspaceHandlers(router, store);
registerPanelHandlers(router, store);
registerSurfaceHandlers(router, store);
registerAgentHandlers(router, store);
registerNotificationHandlers(router, store);
registerSettingsHandlers(router, store);
registerBrowserHandlers(router, store);

const socketServer = new SocketApiServer(router);

// Module-level so window-all-closed can access it
let historyDb: HistoryDb | null = null;

// ---------------------------------------------------------------------------
// 7. app.whenReady: start socket, create window, adopt orphans
// ---------------------------------------------------------------------------
async function createWindow(): Promise<BrowserWindow> {
  const win = new BrowserWindow({
    width: lastWindowGeometry?.width ?? 1200,
    height: lastWindowGeometry?.height ?? 800,
    x: lastWindowGeometry?.x,
    y: lastWindowGeometry?.y,
    center: !lastWindowGeometry,
    show: false,
    title: 'cmux-win',
    frame: false,
    backgroundColor: '#272822',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webviewTag: true,
    },
  });

  // Dispatch window.create to store
  store.dispatch({ type: 'window.create', payload: {} });

  // BUG-22: Get windowId from the last created window in state
  const windowId = store.getState().windows.at(-1)!.id;

  // Register with windowManager and ipcBroadcastMw
  windowManager.register(windowId, win, () => {
    ipcBroadcastMw.unregisterWindow(windowId);
  });
  ipcBroadcastMw.registerWindow(windowId, win, () => {
    windowManager.unregister(windowId);
  });

  // Phase 2: Attach keyboard shortcut interceptor (P2-BUG-1)
  attachShortcutInterceptor(win);

  // Return a Promise that resolves when the renderer is ready
  return new Promise<BrowserWindow>((resolve) => {
    // Capture renderer console messages for debugging
    win.webContents.on('console-message', (_event, level, message, line, sourceId) => {
      if (level >= 2) {
        // warnings and errors only
        console.warn(`[Renderer:${level}] ${message} (${sourceId}:${line})`);
      }
    });

    win.webContents.on('did-finish-load', () => {
      // Send the windowId to the renderer
      win.webContents.send(IPC_CHANNELS.WINDOW_ID, windowId);
      // Show window after content is ready (avoids blank flash)
      win.show();
      // DevTools: Ctrl+Shift+I to open manually (not auto-open)
      // if (process.env.ELECTRON_RENDERER_URL) {
      //   win.webContents.openDevTools({ mode: 'detach' });
      // }
      resolve(win);
    });

    // Load content — use ELECTRON_RENDERER_URL from electron-vite dev
    const rendererUrl = process.env.ELECTRON_RENDERER_URL;
    if (rendererUrl) {
      win.loadURL(rendererUrl);
    } else {
      win.loadFile(path.join(__dirname, '../renderer/index.html'));
    }
  });
}

app.whenReady().then(async () => {
  app.setAppUserModelId('com.cmux-win.app');

  // History DB
  try {
    const historyPath = path.join(app.getPath('appData'), 'cmux-win', 'history.db');
    historyDb = new HistoryDb(historyPath);
  } catch (err) {
    console.error('[cmux-win] Failed to init history DB:', err);
  }

  if (historyDb) {
    ipcMain.handle(
      'browser:history:query',
      (_, args: { prefix: string; profileId: string; limit?: number }) =>
        historyDb!.query(args.profileId, args.prefix, args.limit),
    );
    ipcMain.handle(
      'browser:history:add',
      (_, args: { url: string; title?: string; profileId: string; faviconUrl?: string }) =>
        historyDb!.add(args.profileId, args.url, args.title, args.faviconUrl),
    );
    ipcMain.handle('browser:history:clear', (_, args: { profileId?: string }) =>
      historyDb!.clear(args.profileId),
    );
  }

  // Scrollback IPC handlers
  ipcMain.on(IPC_CHANNELS.SCROLLBACK_SAVE, (_event, surfaceId: string, content: string) => {
    scrollbackStore.set(surfaceId, content);
    if (scrollbackSaveTimer) clearTimeout(scrollbackSaveTimer);
    scrollbackSaveTimer = setTimeout(() => {
      try {
        const dir = path.dirname(scrollbackPath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        const tmp = scrollbackPath + '.tmp';
        fs.writeFileSync(tmp, JSON.stringify(Object.fromEntries(scrollbackStore)));
        fs.renameSync(tmp, scrollbackPath);
      } catch (err) {
        console.error('[cmux-win] scrollback save error:', err);
      }
    }, 5000);
  });

  ipcMain.handle(IPC_CHANNELS.SCROLLBACK_LOAD, (_event, surfaceId: string) => {
    return scrollbackStore.get(surfaceId) ?? null;
  });

  // File read IPC handler (for markdown viewer etc.)
  ipcMain.handle(IPC_CHANNELS.FILE_READ, async (_event, filePath: string) => {
    try {
      // Basic path validation — only allow absolute paths
      if (!path.isAbsolute(filePath)) {
        return { error: 'Only absolute file paths are allowed' };
      }
      const content = await fs.promises.readFile(filePath, 'utf8');
      return { content };
    } catch (err) {
      return { error: err instanceof Error ? err.message : 'Failed to read file' };
    }
  });

  // Telemetry (stub — actual SDKs initialized when API keys present)
  const telemetryConfig = createTelemetryConfig(store.getState().settings.telemetry.enabled);
  void telemetryConfig; // acknowledge

  // Auto-update via electron-updater
  const updateConfig = createUpdateConfig(
    store.getState().settings.updates.channel,
    store.getState().settings.updates.autoCheck,
  );
  void initAutoUpdater(updateConfig);

  // Start socket server
  try {
    const actualPort = await socketServer.start(DEFAULT_SOCKET_PORT);
    process.env.CMUX_SOCKET_PORT = String(actualPort);
    process.env.CMUX_BIN_DIR = path.join(__dirname, '../../resources/bin');
    console.warn(`[cmux-win] Socket API listening on port ${actualPort}`);

    // Write token to file so external tools (CLI, debug) can authenticate
    const tokenPath = path.join(app.getPath('userData'), 'socket-token');
    fs.writeFileSync(tokenPath, `${process.env.CMUX_SOCKET_TOKEN}\n${actualPort}`);
  } catch (err) {
    console.error('[cmux-win] Failed to start socket server:', err);
  }

  // PID sweep: every 10s, remove agent sessions whose process has exited
  setInterval(() => {
    const agents = store.getState().agents;
    for (const agent of agents) {
      if (!agent.pid) continue;
      const status = checkPidStatus(agent.pid);
      if (status === 'dead') {
        store.dispatch({
          type: 'agent.session_end',
          payload: { sessionId: agent.sessionId },
        });
      }
      // 'alive' or 'no_permission' (F17) → keep
    }
  }, 10_000);

  // BUG-22: createWindow returns Promise, await it
  const win = await createWindow();
  const windowId = store.getState().windows.at(-1)!.id;

  // Tray initialization — use resources/icon.png if present, otherwise empty fallback
  const iconPath = path.join(__dirname, '../../resources/icon.png');
  const trayIcon = fs.existsSync(iconPath)
    ? nativeImage.createFromPath(iconPath)
    : nativeImage.createEmpty();
  const tray = new Tray(trayIcon);
  tray.setToolTip(formatTrayTitle(0));
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: 'Show', click: () => win.show() },
      { label: 'Quit', click: () => app.quit() },
    ]),
  );
  appTray = tray; // assign to module-level ref for side-effect handler

  // BUG-14: Adopt orphan workspaces AFTER window creation
  store.adoptOrphanWorkspaces(windowId);

  // Handle macOS reactivation
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      void createWindow();
    }
  });

  void win; // acknowledge usage
});

// ---------------------------------------------------------------------------
// Scrollback cleanup on surface close
// ---------------------------------------------------------------------------
store.on('change', (action: { type?: string; payload?: { surfaceId?: string } }) => {
  if (action?.type === 'surface.close' && action?.payload?.surfaceId) {
    scrollbackStore.delete(action.payload.surfaceId);
  }
});

// ---------------------------------------------------------------------------
// Scrollback sync save before quit
// ---------------------------------------------------------------------------
app.on('before-quit', () => {
  try {
    const dir = path.dirname(scrollbackPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(scrollbackPath, JSON.stringify(Object.fromEntries(scrollbackStore)));
  } catch {
    /* ignore */
  }
});

// ---------------------------------------------------------------------------
// 8. window-all-closed: cleanup and quit
// ---------------------------------------------------------------------------
app.on('window-all-closed', () => {
  // Kill all PTY instances
  killAllPty();

  // Flush pending persistence
  persistenceMw.dispose();

  // Close history DB
  historyDb?.close();

  // Stop socket server
  socketServer.stop().catch((err) => {
    console.error('[cmux-win] Error stopping socket server:', err);
  });

  app.quit();
});
