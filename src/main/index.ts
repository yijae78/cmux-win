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
import { app, BrowserWindow, dialog, ipcMain, Tray, Menu, nativeImage } from 'electron';

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
// C2: Single-instance lock — prevent 409 Conflict on Telegram polling
// and general race conditions with socket/PTY resources.
const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
}

import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import type { AppState } from '../shared/types';
import { DEFAULT_SOCKET_PORT, DEFAULT_SETTINGS, SESSION_SAVE_DEBOUNCE_MS } from '../shared/constants';
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
import { registerWorkflowHandlers } from './socket/handlers/workflow';
import { attachShortcutInterceptor } from './shortcuts/shortcut-interceptor';
import { checkPidStatus } from '../shared/pid-utils';
import { HistoryDb } from './browser/history-db';
import { createTelemetryConfig } from './telemetry/telemetry-manager';
import { createUpdateConfig, initAutoUpdater } from './updates/update-manager';
import { registerPtyHandlers, writeToPty, killAllPty, ptyEvents } from './terminal/pty-manager';
import { showToast } from './notifications/windows-toast';
import { computeUnreadCount, formatTrayTitle } from './notifications/tray-manager';
import { TelegramBotService } from './notifications/telegram-bot';
import { loadBotToken } from './notifications/telegram-token-store';
import { BridgeWatcher } from './bridge-watcher';

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
  // T1: Backfill missing settings sections from DEFAULT_SETTINGS (e.g., telegram)
  const mergedSettings = { ...DEFAULT_SETTINGS, ...migrated.state.settings };
  // BUG-14: Clear transient state — windows, agents, workspaces, panels, surfaces
  // Every app start begins fresh with one workspace created by App.tsx
  initialState = {
    ...migrated.state,
    settings: mergedSettings,
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

// L5: Ctrl+Click link support — open URLs and file paths
ipcMain.handle('cmux:open-external', async (_event, url: string) => {
  const { shell } = await import('electron');
  return shell.openExternal(url);
});
ipcMain.handle('cmux:open-path', async (_event, filePath: string) => {
  const { shell } = await import('electron');
  const cleanPath = filePath.replace(/:\d+$/, ''); // strip :lineNumber
  return shell.openPath(cleanPath);
});

// ---------------------------------------------------------------------------
// 5. Side-effect listener: write directly to PTY in main process
// ---------------------------------------------------------------------------
const windowManager = new WindowManager();

// Module-level tray reference for side-effect handler (assigned in app.whenReady)
let appTray: Tray | null = null;

// Module-level Telegram bot service (initialized in app.whenReady)
const telegramBot = new TelegramBotService(store);

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

    // H1: Forward to Telegram (fire-and-forget with .catch)
    telegramBot
      .sendNotification(title, body, {
        workspaceId: effect.workspaceId as string | undefined,
        surfaceId: effect.surfaceId as string | undefined,
      })
      .catch((err: Error) => console.warn('[telegram] send failed:', err.message));
  }
});

// F7: Track PTY exits → mark agents as done/error
ptyEvents.on('pty-exit', (surfaceId: string, exitInfo: { exitCode: number }) => {
  const state = store.getState();
  const agent = state.agents.find((a) => a.surfaceId === surfaceId);
  if (agent) {
    store.dispatch({
      type: 'agent.status_update',
      payload: {
        sessionId: agent.sessionId,
        status: exitInfo.exitCode === 0 ? 'done' : 'error',
        icon: exitInfo.exitCode === 0 ? '✅' : '❌',
        color: exitInfo.exitCode === 0 ? '#4CAF50' : '#F44336',
      },
    });
  }
  // Also update surface terminal metadata with exit code
  store.dispatch({
    type: 'surface.update_meta',
    payload: { surfaceId, terminal: { exitCode: exitInfo.exitCode } },
  });
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
registerNotificationHandlers(router, store, app.getPath('userData'));
registerSettingsHandlers(router, store);
registerBrowserHandlers(router, store);
registerWorkflowHandlers(router, store);

const socketServer = new SocketApiServer(router, store.getState().settings.socket.mode as any);

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
      // win.webContents.openDevTools({ mode: 'detach' });
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

  // Directory listing IPC handler (for file explorer)
  ipcMain.handle(IPC_CHANNELS.FILE_LIST_DIR, async (_event, dirPath: string) => {
    try {
      if (!path.isAbsolute(dirPath)) {
        return { error: 'Only absolute paths are allowed' };
      }
      const dirents = await fs.promises.readdir(dirPath, { withFileTypes: true });
      const entries = dirents.map((d) => ({
        name: d.name,
        isDirectory: d.isDirectory(),
        path: path.join(dirPath, d.name),
      }));
      // Sort: directories first, then alphabetically
      entries.sort((a, b) => {
        if (a.isDirectory !== b.isDirectory) return a.isDirectory ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      return { entries };
    } catch (err) {
      return { error: err instanceof Error ? err.message : 'Failed to list directory' };
    }
  });

  // Open folder dialog IPC handler (for file explorer)
  ipcMain.handle(IPC_CHANNELS.DIALOG_OPEN_FOLDER, async () => {
    const win = BrowserWindow.getFocusedWindow();
    const result = await dialog.showOpenDialog(win!, { properties: ['openDirectory'] });
    if (result.canceled || result.filePaths.length === 0) {
      return { cancelled: true };
    }
    return { path: result.filePaths[0] };
  });

  // Telegram bot initialization
  const telegramAppDataDir = app.getPath('userData');
  const telegramSettings = store.getState().settings.telegram;
  const telegramToken = loadBotToken(telegramAppDataDir);
  void telegramBot.configure(telegramSettings, telegramToken).catch((err: Error) => {
    console.error('[telegram] Failed to start bot:', err.message);
  });

  // Re-configure Telegram bot when settings change
  store.on('change', (action: { type?: string }) => {
    if (action?.type === 'settings.update') {
      const newSettings = store.getState().settings.telegram;
      const token = loadBotToken(telegramAppDataDir);
      void telegramBot.configure(newSettings, token).catch((err: Error) => {
        console.error('[telegram] Failed to reconfigure bot:', err.message);
      });
    }
  });

  // Cowork Bridge Watcher initialization
  const bridgeWatcher = new BridgeWatcher(store);
  if (store.getState().settings.bridge.enabled) {
    bridgeWatcher.start();
  }

  // Re-configure Bridge when settings change
  store.on('change', (action: { type?: string }) => {
    if (action?.type === 'settings.update') {
      const bridgeSettings = store.getState().settings.bridge;
      bridgeWatcher.stop();
      if (bridgeSettings.enabled) {
        bridgeWatcher.start();
      }
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
    // Copy shim files to ASCII-safe path (Korean OneDrive paths break Windows PATH resolution)
    const srcBinDir = path.join(__dirname, '../../resources/bin');
    const safeBinDir = path.join(os.homedir(), '.cmux-win', 'bin');
    try {
      if (!fs.existsSync(safeBinDir)) fs.mkdirSync(safeBinDir, { recursive: true });
      for (const f of ['tmux.cmd', 'tmux-shim.js', 'claude.cmd', 'claude-wrapper.js', 'claude-wrapper-lib.js', 'cmux.cmd', 'cmux-cli.js']) {
        const src = path.join(srcBinDir, f);
        const dst = path.join(safeBinDir, f);
        if (fs.existsSync(src)) fs.copyFileSync(src, dst);
      }
      // Create bash-compatible tmux shim (Claude Code uses bash, not cmd)
      const bashShimContent = '#!/usr/bin/env node\nconst path = require("path");\nrequire(path.join(__dirname, "tmux-shim.js"));\n';
      const bashShim = path.join(safeBinDir, 'tmux');
      fs.writeFileSync(bashShim, bashShimContent);
      try { fs.chmodSync(bashShim, 0o755); } catch {}

      // Also install shim to ~/bin/ (Claude Code's Bash tool looks here first)
      const userBinDir = path.join(os.homedir(), 'bin');
      try {
        if (!fs.existsSync(userBinDir)) fs.mkdirSync(userBinDir, { recursive: true });
        fs.writeFileSync(path.join(userBinDir, 'tmux'), bashShimContent);
        fs.copyFileSync(path.join(safeBinDir, 'tmux-shim.js'), path.join(userBinDir, 'tmux-shim.js'));
        try { fs.chmodSync(path.join(userBinDir, 'tmux'), 0o755); } catch {}
      } catch {}
    } catch (err) {
      console.error('[cmux-win] Failed to copy shim files:', err);
    }
    process.env.CMUX_BIN_DIR = safeBinDir;
    // Also copy CLI script to safe path and set CMUX_CLI_PATH
    const srcCliPath = path.join(__dirname, '../cli/cmux-win.js');
    const safeCliPath = path.join(os.homedir(), '.cmux-win', 'cli', 'cmux-win.js');
    try {
      const cliDir = path.dirname(safeCliPath);
      if (!fs.existsSync(cliDir)) fs.mkdirSync(cliDir, { recursive: true });
      if (fs.existsSync(srcCliPath)) fs.copyFileSync(srcCliPath, safeCliPath);
    } catch {}
    process.env.CMUX_CLI_PATH = fs.existsSync(safeCliPath) ? safeCliPath : srcCliPath;
    console.warn(`[cmux-win] Socket API listening on port ${actualPort}`);
    console.warn(`[cmux-win] Bin dir: ${safeBinDir}`);

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

  // C2: Focus existing window when second instance is launched
  app.on('second-instance', () => {
    const wins = BrowserWindow.getAllWindows();
    if (wins.length > 0) {
      if (wins[0].isMinimized()) wins[0].restore();
      wins[0].focus();
    }
  });

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
  // C3: Stop Telegram bot polling BEFORE quit to prevent process hang
  telegramBot.stop();
  bridgeWatcher.stop();

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
