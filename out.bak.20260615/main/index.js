"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
const electron = require("electron");
const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");
const node_events = require("node:events");
const immer = require("immer");
const zod = require("zod");
const crypto$1 = require("node:crypto");
const net = require("node:net");
const pty = require("node-pty");
const Database = require("better-sqlite3");
const grammy = require("grammy");
const autoRetry = require("@grammyjs/auto-retry");
const fs$1 = require("fs");
const path$1 = require("path");
const os$1 = require("os");
function _interopNamespaceDefault(e) {
  const n = Object.create(null, { [Symbol.toStringTag]: { value: "Module" } });
  if (e) {
    for (const k in e) {
      if (k !== "default") {
        const d = Object.getOwnPropertyDescriptor(e, k);
        Object.defineProperty(n, k, d.get ? d : {
          enumerable: true,
          get: () => e[k]
        });
      }
    }
  }
  n.default = e;
  return Object.freeze(n);
}
const pty__namespace = /* @__PURE__ */ _interopNamespaceDefault(pty);
const SCHEMA_VERSION = 1;
const DEFAULT_SOCKET_PORT = 19840;
const MAX_SOCKET_PORT_RETRIES = 10;
const SESSION_SAVE_DEBOUNCE_MS = 500;
const STATE_HISTORY_MAX = 100;
const SESSION_BACKUP_SUFFIX = ".bak";
const DEFAULT_SETTINGS = {
  appearance: { theme: "system", language: "system", iconMode: "auto" },
  terminal: {
    defaultShell: "powershell",
    fontSize: 14,
    fontFamily: "Consolas",
    themeName: "Dracula",
    cursorStyle: "block"
  },
  browser: {
    searchEngine: "google",
    searchSuggestions: true,
    httpAllowlist: ["localhost", "127.0.0.1", "::1"],
    externalUrlPatterns: []
  },
  socket: { mode: "automation", port: DEFAULT_SOCKET_PORT },
  agents: {
    claudeHooksEnabled: true,
    codexHooksEnabled: true,
    geminiHooksEnabled: true,
    orchestrationMode: "auto",
    autoStartClaude: true
  },
  telegram: {
    enabled: false,
    chatId: "",
    forwardNotifications: true,
    remoteControl: true
  },
  telemetry: { enabled: true },
  updates: { autoCheck: true, channel: "stable" },
  accessibility: { screenReaderMode: false, reducedMotion: false },
  bridge: {
    enabled: true,
    basePath: "",
    heartbeatIntervalSec: 30,
    pollIntervalSec: 5
  }
};
const IPC_CHANNELS = {
  DISPATCH: "cmux:dispatch",
  QUERY_STATE: "cmux:query-state",
  GET_INITIAL_STATE: "cmux:get-initial-state",
  STATE_UPDATE: "cmux:state-update",
  WINDOW_ID: "cmux:window-id",
  PTY_WRITE: "pty:write",
  PTY_METADATA: "pty:metadata",
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
const GeometrySchema = zod.z.object({
  x: zod.z.number(),
  y: zod.z.number(),
  width: zod.z.number().positive(),
  height: zod.z.number().positive()
});
const WindowStateSchema = zod.z.object({
  id: zod.z.string().min(1),
  workspaceIds: zod.z.array(zod.z.string()),
  geometry: GeometrySchema,
  isActive: zod.z.boolean()
});
const PanelLayoutLeafSchema = zod.z.object({ type: zod.z.literal("leaf"), panelId: zod.z.string() });
const PanelLayoutSplitSchema = zod.z.lazy(
  () => zod.z.object({
    type: zod.z.literal("split"),
    direction: zod.z.enum(["horizontal", "vertical"]),
    ratio: zod.z.number().min(0).max(1),
    children: zod.z.tuple([PanelLayoutTreeSchema, PanelLayoutTreeSchema])
  })
);
const PanelLayoutTreeSchema = zod.z.union([PanelLayoutLeafSchema, PanelLayoutSplitSchema]);
const StatusEntrySchema = zod.z.object({
  key: zod.z.string(),
  label: zod.z.string(),
  icon: zod.z.string().optional(),
  color: zod.z.string().optional()
});
const WorkspaceStateSchema = zod.z.object({
  id: zod.z.string().min(1),
  windowId: zod.z.string().min(1),
  name: zod.z.string(),
  color: zod.z.string().optional(),
  panelLayout: PanelLayoutTreeSchema,
  agentPids: zod.z.record(zod.z.string(), zod.z.number()),
  statusEntries: zod.z.array(StatusEntrySchema),
  unreadCount: zod.z.number().int().min(0),
  isPinned: zod.z.boolean(),
  remoteSession: zod.z.object({
    host: zod.z.string(),
    port: zod.z.number(),
    status: zod.z.enum(["connecting", "connected", "disconnected", "error"])
  }).optional()
});
const PanelTypeEnum = zod.z.enum(["terminal", "browser", "markdown"]);
const PanelStateSchema = zod.z.object({
  id: zod.z.string().min(1),
  workspaceId: zod.z.string().min(1),
  panelType: PanelTypeEnum,
  surfaceIds: zod.z.array(zod.z.string()),
  activeSurfaceId: zod.z.string(),
  isZoomed: zod.z.boolean()
});
const SurfaceStateSchema = zod.z.object({
  id: zod.z.string().min(1),
  panelId: zod.z.string().min(1),
  surfaceType: PanelTypeEnum,
  title: zod.z.string(),
  terminal: zod.z.object({ pid: zod.z.number(), cwd: zod.z.string(), shell: zod.z.string() }).optional(),
  browser: zod.z.object({ url: zod.z.string(), profileId: zod.z.string(), isLoading: zod.z.boolean() }).optional(),
  markdown: zod.z.object({ filePath: zod.z.string() }).optional()
});
const AgentTypeEnum = zod.z.enum(["claude", "codex", "gemini", "opencode"]);
const AgentStatusEnum = zod.z.enum(["running", "idle", "needs_input"]);
const AgentSessionStateSchema = zod.z.object({
  sessionId: zod.z.string().min(1),
  agentType: AgentTypeEnum,
  workspaceId: zod.z.string(),
  surfaceId: zod.z.string(),
  status: AgentStatusEnum,
  statusIcon: zod.z.string(),
  statusColor: zod.z.string(),
  pid: zod.z.number().optional(),
  lastActivity: zod.z.number()
});
const NotificationStateSchema = zod.z.object({
  id: zod.z.string().min(1),
  workspaceId: zod.z.string().optional(),
  surfaceId: zod.z.string().optional(),
  title: zod.z.string(),
  subtitle: zod.z.string().optional(),
  body: zod.z.string().optional(),
  createdAt: zod.z.number(),
  isRead: zod.z.boolean()
});
const SettingsStateSchema = zod.z.object({
  appearance: zod.z.object({
    theme: zod.z.enum(["system", "light", "dark"]),
    language: zod.z.enum(["system", "en", "ko", "ja"]),
    iconMode: zod.z.enum(["auto", "colorful", "monochrome"])
  }),
  terminal: zod.z.object({
    defaultShell: zod.z.enum(["powershell", "cmd", "wsl", "git-bash"]),
    fontSize: zod.z.number().int().min(6).max(72),
    fontFamily: zod.z.string(),
    themeName: zod.z.string(),
    cursorStyle: zod.z.enum(["block", "underline", "bar"])
  }),
  browser: zod.z.object({
    searchEngine: zod.z.enum(["google", "duckduckgo", "bing", "kagi", "startpage"]),
    searchSuggestions: zod.z.boolean(),
    httpAllowlist: zod.z.array(zod.z.string()),
    externalUrlPatterns: zod.z.array(zod.z.string())
  }),
  socket: zod.z.object({
    mode: zod.z.enum(["off", "cmux-only", "automation", "password", "allow-all"]),
    port: zod.z.number().int().min(1024).max(65535)
  }),
  agents: zod.z.object({
    claudeHooksEnabled: zod.z.boolean(),
    codexHooksEnabled: zod.z.boolean(),
    geminiHooksEnabled: zod.z.boolean(),
    orchestrationMode: zod.z.enum(["auto", "claude-teams", "self-managed"])
  }),
  telemetry: zod.z.object({ enabled: zod.z.boolean() }),
  updates: zod.z.object({ autoCheck: zod.z.boolean(), channel: zod.z.enum(["stable", "nightly"]) }),
  accessibility: zod.z.object({ screenReaderMode: zod.z.boolean(), reducedMotion: zod.z.boolean() }),
  bridge: zod.z.object({
    enabled: zod.z.boolean(),
    basePath: zod.z.string(),
    heartbeatIntervalSec: zod.z.number().int().min(5),
    pollIntervalSec: zod.z.number().int().min(1)
  })
});
const FocusStateSchema = zod.z.object({
  activeWindowId: zod.z.string().nullable(),
  activeWorkspaceId: zod.z.string().nullable(),
  activePanelId: zod.z.string().nullable(),
  activeSurfaceId: zod.z.string().nullable(),
  focusTarget: zod.z.enum(["terminal", "browser_webview", "browser_omnibar", "browser_find", "terminal_find"]).nullable()
});
const AppStateSchema = zod.z.object({
  windows: zod.z.array(WindowStateSchema),
  workspaces: zod.z.array(WorkspaceStateSchema),
  panels: zod.z.array(PanelStateSchema),
  surfaces: zod.z.array(SurfaceStateSchema),
  agents: zod.z.array(AgentSessionStateSchema),
  notifications: zod.z.array(NotificationStateSchema),
  settings: SettingsStateSchema,
  shortcuts: zod.z.object({ shortcuts: zod.z.record(zod.z.string(), zod.z.string()) }),
  focus: FocusStateSchema
});
zod.z.object({
  version: zod.z.number().int().positive(),
  state: AppStateSchema
});
const WindowCreateAction = zod.z.object({
  type: zod.z.literal("window.create"),
  payload: zod.z.object({ geometry: GeometrySchema.optional() })
});
const WindowCloseAction = zod.z.object({
  type: zod.z.literal("window.close"),
  payload: zod.z.object({ windowId: zod.z.string() })
});
const WorkspaceCreateAction = zod.z.object({
  type: zod.z.literal("workspace.create"),
  payload: zod.z.object({
    windowId: zod.z.string(),
    name: zod.z.string().optional(),
    cwd: zod.z.string().optional()
  })
});
const WorkspaceCloseAction = zod.z.object({
  type: zod.z.literal("workspace.close"),
  payload: zod.z.object({ workspaceId: zod.z.string() })
});
const WorkspaceSelectAction = zod.z.object({
  type: zod.z.literal("workspace.select"),
  payload: zod.z.object({ workspaceId: zod.z.string() })
});
const WorkspaceRenameAction = zod.z.object({
  type: zod.z.literal("workspace.rename"),
  payload: zod.z.object({ workspaceId: zod.z.string(), name: zod.z.string() })
});
const PanelSplitAction = zod.z.object({
  type: zod.z.literal("panel.split"),
  payload: zod.z.object({
    panelId: zod.z.string(),
    direction: zod.z.enum(["horizontal", "vertical"]),
    newPanelType: PanelTypeEnum,
    url: zod.z.string().optional(),
    filePath: zod.z.string().optional()
  })
});
const PanelCloseAction = zod.z.object({
  type: zod.z.literal("panel.close"),
  payload: zod.z.object({ panelId: zod.z.string() })
});
const PanelFocusAction = zod.z.object({
  type: zod.z.literal("panel.focus"),
  payload: zod.z.object({ panelId: zod.z.string() })
});
const PanelResizeAction = zod.z.object({
  type: zod.z.literal("panel.resize"),
  payload: zod.z.object({ panelId: zod.z.string(), ratio: zod.z.number().min(0).max(1) })
});
const SurfaceCreateAction = zod.z.object({
  type: zod.z.literal("surface.create"),
  payload: zod.z.object({ panelId: zod.z.string(), surfaceType: PanelTypeEnum })
});
const SurfaceCloseAction = zod.z.object({
  type: zod.z.literal("surface.close"),
  payload: zod.z.object({ surfaceId: zod.z.string() })
});
const SurfaceFocusAction = zod.z.object({
  type: zod.z.literal("surface.focus"),
  payload: zod.z.object({ surfaceId: zod.z.string() })
});
const SurfaceSendTextAction = zod.z.object({
  type: zod.z.literal("surface.send_text"),
  payload: zod.z.object({ surfaceId: zod.z.string(), text: zod.z.string() })
});
const SurfaceUpdateMetaAction = zod.z.object({
  type: zod.z.literal("surface.update_meta"),
  payload: zod.z.object({
    surfaceId: zod.z.string(),
    title: zod.z.string().optional(),
    pendingCommand: zod.z.string().nullable().optional(),
    terminal: zod.z.object({
      cwd: zod.z.string().optional(),
      gitBranch: zod.z.string().optional(),
      gitDirty: zod.z.boolean().optional(),
      exitCode: zod.z.number().optional()
    }).optional(),
    browser: zod.z.object({
      url: zod.z.string().optional(),
      isLoading: zod.z.boolean().optional()
    }).optional()
  })
});
const AgentSpawnAction = zod.z.object({
  type: zod.z.literal("agent.spawn"),
  payload: zod.z.object({
    agentType: zod.z.enum(["claude", "codex", "gemini", "opencode"]),
    workspaceId: zod.z.string(),
    task: zod.z.string().optional(),
    cwd: zod.z.string().optional()
  })
});
const AgentSessionStartAction = zod.z.object({
  type: zod.z.literal("agent.session_start"),
  payload: zod.z.object({
    sessionId: zod.z.string(),
    agentType: zod.z.enum(["claude", "codex", "gemini", "opencode"]),
    workspaceId: zod.z.string(),
    surfaceId: zod.z.string(),
    pid: zod.z.number().optional()
  })
});
const AgentStatusUpdateAction = zod.z.object({
  type: zod.z.literal("agent.status_update"),
  payload: zod.z.object({
    sessionId: zod.z.string(),
    status: zod.z.enum(["running", "idle", "needs_input", "done", "error"]),
    icon: zod.z.string().optional(),
    color: zod.z.string().optional()
  })
});
const AgentSessionEndAction = zod.z.object({
  type: zod.z.literal("agent.session_end"),
  payload: zod.z.object({ sessionId: zod.z.string() })
});
const NotificationCreateAction = zod.z.object({
  type: zod.z.literal("notification.create"),
  payload: zod.z.object({
    title: zod.z.string(),
    subtitle: zod.z.string().optional(),
    body: zod.z.string().optional(),
    workspaceId: zod.z.string().optional(),
    surfaceId: zod.z.string().optional()
  })
});
const NotificationClearAction = zod.z.object({
  type: zod.z.literal("notification.clear"),
  payload: zod.z.object({ workspaceId: zod.z.string().optional() })
});
const PanelZoomAction = zod.z.object({
  type: zod.z.literal("panel.zoom"),
  payload: zod.z.object({ panelId: zod.z.string() })
});
const PanelSwapAction = zod.z.object({
  type: zod.z.literal("panel.swap"),
  payload: zod.z.object({ panelId1: zod.z.string(), panelId2: zod.z.string() })
});
const PanelMoveAction = zod.z.object({
  type: zod.z.literal("panel.move"),
  payload: zod.z.object({
    sourcePanelId: zod.z.string(),
    targetPanelId: zod.z.string(),
    direction: zod.z.enum(["left", "right", "top", "bottom"])
  })
});
const SurfaceReorderAction = zod.z.object({
  type: zod.z.literal("surface.reorder"),
  payload: zod.z.object({
    surfaceId: zod.z.string(),
    panelId: zod.z.string(),
    newIndex: zod.z.number().int().min(0)
  })
});
const WorkspaceReorderAction = zod.z.object({
  type: zod.z.literal("workspace.reorder"),
  payload: zod.z.object({
    workspaceId: zod.z.string(),
    windowId: zod.z.string(),
    newIndex: zod.z.number().int().min(0)
  })
});
const WorkspaceSetLayoutAction = zod.z.object({
  type: zod.z.literal("workspace.set_layout"),
  payload: zod.z.object({
    workspaceId: zod.z.string(),
    panelLayout: PanelLayoutTreeSchema
  })
});
const FocusUpdateAction = zod.z.object({
  type: zod.z.literal("focus.update"),
  payload: zod.z.object({
    activeWindowId: zod.z.string().nullable().optional(),
    activeWorkspaceId: zod.z.string().nullable().optional(),
    activePanelId: zod.z.string().nullable().optional(),
    activeSurfaceId: zod.z.string().nullable().optional(),
    focusTarget: zod.z.enum(["terminal", "browser_webview", "browser_omnibar", "browser_find", "terminal_find"]).nullable().optional()
  })
});
const SettingsUpdateAction = zod.z.object({
  type: zod.z.literal("settings.update"),
  payload: zod.z.record(zod.z.string(), zod.z.unknown())
});
const ActionSchema = zod.z.discriminatedUnion("type", [
  WindowCreateAction,
  WindowCloseAction,
  WorkspaceCreateAction,
  WorkspaceCloseAction,
  WorkspaceSelectAction,
  WorkspaceRenameAction,
  WorkspaceReorderAction,
  WorkspaceSetLayoutAction,
  PanelSplitAction,
  PanelCloseAction,
  PanelFocusAction,
  PanelResizeAction,
  PanelZoomAction,
  PanelSwapAction,
  PanelMoveAction,
  SurfaceCreateAction,
  SurfaceCloseAction,
  SurfaceFocusAction,
  SurfaceSendTextAction,
  SurfaceReorderAction,
  SurfaceUpdateMetaAction,
  AgentSpawnAction,
  AgentSessionStartAction,
  AgentStatusUpdateAction,
  AgentSessionEndAction,
  NotificationCreateAction,
  NotificationClearAction,
  FocusUpdateAction,
  SettingsUpdateAction
]);
function createDefaultState() {
  return {
    windows: [],
    workspaces: [],
    panels: [],
    surfaces: [],
    agents: [],
    notifications: [],
    settings: structuredClone(DEFAULT_SETTINGS),
    shortcuts: { shortcuts: {} },
    focus: {
      activeWindowId: null,
      activeWorkspaceId: null,
      activePanelId: null,
      activeSurfaceId: null,
      focusTarget: null
    }
  };
}
function findLeaf(tree, panelId) {
  if (tree.type === "leaf") {
    return tree.panelId === panelId ? tree : null;
  }
  return findLeaf(tree.children[0], panelId) ?? findLeaf(tree.children[1], panelId);
}
function replaceLeaf(tree, panelId, replacement) {
  if (tree.type === "leaf") {
    return tree.panelId === panelId ? replacement : tree;
  }
  return {
    ...tree,
    children: [
      replaceLeaf(tree.children[0], panelId, replacement),
      replaceLeaf(tree.children[1], panelId, replacement)
    ]
  };
}
function updateRatioForPanel(tree, panelId, newRatio) {
  if (tree.type === "leaf") return tree;
  const clamped = Math.max(0.1, Math.min(0.9, newRatio));
  const isDirectChild = tree.children.some((c) => c.type === "leaf" && c.panelId === panelId);
  if (isDirectChild) {
    return { ...tree, ratio: clamped };
  }
  return {
    ...tree,
    children: [
      updateRatioForPanel(tree.children[0], panelId, newRatio),
      updateRatioForPanel(tree.children[1], panelId, newRatio)
    ]
  };
}
function collectLeafIds(tree) {
  if (tree.type === "leaf") return [tree.panelId];
  return [...collectLeafIds(tree.children[0]), ...collectLeafIds(tree.children[1])];
}
function rebuildEqualLayout(panelIds, direction) {
  if (panelIds.length === 0) return { type: "leaf", panelId: "" };
  if (panelIds.length === 1) return { type: "leaf", panelId: panelIds[0] };
  if (panelIds.length === 2) {
    return {
      type: "split",
      direction,
      ratio: 0.5,
      children: [
        { type: "leaf", panelId: panelIds[0] },
        { type: "leaf", panelId: panelIds[1] }
      ]
    };
  }
  const mid = Math.ceil(panelIds.length / 2);
  const left = panelIds.slice(0, mid);
  const right = panelIds.slice(mid);
  return {
    type: "split",
    direction,
    ratio: left.length / panelIds.length,
    children: [
      rebuildEqualLayout(left, direction),
      rebuildEqualLayout(right, direction)
    ]
  };
}
function removeLeaf(tree, panelId) {
  if (tree.type === "leaf") {
    return tree.panelId === panelId ? null : tree;
  }
  const [left, right] = tree.children;
  if (left.type === "leaf" && left.panelId === panelId) return right;
  if (right.type === "leaf" && right.panelId === panelId) return left;
  const newLeft = removeLeaf(left, panelId);
  if (newLeft !== left) return { ...tree, children: [newLeft ?? right, right] };
  const newRight = removeLeaf(right, panelId);
  if (newRight !== right) return { ...tree, children: [left, newRight ?? left] };
  return tree;
}
class AppStateStore extends node_events.EventEmitter {
  constructor(initialState2) {
    super();
    this.history = [];
    this.middlewares = [];
    this.state = initialState2 ?? createDefaultState();
  }
  getState() {
    return this.state;
  }
  getHistory() {
    return this.history;
  }
  use(mw) {
    this.middlewares.push(mw);
  }
  // BUG-14: 세션 복원 시 고아 워크스페이스를 새 윈도우에 입양
  adoptOrphanWorkspaces(windowId) {
    this.state = immer.produce(this.state, (draft) => {
      const win = draft.windows.find((w) => w.id === windowId);
      if (!win) return;
      for (const ws of draft.workspaces) {
        if (!ws.windowId || !draft.windows.some((w) => w.id === ws.windowId)) {
          ws.windowId = windowId;
          if (!win.workspaceIds.includes(ws.id)) {
            win.workspaceIds.push(ws.id);
          }
        }
      }
    });
    this.emit("change", { type: "session.restore" });
  }
  dispatch(rawAction) {
    const parsed = ActionSchema.safeParse(rawAction);
    if (!parsed.success) return { ok: false, error: parsed.error.message };
    const action = parsed.data;
    for (const mw of this.middlewares) {
      if (mw.beforeMutation) {
        const result = mw.beforeMutation(action, this.state);
        if (result.abort) return { ok: false, error: result.reason ?? "Aborted by middleware" };
      }
    }
    const prevState = this.state;
    try {
      if (action.type === "surface.send_text") {
        this.emit("side-effect", {
          type: "pty-write",
          surfaceId: action.payload.surfaceId,
          text: action.payload.text
        });
        for (const mw of this.middlewares) {
          try {
            mw.afterMutation?.(action, prevState, prevState);
          } catch (err) {
            console.error("[Middleware] afterMutation error:", err);
          }
        }
        for (const mw of this.middlewares) {
          try {
            mw.post?.(action, prevState, prevState);
          } catch (err) {
            console.error("[Middleware] post error:", err);
          }
        }
        return { ok: true };
      }
      this.state = immer.produce(this.state, (draft) => {
        this.applyAction(draft, action);
      });
      this.history.push({ action, timestamp: Date.now() });
      if (this.history.length > STATE_HISTORY_MAX) this.history.shift();
      for (const mw of this.middlewares) {
        try {
          mw.afterMutation?.(action, prevState, this.state);
        } catch (err) {
          console.error("[Middleware] afterMutation error:", err);
        }
      }
      for (const mw of this.middlewares) {
        try {
          mw.post?.(action, prevState, this.state);
        } catch (err) {
          console.error("[Middleware] post error:", err);
        }
      }
      this.emit("change", action);
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : String(err) };
    }
  }
  // GAP-4: monotonically increasing pane index — survives panel close/reorder
  nextPaneIndex(draft) {
    let max = -1;
    for (const p of draft.panels) {
      if (p.paneIndex !== void 0 && p.paneIndex > max) max = p.paneIndex;
    }
    return max + 1;
  }
  applyAction(draft, action) {
    switch (action.type) {
      // BUG-2: window.create / window.close
      case "window.create": {
        const id = crypto$1.randomUUID();
        const geo = action.payload.geometry ?? { x: 100, y: 100, width: 1200, height: 800 };
        draft.windows.push({ id, workspaceIds: [], geometry: geo, isActive: true });
        draft.focus.activeWindowId = id;
        break;
      }
      case "window.close": {
        const idx = draft.windows.findIndex((w) => w.id === action.payload.windowId);
        if (idx === -1) break;
        const win = draft.windows[idx];
        for (const wsId of win.workspaceIds) {
          draft.panels = draft.panels.filter((p) => p.workspaceId !== wsId);
          draft.surfaces = draft.surfaces.filter(
            (s) => draft.panels.some((p) => p.id === s.panelId)
          );
        }
        draft.workspaces = draft.workspaces.filter((ws) => !win.workspaceIds.includes(ws.id));
        draft.windows.splice(idx, 1);
        if (draft.focus.activeWindowId === action.payload.windowId) {
          draft.focus.activeWindowId = draft.windows[0]?.id ?? null;
        }
        break;
      }
      case "workspace.create": {
        const id = crypto$1.randomUUID();
        const panelId = crypto$1.randomUUID();
        const surfaceId = crypto$1.randomUUID();
        draft.workspaces.push({
          id,
          windowId: action.payload.windowId,
          name: action.payload.name ?? "New Workspace",
          panelLayout: { type: "leaf", panelId },
          agentPids: {},
          statusEntries: [],
          unreadCount: 0,
          isPinned: false
        });
        draft.panels.push({
          id: panelId,
          workspaceId: id,
          panelType: "terminal",
          surfaceIds: [surfaceId],
          activeSurfaceId: surfaceId,
          isZoomed: false,
          paneIndex: this.nextPaneIndex(draft)
        });
        const isFirstWorkspace = draft.workspaces.length === 1;
        const claudeCmd = isFirstWorkspace ? "claude\r" : void 0;
        draft.surfaces.push({
          id: surfaceId,
          panelId,
          surfaceType: "terminal",
          title: claudeCmd ? "🧠 Claude" : "Terminal",
          pendingCommand: claudeCmd
        });
        const win = draft.windows.find((w) => w.id === action.payload.windowId);
        if (win) win.workspaceIds.push(id);
        draft.focus.activeWorkspaceId = id;
        draft.focus.activeWindowId = action.payload.windowId;
        draft.focus.activePanelId = panelId;
        draft.focus.activeSurfaceId = surfaceId;
        break;
      }
      case "workspace.close": {
        const wsIdx = draft.workspaces.findIndex((w) => w.id === action.payload.workspaceId);
        if (wsIdx === -1) break;
        draft.panels = draft.panels.filter((p) => p.workspaceId !== action.payload.workspaceId);
        draft.surfaces = draft.surfaces.filter((s) => draft.panels.some((p) => p.id === s.panelId));
        draft.workspaces.splice(wsIdx, 1);
        for (const win of draft.windows) {
          win.workspaceIds = win.workspaceIds.filter((id) => id !== action.payload.workspaceId);
        }
        if (draft.focus.activeWorkspaceId === action.payload.workspaceId) {
          draft.focus.activeWorkspaceId = draft.workspaces[0]?.id ?? null;
        }
        break;
      }
      case "workspace.select": {
        draft.focus.activeWorkspaceId = action.payload.workspaceId;
        const ws = draft.workspaces.find((w) => w.id === action.payload.workspaceId);
        if (ws) {
          draft.focus.activeWindowId = ws.windowId;
          const firstPanel = draft.panels.find((p) => p.workspaceId === ws.id);
          if (firstPanel) {
            draft.focus.activePanelId = firstPanel.id;
            draft.focus.activeSurfaceId = firstPanel.activeSurfaceId || firstPanel.surfaceIds[0] || null;
          }
        }
        break;
      }
      case "workspace.rename": {
        const ws = draft.workspaces.find((w) => w.id === action.payload.workspaceId);
        if (ws) ws.name = action.payload.name;
        break;
      }
      case "panel.focus": {
        draft.focus.activePanelId = action.payload.panelId;
        break;
      }
      case "panel.close": {
        const panelId = action.payload.panelId;
        const idx = draft.panels.findIndex((p) => p.id === panelId);
        if (idx === -1) break;
        draft.surfaces = draft.surfaces.filter((s) => s.panelId !== panelId);
        draft.panels.splice(idx, 1);
        const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panelId) !== null);
        if (ws) {
          const newLayout = removeLeaf(ws.panelLayout, panelId);
          if (newLayout) ws.panelLayout = newLayout;
        }
        break;
      }
      case "panel.split": {
        const { panelId, direction, newPanelType, url } = action.payload;
        const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panelId) !== null);
        if (!ws) break;
        const newPanelId = crypto$1.randomUUID();
        const newSurfaceId = crypto$1.randomUUID();
        draft.panels.push({
          id: newPanelId,
          workspaceId: ws.id,
          panelType: newPanelType,
          surfaceIds: [newSurfaceId],
          activeSurfaceId: newSurfaceId,
          isZoomed: false,
          paneIndex: this.nextPaneIndex(draft)
        });
        const surface = {
          id: newSurfaceId,
          panelId: newPanelId,
          surfaceType: newPanelType,
          title: newPanelType === "terminal" ? "Terminal" : "New Tab"
        };
        if (newPanelType === "browser" && url) {
          surface.browser = { url, profileId: "default", isLoading: false };
          surface.title = new URL(url).hostname;
        }
        if (newPanelType === "markdown" && action.payload.filePath) {
          surface.markdown = { filePath: action.payload.filePath };
          surface.title = action.payload.filePath.split(/[\\/]/).pop() || "Markdown";
        }
        draft.surfaces.push(surface);
        const allLeafIds = collectLeafIds(ws.panelLayout);
        allLeafIds.push(newPanelId);
        ws.panelLayout = rebuildEqualLayout(allLeafIds, direction);
        break;
      }
      case "panel.resize": {
        const { panelId, ratio } = action.payload;
        const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panelId) !== null);
        if (!ws) break;
        ws.panelLayout = updateRatioForPanel(ws.panelLayout, panelId, ratio);
        break;
      }
      case "panel.zoom": {
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (panel) panel.isZoomed = !panel.isZoomed;
        break;
      }
      case "panel.swap": {
        let swapInTree = function(node) {
          if (node.type === "leaf") {
            if (node.panelId === panelId1) node.panelId = panelId2;
            else if (node.panelId === panelId2) node.panelId = panelId1;
          } else if (node.children) {
            node.children.forEach(swapInTree);
          }
        };
        const { panelId1, panelId2 } = action.payload;
        if (panelId1 === panelId2) break;
        for (const ws of draft.workspaces) swapInTree(ws.panelLayout);
        break;
      }
      case "panel.move": {
        const { sourcePanelId, targetPanelId, direction } = action.payload;
        if (sourcePanelId === targetPanelId) break;
        const ws = draft.workspaces.find(
          (w) => findLeaf(w.panelLayout, sourcePanelId) !== null && findLeaf(w.panelLayout, targetPanelId) !== null
        );
        if (!ws) break;
        const layoutAfterRemove = removeLeaf(ws.panelLayout, sourcePanelId);
        if (!layoutAfterRemove) break;
        const splitDirection = direction === "left" || direction === "right" ? "horizontal" : "vertical";
        const sourceFirst = direction === "left" || direction === "top";
        const newSplit = {
          type: "split",
          direction: splitDirection,
          ratio: 0.5,
          children: sourceFirst ? [
            { type: "leaf", panelId: sourcePanelId },
            { type: "leaf", panelId: targetPanelId }
          ] : [
            { type: "leaf", panelId: targetPanelId },
            { type: "leaf", panelId: sourcePanelId }
          ]
        };
        ws.panelLayout = replaceLeaf(layoutAfterRemove, targetPanelId, newSplit);
        break;
      }
      case "surface.create": {
        const newId = crypto$1.randomUUID();
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (!panel) break;
        draft.surfaces.push({
          id: newId,
          panelId: action.payload.panelId,
          surfaceType: action.payload.surfaceType,
          title: action.payload.surfaceType === "terminal" ? "Terminal" : "New Tab"
        });
        panel.surfaceIds.push(newId);
        panel.activeSurfaceId = newId;
        break;
      }
      case "surface.close": {
        const si = draft.surfaces.findIndex((s) => s.id === action.payload.surfaceId);
        if (si === -1) break;
        const surf = draft.surfaces[si];
        const panel = draft.panels.find((p) => p.id === surf.panelId);
        if (panel) {
          panel.surfaceIds = panel.surfaceIds.filter((id) => id !== action.payload.surfaceId);
          if (panel.activeSurfaceId === action.payload.surfaceId)
            panel.activeSurfaceId = panel.surfaceIds[0] ?? "";
          if (panel.surfaceIds.length === 0) {
            const pIdx = draft.panels.findIndex((p2) => p2.id === panel.id);
            if (pIdx !== -1) draft.panels.splice(pIdx, 1);
            const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panel.id) !== null);
            if (ws) {
              const newLayout = removeLeaf(ws.panelLayout, panel.id);
              if (newLayout) ws.panelLayout = newLayout;
            }
          }
        }
        draft.surfaces.splice(si, 1);
        draft.agents = draft.agents.filter(
          (a) => draft.surfaces.some((sf) => sf.id === a.surfaceId)
        );
        break;
      }
      case "surface.focus": {
        draft.focus.activeSurfaceId = action.payload.surfaceId;
        const s = draft.surfaces.find((sf) => sf.id === action.payload.surfaceId);
        if (s) {
          draft.focus.activePanelId = s.panelId;
          const p = draft.panels.find((pp) => pp.id === s.panelId);
          if (p) p.activeSurfaceId = action.payload.surfaceId;
        }
        break;
      }
      case "surface.reorder": {
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (!panel) break;
        const oldIndex = panel.surfaceIds.indexOf(action.payload.surfaceId);
        if (oldIndex === -1) break;
        panel.surfaceIds.splice(oldIndex, 1);
        panel.surfaceIds.splice(action.payload.newIndex, 0, action.payload.surfaceId);
        break;
      }
      case "workspace.reorder": {
        const win = draft.windows.find((w) => w.id === action.payload.windowId);
        if (!win) break;
        const oldIdx = win.workspaceIds.indexOf(action.payload.workspaceId);
        if (oldIdx === -1) break;
        win.workspaceIds.splice(oldIdx, 1);
        win.workspaceIds.splice(action.payload.newIndex, 0, action.payload.workspaceId);
        break;
      }
      case "workspace.set_layout": {
        const ws = draft.workspaces.find((w) => w.id === action.payload.workspaceId);
        if (ws && action.payload.panelLayout) {
          ws.panelLayout = action.payload.panelLayout;
        }
        break;
      }
      case "surface.send_text":
        break;
      // side-effect only, handled above dispatch
      case "agent.spawn": {
        const { agentType, workspaceId, task, cwd } = action.payload;
        const ws = draft.workspaces.find((w) => w.id === workspaceId);
        if (!ws) break;
        const agentIcons = {
          claude: "🧠",
          gemini: "💎",
          codex: "🤖",
          opencode: "🔧"
        };
        const agentIcon = agentIcons[agentType] || "⚡";
        const agentDisplayName = agentType.charAt(0).toUpperCase() + agentType.slice(1);
        const newPanelId = crypto$1.randomUUID();
        const newSurfaceId = crypto$1.randomUUID();
        const spawnedPaneIndex = this.nextPaneIndex(draft);
        draft.panels.push({
          id: newPanelId,
          workspaceId,
          panelType: "terminal",
          surfaceIds: [newSurfaceId],
          activeSurfaceId: newSurfaceId,
          isZoomed: false,
          paneIndex: spawnedPaneIndex
        });
        const teamName = workspaceId;
        const agentName = `${agentType}-${spawnedPaneIndex}`;
        const teamArgs = `--team-name "${teamName}" --agent-name "${agentName}"`;
        const safeTask = task ? task.replace(/[\r\n]+/g, " ").replace(/"/g, '\\"').trim() : "";
        let agentCmd;
        if (agentType === "gemini") {
          agentCmd = safeTask ? `gemini -i "${safeTask}" -y\r` : `gemini -y\r`;
        } else if (agentType === "codex") {
          agentCmd = safeTask ? `codex --full-auto --no-alt-screen "${safeTask}"\r` : `codex --full-auto --no-alt-screen\r`;
        } else {
          agentCmd = safeTask ? `${agentType} ${teamArgs} "${safeTask}"\r` : `${agentType} ${teamArgs}\r`;
        }
        const cmd = cwd ? `cd "${cwd.replace(/\\/g, "/")}"\r__DELAY__${agentCmd}` : agentCmd;
        draft.surfaces.push({
          id: newSurfaceId,
          panelId: newPanelId,
          surfaceType: "terminal",
          title: cwd ? `${agentIcon} ${agentDisplayName} · ${cwd.split(/[\\/]/).pop()}` : `${agentIcon} ${agentDisplayName}`,
          pendingCommand: cmd
        });
        const spawnLeafIds = collectLeafIds(ws.panelLayout);
        spawnLeafIds.push(newPanelId);
        ws.panelLayout = rebuildEqualLayout(spawnLeafIds, "horizontal");
        draft.agents.push({
          sessionId: crypto$1.randomUUID(),
          agentType,
          workspaceId,
          surfaceId: newSurfaceId,
          status: "running",
          statusIcon: "⚡",
          statusColor: "#4C8DFF",
          lastActivity: Date.now()
        });
        break;
      }
      case "agent.session_start": {
        draft.agents.push({
          sessionId: action.payload.sessionId,
          agentType: action.payload.agentType,
          workspaceId: action.payload.workspaceId,
          surfaceId: action.payload.surfaceId,
          status: "running",
          statusIcon: "⚡",
          statusColor: "blue",
          pid: action.payload.pid,
          lastActivity: Date.now()
        });
        break;
      }
      case "agent.status_update": {
        const agent = draft.agents.find((a) => a.sessionId === action.payload.sessionId);
        if (agent) {
          agent.status = action.payload.status;
          if (action.payload.icon) agent.statusIcon = action.payload.icon;
          if (action.payload.color) agent.statusColor = action.payload.color;
          agent.lastActivity = Date.now();
        }
        break;
      }
      case "agent.session_end": {
        draft.agents = draft.agents.filter((a) => a.sessionId !== action.payload.sessionId);
        break;
      }
      case "notification.create": {
        draft.notifications.push({
          id: crypto$1.randomUUID(),
          title: action.payload.title,
          subtitle: action.payload.subtitle,
          body: action.payload.body,
          workspaceId: action.payload.workspaceId,
          surfaceId: action.payload.surfaceId,
          createdAt: Date.now(),
          isRead: false
        });
        break;
      }
      case "notification.clear": {
        if (action.payload.workspaceId) {
          draft.notifications = draft.notifications.filter(
            (n) => n.workspaceId !== action.payload.workspaceId
          );
        } else {
          draft.notifications = [];
        }
        break;
      }
      case "focus.update": {
        const p = action.payload;
        if (p.activeWindowId !== void 0) draft.focus.activeWindowId = p.activeWindowId;
        if (p.activeWorkspaceId !== void 0) draft.focus.activeWorkspaceId = p.activeWorkspaceId;
        if (p.activePanelId !== void 0) draft.focus.activePanelId = p.activePanelId;
        if (p.activeSurfaceId !== void 0) draft.focus.activeSurfaceId = p.activeSurfaceId;
        if (p.focusTarget !== void 0) draft.focus.focusTarget = p.focusTarget;
        break;
      }
      case "surface.update_meta": {
        const surface = draft.surfaces.find((s) => s.id === action.payload.surfaceId);
        if (!surface) break;
        if (action.payload.title !== void 0) surface.title = action.payload.title;
        if (action.payload.pendingCommand !== void 0) {
          surface.pendingCommand = action.payload.pendingCommand ?? void 0;
        }
        if (action.payload.terminal) {
          const t = action.payload.terminal;
          if (!surface.terminal) surface.terminal = { pid: 0, cwd: "", shell: "" };
          if (t.cwd !== void 0) surface.terminal.cwd = t.cwd;
          if (t.gitBranch !== void 0) surface.terminal.gitBranch = t.gitBranch;
          if (t.gitDirty !== void 0) surface.terminal.gitDirty = t.gitDirty;
          if (t.exitCode !== void 0) surface.terminal.exitCode = t.exitCode;
        }
        if (action.payload.browser) {
          if (!surface.browser)
            surface.browser = { url: "", profileId: "default", isLoading: false };
          const b = action.payload.browser;
          if (b.url !== void 0) surface.browser.url = b.url;
          if (b.isLoading !== void 0) surface.browser.isLoading = b.isLoading;
        }
        break;
      }
      case "settings.update": {
        Object.assign(draft.settings, action.payload);
        break;
      }
    }
  }
}
const migrations = [
  // Example: { fromVersion: 1, toVersion: 2, migrate: (state) => { ... return state; } }
];
function migrateState(persisted2, filePath) {
  let { version, state } = persisted2;
  if (version === SCHEMA_VERSION) {
    return persisted2;
  }
  if (filePath && fs.existsSync(filePath)) {
    const backupPath = filePath + SESSION_BACKUP_SUFFIX;
    try {
      fs.copyFileSync(filePath, backupPath);
    } catch (err) {
      console.error("[migrateState] Failed to create backup:", err);
    }
  }
  while (version < SCHEMA_VERSION) {
    const migration = migrations.find((m) => m.fromVersion === version);
    if (!migration) {
      console.warn(
        `[migrateState] No migration found from version ${version} to ${version + 1}`
      );
      break;
    }
    state = migration.migrate(state);
    version = migration.toVersion;
  }
  return { version, state };
}
function loadPersistedState(filePath) {
  const mainResult = tryLoadFile(filePath);
  if (mainResult) return mainResult;
  const backupPath = filePath + SESSION_BACKUP_SUFFIX;
  const backupResult = tryLoadFile(backupPath);
  if (backupResult) return backupResult;
  return null;
}
function tryLoadFile(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    const raw = fs.readFileSync(filePath, "utf-8");
    const parsed = JSON.parse(raw);
    if (typeof parsed === "object" && parsed !== null && "version" in parsed && "state" in parsed && typeof parsed.version === "number") {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}
class ValidationMiddleware {
  beforeMutation(action, state) {
    switch (action.type) {
      case "workspace.close": {
        const exists = state.workspaces.some(
          (ws) => ws.id === action.payload.workspaceId
        );
        if (!exists) {
          return {
            abort: true,
            reason: `Workspace not found: ${action.payload.workspaceId}`
          };
        }
        break;
      }
      case "window.close": {
        const exists = state.windows.some(
          (w) => w.id === action.payload.windowId
        );
        if (!exists) {
          return {
            abort: true,
            reason: `Window not found: ${action.payload.windowId}`
          };
        }
        break;
      }
      case "surface.close": {
        const exists = state.surfaces.some(
          (s) => s.id === action.payload.surfaceId
        );
        if (!exists) {
          return {
            abort: true,
            reason: `Surface not found: ${action.payload.surfaceId}`
          };
        }
        break;
      }
    }
    return {};
  }
}
class SideEffectsMiddleware {
  constructor(callback) {
    this.callback = callback;
  }
  afterMutation(action, _prevState, nextState) {
    switch (action.type) {
      case "workspace.create": {
        const workspaces = nextState.workspaces.filter(
          (ws) => ws.windowId === action.payload.windowId
        );
        const created = workspaces[workspaces.length - 1];
        this.callback({
          type: "workspace-created",
          workspaceId: created?.id,
          windowId: action.payload.windowId,
          name: action.payload.name ?? "New Workspace"
        });
        break;
      }
      case "surface.close": {
        this.callback({
          type: "surface-closed",
          surfaceId: action.payload.surfaceId
        });
        break;
      }
      case "workspace.close": {
        this.callback({
          type: "workspace-closed",
          workspaceId: action.payload.workspaceId
        });
        break;
      }
      case "window.create": {
        const win = nextState.windows[nextState.windows.length - 1];
        this.callback({
          type: "window-created",
          windowId: win?.id
        });
        break;
      }
      case "window.close": {
        this.callback({
          type: "window-closed",
          windowId: action.payload.windowId
        });
        break;
      }
      case "notification.create": {
        this.callback({
          type: "notification-created",
          title: action.payload.title,
          body: action.payload.body ?? "",
          surfaceId: action.payload.surfaceId,
          workspaceId: action.payload.workspaceId
        });
        break;
      }
    }
  }
}
class PersistenceMiddleware {
  constructor(filePath, debounceMs = 500) {
    this.timer = null;
    this.pendingState = null;
    this.hasSavedBefore = false;
    this.filePath = filePath;
    this.debounceMs = debounceMs;
  }
  post(_action, _prevState, nextState) {
    this.pendingState = nextState;
    if (this.timer) {
      clearTimeout(this.timer);
    }
    this.timer = setTimeout(() => {
      this.flush();
    }, this.debounceMs);
  }
  dispose() {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.flush();
  }
  flush() {
    if (!this.pendingState) return;
    const state = this.pendingState;
    this.pendingState = null;
    this.timer = null;
    try {
      if (this.hasSavedBefore && fs.existsSync(this.filePath)) {
        const backupPath = this.filePath + SESSION_BACKUP_SUFFIX;
        fs.copyFileSync(this.filePath, backupPath);
      }
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      const persisted2 = {
        version: SCHEMA_VERSION,
        state
      };
      fs.writeFileSync(this.filePath, JSON.stringify(persisted2), "utf-8");
      this.hasSavedBefore = true;
    } catch (err) {
      console.error("[PersistenceMiddleware] Failed to save state:", err);
    }
  }
  static loadState(filePath) {
    try {
      if (!fs.existsSync(filePath)) return null;
      const raw = fs.readFileSync(filePath, "utf-8");
      const parsed = JSON.parse(raw);
      if (typeof parsed === "object" && parsed !== null && "version" in parsed && "state" in parsed) {
        return parsed;
      }
      return null;
    } catch {
      return null;
    }
  }
}
const sliceMap = {
  window: "windows",
  workspace: "workspaces",
  panel: "panels",
  surface: "surfaces",
  agent: "agents",
  notification: "notifications",
  focus: "focus",
  settings: "settings"
};
function getSlice(actionType) {
  const prefix = actionType.split(".")[0];
  return sliceMap[prefix] ?? null;
}
const multiSliceActions = {
  "panel.resize": ["workspaces"],
  "panel.zoom": ["panels"],
  "panel.swap": ["workspaces"],
  "panel.split": ["panels", "surfaces", "workspaces", "focus"],
  "panel.close": ["panels", "surfaces", "workspaces"],
  "workspace.create": ["workspaces", "panels", "surfaces", "windows", "focus"],
  "workspace.close": ["workspaces", "panels", "surfaces", "windows", "focus"],
  "surface.create": ["surfaces", "panels"],
  "surface.close": ["surfaces", "panels"],
  "agent.spawn": ["panels", "surfaces", "workspaces", "agents"],
  "panel.move": ["panels", "workspaces"]
};
class IpcBroadcastMiddleware {
  constructor() {
    this.windows = /* @__PURE__ */ new Map();
  }
  registerWindow(windowId, target, onClose) {
    this.windows.set(windowId, { target, onClose });
  }
  unregisterWindow(windowId) {
    const entry = this.windows.get(windowId);
    if (entry) {
      entry.onClose();
      this.windows.delete(windowId);
    }
  }
  post(action, _prevState, nextState) {
    const slices = multiSliceActions[action.type] ?? (getSlice(action.type) ? [getSlice(action.type)] : []);
    if (slices.length === 0) return;
    const destroyed = [];
    for (const [windowId, entry] of this.windows) {
      if (entry.target.isDestroyed()) {
        destroyed.push(windowId);
        continue;
      }
      for (const sliceKey of slices) {
        entry.target.webContents.send(IPC_CHANNELS.STATE_UPDATE, sliceKey, nextState[sliceKey]);
      }
    }
    for (const id of destroyed) {
      const entry = this.windows.get(id);
      if (entry) {
        entry.onClose();
        this.windows.delete(id);
      }
    }
  }
}
class AuditLogMiddleware {
  constructor(filePath) {
    this.filePath = filePath;
  }
  post(action, _prevState, _nextState) {
    try {
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      const entry = {
        timestamp: (/* @__PURE__ */ new Date()).toISOString(),
        type: action.type,
        payload: action.payload
      };
      fs.appendFileSync(
        this.filePath,
        JSON.stringify(entry) + "\n",
        "utf-8"
      );
    } catch (err) {
      console.error("[AuditLogMiddleware] Failed to write audit log:", err);
    }
  }
}
function registerIpcHandlers(store2) {
  electron.ipcMain.handle(IPC_CHANNELS.DISPATCH, (_event, rawAction) => {
    return store2.dispatch(rawAction);
  });
  electron.ipcMain.handle(
    IPC_CHANNELS.QUERY_STATE,
    (_event, query) => {
      const state = store2.getState();
      return state[query.slice];
    }
  );
  electron.ipcMain.handle(IPC_CHANNELS.GET_INITIAL_STATE, () => {
    return store2.getState();
  });
}
class WindowManager {
  constructor() {
    this.entries = /* @__PURE__ */ new Map();
  }
  /**
   * Register a window with an associated windowId and close callback.
   */
  register(windowId, win, onClose) {
    this.entries.set(windowId, { windowId, win, onClose });
  }
  /**
   * Get a managed window by its windowId.
   */
  get(windowId) {
    return this.entries.get(windowId)?.win;
  }
  /**
   * Get all registered entries as an array of [windowId, ManagedWindow] tuples.
   */
  getAll() {
    return Array.from(this.entries.entries()).map(([id, entry]) => [
      id,
      entry.win
    ]);
  }
  /**
   * Find a window entry by its webContents id.
   */
  findByWebContentsId(webContentsId) {
    for (const entry of this.entries.values()) {
      if (entry.win.webContents.id === webContentsId) {
        return entry.win;
      }
    }
    return void 0;
  }
  /**
   * Unregister a window, invoking its onClose callback and removing it.
   */
  unregister(windowId) {
    const entry = this.entries.get(windowId);
    if (entry) {
      entry.onClose();
      this.entries.delete(windowId);
    }
  }
}
class JsonRpcRouter {
  constructor() {
    this.handlers = /* @__PURE__ */ new Map();
  }
  register(method, handler) {
    this.handlers.set(method, handler);
  }
  async handle(raw) {
    let request;
    try {
      request = JSON.parse(raw);
    } catch {
      return JSON.stringify(this.errorResponse(null, -32700, "Parse error"));
    }
    if (!request || typeof request !== "object" || request.jsonrpc !== "2.0" || typeof request.method !== "string") {
      return JSON.stringify(
        this.errorResponse(request?.id ?? null, -32600, "Invalid Request")
      );
    }
    const id = request.id ?? null;
    const handler = this.handlers.get(request.method);
    if (!handler) {
      return JSON.stringify(
        this.errorResponse(id, -32601, `Method not found: ${request.method}`)
      );
    }
    try {
      const result = await handler(request.params);
      return JSON.stringify(this.successResponse(id, result));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return JSON.stringify(this.errorResponse(id, -32603, `Internal error: ${message}`));
    }
  }
  getMethods() {
    return Array.from(this.handlers.keys());
  }
  successResponse(id, result) {
    return { jsonrpc: "2.0", id, result };
  }
  errorResponse(id, code, message) {
    return { jsonrpc: "2.0", id, error: { code, message } };
  }
}
class SocketAuth {
  constructor(mode = "cmux-only", password) {
    this.authenticatedSockets = /* @__PURE__ */ new WeakSet();
    this.mode = mode;
    this.token = crypto.randomUUID();
    this.password = password || "";
  }
  /** Get the shared secret token for cmux-only / automation modes. */
  getToken() {
    return this.token;
  }
  /** Get the current auth mode. */
  getMode() {
    return this.mode;
  }
  /** Change the auth mode at runtime. */
  setMode(mode) {
    this.mode = mode;
  }
  /**
   * Check if a connection is allowed.
   *
   * For token-based modes (cmux-only, automation), the first message must
   * contain `{"token":"<token>"}`. For password mode, `{"auth":"<password>"}`.
   *
   * Once authenticated, the socketId object is remembered in a WeakSet so
   * subsequent calls for the same socket do not require re-authentication.
   */
  authenticate(socketId, firstMessage) {
    if (this.mode === "off") {
      return { allowed: false, reason: "Socket API is disabled" };
    }
    if (this.mode === "allow-all") {
      return { allowed: true };
    }
    if (this.mode === "password") {
      if (this.authenticatedSockets.has(socketId)) {
        return { allowed: true };
      }
      try {
        const parsed = JSON.parse(firstMessage || "");
        if (parsed.auth === this.password) {
          this.authenticatedSockets.add(socketId);
          return { allowed: true };
        }
      } catch {
      }
      return { allowed: false, reason: "Invalid password" };
    }
    if (this.authenticatedSockets.has(socketId)) {
      return { allowed: true };
    }
    try {
      const parsed = JSON.parse(firstMessage || "");
      const params = parsed.params;
      const extractedToken = parsed.token ?? params?.token;
      if (extractedToken === this.token) {
        this.authenticatedSockets.add(socketId);
        return { allowed: true };
      }
    } catch {
    }
    return { allowed: false, reason: "Invalid token" };
  }
  /**
   * Check if a specific JSON-RPC method is allowed for the current auth mode.
   *
   * - off:       no methods allowed
   * - cmux-only: system.*, workspace.*, surface.*, panel.*, window.*, notification.*, agent.*
   * - automation: all methods (including browser.*)
   * - password:  all methods
   * - allow-all: all methods
   */
  isMethodAllowed(method) {
    if (this.mode === "off") {
      return false;
    }
    if (this.mode === "allow-all") {
      return true;
    }
    if (this.mode === "cmux-only") {
      return method.startsWith("system.") || method.startsWith("workspace.") || method.startsWith("surface.") || method.startsWith("panel.") || method.startsWith("window.") || method.startsWith("notification.") || method.startsWith("agent.") || method.startsWith("workflow.");
    }
    return true;
  }
}
class SocketApiServer {
  constructor(router2, authMode = "cmux-only") {
    this.server = null;
    this.boundPort = 0;
    this.router = router2;
    this.auth = new SocketAuth(authMode);
    process.env.CMUX_SOCKET_TOKEN = this.auth.getToken();
  }
  /** Get the auth token for child process injection. */
  getAuthToken() {
    return this.auth.getToken();
  }
  /**
   * Start the server, trying ports starting from `startPort`.
   * Returns the actual port bound (BUG-3 fix).
   */
  async start(startPort) {
    let lastError = null;
    for (let attempt = 0; attempt < MAX_SOCKET_PORT_RETRIES; attempt++) {
      try {
        const port = await this.listen(startPort + attempt);
        return port;
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
      }
    }
    throw lastError ?? new Error("Failed to start socket server");
  }
  /**
   * Attempt to listen on a specific port.
   * BUG-3 FIX: Returns the ACTUAL bound port from server.address().
   */
  listen(port) {
    return new Promise((resolve, reject) => {
      const server = net.createServer((socket) => {
        this.handleConnection(socket);
      });
      server.on("error", (err) => {
        reject(err);
      });
      server.listen(port, "127.0.0.1", () => {
        const addr = server.address();
        this.server = server;
        this.boundPort = addr.port;
        resolve(addr.port);
      });
    });
  }
  /**
   * Handle an individual TCP connection.
   * Protocol: newline-delimited JSON-RPC 2.0.
   * R2: First message must authenticate (unless auth mode is allow-all).
   */
  handleConnection(socket) {
    socket.setKeepAlive(true, 3e4);
    let buffer = "";
    let authenticated = false;
    const socketRef = socket;
    socket.on("data", (data) => {
      buffer += data.toString();
      if (buffer.length > 10 * 1024 * 1024) {
        console.error("[socket] Buffer exceeded 10 MB limit — disconnecting client");
        socket.destroy();
        return;
      }
      let newlineIdx = buffer.indexOf("\n");
      while (newlineIdx !== -1) {
        const line = buffer.substring(0, newlineIdx).trim();
        buffer = buffer.substring(newlineIdx + 1);
        if (line.length > 0) {
          if (!authenticated) {
            const authResult = this.auth.authenticate(socketRef, line);
            if (authResult.allowed) {
              authenticated = true;
              try {
                const parsed = JSON.parse(line);
                if (parsed.method === "auth.handshake") {
                  if (!socket.destroyed) {
                    socket.write(
                      JSON.stringify({
                        jsonrpc: "2.0",
                        id: parsed.id ?? null,
                        result: { ok: true }
                      }) + "\n"
                    );
                  }
                  newlineIdx = buffer.indexOf("\n");
                  continue;
                }
              } catch {
              }
            } else {
              try {
                const parsed = JSON.parse(line);
                if (!socket.destroyed) {
                  socket.write(
                    JSON.stringify({
                      jsonrpc: "2.0",
                      id: parsed.id ?? null,
                      error: {
                        code: -32600,
                        message: authResult.reason || "Authentication required"
                      }
                    }) + "\n"
                  );
                }
              } catch {
              }
              socket.destroy();
              return;
            }
          }
          let methodAllowed = true;
          try {
            const parsed = JSON.parse(line);
            if (parsed.method && !this.auth.isMethodAllowed(parsed.method)) {
              methodAllowed = false;
              if (!socket.destroyed) {
                socket.write(
                  JSON.stringify({
                    jsonrpc: "2.0",
                    id: parsed.id ?? null,
                    error: { code: -32600, message: `Method not allowed: ${parsed.method}` }
                  }) + "\n"
                );
              }
            }
          } catch {
            methodAllowed = false;
            if (!socket.destroyed) {
              socket.write(
                JSON.stringify({
                  jsonrpc: "2.0",
                  id: null,
                  error: { code: -32700, message: "Parse error" }
                }) + "\n"
              );
            }
          }
          if (methodAllowed) {
            this.router.handle(line).then((response) => {
              if (!socket.destroyed) {
                socket.write(response + "\n");
              }
            }).catch(() => {
            });
          }
        }
        newlineIdx = buffer.indexOf("\n");
      }
    });
    socket.on("error", () => {
    });
  }
  /**
   * Get the actual bound port.
   */
  getPort() {
    return this.boundPort;
  }
  /**
   * Stop the server.
   */
  async stop() {
    return new Promise((resolve, reject) => {
      if (!this.server) {
        resolve();
        return;
      }
      this.server.close((err) => {
        this.server = null;
        this.boundPort = 0;
        if (err) {
          reject(err);
        } else {
          resolve();
        }
      });
    });
  }
}
function registerSystemHandlers(router2, store2) {
  router2.register("system.ping", () => {
    return { pong: true, timestamp: Date.now() };
  });
  router2.register("system.identify", (params) => {
    const p = params;
    const state = store2.getState();
    const base = {
      name: "cmux-win",
      version: "0.1.0",
      platform: "win32"
    };
    if (p?.surfaceId) {
      const surface = state.surfaces.find((s) => s.id === p.surfaceId);
      const panel = surface ? state.panels.find((pp) => pp.id === surface.panelId) : null;
      const workspace = panel ? state.workspaces.find((w) => w.id === panel.workspaceId) : null;
      return {
        ...base,
        caller: {
          surfaceId: p.surfaceId,
          panelId: panel?.id,
          paneIndex: panel?.paneIndex,
          workspaceId: workspace?.id,
          workspaceName: workspace?.name
        }
      };
    }
    return base;
  });
  router2.register("system.tree", () => {
    const state = store2.getState();
    return {
      workspaces: state.workspaces.map((ws) => ({
        id: ws.id,
        name: ws.name,
        panelLayout: ws.panelLayout,
        panels: state.panels.filter((p) => p.workspaceId === ws.id).map((p) => ({
          id: p.id,
          paneIndex: p.paneIndex,
          panelType: p.panelType,
          surfaces: state.surfaces.filter((s) => s.panelId === p.id).map((s) => ({
            id: s.id,
            surfaceType: s.surfaceType,
            title: s.title,
            terminal: s.terminal
          }))
        })),
        agents: state.agents.filter((a) => a.workspaceId === ws.id).map((a) => ({
          sessionId: a.sessionId,
          agentType: a.agentType,
          surfaceId: a.surfaceId,
          status: a.status,
          statusIcon: a.statusIcon
        }))
      })),
      focus: state.focus
    };
  });
  router2.register("system.capabilities", () => {
    return {
      methods: router2.getMethods()
    };
  });
}
function registerWindowHandlers(router2, store2) {
  router2.register("window.list", () => {
    return { windows: store2.getState().windows };
  });
  router2.register("window.current", () => {
    const state = store2.getState();
    const activeId = state.focus.activeWindowId;
    const window = activeId ? state.windows.find((w) => w.id === activeId) ?? null : null;
    return { window };
  });
  router2.register("window.create", (params) => {
    const p = params ?? {};
    const result = store2.dispatch({ type: "window.create", payload: { geometry: p.geometry } });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to create window");
    }
    const windows = store2.getState().windows;
    return { window: windows[windows.length - 1] };
  });
  router2.register("window.move", (params) => {
    const p = params;
    if (p?.x === void 0 || p?.y === void 0) throw new Error("x and y are required");
    const wins = electron.BrowserWindow.getAllWindows();
    if (wins.length === 0) throw new Error("No window found");
    const win = wins[0];
    const width = p.width ?? win.getBounds().width;
    const height = p.height ?? win.getBounds().height;
    win.setBounds({ x: p.x, y: p.y, width, height });
    return { ok: true, bounds: win.getBounds() };
  });
  router2.register("window.close", (params) => {
    const p = params;
    if (!p?.windowId) throw new Error("windowId is required");
    const result = store2.dispatch({ type: "window.close", payload: { windowId: p.windowId } });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to close window");
    }
    return { ok: true };
  });
}
function registerWorkspaceHandlers(router2, store2) {
  router2.register("workspace.list", () => {
    return { workspaces: store2.getState().workspaces };
  });
  router2.register("workspace.current", () => {
    const state = store2.getState();
    const activeId = state.focus.activeWorkspaceId;
    const workspace = activeId ? state.workspaces.find((ws) => ws.id === activeId) ?? null : null;
    return { workspace };
  });
  router2.register("workspace.create", (params) => {
    const p = params;
    if (!p?.windowId) throw new Error("windowId is required");
    const result = store2.dispatch({
      type: "workspace.create",
      payload: { windowId: p.windowId, name: p.name, cwd: p.cwd }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to create workspace");
    }
    const workspaces = store2.getState().workspaces;
    return { workspace: workspaces[workspaces.length - 1] };
  });
  router2.register("workspace.select", (params) => {
    const p = params;
    if (!p?.workspaceId) throw new Error("workspaceId is required");
    const result = store2.dispatch({
      type: "workspace.select",
      payload: { workspaceId: p.workspaceId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to select workspace");
    }
    return { ok: true };
  });
  router2.register("workspace.close", (params) => {
    const p = params;
    if (!p?.workspaceId) throw new Error("workspaceId is required");
    const result = store2.dispatch({
      type: "workspace.close",
      payload: { workspaceId: p.workspaceId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to close workspace");
    }
    return { ok: true };
  });
  router2.register("workspace.set_layout", (params) => {
    const p = params;
    if (!p?.workspaceId) throw new Error("workspaceId is required");
    if (!p?.panelLayout) throw new Error("panelLayout is required");
    const result = store2.dispatch({
      type: "workspace.set_layout",
      payload: { workspaceId: p.workspaceId, panelLayout: p.panelLayout }
    });
    if (!result.ok) throw new Error(result.error ?? "Failed to set layout");
    return { ok: true };
  });
  router2.register("workspace.rename", (params) => {
    const p = params;
    if (!p?.workspaceId) throw new Error("workspaceId is required");
    if (!p?.name) throw new Error("name is required");
    const result = store2.dispatch({
      type: "workspace.rename",
      payload: { workspaceId: p.workspaceId, name: p.name }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to rename workspace");
    }
    return { ok: true };
  });
}
function registerPanelHandlers(router2, store2) {
  router2.register("panel.list", () => {
    return { panels: store2.getState().panels };
  });
  router2.register("panel.focus", (params) => {
    const p = params;
    if (!p?.panelId) throw new Error("panelId is required");
    const result = store2.dispatch({
      type: "panel.focus",
      payload: { panelId: p.panelId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to focus panel");
    }
    return { ok: true };
  });
  router2.register("panel.split", (params) => {
    const p = params;
    if (!p?.panelId) throw new Error("panelId is required");
    if (!p?.direction) throw new Error("direction is required");
    const panelsBefore = store2.getState().panels.length;
    const result = store2.dispatch({
      type: "panel.split",
      payload: {
        panelId: p.panelId,
        direction: p.direction,
        newPanelType: p.newPanelType ?? "terminal",
        url: p.url,
        // L4: pass URL for browser panels (dashboard, etc.)
        filePath: p.filePath
        // L4: pass filePath for markdown panels
      }
    });
    if (!result.ok) throw new Error(result.error ?? "Failed to split panel");
    const newPanels = store2.getState().panels.slice(panelsBefore);
    const newPanel = newPanels[0];
    return {
      ok: true,
      paneIndex: newPanel?.paneIndex,
      panelId: newPanel?.id,
      surfaceId: newPanel?.activeSurfaceId
    };
  });
  router2.register("panel.resize", (params) => {
    const p = params;
    if (!p?.panelId) throw new Error("panelId is required");
    if (p?.ratio === void 0) throw new Error("ratio is required");
    const result = store2.dispatch({
      type: "panel.resize",
      payload: { panelId: p.panelId, ratio: p.ratio }
    });
    if (!result.ok) throw new Error(result.error ?? "Failed to resize panel");
    return { ok: true };
  });
  router2.register("panel.zoom", (params) => {
    const p = params;
    if (!p?.panelId) throw new Error("panelId is required");
    const result = store2.dispatch({
      type: "panel.zoom",
      payload: { panelId: p.panelId }
    });
    if (!result.ok) throw new Error(result.error ?? "Failed to zoom panel");
    return { ok: true };
  });
  router2.register("panel.close", (params) => {
    const p = params;
    if (!p?.panelId) throw new Error("panelId is required");
    const result = store2.dispatch({
      type: "panel.close",
      payload: { panelId: p.panelId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to close panel");
    }
    return { ok: true };
  });
}
const CSI_RE = /\x1B\[[0-9;?]*[a-zA-Z]/g;
const OSC_RE = /\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)/g;
const DCS_RE = /\x1BP[^\x1B]*\x1B\\/g;
const CHARSET_RE = /\x1B[()][0-9A-B]/g;
const MISC_ESC_RE = /\x1B[>=<N~}{F|7-8]/g;
const C0_RE = /[\x00-\x08\x0B-\x0C\x0E-\x1F]/g;
function stripAnsiEscapes(s) {
  return s.replace(OSC_RE, "").replace(DCS_RE, "").replace(CSI_RE, "").replace(CHARSET_RE, "").replace(MISC_ESC_RE, "").replace(C0_RE, "");
}
function registerSurfaceHandlers(router2, store2) {
  router2.register("surface.list", () => {
    return { surfaces: store2.getState().surfaces };
  });
  router2.register("surface.create", (params) => {
    const p = params;
    if (!p?.panelId) throw new Error("panelId is required");
    const surfaceType = p.surfaceType ?? "terminal";
    const result = store2.dispatch({
      type: "surface.create",
      payload: { panelId: p.panelId, surfaceType }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to create surface");
    }
    const surfaces = store2.getState().surfaces;
    return { surface: surfaces[surfaces.length - 1] };
  });
  router2.register("surface.close", (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId is required");
    const result = store2.dispatch({
      type: "surface.close",
      payload: { surfaceId: p.surfaceId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to close surface");
    }
    return { ok: true };
  });
  router2.register("surface.focus", (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId is required");
    const result = store2.dispatch({
      type: "surface.focus",
      payload: { surfaceId: p.surfaceId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to focus surface");
    }
    return { ok: true };
  });
  router2.register("surface.send_text", (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId is required");
    if (p.text === void 0 || p.text === null) throw new Error("text is required");
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    if (!liveBuffers2?.has(p.surfaceId)) {
      throw new Error("Surface has no active PTY — text not delivered");
    }
    const result = store2.dispatch({
      type: "surface.send_text",
      payload: { surfaceId: p.surfaceId, text: p.text }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to send text");
    }
    return { ok: true };
  });
  router2.register("surface.read", (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId is required");
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    const scrollbackStore2 = g.__cmuxScrollbackStore;
    const liveRaw = liveBuffers2?.get(p.surfaceId);
    const content = liveRaw ? stripAnsiEscapes(liveRaw) : scrollbackStore2?.get(p.surfaceId) ?? "";
    if (p.lines && p.lines > 0) {
      const allLines = content.split("\n");
      return { content: allLines.slice(-p.lines).join("\n") };
    }
    return { content };
  });
  router2.register("surface.health", (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId is required");
    const state = store2.getState();
    const surface = state.surfaces.find((s) => s.id === p.surfaceId);
    if (!surface) throw new Error("Surface not found");
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    const liveBuffer = liveBuffers2?.get(p.surfaceId);
    const agent = state.agents.find((a) => a.surfaceId === p.surfaceId);
    return {
      surfaceId: p.surfaceId,
      surfaceType: surface.surfaceType,
      title: surface.title,
      hasPty: !!liveBuffer,
      bufferSize: liveBuffer?.length ?? 0,
      terminal: surface.terminal,
      agent: agent ? {
        sessionId: agent.sessionId,
        agentType: agent.agentType,
        status: agent.status,
        lastActivity: agent.lastActivity
      } : null
    };
  });
}
const ALLOWED_SHELLS = /* @__PURE__ */ new Set([
  "powershell",
  "cmd",
  "wsl",
  "git-bash",
  "powershell.exe",
  "cmd.exe",
  "wsl.exe",
  "bash.exe",
  "bash"
]);
function shouldUseConpty(resolvedShell) {
  const lower = resolvedShell.toLowerCase();
  if (lower.includes("git") && lower.includes("bash")) {
    return false;
  }
  if (lower.includes("git") && lower.endsWith("bash.exe")) {
    return false;
  }
  return true;
}
function resolveShell(shell) {
  switch (shell) {
    case "powershell":
    case "powershell.exe":
      return "powershell.exe";
    case "cmd":
    case "cmd.exe":
      return "cmd.exe";
    case "wsl":
    case "wsl.exe":
      return "wsl.exe";
    case "bash":
    case "bash.exe":
      return "bash.exe";
    case "git-bash": {
      const candidates = [
        path.join(
          process.env["PROGRAMFILES"] ?? "C:\\Program Files",
          "Git",
          "bin",
          "bash.exe"
        ),
        path.join(
          process.env["PROGRAMFILES(X86)"] ?? "C:\\Program Files (x86)",
          "Git",
          "bin",
          "bash.exe"
        ),
        path.join(
          process.env["LOCALAPPDATA"] ?? "",
          "Programs",
          "Git",
          "bin",
          "bash.exe"
        )
      ];
      for (const candidate of candidates) {
        if (candidate && fs.existsSync(candidate)) {
          return candidate;
        }
      }
      return "bash.exe";
    }
    default:
      return shell;
  }
}
let nextId = 1;
class PtyBridge {
  constructor() {
    this.instances = /* @__PURE__ */ new Map();
  }
  /**
   * Spawn a new PTY process.
   */
  spawn(options = {}) {
    const shellName = options.shell ?? "powershell";
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
      ...options.env
    };
    const ptyProcess = pty__namespace.spawn(resolvedShell, options.args ?? [], {
      name: "xterm-256color",
      cols,
      rows,
      cwd,
      env,
      useConpty
    });
    const id = `pty-${nextId++}`;
    const instance = {
      id,
      pid: ptyProcess.pid,
      process: ptyProcess.process,
      pty: ptyProcess
    };
    this.instances.set(id, instance);
    return { id, pid: ptyProcess.pid };
  }
  /**
   * Write data to a PTY instance.
   */
  write(id, data) {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    instance.pty.write(data);
  }
  /**
   * Resize a PTY instance.
   */
  resize(id, cols, rows) {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    instance.pty.resize(cols, rows);
  }
  /**
   * Kill a PTY instance and remove it from the map.
   */
  kill(id) {
    const instance = this.instances.get(id);
    if (!instance) {
      return;
    }
    try {
      instance.pty.kill();
    } catch (err) {
      console.warn(`[PtyBridge] kill(${id}) error (ignored):`, err.message);
    }
    this.instances.delete(id);
  }
  /**
   * Check whether a PTY instance exists.
   */
  has(id) {
    return this.instances.has(id);
  }
  /**
   * Subscribe to data output from a PTY instance.
   */
  onData(id, callback) {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    return instance.pty.onData(callback);
  }
  /**
   * Subscribe to exit events from a PTY instance.
   */
  onExit(id, callback) {
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
  getAvailableShells() {
    const shells = ["powershell", "cmd"];
    try {
      const wslPath = path.join(
        process.env["SYSTEMROOT"] ?? "C:\\Windows",
        "System32",
        "wsl.exe"
      );
      if (fs.existsSync(wslPath)) {
        shells.push("wsl");
      }
    } catch {
    }
    const gitBashCandidates = [
      path.join(
        process.env["PROGRAMFILES"] ?? "C:\\Program Files",
        "Git",
        "bin",
        "bash.exe"
      ),
      path.join(
        process.env["PROGRAMFILES(X86)"] ?? "C:\\Program Files (x86)",
        "Git",
        "bin",
        "bash.exe"
      ),
      path.join(
        process.env["LOCALAPPDATA"] ?? "",
        "Programs",
        "Git",
        "bin",
        "bash.exe"
      )
    ];
    for (const candidate of gitBashCandidates) {
      if (candidate && fs.existsSync(candidate)) {
        shells.push("git-bash");
        break;
      }
    }
    return shells;
  }
  /**
   * Get all active instance IDs.
   */
  getInstanceIds() {
    return Array.from(this.instances.keys());
  }
  /**
   * Kill all instances (cleanup on app quit).
   */
  killAll() {
    for (const id of this.instances.keys()) {
      this.kill(id);
    }
  }
}
function buildPtyEnv(surfaceId, workspaceId, baseEnv, paneIndex) {
  const env = { ...baseEnv };
  env.CMUX_SURFACE_ID = surfaceId;
  if (workspaceId) env.CMUX_WORKSPACE_ID = workspaceId;
  const binDir = env.CMUX_BIN_DIR || "";
  if (binDir) {
    const sep = process.platform === "win32" ? ";" : ":";
    env.PATH = binDir + sep + (env.PATH || "");
    if (process.platform === "win32") {
      const pathext = env.PATHEXT || ".COM;.EXE;.BAT;.CMD";
      const parts = pathext.split(";").filter(Boolean);
      const cmdIdx = parts.findIndex((p) => p.toUpperCase() === ".CMD");
      const exeIdx = parts.findIndex((p) => p.toUpperCase() === ".EXE");
      if (cmdIdx > exeIdx && exeIdx >= 0) {
        parts.splice(cmdIdx, 1);
        parts.splice(exeIdx, 0, ".CMD");
      }
      env.PATHEXT = parts.join(";");
    }
  }
  const socketPort = env.CMUX_SOCKET_PORT || "19840";
  env.CMUX_SOCKET_ADDR = `tcp://127.0.0.1:${socketPort}`;
  env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = "1";
  env.CMUX_PANE_INDEX = `${paneIndex ?? 0}`;
  if (baseEnv.CMUX_SOCKET_TOKEN) {
    env.CMUX_SOCKET_TOKEN = baseEnv.CMUX_SOCKET_TOKEN;
  }
  return env;
}
function getShellIntegrationArgs(shell, integrationDir) {
  const env = {};
  const shellLower = shell.toLowerCase();
  if (shellLower === "powershell" || shellLower.includes("pwsh")) {
    const psScript = path.join(integrationDir, "powershell.ps1");
    return { args: ["-ExecutionPolicy", "Bypass", "-NoExit", "-Command", `. '${psScript}'`], env };
  }
  if (shellLower === "wsl") {
    const wslScript = path.join(integrationDir, "wsl", "cmux-wsl-integration.sh");
    env.CMUX_SHELL_INTEGRATION = "1";
    env.CMUX_SHELL_INTEGRATION_DIR = integrationDir;
    return { args: ["--rcfile", wslScript], env };
  }
  if (shellLower === "bash" || shellLower === "git-bash" || shellLower.includes("bash")) {
    const bashScript = path.join(integrationDir, "bash.sh");
    env.CMUX_SHELL_INTEGRATION = "1";
    env.CMUX_SHELL_INTEGRATION_DIR = integrationDir;
    return { args: ["--rcfile", bashScript], env };
  }
  if (shellLower === "cmd" || shellLower.includes("cmd.exe")) {
    const cmdScript = path.join(integrationDir, "cmd", "cmux-cmd-integration.cmd");
    env.CMUX_SHELL_INTEGRATION = "1";
    return { args: ["/k", cmdScript], env };
  }
  return { args: [], env };
}
const DEFAULT_APPROVE_PATTERNS = {
  claude: [
    { includes: ["Do you want to", "Yes"] },
    { includes: ["Esc to cancel", "1. Yes"] },
    { includes: ["requires approval", "Yes"] }
  ],
  gemini: [{ includes: ["Apply this change"] }],
  codex: [{ includes: ["Press enter to confirm"] }]
};
function loadApprovePatterns() {
  const configPath = path.join(os.homedir(), ".cmux-win", "auto-approve-patterns.json");
  try {
    if (fs.existsSync(configPath)) {
      const raw = fs.readFileSync(configPath, "utf-8");
      return JSON.parse(raw);
    }
  } catch (err) {
    console.error("[cmux-win] Failed to load auto-approve-patterns.json, using defaults:", err);
  }
  return DEFAULT_APPROVE_PATTERNS;
}
const approvePatterns = loadApprovePatterns();
const bridge = new PtyBridge();
const ptyEvents = new node_events.EventEmitter();
const surfacePtyMap = /* @__PURE__ */ new Map();
const MAX_LIVE_BUFFER = 1e5;
const liveBuffers = /* @__PURE__ */ new Map();
globalThis.__cmuxLiveBuffers = liveBuffers;
function filterSources(_surfaceId, data) {
  if (!data.includes("\n") && !data.includes("\r")) {
    return data;
  }
  const lines = data.split(/(\r?\n|\r)/);
  const filtered = [];
  for (const line of lines) {
    const stripped = line.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "").trim();
    if (/^\[\d+\]\s*https?:\/\//.test(stripped)) continue;
    if (/^Sources?\s*:?\s*$/i.test(stripped)) continue;
    if (/^출처\s*:?\s*$/.test(stripped)) continue;
    if (/^Source:\s*https?:\/\//.test(stripped)) continue;
    filtered.push(line);
  }
  return filtered.join("");
}
function registerPtyHandlers() {
  electron.ipcMain.handle(
    IPC_CHANNELS.PTY_SPAWN,
    (_event, surfaceId, options) => {
      const mergedEnv = buildPtyEnv(
        surfaceId,
        options?.workspaceId,
        {
          ...process.env
        },
        options?.paneIndex
      );
      const integrationDir = path.join(
        mergedEnv.CMUX_BIN_DIR || path.join(__dirname, "../../resources"),
        "../shell-integration"
      );
      const shellName = options?.shell || "powershell";
      const integration = getShellIntegrationArgs(shellName, integrationDir);
      Object.assign(mergedEnv, integration.env);
      const result = bridge.spawn({ ...options, env: mergedEnv, args: integration.args });
      surfacePtyMap.set(surfaceId, result.id);
      const ptyId = result.id;
      const g10 = globalThis;
      const autoApproveCooldowns = g10.__cmuxAutoApproveCooldowns || /* @__PURE__ */ new Map();
      g10.__cmuxAutoApproveCooldowns = autoApproveCooldowns;
      bridge.onData(ptyId, (data) => {
        let buf = (liveBuffers.get(surfaceId) ?? "") + data;
        if (buf.length > MAX_LIVE_BUFFER) {
          buf = buf.slice(buf.length - MAX_LIVE_BUFFER);
        }
        liveBuffers.set(surfaceId, buf);
        const stripped = data.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "");
        const now = Date.now();
        const lastApproval = autoApproveCooldowns.get(surfaceId) ?? 0;
        if (now - lastApproval > 1e3) {
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
            setTimeout(() => bridge.write(ptyId, "\r"), 500);
          }
        }
        const filtered = filterSources(surfaceId, data);
        if (filtered.length === 0) return;
        for (const win of electron.BrowserWindow.getAllWindows()) {
          if (!win.isDestroyed()) {
            win.webContents.send(IPC_CHANNELS.PTY_DATA, surfaceId, filtered);
          }
        }
      });
      bridge.onExit(ptyId, (exitInfo) => {
        for (const win of electron.BrowserWindow.getAllWindows()) {
          if (!win.isDestroyed()) {
            win.webContents.send(IPC_CHANNELS.PTY_EXIT, surfaceId, exitInfo);
          }
        }
        ptyEvents.emit("pty-exit", surfaceId, exitInfo);
        surfacePtyMap.delete(surfaceId);
        liveBuffers.delete(surfaceId);
      });
      return { id: result.id, pid: result.pid };
    }
  );
  electron.ipcMain.on(IPC_CHANNELS.PTY_WRITE, (_event, surfaceId, data) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    if (ptyId) bridge.write(ptyId, data);
  });
  electron.ipcMain.on(IPC_CHANNELS.PTY_RESIZE, (_event, surfaceId, cols, rows) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    if (ptyId) bridge.resize(ptyId, cols, rows);
  });
  electron.ipcMain.on(IPC_CHANNELS.PTY_KILL, (_event, surfaceId) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    if (ptyId) {
      bridge.kill(ptyId);
      surfacePtyMap.delete(surfaceId);
      liveBuffers.delete(surfaceId);
    }
  });
  electron.ipcMain.handle(IPC_CHANNELS.PTY_HAS, (_event, surfaceId) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    return ptyId ? bridge.has(ptyId) : false;
  });
  electron.ipcMain.handle(IPC_CHANNELS.PTY_GET_SHELLS, () => {
    return bridge.getAvailableShells();
  });
}
function writeToPty(surfaceId, data) {
  const ptyId = surfacePtyMap.get(surfaceId);
  if (ptyId) {
    bridge.write(ptyId, data);
    return true;
  }
  return false;
}
function killAllPty() {
  bridge.killAll();
  surfacePtyMap.clear();
}
function registerAgentHandlers(router2, store2) {
  router2.register("agent.spawn", (params) => {
    const p = params;
    if (!p?.agentType) throw new Error("agentType is required");
    if (!p?.workspaceId) throw new Error("workspaceId is required");
    const panelsBefore = store2.getState().panels.length;
    const result = store2.dispatch({
      type: "agent.spawn",
      payload: {
        agentType: p.agentType,
        workspaceId: p.workspaceId,
        task: p.task
      }
    });
    if (!result.ok) throw new Error(result.error ?? "Failed to spawn agent");
    const newPanels = store2.getState().panels.slice(panelsBefore);
    const newPanel = newPanels[0];
    return {
      ok: true,
      paneIndex: newPanel?.paneIndex,
      panelId: newPanel?.id,
      surfaceId: newPanel?.activeSurfaceId
    };
  });
  router2.register("agent.session_start", (params) => {
    const p = params;
    if (!p?.sessionId) throw new Error("sessionId is required");
    if (!p?.agentType) throw new Error("agentType is required");
    if (!p?.workspaceId) throw new Error("workspaceId is required");
    if (!p?.surfaceId) throw new Error("surfaceId is required");
    const result = store2.dispatch({
      type: "agent.session_start",
      payload: {
        sessionId: p.sessionId,
        agentType: p.agentType,
        workspaceId: p.workspaceId,
        surfaceId: p.surfaceId,
        pid: p.pid
      }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to start agent session");
    }
    return { ok: true };
  });
  router2.register("agent.status_update", (params) => {
    const p = params;
    if (!p?.sessionId) throw new Error("sessionId is required");
    if (!p?.status) throw new Error("status is required");
    const result = store2.dispatch({
      type: "agent.status_update",
      payload: {
        sessionId: p.sessionId,
        status: p.status,
        icon: p.icon,
        color: p.color
      }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to update agent status");
    }
    return { ok: true };
  });
  router2.register("agent.session_end", (params) => {
    const p = params;
    if (!p?.sessionId) throw new Error("sessionId is required");
    const result = store2.dispatch({
      type: "agent.session_end",
      payload: { sessionId: p.sessionId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to end agent session");
    }
    return { ok: true };
  });
  const SEND_LOCK_TTL = 3e4;
  const sendLocks = /* @__PURE__ */ new Map();
  router2.register("agent.send_task", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId is required");
    if (!p?.task) throw new Error("task is required");
    const lockTime = sendLocks.get(p.surfaceId);
    if (lockTime && Date.now() - lockTime < SEND_LOCK_TTL) {
      throw new Error("Another send is in progress for this surface");
    }
    sendLocks.set(p.surfaceId, Date.now());
    try {
      const g = globalThis;
      const liveBuffers2 = g.__cmuxLiveBuffers;
      if (!liveBuffers2?.has(p.surfaceId)) {
        throw new Error("Surface has no active PTY");
      }
      const cooldowns = g.__cmuxAutoApproveCooldowns;
      cooldowns?.set(p.surfaceId, Date.now());
      store2.dispatch({
        type: "surface.send_text",
        payload: { surfaceId: p.surfaceId, text: p.task }
      });
      await new Promise((r) => setTimeout(r, 500));
      store2.dispatch({
        type: "surface.send_text",
        payload: { surfaceId: p.surfaceId, text: "\r" }
      });
      const agent = store2.getState().agents.find((a) => a.surfaceId === p.surfaceId);
      if (agent) {
        store2.dispatch({
          type: "agent.status_update",
          payload: { sessionId: agent.sessionId, status: "running", icon: "⚡", color: "#4C8DFF" }
        });
      }
      return { ok: true, surfaceId: p.surfaceId };
    } finally {
      sendLocks.delete(p.surfaceId);
    }
  });
  router2.register("agent.rerun", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId is required");
    if (!p?.task) throw new Error("task is required");
    const state = store2.getState();
    const surface = state.surfaces.find((s) => s.id === p.surfaceId);
    if (!surface) throw new Error("Surface not found");
    const agent = state.agents.find((a) => a.surfaceId === p.surfaceId);
    const agentType = p.agentType || agent?.agentType || "gemini";
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    const ptyAlive = liveBuffers2?.has(p.surfaceId) ?? false;
    if (agent && agent.status !== "done" && agent.status !== "error" && ptyAlive) {
      store2.dispatch({
        type: "surface.send_text",
        payload: { surfaceId: p.surfaceId, text: p.task }
      });
      await new Promise((r) => setTimeout(r, 500));
      store2.dispatch({
        type: "surface.send_text",
        payload: { surfaceId: p.surfaceId, text: "\r" }
      });
      store2.dispatch({
        type: "agent.status_update",
        payload: { sessionId: agent.sessionId, status: "running", icon: "⚡", color: "#4C8DFF" }
      });
      return { ok: true, surfaceId: p.surfaceId, mode: "interactive" };
    }
    let cmd;
    if (agentType === "gemini") {
      cmd = `gemini -i "${p.task.replace(/"/g, '\\"')}" -y`;
    } else if (agentType === "codex") {
      cmd = `codex --full-auto --no-alt-screen "${p.task.replace(/"/g, '\\"')}"`;
    } else {
      cmd = `${agentType} "${p.task.replace(/"/g, '\\"')}"`;
    }
    store2.dispatch({
      type: "surface.send_text",
      payload: { surfaceId: p.surfaceId, text: cmd + "\r" }
    });
    if (agent) {
      store2.dispatch({
        type: "agent.status_update",
        payload: { sessionId: agent.sessionId, status: "running", icon: "⚡", color: "#4C8DFF" }
      });
    }
    return { ok: true, surfaceId: p.surfaceId, mode: "relaunch" };
  });
  router2.register("agent.wait", (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId is required");
    const timeoutMs = p.timeout ?? 3e5;
    const startTime = Date.now();
    return new Promise((resolve) => {
      const onExit = (sid, exitInfo) => {
        if (sid === p.surfaceId) {
          clearTimeout(timer);
          ptyEvents.removeListener("pty-exit", onExit);
          resolve({ exitCode: exitInfo.exitCode, elapsed: Date.now() - startTime, timeout: false });
        }
      };
      const timer = setTimeout(() => {
        ptyEvents.removeListener("pty-exit", onExit);
        resolve({ exitCode: null, elapsed: timeoutMs, timeout: true });
      }, timeoutMs);
      ptyEvents.on("pty-exit", onExit);
      const agent = store2.getState().agents.find((a) => a.surfaceId === p.surfaceId);
      if (agent && (agent.status === "done" || agent.status === "error")) {
        clearTimeout(timer);
        ptyEvents.removeListener("pty-exit", onExit);
        resolve({ exitCode: agent.status === "done" ? 0 : 1, elapsed: 0, timeout: false });
      }
    });
  });
  router2.register("agent.output", (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId is required");
    const lines = p.lines ?? 50;
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    const scrollbackStore2 = g.__cmuxScrollbackStore;
    const liveRaw = liveBuffers2?.get(p.surfaceId);
    const ansiRe2 = /[\x1b\x9b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nq-uy=><~]/g;
    const oscRe2 = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g;
    const raw = liveRaw ?? scrollbackStore2?.get(p.surfaceId) ?? "";
    const clean = raw.replace(oscRe2, "").replace(ansiRe2, "");
    const allLines = clean.split("\n");
    return { content: allLines.slice(-lines).join("\n") };
  });
}
const TOKEN_FILENAME = "telegram-token.enc";
function getTokenPath(appDataDir) {
  return path.join(appDataDir, TOKEN_FILENAME);
}
function saveBotToken(appDataDir, token) {
  if (!electron.safeStorage.isEncryptionAvailable()) {
    console.warn("[telegram] safeStorage encryption not available — cannot save token");
    return false;
  }
  try {
    const dir = appDataDir;
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const encrypted = electron.safeStorage.encryptString(token);
    fs.writeFileSync(getTokenPath(dir), encrypted);
    return true;
  } catch (err) {
    console.error("[telegram] Failed to save bot token:", err);
    return false;
  }
}
function loadBotToken(appDataDir) {
  const tokenPath = getTokenPath(appDataDir);
  if (!fs.existsSync(tokenPath)) return null;
  if (!electron.safeStorage.isEncryptionAvailable()) {
    console.warn("[telegram] safeStorage encryption not available — cannot load token");
    return null;
  }
  try {
    const encrypted = fs.readFileSync(tokenPath);
    return electron.safeStorage.decryptString(encrypted);
  } catch (err) {
    console.error("[telegram] Failed to load bot token:", err);
    return null;
  }
}
function deleteBotToken(appDataDir) {
  const tokenPath = getTokenPath(appDataDir);
  try {
    if (fs.existsSync(tokenPath)) fs.unlinkSync(tokenPath);
  } catch {
  }
}
function registerNotificationHandlers(router2, store2, appDataDir) {
  if (appDataDir) {
    router2.register("telegram.set_token", (params) => {
      const p = params;
      if (!p?.token) throw new Error("token is required");
      const ok = saveBotToken(appDataDir, p.token);
      if (!ok) throw new Error("Failed to save token (encryption unavailable)");
      return { ok: true };
    });
    router2.register("telegram.get_token_status", () => {
      const token = loadBotToken(appDataDir);
      return { hasToken: token !== null };
    });
    router2.register("telegram.delete_token", () => {
      deleteBotToken(appDataDir);
      return { ok: true };
    });
    router2.register("telegram.test", async () => {
      const token = loadBotToken(appDataDir);
      if (!token) throw new Error("No bot token configured");
      const chatId = store2.getState().settings.telegram.chatId;
      if (!chatId) throw new Error("No chat ID configured");
      return { ok: true, message: "Token and chatId present" };
    });
  }
  router2.register("notification.create", (params) => {
    const p = params;
    if (!p?.title) throw new Error("title is required");
    const result = store2.dispatch({
      type: "notification.create",
      payload: {
        title: p.title,
        subtitle: p.subtitle,
        body: p.body,
        workspaceId: p.workspaceId,
        surfaceId: p.surfaceId
      }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to create notification");
    }
    const notifications = store2.getState().notifications;
    return { notification: notifications[notifications.length - 1] };
  });
  router2.register("notification.list", () => {
    return { notifications: store2.getState().notifications };
  });
  router2.register("notification.clear", (params) => {
    const p = params ?? {};
    const result = store2.dispatch({
      type: "notification.clear",
      payload: { workspaceId: p.workspaceId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to clear notifications");
    }
    return { ok: true };
  });
}
function registerSettingsHandlers(router2, store2) {
  router2.register("settings.get", () => {
    return { settings: store2.getState().settings };
  });
  router2.register("settings.update", (params) => {
    const p = params;
    if (!p || typeof p !== "object" || Object.keys(p).length === 0) {
      throw new Error("settings object is required");
    }
    const result = store2.dispatch({
      type: "settings.update",
      payload: p
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to update settings");
    }
    return { settings: store2.getState().settings };
  });
}
let ipcMainModule = null;
let BrowserWindowModule = null;
try {
  const electron2 = require("electron");
  ipcMainModule = electron2.ipcMain;
  BrowserWindowModule = electron2.BrowserWindow;
} catch {
}
const pendingRequests = /* @__PURE__ */ new Map();
let resultListenerRegistered = false;
function ensureResultListener() {
  if (resultListenerRegistered || !ipcMainModule) return;
  resultListenerRegistered = true;
  ipcMainModule.on(
    "cmux:browser-execute-result",
    (_event, requestId, result, error) => {
      const pending = pendingRequests.get(requestId);
      if (!pending) return;
      clearTimeout(pending.timeout);
      pendingRequests.delete(requestId);
      if (error) {
        pending.reject(new Error(error));
      } else {
        pending.resolve(result);
      }
    }
  );
}
async function executeOnWebview(surfaceId, code, timeoutMs = 1e4) {
  if (!BrowserWindowModule) return null;
  ensureResultListener();
  const requestId = crypto$1.randomUUID();
  for (const win of BrowserWindowModule.getAllWindows()) {
    if (!win.isDestroyed()) {
      win.webContents.send("cmux:browser-execute", requestId, surfaceId, code);
    }
  }
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pendingRequests.delete(requestId);
      reject(new Error("Browser execute timeout"));
    }, timeoutMs);
    pendingRequests.set(requestId, { resolve, reject, timeout });
  });
}
function registerBrowserHandlers(router2, _store) {
  router2.register("browser.eval", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    if (!p?.code) throw new Error("code required");
    const result = await executeOnWebview(p.surfaceId, p.code);
    return { ok: true, result };
  });
  router2.register("browser.snapshot", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    const snapshot = await executeOnWebview(p.surfaceId, "document.documentElement.outerHTML");
    return { ok: true, snapshot };
  });
  router2.register("browser.screenshot", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    const html = await executeOnWebview(p.surfaceId, "document.documentElement.outerHTML");
    return {
      ok: true,
      format: "html",
      data: typeof html === "string" ? html : "",
      note: "Image capture requires webview.capturePage IPC (future)"
    };
  });
  router2.register("browser.click", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    if (!p?.ref) throw new Error("ref required");
    await executeOnWebview(
      p.surfaceId,
      `document.querySelector('[data-cmux-ref="${p.ref}"]')?.click()`
    );
    return { ok: true };
  });
  router2.register("browser.type", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    if (!p?.text) throw new Error("text required");
    const escapedText = JSON.stringify(p.text);
    await executeOnWebview(
      p.surfaceId,
      `(() => {
        const el = document.activeElement;
        if (el) {
          el.value = (el.value || '') + ${escapedText};
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }
      })()`
    );
    return { ok: true };
  });
  router2.register("browser.fill", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    if (!p?.ref) throw new Error("ref required");
    await executeOnWebview(
      p.surfaceId,
      `(() => {
        const el = document.querySelector('[data-cmux-ref="${p.ref}"]');
        if (el) {
          el.value = ${JSON.stringify(p.value || "")};
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }
      })()`
    );
    return { ok: true };
  });
  router2.register("browser.press", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    if (!p?.key) throw new Error("key required");
    await executeOnWebview(
      p.surfaceId,
      `(() => {
        const el = document.activeElement;
        if (el) {
          el.dispatchEvent(new KeyboardEvent('keydown', { key: ${JSON.stringify(p.key)}, bubbles: true }));
          el.dispatchEvent(new KeyboardEvent('keyup', { key: ${JSON.stringify(p.key)}, bubbles: true }));
        }
      })()`
    );
    return { ok: true };
  });
  router2.register("browser.wait", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    if (p.selector) {
      const timeoutMs = p.timeout || 5e3;
      await executeOnWebview(
        p.surfaceId,
        `new Promise((resolve, reject) => {
          const el = document.querySelector(${JSON.stringify(p.selector)});
          if (el) { resolve(true); return; }
          const observer = new MutationObserver(() => {
            if (document.querySelector(${JSON.stringify(p.selector)})) {
              observer.disconnect();
              resolve(true);
            }
          });
          observer.observe(document.body, { childList: true, subtree: true });
          setTimeout(() => { observer.disconnect(); reject('Timeout waiting for ' + ${JSON.stringify(p.selector)}); }, ${timeoutMs});
        })`,
        timeoutMs + 2e3
        // IPC timeout slightly longer than JS timeout
      );
    }
    return { ok: true };
  });
  router2.register("browser.navigate", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    if (!p?.url) throw new Error("url required");
    await executeOnWebview(p.surfaceId, `window.location.href = ${JSON.stringify(p.url)}`);
    return { ok: true };
  });
  router2.register("browser.url.get", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    const url = await executeOnWebview(p.surfaceId, "window.location.href");
    return { url };
  });
  router2.register("browser.title.get", async (params) => {
    const p = params;
    if (!p?.surfaceId) throw new Error("surfaceId required");
    const title = await executeOnWebview(p.surfaceId, "document.title");
    return { title };
  });
}
const ansiRe = /[\x1b\x9b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nq-uy=><~]/g;
const oscRe = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g;
function readOutput(surfaceId, lines) {
  const g = globalThis;
  const liveBuffers2 = g.__cmuxLiveBuffers;
  const scrollbackStore2 = g.__cmuxScrollbackStore;
  const raw = liveBuffers2?.get(surfaceId) ?? scrollbackStore2?.get(surfaceId) ?? "";
  const clean = raw.replace(oscRe, "").replace(ansiRe, "");
  return clean.split("\n").slice(-30).join("\n");
}
function waitForIdle(surfaceId, agentType, timeoutMs) {
  return new Promise((resolve) => {
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    const startLen = (liveBuffers2?.get(surfaceId) ?? "").length;
    let lastLen = startLen;
    let stableCount = 0;
    const onExit = (sid) => {
      if (sid !== surfaceId) return;
      cleanup();
      resolve({
        idle: false,
        timeout: false,
        exited: true,
        output: readOutput(surfaceId)
      });
    };
    ptyEvents.on("pty-exit", onExit);
    const idlePatterns = {
      gemini: ["Type your message", "Enter your prompt", "What can I help"],
      codex: ["What would you like", "Enter a prompt"]
    };
    const patterns = idlePatterns[agentType] || [];
    const interval = setInterval(() => {
      const raw = liveBuffers2?.get(surfaceId) ?? "";
      const tail = raw.slice(-500).replace(ansiRe, "");
      const patternMatch = patterns.some((p) => tail.includes(p)) && raw.length > startLen;
      const outputStable = raw.length === lastLen && raw.length > startLen;
      if (outputStable) stableCount++;
      else stableCount = 0;
      if (patternMatch && stableCount >= 2 || stableCount >= 10) {
        cleanup();
        resolve({
          idle: true,
          timeout: false,
          exited: false,
          output: readOutput(surfaceId)
        });
      }
      lastLen = raw.length;
    }, 500);
    const timer = setTimeout(() => {
      cleanup();
      resolve({
        idle: false,
        timeout: true,
        exited: false,
        output: readOutput(surfaceId)
      });
    }, timeoutMs);
    function cleanup() {
      clearInterval(interval);
      clearTimeout(timer);
      ptyEvents.removeListener("pty-exit", onExit);
    }
  });
}
function registerWorkflowHandlers(router2, store2) {
  router2.register("workflow.run", async (params) => {
    const p = params;
    if (!p?.steps || !Array.isArray(p.steps) || p.steps.length === 0) {
      throw new Error("steps array is required");
    }
    const state = store2.getState();
    const workspaceId = p.workspaceId || state.focus.activeWorkspaceId || state.workspaces[0]?.id;
    if (!workspaceId) throw new Error("No workspace available");
    const stepTimeout = p.timeout ?? 3e5;
    const results = [];
    for (let i = 0; i < p.steps.length; i++) {
      const step = p.steps[i];
      const panelsBefore = store2.getState().panels.length;
      const spawnResult = store2.dispatch({
        type: "agent.spawn",
        payload: {
          agentType: step.agent,
          workspaceId,
          task: step.task,
          cwd: step.cwd
        }
      });
      if (!spawnResult.ok) {
        results.push({ step: i, agent: step.agent, task: step.task, exitCode: -1, timeout: false, output: `Spawn failed: ${spawnResult.error}` });
        continue;
      }
      const newPanels = store2.getState().panels.slice(panelsBefore);
      const surfaceId = newPanels[0]?.activeSurfaceId;
      if (!surfaceId) {
        results.push({ step: i, agent: step.agent, task: step.task, exitCode: -1, timeout: false, output: "No surface created" });
        continue;
      }
      const idleResult = await waitForIdle(surfaceId, step.agent, stepTimeout);
      results.push({
        step: i,
        agent: step.agent,
        task: step.task,
        exitCode: idleResult.exited ? 1 : idleResult.idle ? 0 : null,
        timeout: idleResult.timeout,
        output: idleResult.output
      });
    }
    return {
      name: p.name ?? "unnamed",
      stepsCompleted: results.filter((r) => r.exitCode === 0).length,
      stepsTotal: p.steps.length,
      results
    };
  });
}
const DEFAULT_SHORTCUTS = [
  // Workspace
  { id: "newWorkspace", label: "New Workspace", defaultKey: "Ctrl+N", category: "workspace" },
  {
    id: "closeWorkspace",
    label: "Close Workspace",
    defaultKey: "Ctrl+Shift+W",
    category: "workspace"
  },
  { id: "nextWorkspace", label: "Next Workspace", defaultKey: "Ctrl+Tab", category: "workspace" },
  {
    id: "prevWorkspace",
    label: "Prev Workspace",
    defaultKey: "Ctrl+Shift+Tab",
    category: "workspace"
  },
  {
    id: "renameWorkspace",
    label: "Rename Workspace",
    defaultKey: "Ctrl+Shift+R",
    category: "workspace"
  },
  // Panel
  { id: "splitRight", label: "Split Right", defaultKey: "Ctrl+D", category: "panel" },
  { id: "splitDown", label: "Split Down", defaultKey: "Ctrl+Shift+D", category: "panel" },
  { id: "closePanel", label: "Close Panel", defaultKey: "Ctrl+Shift+X", category: "panel" },
  { id: "toggleZoom", label: "Toggle Zoom", defaultKey: "Ctrl+Shift+Enter", category: "panel" },
  { id: "focusLeft", label: "Focus Left", defaultKey: "Ctrl+Alt+Left", category: "panel" },
  { id: "focusRight", label: "Focus Right", defaultKey: "Ctrl+Alt+Right", category: "panel" },
  { id: "focusUp", label: "Focus Up", defaultKey: "Ctrl+Alt+Up", category: "panel" },
  { id: "focusDown", label: "Focus Down", defaultKey: "Ctrl+Alt+Down", category: "panel" },
  // Surface
  { id: "newSurface", label: "New Tab", defaultKey: "Ctrl+Shift+T", category: "surface" },
  { id: "closeSurface", label: "Close Tab", defaultKey: "Ctrl+Shift+Q", category: "surface" },
  { id: "nextSurface", label: "Next Tab", defaultKey: "Ctrl+Shift+]", category: "surface" },
  { id: "prevSurface", label: "Prev Tab", defaultKey: "Ctrl+Shift+[", category: "surface" },
  // Navigation
  { id: "find", label: "Find", defaultKey: "Ctrl+F", category: "navigation" },
  // View
  { id: "toggleSidebar", label: "Toggle Sidebar", defaultKey: "Ctrl+B", category: "view" },
  { id: "toggleExplorer", label: "Toggle File Explorer", defaultKey: "Ctrl+E", category: "view" },
  { id: "newWindow", label: "New Window", defaultKey: "Ctrl+Shift+N", category: "view" },
  { id: "closeWindow", label: "Close Window", defaultKey: "Ctrl+Alt+W", category: "view" },
  { id: "commandPalette", label: "Command Palette", defaultKey: "Ctrl+Shift+P", category: "view" },
  { id: "openSettings", label: "Open Settings", defaultKey: "Ctrl+,", category: "view" },
  { id: "togglePanels", label: "Toggle Panels (Collapse/Expand)", defaultKey: "Ctrl+`", category: "view" },
  { id: "equalizeHorizontal", label: "Equal Width (Horizontal)", defaultKey: "Ctrl+Shift+=", category: "view" },
  { id: "equalizeVertical", label: "Equal Height (Vertical)", defaultKey: "Ctrl+Alt+=", category: "view" }
];
function parseKeyCombo(key) {
  const parts = key.split("+");
  return {
    ctrl: parts.includes("Ctrl"),
    shift: parts.includes("Shift"),
    alt: parts.includes("Alt"),
    key: parts[parts.length - 1]
  };
}
function matchInput(input, shortcuts) {
  for (const sc of shortcuts) {
    const combo = parseKeyCombo(sc.defaultKey);
    if (input.control === combo.ctrl && input.shift === combo.shift && input.alt === combo.alt && input.key.toLowerCase() === combo.key.toLowerCase()) {
      return sc.id;
    }
  }
  return null;
}
function attachShortcutInterceptor(win) {
  win.webContents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown") return;
    const shortcutId = matchInput(input, DEFAULT_SHORTCUTS);
    if (shortcutId) {
      event.preventDefault();
      win.webContents.send(IPC_CHANNELS.SHORTCUT, shortcutId);
    }
  });
}
function checkPidStatus(pid) {
  try {
    process.kill(pid, 0);
    return "alive";
  } catch (err) {
    const code = err.code;
    if (code === "ESRCH") return "dead";
    if (code === "EPERM") return "no_permission";
    return "dead";
  }
}
class HistoryDb {
  constructor(dbPath) {
    this.db = new Database(dbPath);
    this.db.pragma("journal_mode = WAL");
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT,
        visit_time INTEGER NOT NULL,
        favicon_url TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_history_url ON history(url);
      CREATE INDEX IF NOT EXISTS idx_history_profile ON history(profile_id);
      CREATE INDEX IF NOT EXISTS idx_history_visit ON history(visit_time DESC);
    `);
  }
  add(profileId, url, title, faviconUrl) {
    this.db.prepare(
      "INSERT INTO history (profile_id, url, title, visit_time, favicon_url) VALUES (?, ?, ?, ?, ?)"
    ).run(profileId, url, title ?? null, Date.now(), faviconUrl ?? null);
  }
  query(profileId, prefix, limit = 10) {
    return this.db.prepare(
      `
      SELECT url, title, MAX(visit_time) as lastVisit, COUNT(*) as visits
      FROM history WHERE profile_id = ? AND url LIKE ? || '%'
      GROUP BY url ORDER BY visits DESC, lastVisit DESC LIMIT ?
    `
    ).all(profileId, prefix, limit);
  }
  clear(profileId) {
    if (profileId) {
      this.db.prepare("DELETE FROM history WHERE profile_id = ?").run(profileId);
    } else {
      this.db.exec("DELETE FROM history");
    }
  }
  close() {
    this.db.close();
  }
}
function createTelemetryConfig(enabled) {
  return {
    enabled,
    sentryDsn: process.env.SENTRY_DSN,
    posthogApiKey: process.env.POSTHOG_API_KEY
  };
}
function createUpdateConfig(channel, autoCheck) {
  return { channel, autoCheck };
}
function getUpdateConfig() {
  return { provider: "github", owner: "cmux-win", repo: "cmux-win" };
}
let autoUpdaterInstance = null;
async function initAutoUpdater(config) {
  try {
    const { autoUpdater } = await import("electron-updater");
    autoUpdaterInstance = autoUpdater;
    autoUpdater.autoDownload = true;
    autoUpdater.channel = config.channel;
    const ghConfig = getUpdateConfig();
    autoUpdater.setFeedURL({
      provider: ghConfig.provider,
      owner: ghConfig.owner,
      repo: ghConfig.repo
    });
    autoUpdater.on("update-available", (info) => {
      console.warn(`[cmux-win] Update available: ${info.version}`);
    });
    autoUpdater.on("update-downloaded", () => {
      console.warn("[cmux-win] Update downloaded. Will install on quit.");
    });
    autoUpdater.on("error", (err) => {
      console.error("[cmux-win] Auto-update error:", err.message);
    });
    if (config.autoCheck) {
      autoUpdater.checkForUpdatesAndNotify().catch((_err) => {
        console.warn("[cmux-win] Update check skipped (dev mode or no publish config)");
      });
    }
  } catch {
    autoUpdaterInstance = null;
    console.warn("[cmux-win] Auto-updater not available");
  }
}
function showToast(title, body, onClick) {
  if (!electron.Notification.isSupported()) return;
  const notification = new electron.Notification({
    title,
    body: body || "",
    silent: false
  });
  notification.on("click", () => {
    {
      focusFirstWindow();
    }
  });
  notification.show();
}
function focusFirstWindow() {
  const wins = electron.BrowserWindow.getAllWindows();
  if (wins.length === 0) return;
  const win = wins[0];
  if (win.isMinimized()) win.restore();
  win.focus();
}
function computeUnreadCount(notifications) {
  if (!notifications || notifications.length === 0) return 0;
  const count = notifications.filter((n) => !n.isRead).length;
  return Math.max(0, count);
}
function formatTrayTitle(unreadCount, appName = "cmux-win") {
  if (unreadCount <= 0) return appName;
  return `(${unreadCount}) ${appName}`;
}
const DEBOUNCE_MS = 3e3;
const CALLBACK_EXPIRY_MS = 5 * 60 * 1e3;
function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
class TelegramBotService {
  constructor(store2) {
    this.bot = null;
    this.chatId = "";
    this.settings = {
      enabled: false,
      chatId: "",
      forwardNotifications: true,
      remoteControl: true
    };
    this.debounceTimers = /* @__PURE__ */ new Map();
    this.networkErrorCount = 0;
    this.store = store2;
  }
  /**
   * H6: Serialized configure — await stop before start.
   * Safe to call multiple times (settings change, etc.).
   */
  async configure(settings, botToken) {
    if (this.bot) {
      const oldBot = this.bot;
      this.bot = null;
      try {
        oldBot.stop();
        await new Promise((r) => setTimeout(r, 500));
      } catch {
      }
    }
    this.settings = { ...settings };
    this.chatId = settings.chatId;
    if (!settings.enabled || !botToken || !settings.chatId) {
      return;
    }
    const bot = new grammy.Bot(botToken);
    bot.api.config.use(autoRetry.autoRetry({ maxRetryAttempts: 3, maxDelaySeconds: 60 }));
    bot.catch((err) => {
      const e = err.error;
      if (e instanceof grammy.GrammyError) {
        console.warn(`[telegram] API error ${e.error_code}: ${e.description}`);
      } else if (e instanceof grammy.HttpError) {
        this.networkErrorCount++;
        if (this.networkErrorCount <= 3 || this.networkErrorCount % 100 === 0) {
          console.warn(`[telegram] Network error (#${this.networkErrorCount}):`, e.message);
        }
      } else {
        console.warn("[telegram] Unexpected error:", e);
      }
    });
    if (settings.remoteControl) {
      this.setupCommands(bot);
    }
    bot.on("message:text", async (ctx) => {
      if (!ctx.message.text.startsWith("/")) {
        if (String(ctx.chat.id) !== this.chatId) return;
        await ctx.reply(
          "명령어를 입력해주세요.\n\n/status — 워크스페이스 상태\n/agents — 에이전트 목록\n/approve — 대기 중인 에이전트 승인\n/reject — 대기 중인 에이전트 거부\n/send &lt;text&gt; — 텍스트 전송\n/help — 도움말",
          { parse_mode: "HTML" }
        );
      }
    });
    this.bot = bot;
    bot.start({
      drop_pending_updates: true,
      allowed_updates: ["message", "callback_query"],
      onStart: () => {
        this.networkErrorCount = 0;
        console.warn("[telegram] Bot polling started");
      }
    });
  }
  /**
   * Send notification to Telegram with InlineKeyboard.
   * H1: Must be called with .catch() — never let rejection propagate.
   * H2: Debounced per workspaceId (3 seconds).
   * H3: HTML escaped.
   */
  async sendNotification(title, body, meta) {
    if (!this.bot || !this.chatId || !this.settings.forwardNotifications) return;
    const key = meta?.workspaceId ?? "global";
    const existing = this.debounceTimers.get(key);
    if (existing) clearTimeout(existing);
    return new Promise((resolve) => {
      const timer = setTimeout(async () => {
        this.debounceTimers.delete(key);
        try {
          const safeTitle = escapeHtml(title);
          const safeBody = escapeHtml(body || "");
          let context = "";
          if (meta?.workspaceId) {
            const ws = this.store.getState().workspaces.find((w) => w.id === meta.workspaceId);
            if (ws) context = `

📂 <b>${escapeHtml(ws.name)}</b>`;
          }
          const now = Date.now();
          const keyboard = new grammy.InlineKeyboard().text("✅ 승인", `approve:${meta?.surfaceId ?? ""}:${now}`).text("❌ 거부", `reject:${meta?.surfaceId ?? ""}:${now}`).row().text("📊 상태", "status");
          await this.bot.api.sendMessage(
            this.chatId,
            `🔔 <b>${safeTitle}</b>

${safeBody}${context}`,
            { parse_mode: "HTML", reply_markup: keyboard }
          );
        } catch (err) {
          console.warn("[telegram] sendNotification failed:", err.message);
        }
        resolve();
      }, DEBOUNCE_MS);
      this.debounceTimers.set(key, timer);
    });
  }
  /**
   * C3: Stop bot polling — MUST be called on app quit.
   * Synchronous for use in before-quit handler.
   */
  stop() {
    if (this.bot) {
      try {
        this.bot.stop();
      } catch {
      }
      this.bot = null;
    }
    for (const timer of this.debounceTimers.values()) clearTimeout(timer);
    this.debounceTimers.clear();
  }
  get isRunning() {
    return this.bot !== null;
  }
  // ---- Private: Inbound command handlers ----
  setupCommands(bot) {
    bot.use(async (ctx, next) => {
      if (String(ctx.chat?.id) !== this.chatId) return;
      await next();
    });
    bot.command("status", async (ctx) => {
      const state = this.store.getState();
      const lines = ["📊 <b>cmux-win 상태</b>\n"];
      for (const ws of state.workspaces) {
        const wsAgents = state.agents.filter((a) => a.workspaceId === ws.id);
        const agentInfo = wsAgents.length > 0 ? wsAgents.map((a) => `  ${a.statusIcon} ${a.agentType} (${a.status})`).join("\n") : "  (에이전트 없음)";
        lines.push(`📂 <b>${escapeHtml(ws.name)}</b>
${agentInfo}`);
      }
      if (state.workspaces.length === 0) {
        lines.push("워크스페이스가 없습니다.");
      }
      await ctx.reply(lines.join("\n"), { parse_mode: "HTML" });
    });
    bot.command("agents", async (ctx) => {
      const agents = this.store.getState().agents;
      if (agents.length === 0) {
        await ctx.reply("실행 중인 에이전트가 없습니다.");
        return;
      }
      const lines = agents.map(
        (a) => `${a.statusIcon} <b>${a.agentType}</b> — ${a.status}`
      );
      await ctx.reply(lines.join("\n"), { parse_mode: "HTML" });
    });
    bot.command("approve", async (ctx) => {
      const agent = this.findNeedsInputAgent();
      if (!agent) {
        await ctx.reply("대기 중인 에이전트가 없습니다.");
        return;
      }
      this.sendTextToSurface(agent.surfaceId, "y\r");
      await ctx.reply(`✅ ${agent.agentType} 에이전트에 승인(y) 전송 완료`);
    });
    bot.command("reject", async (ctx) => {
      const agent = this.findNeedsInputAgent();
      if (!agent) {
        await ctx.reply("대기 중인 에이전트가 없습니다.");
        return;
      }
      this.sendTextToSurface(agent.surfaceId, "n\r");
      await ctx.reply(`❌ ${agent.agentType} 에이전트에 거부(n) 전송 완료`);
    });
    bot.command("send", async (ctx) => {
      const raw = ctx.match?.trim();
      if (!raw) {
        await ctx.reply(
          "사용법:\n/send &lt;텍스트&gt; — 활성 에이전트에 전송\n/send claude &lt;텍스트&gt; — 특정 에이전트에 전송",
          { parse_mode: "HTML" }
        );
        return;
      }
      const agentTypes = ["claude", "gemini", "codex", "opencode"];
      const firstWord = raw.split(/\s+/)[0].toLowerCase();
      let targetType = null;
      let text = raw;
      if (agentTypes.includes(firstWord)) {
        targetType = firstWord;
        text = raw.slice(firstWord.length).trim();
        if (!text) {
          await ctx.reply("전송할 텍스트를 입력하세요.");
          return;
        }
      }
      const agents = this.store.getState().agents;
      let agent = targetType ? agents.find((a) => a.agentType === targetType && a.status !== "done" && a.status !== "error") : this.findNeedsInputAgent() ?? agents.find((a) => a.status === "running");
      if (!agent) {
        await ctx.reply(targetType ? `활성 ${targetType} 에이전트가 없습니다.` : "활성 에이전트가 없습니다.");
        return;
      }
      const keyboard = new grammy.InlineKeyboard().text("✅ 전송", `send_confirm:${agent.surfaceId}:${encodeURIComponent(text)}`).text("취소", "send_cancel");
      await ctx.reply(
        `<code>${escapeHtml(text)}</code>

위 텍스트를 <b>${escapeHtml(agent.agentType)}</b> 에이전트에 전송할까요?`,
        { parse_mode: "HTML", reply_markup: keyboard }
      );
    });
    bot.command("task", async (ctx) => {
      const text = ctx.match?.trim();
      if (!text) {
        await ctx.reply("사용법: /task &lt;작업 내용&gt;", { parse_mode: "HTML" });
        return;
      }
      const agents = this.store.getState().agents;
      const claude = agents.find((a) => a.agentType === "claude" && a.status !== "done" && a.status !== "error");
      if (!claude) {
        const surfaces = this.store.getState().surfaces;
        if (surfaces.length === 0) {
          await ctx.reply("활성 터미널이 없습니다.");
          return;
        }
        this.sendTextToSurface(surfaces[0].id, text + "\r");
        await ctx.reply(`✅ 첫 번째 터미널에 작업 전송 완료`);
        return;
      }
      this.sendTextToSurface(claude.surfaceId, text + "\r");
      await ctx.reply(`✅ Claude 리더에게 작업 전송 완료:
<code>${escapeHtml(text)}</code>`, { parse_mode: "HTML" });
    });
    bot.command("help", async (ctx) => {
      await ctx.reply(
        "<b>cmux-win 텔레그램 봇</b>\n\n/status — 워크스페이스 + 에이전트 상태\n/agents — 에이전트 목록\n/approve — 대기 중인 에이전트 승인 (y)\n/reject — 대기 중인 에이전트 거부 (n)\n/send &lt;text&gt; — 에이전트에 텍스트 전송\n/send gemini &lt;text&gt; — 특정 에이전트에 전송\n/task &lt;text&gt; — Claude 리더에게 작업 지시\n/help — 이 도움말",
        { parse_mode: "HTML" }
      );
    });
    bot.on("callback_query:data", async (ctx) => {
      const data = ctx.callbackQuery.data;
      if (data.startsWith("approve:") || data.startsWith("reject:")) {
        const parts = data.split(":");
        const surfaceId = parts[1];
        const timestamp = parseInt(parts[2], 10);
        if (Date.now() - timestamp > CALLBACK_EXPIRY_MS) {
          await ctx.answerCallbackQuery({ text: "⏰ 만료된 버튼입니다.", show_alert: true });
          return;
        }
        const agent = surfaceId ? this.store.getState().agents.find((a) => a.surfaceId === surfaceId) : this.findNeedsInputAgent();
        if (!agent || agent.status !== "needs_input") {
          await ctx.answerCallbackQuery({
            text: "에이전트가 더 이상 입력 대기 상태가 아닙니다.",
            show_alert: true
          });
          return;
        }
        const isApprove = data.startsWith("approve:");
        this.sendTextToSurface(agent.surfaceId, isApprove ? "y\r" : "n\r");
        await ctx.answerCallbackQuery({
          text: isApprove ? "✅ 승인됨" : "❌ 거부됨"
        });
        await ctx.editMessageReplyMarkup({ reply_markup: void 0 });
        return;
      }
      if (data === "status") {
        await ctx.answerCallbackQuery();
        const state = this.store.getState();
        const lines = ["📊 <b>cmux-win 상태</b>\n"];
        for (const ws of state.workspaces) {
          const wsAgents = state.agents.filter((a) => a.workspaceId === ws.id);
          const agentInfo = wsAgents.length > 0 ? wsAgents.map((a) => `  ${a.statusIcon} ${a.agentType} (${a.status})`).join("\n") : "  (에이전트 없음)";
          lines.push(`📂 <b>${escapeHtml(ws.name)}</b>
${agentInfo}`);
        }
        await ctx.reply(lines.join("\n"), { parse_mode: "HTML" });
        return;
      }
      if (data.startsWith("send_confirm:")) {
        const parts = data.split(":");
        const surfaceId = parts[1];
        const text = decodeURIComponent(parts.slice(2).join(":"));
        this.sendTextToSurface(surfaceId, text + "\r");
        await ctx.answerCallbackQuery({ text: "✅ 전송됨" });
        await ctx.editMessageReplyMarkup({ reply_markup: void 0 });
        return;
      }
      if (data === "send_cancel") {
        await ctx.answerCallbackQuery({ text: "취소됨" });
        await ctx.editMessageReplyMarkup({ reply_markup: void 0 });
        return;
      }
      await ctx.answerCallbackQuery();
    });
  }
  findNeedsInputAgent() {
    return this.store.getState().agents.find((a) => a.status === "needs_input") ?? null;
  }
  sendTextToSurface(surfaceId, text) {
    this.store.dispatch({
      type: "surface.send_text",
      payload: { surfaceId, text }
    });
  }
}
class BridgeWatcher {
  constructor(store2) {
    this.basePath = "";
    this.heartbeatTimer = null;
    this.scanTimer = null;
    this.activePollers = /* @__PURE__ */ new Map();
    this.store = store2;
  }
  // ── Lifecycle ────────────────────────────────────────────────────────
  start() {
    const settings = this.store.getState().settings.bridge;
    this.basePath = settings.basePath || path$1.join(os$1.homedir(), "cmux-bridge");
    this.ensureDirs();
    this.scanTimer = setInterval(() => this.scanInbox(), 1e3);
    const hbMs = settings.heartbeatIntervalSec * 1e3;
    this.heartbeatTimer = setInterval(() => this.writeHeartbeat(), hbMs);
    this.writeHeartbeat();
    console.warn(`[bridge] Watching ${path$1.join(this.basePath, "inbox")}`);
  }
  stop() {
    if (this.scanTimer) {
      clearInterval(this.scanTimer);
      this.scanTimer = null;
    }
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    for (const [, poller] of this.activePollers) {
      clearInterval(poller.timer);
    }
    this.activePollers.clear();
  }
  // ── Directory setup ──────────────────────────────────────────────────
  ensureDirs() {
    for (const dir of ["inbox", "outbox", "processed"]) {
      const p = path$1.join(this.basePath, dir);
      if (!fs$1.existsSync(p)) fs$1.mkdirSync(p, { recursive: true });
    }
  }
  // ── Inbox scanning ──────────────────────────────────────────────────
  scanInbox() {
    const inboxPath = path$1.join(this.basePath, "inbox");
    let files;
    try {
      files = fs$1.readdirSync(inboxPath).filter((f) => f.endsWith(".task.json"));
    } catch {
      return;
    }
    for (const file of files) {
      const filePath = path$1.join(inboxPath, file);
      const lockPath = filePath.replace(".task.json", `.${os$1.hostname()}.processing`);
      try {
        fs$1.renameSync(filePath, lockPath);
      } catch {
        continue;
      }
      try {
        const content = fs$1.readFileSync(lockPath, "utf8");
        const task = JSON.parse(content);
        this.processTask(task, lockPath);
      } catch (err) {
        console.error("[bridge] Failed to parse task:", err);
        this.writeResult({
          id: "parse-error",
          status: "error",
          output: `Parse error: ${err}`,
          started_at: (/* @__PURE__ */ new Date()).toISOString(),
          ended_at: (/* @__PURE__ */ new Date()).toISOString(),
          panel: -1
        });
        this.moveToProcessed(lockPath);
      }
    }
  }
  // ── Task processing ─────────────────────────────────────────────────
  processTask(task, lockPath) {
    const state = this.store.getState();
    const panel = state.panels.find((p) => p.paneIndex === task.target_panel);
    if (!panel) {
      this.writeResult({
        id: task.id,
        status: "error",
        output: `Panel %${task.target_panel} not found`,
        started_at: (/* @__PURE__ */ new Date()).toISOString(),
        ended_at: (/* @__PURE__ */ new Date()).toISOString(),
        panel: task.target_panel
      });
      this.moveToProcessed(lockPath);
      return;
    }
    const surfaceId = panel.activeSurfaceId;
    const startedAt = (/* @__PURE__ */ new Date()).toISOString();
    let prompt = task.prompt;
    if (task.mode === "leader") {
      prompt = "다음 작업을 수행해. 필요하면 tmux split-window -h로 다른 AI(gemini, codex)를 실행해서 협업해:\n" + prompt;
    }
    this.store.dispatch({
      type: "surface.send_text",
      payload: { surfaceId, text: prompt }
    });
    console.warn(`[bridge] Task ${task.id} → panel %${task.target_panel} (${task.mode})`);
    setTimeout(() => {
      this.store.dispatch({
        type: "surface.send_text",
        payload: { surfaceId, text: "\r" }
      });
      setTimeout(() => {
        this.startPolling(
          task.id,
          surfaceId,
          startedAt,
          task.timeout_sec,
          lockPath,
          task.target_panel
        );
      }, 3e3);
    }, 500);
  }
  // ── Result polling (polled-diff pattern — buffer overflow safe) ─────
  startPolling(taskId, surfaceId, startedAt, timeoutSec, lockPath, panelIndex) {
    const pollMs = this.store.getState().settings.bridge.pollIntervalSec * 1e3;
    const deadline = Date.now() + timeoutSec * 1e3;
    const liveBuffers2 = globalThis.__cmuxLiveBuffers;
    const poller = {
      timer: null,
      lastRawLength: (liveBuffers2?.get(surfaceId) ?? "").length,
      lastNewOutputTime: Date.now()
    };
    poller.timer = setInterval(() => {
      const buf = liveBuffers2?.get(surfaceId) ?? "";
      if (buf.length !== poller.lastRawLength) {
        poller.lastNewOutputTime = Date.now();
        poller.lastRawLength = buf.length;
      }
      const clean = stripAnsiEscapes(buf);
      const tail = clean.split("\n").slice(-50).join("\n");
      const hasMarker = tail.includes("===BRIDGE_DONE===") || tail.includes("===END===") || tail.includes("작업완료");
      const isIdle = Date.now() - poller.lastNewOutputTime > 3e3;
      const isTimeout = Date.now() > deadline;
      if (hasMarker && isIdle || isTimeout) {
        clearInterval(poller.timer);
        this.activePollers.delete(taskId);
        const trimmedOutput = clean.split("\n").slice(-200).join("\n").trim();
        this.writeResult({
          id: taskId,
          status: isTimeout ? "timeout" : "completed",
          output: trimmedOutput,
          started_at: startedAt,
          ended_at: (/* @__PURE__ */ new Date()).toISOString(),
          panel: panelIndex
        });
        this.moveToProcessed(lockPath);
        console.warn(
          `[bridge] Task ${taskId} ${isTimeout ? "timed out" : "completed"} (${Math.round((Date.now() - new Date(startedAt).getTime()) / 1e3)}s)`
        );
      }
    }, pollMs);
    this.activePollers.set(taskId, poller);
  }
  // ── Result writing ──────────────────────────────────────────────────
  writeResult(result) {
    const outPath = path$1.join(this.basePath, "outbox", `${result.id}.result.json`);
    try {
      fs$1.writeFileSync(outPath, JSON.stringify(result, null, 2));
    } catch (err) {
      console.error("[bridge] Failed to write result:", err);
    }
  }
  moveToProcessed(lockPath) {
    const dest = path$1.join(this.basePath, "processed", path$1.basename(lockPath));
    try {
      fs$1.renameSync(lockPath, dest);
    } catch {
      try {
        fs$1.unlinkSync(lockPath);
      } catch {
      }
    }
  }
  // ── Heartbeat ───────────────────────────────────────────────────────
  writeHeartbeat() {
    const state = this.store.getState();
    const heartbeat = {
      alive: true,
      ts: (/* @__PURE__ */ new Date()).toISOString(),
      hostname: os$1.hostname(),
      panels: state.panels.map((p) => ({
        index: p.paneIndex,
        type: p.panelType,
        surface: p.activeSurfaceId
      })),
      agents: state.agents.map((a) => ({
        type: a.agentType,
        status: a.status,
        surface: a.surfaceId
      }))
    };
    try {
      fs$1.writeFileSync(
        path$1.join(this.basePath, "heartbeat.json"),
        JSON.stringify(heartbeat, null, 2)
      );
    } catch {
    }
  }
}
process.on("uncaughtException", (err) => {
  if (err.message?.includes("AttachConsole")) {
    console.warn("[cmux-win] ConPTY AttachConsole error (ignored):", err.message);
    return;
  }
  console.error("[cmux-win] Uncaught exception:", err);
  throw err;
});
const gotSingleInstanceLock = electron.app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  electron.app.quit();
}
const sessionFilePath = path.join(electron.app.getPath("appData"), "cmux-win", "session.json");
const debugLogPath = path.join(electron.app.getPath("temp"), "cmux-win-debug.log");
let initialState;
let lastWindowGeometry;
const persisted = loadPersistedState(sessionFilePath);
if (persisted) {
  const migrated = migrateState(persisted, sessionFilePath);
  lastWindowGeometry = migrated.state.windows[0]?.geometry;
  const mergedSettings = { ...DEFAULT_SETTINGS, ...migrated.state.settings };
  initialState = {
    ...migrated.state,
    settings: mergedSettings,
    windows: [],
    agents: [],
    workspaces: [],
    panels: [],
    surfaces: []
  };
}
const scrollbackPath = path.join(
  process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"),
  "cmux-win",
  "scrollback.json"
);
const scrollbackStore = /* @__PURE__ */ new Map();
globalThis.__cmuxScrollbackStore = scrollbackStore;
let scrollbackSaveTimer = null;
try {
  const raw = fs.readFileSync(scrollbackPath, "utf8");
  const data = JSON.parse(raw);
  for (const [k, v] of Object.entries(data)) scrollbackStore.set(k, v);
} catch {
}
const store = new AppStateStore(initialState);
const validationMw = new ValidationMiddleware();
const sideEffectsMw = new SideEffectsMiddleware((effect) => {
  store.emit("side-effect", effect);
});
const persistenceMw = new PersistenceMiddleware(sessionFilePath, SESSION_SAVE_DEBOUNCE_MS);
const ipcBroadcastMw = new IpcBroadcastMiddleware();
const auditLogMw = new AuditLogMiddleware(debugLogPath);
store.use(validationMw);
store.use(sideEffectsMw);
store.use(persistenceMw);
store.use(ipcBroadcastMw);
store.use(auditLogMw);
registerIpcHandlers(store);
registerPtyHandlers();
electron.ipcMain.on("window:minimize", (event) => {
  electron.BrowserWindow.fromWebContents(event.sender)?.minimize();
});
electron.ipcMain.on("window:maximize", (event) => {
  const win = electron.BrowserWindow.fromWebContents(event.sender);
  if (win?.isMaximized()) win.unmaximize();
  else win?.maximize();
});
electron.ipcMain.on("window:close", (event) => {
  electron.BrowserWindow.fromWebContents(event.sender)?.close();
});
electron.ipcMain.handle("cmux:open-external", async (_event, url) => {
  const { shell } = await import("electron");
  return shell.openExternal(url);
});
electron.ipcMain.handle("cmux:open-path", async (_event, filePath) => {
  const { shell } = await import("electron");
  const cleanPath = filePath.replace(/:\d+$/, "");
  return shell.openPath(cleanPath);
});
const windowManager = new WindowManager();
let appTray = null;
const telegramBot = new TelegramBotService(store);
store.on(
  "side-effect",
  (effect) => {
    if (effect.type === "pty-write" && effect.surfaceId && effect.text !== void 0) {
      writeToPty(effect.surfaceId, effect.text);
    }
    if (effect.type === "notification-created") {
      const title = effect.title || "cmux-win";
      const body = effect.body || "";
      showToast(title, body);
      if (appTray) {
        const unread = computeUnreadCount(store.getState().notifications);
        appTray.setToolTip(formatTrayTitle(unread));
      }
      telegramBot.sendNotification(title, body, {
        workspaceId: effect.workspaceId,
        surfaceId: effect.surfaceId
      }).catch((err) => console.warn("[telegram] send failed:", err.message));
    }
  }
);
ptyEvents.on("pty-exit", (surfaceId, exitInfo) => {
  const state = store.getState();
  const agent = state.agents.find((a) => a.surfaceId === surfaceId);
  if (agent) {
    store.dispatch({
      type: "agent.status_update",
      payload: {
        sessionId: agent.sessionId,
        status: exitInfo.exitCode === 0 ? "done" : "error",
        icon: exitInfo.exitCode === 0 ? "✅" : "❌",
        color: exitInfo.exitCode === 0 ? "#4CAF50" : "#F44336"
      }
    });
  }
  store.dispatch({
    type: "surface.update_meta",
    payload: { surfaceId, terminal: { exitCode: exitInfo.exitCode } }
  });
});
const router = new JsonRpcRouter();
registerSystemHandlers(router, store);
registerWindowHandlers(router, store);
registerWorkspaceHandlers(router, store);
registerPanelHandlers(router, store);
registerSurfaceHandlers(router, store);
registerAgentHandlers(router, store);
registerNotificationHandlers(router, store, electron.app.getPath("userData"));
registerSettingsHandlers(router, store);
registerBrowserHandlers(router);
registerWorkflowHandlers(router, store);
const socketServer = new SocketApiServer(router, store.getState().settings.socket.mode);
let historyDb = null;
async function createWindow() {
  const win = new electron.BrowserWindow({
    width: lastWindowGeometry?.width ?? 1200,
    height: lastWindowGeometry?.height ?? 800,
    x: lastWindowGeometry?.x,
    y: lastWindowGeometry?.y,
    center: !lastWindowGeometry,
    show: false,
    title: "cmux-win",
    frame: false,
    backgroundColor: "#272822",
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webviewTag: true
    }
  });
  store.dispatch({ type: "window.create", payload: {} });
  const windowId = store.getState().windows.at(-1).id;
  windowManager.register(windowId, win, () => {
    ipcBroadcastMw.unregisterWindow(windowId);
  });
  ipcBroadcastMw.registerWindow(windowId, win, () => {
    windowManager.unregister(windowId);
  });
  attachShortcutInterceptor(win);
  return new Promise((resolve) => {
    win.webContents.on("console-message", (_event, level, message, line, sourceId) => {
      if (level >= 2) {
        console.warn(`[Renderer:${level}] ${message} (${sourceId}:${line})`);
      }
    });
    win.webContents.on("did-finish-load", () => {
      win.webContents.send(IPC_CHANNELS.WINDOW_ID, windowId);
      win.show();
      resolve(win);
    });
    const rendererUrl = process.env.ELECTRON_RENDERER_URL;
    if (rendererUrl) {
      win.loadURL(rendererUrl);
    } else {
      win.loadFile(path.join(__dirname, "../renderer/index.html"));
    }
  });
}
electron.app.whenReady().then(async () => {
  electron.app.setAppUserModelId("com.cmux-win.app");
  try {
    const historyPath = path.join(electron.app.getPath("appData"), "cmux-win", "history.db");
    historyDb = new HistoryDb(historyPath);
  } catch (err) {
    console.error("[cmux-win] Failed to init history DB:", err);
  }
  if (historyDb) {
    electron.ipcMain.handle(
      "browser:history:query",
      (_, args) => historyDb.query(args.profileId, args.prefix, args.limit)
    );
    electron.ipcMain.handle(
      "browser:history:add",
      (_, args) => historyDb.add(args.profileId, args.url, args.title, args.faviconUrl)
    );
    electron.ipcMain.handle(
      "browser:history:clear",
      (_, args) => historyDb.clear(args.profileId)
    );
  }
  electron.ipcMain.on(IPC_CHANNELS.SCROLLBACK_SAVE, (_event, surfaceId, content) => {
    scrollbackStore.set(surfaceId, content);
    if (scrollbackSaveTimer) clearTimeout(scrollbackSaveTimer);
    scrollbackSaveTimer = setTimeout(() => {
      try {
        const dir = path.dirname(scrollbackPath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        const tmp = scrollbackPath + ".tmp";
        fs.writeFileSync(tmp, JSON.stringify(Object.fromEntries(scrollbackStore)));
        fs.renameSync(tmp, scrollbackPath);
      } catch (err) {
        console.error("[cmux-win] scrollback save error:", err);
      }
    }, 5e3);
  });
  electron.ipcMain.handle(IPC_CHANNELS.SCROLLBACK_LOAD, (_event, surfaceId) => {
    return scrollbackStore.get(surfaceId) ?? null;
  });
  electron.ipcMain.handle(IPC_CHANNELS.FILE_READ, async (_event, filePath) => {
    try {
      if (!path.isAbsolute(filePath)) {
        return { error: "Only absolute file paths are allowed" };
      }
      const content = await fs.promises.readFile(filePath, "utf8");
      return { content };
    } catch (err) {
      return { error: err instanceof Error ? err.message : "Failed to read file" };
    }
  });
  electron.ipcMain.handle(IPC_CHANNELS.FILE_LIST_DIR, async (_event, dirPath) => {
    try {
      if (!path.isAbsolute(dirPath)) {
        return { error: "Only absolute paths are allowed" };
      }
      const dirents = await fs.promises.readdir(dirPath, { withFileTypes: true });
      const entries = dirents.map((d) => ({
        name: d.name,
        isDirectory: d.isDirectory(),
        path: path.join(dirPath, d.name)
      }));
      entries.sort((a, b) => {
        if (a.isDirectory !== b.isDirectory) return a.isDirectory ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      return { entries };
    } catch (err) {
      return { error: err instanceof Error ? err.message : "Failed to list directory" };
    }
  });
  const fileWatchers = /* @__PURE__ */ new Map();
  electron.ipcMain.on(IPC_CHANNELS.FILE_WATCH, (event, filePath) => {
    if (fileWatchers.has(filePath)) return;
    try {
      const watcher = fs.watch(filePath, { persistent: false }, () => {
        event.sender.send(IPC_CHANNELS.FILE_CHANGED, filePath);
      });
      watcher.on("error", () => {
        fileWatchers.delete(filePath);
      });
      fileWatchers.set(filePath, watcher);
    } catch {
    }
  });
  electron.ipcMain.on(IPC_CHANNELS.FILE_UNWATCH, (_event, filePath) => {
    const watcher = fileWatchers.get(filePath);
    if (watcher) {
      watcher.close();
      fileWatchers.delete(filePath);
    }
  });
  electron.ipcMain.handle(IPC_CHANNELS.DIALOG_OPEN_FOLDER, async () => {
    const win2 = electron.BrowserWindow.getFocusedWindow();
    const result = await electron.dialog.showOpenDialog(win2, { properties: ["openDirectory"] });
    if (result.canceled || result.filePaths.length === 0) {
      return { cancelled: true };
    }
    return { path: result.filePaths[0] };
  });
  const telegramAppDataDir = electron.app.getPath("userData");
  const telegramSettings = store.getState().settings.telegram;
  const telegramToken = loadBotToken(telegramAppDataDir);
  void telegramBot.configure(telegramSettings, telegramToken).catch((err) => {
    console.error("[telegram] Failed to start bot:", err.message);
  });
  store.on("change", (action) => {
    if (action?.type === "settings.update") {
      const newSettings = store.getState().settings.telegram;
      const token = loadBotToken(telegramAppDataDir);
      void telegramBot.configure(newSettings, token).catch((err) => {
        console.error("[telegram] Failed to reconfigure bot:", err.message);
      });
    }
  });
  const bridgeWatcher2 = new BridgeWatcher(store);
  if (store.getState().settings.bridge.enabled) {
    bridgeWatcher2.start();
  }
  store.on("change", (action) => {
    if (action?.type === "settings.update") {
      const bridgeSettings = store.getState().settings.bridge;
      bridgeWatcher2.stop();
      if (bridgeSettings.enabled) {
        bridgeWatcher2.start();
      }
    }
  });
  createTelemetryConfig(store.getState().settings.telemetry.enabled);
  const updateConfig = createUpdateConfig(
    store.getState().settings.updates.channel,
    store.getState().settings.updates.autoCheck
  );
  void initAutoUpdater(updateConfig);
  try {
    const actualPort = await socketServer.start(DEFAULT_SOCKET_PORT);
    process.env.CMUX_SOCKET_PORT = String(actualPort);
    const srcBinDir = path.join(__dirname, "../../resources/bin");
    const safeBinDir = path.join(os.homedir(), ".cmux-win", "bin");
    try {
      if (!fs.existsSync(safeBinDir)) fs.mkdirSync(safeBinDir, { recursive: true });
      for (const f of [
        "tmux.cmd",
        "tmux-shim.js",
        "claude.cmd",
        "claude-wrapper.js",
        "claude-wrapper-lib.js",
        "cmux.cmd",
        "cmux-cli.js"
      ]) {
        const src = path.join(srcBinDir, f);
        const dst = path.join(safeBinDir, f);
        if (fs.existsSync(src)) fs.copyFileSync(src, dst);
      }
      const srcShellDir = path.join(__dirname, "../../resources/shell-integration");
      const dstShellDir = path.join(os.homedir(), ".cmux-win", "shell-integration");
      try {
        const copyRecursive = (src, dst) => {
          const stat = fs.statSync(src);
          if (stat.isDirectory()) {
            if (!fs.existsSync(dst)) fs.mkdirSync(dst, { recursive: true });
            for (const f of fs.readdirSync(src))
              copyRecursive(path.join(src, f), path.join(dst, f));
          } else {
            fs.copyFileSync(src, dst);
          }
        };
        if (fs.existsSync(srcShellDir)) copyRecursive(srcShellDir, dstShellDir);
      } catch (err) {
        console.error("[cmux-win] Failed to copy shell-integration files:", err);
      }
      const bashShimContent = '#!/usr/bin/env node\nconst path = require("path");\nrequire(path.join(__dirname, "tmux-shim.js"));\n';
      const bashShim = path.join(safeBinDir, "tmux");
      fs.writeFileSync(bashShim, bashShimContent);
      try {
        fs.chmodSync(bashShim, 493);
      } catch {
      }
      const userBinDir = path.join(os.homedir(), "bin");
      try {
        if (!fs.existsSync(userBinDir)) fs.mkdirSync(userBinDir, { recursive: true });
        fs.writeFileSync(path.join(userBinDir, "tmux"), bashShimContent);
        fs.copyFileSync(
          path.join(safeBinDir, "tmux-shim.js"),
          path.join(userBinDir, "tmux-shim.js")
        );
        try {
          fs.chmodSync(path.join(userBinDir, "tmux"), 493);
        } catch {
        }
      } catch (err) {
        console.error("[cmux-win] Failed to copy shims to ~/bin/:", err);
      }
    } catch (err) {
      console.error("[cmux-win] Failed to copy shim files:", err);
    }
    process.env.CMUX_BIN_DIR = safeBinDir;
    const srcCliPath = path.join(__dirname, "../cli/cmux-win.js");
    const safeCliPath = path.join(os.homedir(), ".cmux-win", "cli", "cmux-win.js");
    try {
      const cliDir = path.dirname(safeCliPath);
      if (!fs.existsSync(cliDir)) fs.mkdirSync(cliDir, { recursive: true });
      if (fs.existsSync(srcCliPath)) fs.copyFileSync(srcCliPath, safeCliPath);
    } catch {
    }
    process.env.CMUX_CLI_PATH = fs.existsSync(safeCliPath) ? safeCliPath : srcCliPath;
    console.warn(`[cmux-win] Socket API listening on port ${actualPort}`);
    console.warn(`[cmux-win] Bin dir: ${safeBinDir}`);
    const tokenPath = path.join(electron.app.getPath("userData"), "socket-token");
    const tokenTmp = tokenPath + ".tmp";
    fs.writeFileSync(tokenTmp, `${process.env.CMUX_SOCKET_TOKEN}
${actualPort}`);
    fs.renameSync(tokenTmp, tokenPath);
    try {
      const mcpSrc = path.join(__dirname, "../../resources/mcp/cmux-mcp-server.js");
      const mcpDst = path.join(os.homedir(), ".cmux-win", "mcp", "cmux-mcp-server.js");
      const mcpDir = path.dirname(mcpDst);
      if (!fs.existsSync(mcpDir)) fs.mkdirSync(mcpDir, { recursive: true });
      if (fs.existsSync(mcpSrc)) fs.copyFileSync(mcpSrc, mcpDst);
      const configPaths = [];
      const roaming = process.env.APPDATA || "";
      const local = process.env.LOCALAPPDATA || "";
      const stdPath = path.join(roaming, "Claude", "claude_desktop_config.json");
      if (fs.existsSync(stdPath)) configPaths.push(stdPath);
      try {
        for (const d of fs.readdirSync(path.join(local, "Packages"))) {
          if (!d.startsWith("Claude_")) continue;
          const p = path.join(
            local,
            "Packages",
            d,
            "LocalCache",
            "Roaming",
            "Claude",
            "claude_desktop_config.json"
          );
          if (fs.existsSync(p)) configPaths.push(p);
        }
      } catch {
      }
      for (const cfgPath of configPaths) {
        const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
        if (!cfg.mcpServers) cfg.mcpServers = {};
        const newEntry = { command: "node", args: [mcpDst.replace(/\\/g, "/")] };
        const existing = cfg.mcpServers["cmux-win"];
        if (JSON.stringify(existing) !== JSON.stringify(newEntry)) {
          cfg.mcpServers["cmux-win"] = newEntry;
          fs.writeFileSync(cfgPath, JSON.stringify(cfg, null, 2));
          console.warn(`[cmux-win] MCP server registered → ${cfgPath}`);
        } else {
          console.warn(`[cmux-win] MCP config unchanged, skip write → ${cfgPath}`);
        }
      }
    } catch (mcpErr) {
      console.warn("[cmux-win] MCP auto-register skipped:", mcpErr.message);
    }
  } catch (err) {
    console.error("[cmux-win] Failed to start socket server:", err);
  }
  setInterval(() => {
    const agents = store.getState().agents;
    for (const agent of agents) {
      if (!agent.pid) continue;
      const status = checkPidStatus(agent.pid);
      if (status === "dead") {
        store.dispatch({
          type: "agent.session_end",
          payload: { sessionId: agent.sessionId }
        });
      }
    }
  }, 1e4);
  const win = await createWindow();
  const windowId = store.getState().windows.at(-1).id;
  const iconPath = path.join(__dirname, "../../resources/icon.png");
  const trayIcon = fs.existsSync(iconPath) ? electron.nativeImage.createFromPath(iconPath) : electron.nativeImage.createEmpty();
  const tray = new electron.Tray(trayIcon);
  tray.setToolTip(formatTrayTitle(0));
  tray.setContextMenu(
    electron.Menu.buildFromTemplate([
      { label: "Show", click: () => win.show() },
      { label: "Quit", click: () => electron.app.quit() }
    ])
  );
  appTray = tray;
  store.adoptOrphanWorkspaces(windowId);
  electron.app.on("second-instance", () => {
    const wins = electron.BrowserWindow.getAllWindows();
    if (wins.length > 0) {
      if (wins[0].isMinimized()) wins[0].restore();
      wins[0].focus();
    }
  });
  electron.app.on("activate", () => {
    if (electron.BrowserWindow.getAllWindows().length === 0) {
      void createWindow();
    }
  });
});
store.on("change", (action) => {
  if (action?.type === "surface.close" && action?.payload?.surfaceId) {
    scrollbackStore.delete(action.payload.surfaceId);
  }
});
electron.app.on("before-quit", () => {
  telegramBot.stop();
  bridgeWatcher.stop();
  try {
    const tokenPath = path.join(electron.app.getPath("userData"), "socket-token");
    if (fs.existsSync(tokenPath)) fs.unlinkSync(tokenPath);
  } catch {
  }
  try {
    const dir = path.dirname(scrollbackPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(scrollbackPath, JSON.stringify(Object.fromEntries(scrollbackStore)));
  } catch {
  }
});
electron.app.on("window-all-closed", () => {
  killAllPty();
  persistenceMw.dispose();
  historyDb?.close();
  socketServer.stop().catch((err) => {
    console.error("[cmux-win] Error stopping socket server:", err);
  });
  electron.app.quit();
});
