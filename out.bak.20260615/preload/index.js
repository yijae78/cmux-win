"use strict";
const electron = require("electron");
const IPC_CHANNELS = {
  DISPATCH: "cmux:dispatch",
  QUERY_STATE: "cmux:query-state",
  GET_INITIAL_STATE: "cmux:get-initial-state",
  STATE_UPDATE: "cmux:state-update",
  WINDOW_ID: "cmux:window-id",
  PTY_WRITE: "pty:write",
  PTY_SPAWN: "pty:spawn",
  PTY_RESIZE: "pty:resize",
  PTY_KILL: "pty:kill",
  PTY_HAS: "pty:has",
  PTY_DATA: "pty:data",
  PTY_EXIT: "pty:exit",
  PTY_GET_SHELLS: "pty:get-shells",
  SHORTCUT: "cmux:shortcut",
  SCROLLBACK_SAVE: "cmux:scrollback-save",
  SCROLLBACK_LOAD: "cmux:scrollback-load",
  BROWSER_EXECUTE: "cmux:browser-execute",
  BROWSER_EXECUTE_RESULT: "cmux:browser-execute-result",
  FILE_READ: "cmux:file-read",
  FILE_LIST_DIR: "cmux:file-list-dir",
  FILE_WATCH: "cmux:file-watch",
  FILE_UNWATCH: "cmux:file-unwatch",
  FILE_CHANGED: "cmux:file-changed",
  DIALOG_OPEN_FOLDER: "cmux:dialog-open-folder"
};
electron.contextBridge.exposeInMainWorld("cmuxIpc", {
  dispatch(action) {
    return electron.ipcRenderer.invoke(IPC_CHANNELS.DISPATCH, action);
  },
  queryState(query) {
    return electron.ipcRenderer.invoke(IPC_CHANNELS.QUERY_STATE, query);
  },
  getInitialState() {
    return electron.ipcRenderer.invoke(IPC_CHANNELS.GET_INITIAL_STATE);
  },
  onStateUpdate(callback) {
    const handler = (_event, slice, data) => {
      callback(slice, data);
    };
    electron.ipcRenderer.on(IPC_CHANNELS.STATE_UPDATE, handler);
    return () => {
      electron.ipcRenderer.removeListener(IPC_CHANNELS.STATE_UPDATE, handler);
    };
  }
});
electron.contextBridge.exposeInMainWorld("cmuxWindowId", {
  onWindowId(callback) {
    const handler = (_event, id) => {
      callback(id);
    };
    electron.ipcRenderer.on(IPC_CHANNELS.WINDOW_ID, handler);
    return () => {
      electron.ipcRenderer.removeListener(IPC_CHANNELS.WINDOW_ID, handler);
    };
  }
});
electron.contextBridge.exposeInMainWorld("ptyBridge", {
  async spawn(surfaceId, options) {
    return electron.ipcRenderer.invoke(IPC_CHANNELS.PTY_SPAWN, surfaceId, options);
  },
  write(surfaceId, data) {
    electron.ipcRenderer.send(IPC_CHANNELS.PTY_WRITE, surfaceId, data);
  },
  resize(surfaceId, cols, rows) {
    electron.ipcRenderer.send(IPC_CHANNELS.PTY_RESIZE, surfaceId, cols, rows);
  },
  kill(surfaceId) {
    electron.ipcRenderer.send(IPC_CHANNELS.PTY_KILL, surfaceId);
  },
  async has(surfaceId) {
    return electron.ipcRenderer.invoke(IPC_CHANNELS.PTY_HAS, surfaceId);
  },
  onData(surfaceId, callback) {
    const handler = (_e, sid, data) => {
      if (sid === surfaceId) callback(data);
    };
    electron.ipcRenderer.on(IPC_CHANNELS.PTY_DATA, handler);
    return { dispose: () => electron.ipcRenderer.removeListener(IPC_CHANNELS.PTY_DATA, handler) };
  },
  onExit(surfaceId, callback) {
    const handler = (_e, sid, exitInfo) => {
      if (sid === surfaceId) callback(exitInfo);
    };
    electron.ipcRenderer.on(IPC_CHANNELS.PTY_EXIT, handler);
    return { dispose: () => electron.ipcRenderer.removeListener(IPC_CHANNELS.PTY_EXIT, handler) };
  },
  async getAvailableShells() {
    return electron.ipcRenderer.invoke(IPC_CHANNELS.PTY_GET_SHELLS);
  }
});
electron.contextBridge.exposeInMainWorld("cmuxShortcut", {
  onShortcut(callback) {
    const handler = (_e, id) => callback(id);
    electron.ipcRenderer.on(IPC_CHANNELS.SHORTCUT, handler);
    return () => electron.ipcRenderer.removeListener(IPC_CHANNELS.SHORTCUT, handler);
  }
});
electron.contextBridge.exposeInMainWorld("cmuxBrowser", {
  onExecuteRequest(callback) {
    const handler = (_e, requestId, surfaceId, code) => {
      callback(requestId, surfaceId, code);
    };
    electron.ipcRenderer.on(IPC_CHANNELS.BROWSER_EXECUTE, handler);
    return () => {
      electron.ipcRenderer.removeListener(IPC_CHANNELS.BROWSER_EXECUTE, handler);
    };
  },
  sendExecuteResult(requestId, result, error) {
    electron.ipcRenderer.send(IPC_CHANNELS.BROWSER_EXECUTE_RESULT, requestId, result, error);
  }
});
electron.contextBridge.exposeInMainWorld("cmuxScrollback", {
  saveScrollback(surfaceId, content) {
    electron.ipcRenderer.send(IPC_CHANNELS.SCROLLBACK_SAVE, surfaceId, content);
  },
  loadScrollback(surfaceId) {
    return electron.ipcRenderer.invoke(IPC_CHANNELS.SCROLLBACK_LOAD, surfaceId);
  }
});
electron.contextBridge.exposeInMainWorld("cmuxFile", {
  readFile(filePath) {
    return electron.ipcRenderer.invoke(IPC_CHANNELS.FILE_READ, filePath);
  },
  listDirectory(dirPath) {
    return electron.ipcRenderer.invoke(IPC_CHANNELS.FILE_LIST_DIR, dirPath);
  },
  openFolderDialog() {
    return electron.ipcRenderer.invoke(IPC_CHANNELS.DIALOG_OPEN_FOLDER);
  },
  watchFile(filePath, callback) {
    const handler = (_event, changed) => {
      if (changed === filePath) callback(changed);
    };
    electron.ipcRenderer.on(IPC_CHANNELS.FILE_CHANGED, handler);
    electron.ipcRenderer.send(IPC_CHANNELS.FILE_WATCH, filePath);
    return () => {
      electron.ipcRenderer.removeListener(IPC_CHANNELS.FILE_CHANGED, handler);
      electron.ipcRenderer.send(IPC_CHANNELS.FILE_UNWATCH, filePath);
    };
  }
});
electron.contextBridge.exposeInMainWorld("cmuxWin", {
  platform: process.platform,
  minimize: () => electron.ipcRenderer.send("window:minimize"),
  maximize: () => electron.ipcRenderer.send("window:maximize"),
  close: () => electron.ipcRenderer.send("window:close"),
  // L5: Ctrl+Click link support
  openExternal: (url) => electron.ipcRenderer.invoke("cmux:open-external", url),
  openPath: (filePath) => electron.ipcRenderer.invoke("cmux:open-path", filePath)
});
