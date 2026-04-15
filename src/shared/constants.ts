import type { SettingsState } from './types';

export const SCHEMA_VERSION = 1;
export const DEFAULT_SOCKET_PORT = 19840;
export const MAX_SOCKET_PORT_RETRIES = 10;
export const SESSION_SAVE_DEBOUNCE_MS = 500;
export const IPC_BROADCAST_DEBOUNCE_MS = 16;
export const AGENT_PID_CHECK_INTERVAL_MS = 5000;
export const AGENT_SESSION_TTL_DAYS = 7;
export const STATE_HISTORY_MAX = 100;
export const PTY_RESTART_MAX_RETRIES = 3;
export const SESSION_BACKUP_SUFFIX = '.bak';

export const DEFAULT_SETTINGS: SettingsState = {
  appearance: { theme: 'system', language: 'system', iconMode: 'auto' },
  terminal: {
    defaultShell: 'powershell',
    fontSize: 14,
    fontFamily: 'Consolas',
    themeName: 'Dracula',
    cursorStyle: 'block',
  },
  browser: {
    searchEngine: 'google',
    searchSuggestions: true,
    httpAllowlist: ['localhost', '127.0.0.1', '::1'],
    externalUrlPatterns: [],
  },
  socket: { mode: 'automation', port: DEFAULT_SOCKET_PORT },
  agents: {
    claudeHooksEnabled: true,
    codexHooksEnabled: true,
    geminiHooksEnabled: true,
    orchestrationMode: 'auto',
    autoStartClaude: true,
  },
  telegram: {
    enabled: false,
    chatId: '',
    forwardNotifications: true,
    remoteControl: true,
  },
  telemetry: { enabled: true },
  updates: { autoCheck: true, channel: 'stable' },
  accessibility: { screenReaderMode: false, reducedMotion: false },
};
