import { z } from 'zod';

export const GeometrySchema = z.object({
  x: z.number(),
  y: z.number(),
  width: z.number().positive(),
  height: z.number().positive(),
});

export const WindowStateSchema = z.object({
  id: z.string().min(1),
  workspaceIds: z.array(z.string()),
  geometry: GeometrySchema,
  isActive: z.boolean(),
});

const PanelLayoutLeafSchema = z.object({ type: z.literal('leaf'), panelId: z.string() });
const PanelLayoutSplitSchema: z.ZodType<unknown> = z.lazy(() =>
  z.object({
    type: z.literal('split'),
    direction: z.enum(['horizontal', 'vertical']),
    ratio: z.number().min(0).max(1),
    children: z.tuple([PanelLayoutTreeSchema, PanelLayoutTreeSchema]),
  }),
);
export const PanelLayoutTreeSchema = z.union([PanelLayoutLeafSchema, PanelLayoutSplitSchema]);

export const StatusEntrySchema = z.object({
  key: z.string(),
  label: z.string(),
  icon: z.string().optional(),
  color: z.string().optional(),
});

export const WorkspaceStateSchema = z.object({
  id: z.string().min(1),
  windowId: z.string().min(1),
  name: z.string(),
  color: z.string().optional(),
  panelLayout: PanelLayoutTreeSchema,
  agentPids: z.record(z.string(), z.number()),
  statusEntries: z.array(StatusEntrySchema),
  unreadCount: z.number().int().min(0),
  isPinned: z.boolean(),
  remoteSession: z
    .object({
      host: z.string(),
      port: z.number(),
      status: z.enum(['connecting', 'connected', 'disconnected', 'error']),
    })
    .optional(),
});

export const PanelTypeEnum = z.enum(['terminal', 'browser', 'markdown']);

export const PanelStateSchema = z.object({
  id: z.string().min(1),
  workspaceId: z.string().min(1),
  panelType: PanelTypeEnum,
  surfaceIds: z.array(z.string()),
  activeSurfaceId: z.string(),
  isZoomed: z.boolean(),
});

export const SurfaceStateSchema = z.object({
  id: z.string().min(1),
  panelId: z.string().min(1),
  surfaceType: PanelTypeEnum,
  title: z.string(),
  terminal: z.object({ pid: z.number(), cwd: z.string(), shell: z.string() }).optional(),
  browser: z
    .object({ url: z.string(), profileId: z.string(), isLoading: z.boolean() })
    .optional(),
  markdown: z.object({ filePath: z.string() }).optional(),
});

export const AgentTypeEnum = z.enum(['claude', 'codex', 'gemini', 'opencode']);
export const AgentStatusEnum = z.enum(['running', 'idle', 'needs_input']);

export const AgentSessionStateSchema = z.object({
  sessionId: z.string().min(1),
  agentType: AgentTypeEnum,
  workspaceId: z.string(),
  surfaceId: z.string(),
  status: AgentStatusEnum,
  statusIcon: z.string(),
  statusColor: z.string(),
  pid: z.number().optional(),
  lastActivity: z.number(),
});

export const NotificationStateSchema = z.object({
  id: z.string().min(1),
  workspaceId: z.string().optional(),
  surfaceId: z.string().optional(),
  title: z.string(),
  subtitle: z.string().optional(),
  body: z.string().optional(),
  createdAt: z.number(),
  isRead: z.boolean(),
});

export const SettingsStateSchema = z.object({
  appearance: z.object({
    theme: z.enum(['system', 'light', 'dark']),
    language: z.enum(['system', 'en', 'ko', 'ja']),
    iconMode: z.enum(['auto', 'colorful', 'monochrome']),
  }),
  terminal: z.object({
    defaultShell: z.enum(['powershell', 'cmd', 'wsl', 'git-bash']),
    fontSize: z.number().int().min(6).max(72),
    fontFamily: z.string(),
    themeName: z.string(),
    cursorStyle: z.enum(['block', 'underline', 'bar']),
  }),
  browser: z.object({
    searchEngine: z.enum(['google', 'duckduckgo', 'bing', 'kagi', 'startpage']),
    searchSuggestions: z.boolean(),
    httpAllowlist: z.array(z.string()),
    externalUrlPatterns: z.array(z.string()),
  }),
  socket: z.object({
    mode: z.enum(['off', 'cmux-only', 'automation', 'password', 'allow-all']),
    port: z.number().int().min(1024).max(65535),
  }),
  agents: z.object({
    claudeHooksEnabled: z.boolean(),
    codexHooksEnabled: z.boolean(),
    geminiHooksEnabled: z.boolean(),
    orchestrationMode: z.enum(['auto', 'claude-teams', 'self-managed']),
  }),
  telemetry: z.object({ enabled: z.boolean() }),
  updates: z.object({ autoCheck: z.boolean(), channel: z.enum(['stable', 'nightly']) }),
  accessibility: z.object({ screenReaderMode: z.boolean(), reducedMotion: z.boolean() }),
});

export const FocusStateSchema = z.object({
  activeWindowId: z.string().nullable(),
  activeWorkspaceId: z.string().nullable(),
  activePanelId: z.string().nullable(),
  activeSurfaceId: z.string().nullable(),
  focusTarget: z
    .enum(['terminal', 'browser_webview', 'browser_omnibar', 'browser_find', 'terminal_find'])
    .nullable(),
});

export const AppStateSchema = z.object({
  windows: z.array(WindowStateSchema),
  workspaces: z.array(WorkspaceStateSchema),
  panels: z.array(PanelStateSchema),
  surfaces: z.array(SurfaceStateSchema),
  agents: z.array(AgentSessionStateSchema),
  notifications: z.array(NotificationStateSchema),
  settings: SettingsStateSchema,
  shortcuts: z.object({ shortcuts: z.record(z.string(), z.string()) }),
  focus: FocusStateSchema,
});

export const PersistedStateSchema = z.object({
  version: z.number().int().positive(),
  state: AppStateSchema,
});
