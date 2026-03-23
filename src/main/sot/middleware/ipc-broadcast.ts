import type { Middleware } from '../store';
import type { Action } from '../../../shared/actions';
import type { AppState } from '../../../shared/types';
import { IPC_CHANNELS } from '../../../shared/ipc-channels';

/**
 * BUG-11: DO NOT import from 'electron'. Use BroadcastTarget interface instead.
 */
export interface BroadcastTarget {
  isDestroyed(): boolean;
  webContents: {
    send(channel: string, ...args: unknown[]): void;
  };
}

interface RegisteredWindow {
  target: BroadcastTarget;
  onClose: () => void;
}

// BUG-9: sliceMap must include 'window' → 'windows'
const sliceMap: Record<string, keyof AppState> = {
  window: 'windows',
  workspace: 'workspaces',
  panel: 'panels',
  surface: 'surfaces',
  agent: 'agents',
  notification: 'notifications',
  focus: 'focus',
  settings: 'settings',
};

function getSlice(actionType: string): keyof AppState | null {
  const prefix = actionType.split('.')[0];
  return sliceMap[prefix] ?? null;
}

// Actions that modify multiple slices need to broadcast all affected slices
const multiSliceActions: Record<string, (keyof AppState)[]> = {
  'panel.resize': ['workspaces'],
  'panel.zoom': ['panels'],
  'panel.swap': ['workspaces'],
  'panel.split': ['panels', 'surfaces', 'workspaces', 'focus'],
  'panel.close': ['panels', 'surfaces', 'workspaces'],
  'workspace.create': ['workspaces', 'panels', 'surfaces', 'windows', 'focus'],
  'workspace.close': ['workspaces', 'panels', 'surfaces', 'windows', 'focus'],
  'surface.create': ['surfaces', 'panels'],
  'surface.close': ['surfaces', 'panels'],
  'agent.spawn': ['panels', 'surfaces', 'workspaces', 'agents'],
  'panel.move': ['panels', 'workspaces'],
};

export class IpcBroadcastMiddleware implements Middleware {
  private windows = new Map<string, RegisteredWindow>();

  registerWindow(windowId: string, target: BroadcastTarget, onClose: () => void): void {
    this.windows.set(windowId, { target, onClose });
  }

  unregisterWindow(windowId: string): void {
    const entry = this.windows.get(windowId);
    if (entry) {
      entry.onClose();
      this.windows.delete(windowId);
    }
  }

  post(action: Action, _prevState: Readonly<AppState>, nextState: Readonly<AppState>): void {
    // Determine which slices to broadcast
    const slices: (keyof AppState)[] =
      multiSliceActions[action.type] ?? (getSlice(action.type) ? [getSlice(action.type)!] : []);
    if (slices.length === 0) return;

    const destroyed: string[] = [];

    for (const [windowId, entry] of this.windows) {
      if (entry.target.isDestroyed()) {
        destroyed.push(windowId);
        continue;
      }
      for (const sliceKey of slices) {
        entry.target.webContents.send(IPC_CHANNELS.STATE_UPDATE, sliceKey, nextState[sliceKey]);
      }
    }

    // Cleanup destroyed windows
    for (const id of destroyed) {
      const entry = this.windows.get(id);
      if (entry) {
        entry.onClose();
        this.windows.delete(id);
      }
    }
  }
}
