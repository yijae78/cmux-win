export interface PersistedState {
  version: number;
  state: AppState;
}

export interface AppState {
  windows: WindowState[];
  workspaces: WorkspaceState[];
  panels: PanelState[];
  surfaces: SurfaceState[];
  agents: AgentSessionState[];
  notifications: NotificationState[];
  settings: SettingsState;
  shortcuts: ShortcutState;
  focus: FocusState;
}

export interface WindowState {
  id: string;
  workspaceIds: string[];
  geometry: { x: number; y: number; width: number; height: number };
  isActive: boolean;
}

export interface WorkspaceState {
  id: string;
  windowId: string;
  name: string;
  color?: string;
  panelLayout: PanelLayoutTree;
  agentPids: Record<string, number>;
  statusEntries: StatusEntry[];
  unreadCount: number;
  isPinned: boolean;
  remoteSession?: RemoteSessionState;
}

export type PanelLayoutTree =
  | { type: 'leaf'; panelId: string }
  | {
      type: 'split';
      direction: 'horizontal' | 'vertical';
      ratio: number;
      children: [PanelLayoutTree, PanelLayoutTree];
    };

export interface PanelState {
  id: string;
  workspaceId: string;
  panelType: 'terminal' | 'browser' | 'markdown';
  surfaceIds: string[];
  activeSurfaceId: string;
  isZoomed: boolean;
  paneIndex?: number; // GAP-4: stable tmux pane index (survives panel close/reorder)
}

export interface SurfaceState {
  id: string;
  panelId: string;
  surfaceType: 'terminal' | 'browser' | 'markdown';
  title: string;
  terminal?: {
    pid: number;
    cwd: string;
    shell: string;
    gitBranch?: string;
    gitDirty?: boolean;
    exitCode?: number;
  };
  browser?: { url: string; profileId: string; isLoading: boolean };
  markdown?: { filePath: string };
  pendingCommand?: string; // agent.spawn: PTY ready 후 실행할 커맨드
}

export interface AgentSessionState {
  sessionId: string;
  agentType: 'claude' | 'codex' | 'gemini' | 'opencode';
  workspaceId: string;
  surfaceId: string;
  status: 'running' | 'idle' | 'needs_input';
  statusIcon: string;
  statusColor: string;
  pid?: number;
  lastActivity: number;
}

export interface NotificationState {
  id: string;
  workspaceId?: string;
  surfaceId?: string;
  title: string;
  subtitle?: string;
  body?: string;
  createdAt: number;
  isRead: boolean;
}

export interface StatusEntry {
  key: string;
  label: string;
  icon?: string;
  color?: string;
}

export interface FocusState {
  activeWindowId: string | null;
  activeWorkspaceId: string | null;
  activePanelId: string | null;
  activeSurfaceId: string | null;
  focusTarget:
    | 'terminal'
    | 'browser_webview'
    | 'browser_omnibar'
    | 'browser_find'
    | 'terminal_find'
    | null;
}

export interface SettingsState {
  appearance: {
    theme: 'system' | 'light' | 'dark';
    language: 'system' | 'en' | 'ko' | 'ja';
    iconMode: 'auto' | 'colorful' | 'monochrome';
  };
  terminal: {
    defaultShell: 'powershell' | 'cmd' | 'wsl' | 'git-bash';
    fontSize: number;
    fontFamily: string;
    themeName: string;
    cursorStyle: 'block' | 'underline' | 'bar';
  };
  browser: {
    searchEngine: 'google' | 'duckduckgo' | 'bing' | 'kagi' | 'startpage';
    searchSuggestions: boolean;
    httpAllowlist: string[];
    externalUrlPatterns: string[];
  };
  socket: {
    mode: 'off' | 'cmux-only' | 'automation' | 'password' | 'allow-all';
    port: number;
  };
  agents: {
    claudeHooksEnabled: boolean;
    codexHooksEnabled: boolean;
    geminiHooksEnabled: boolean;
    orchestrationMode: 'auto' | 'claude-teams' | 'self-managed';
  };
  telegram: {
    enabled: boolean;
    chatId: string;
    forwardNotifications: boolean;
    remoteControl: boolean;
    // botToken is NOT stored here — encrypted via safeStorage in separate file
  };
  telemetry: { enabled: boolean };
  updates: { autoCheck: boolean; channel: 'stable' | 'nightly' };
  accessibility: { screenReaderMode: boolean; reducedMotion: boolean };
}

export interface ShortcutState {
  shortcuts: Record<string, string>;
}

export interface RemoteSessionState {
  host: string;
  port: number;
  status: 'connecting' | 'connected' | 'disconnected' | 'error';
}
