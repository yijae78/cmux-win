import type { AppState } from '../../shared/types';
import { DEFAULT_SETTINGS } from '../../shared/constants';

export function createDefaultState(): AppState {
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
      focusTarget: null,
    },
  };
}
