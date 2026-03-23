import type { Middleware } from '../store';
import type { Action } from '../../../shared/actions';
import type { AppState } from '../../../shared/types';

/**
 * Side-effect event payload types.
 * BUG-12: No EventEmitter inheritance. Uses callback pattern instead.
 */
export interface SideEffectEvent {
  type: string;
  [key: string]: unknown;
}

export type SideEffectCallback = (event: SideEffectEvent) => void;

export class SideEffectsMiddleware implements Middleware {
  private callback: SideEffectCallback;

  constructor(callback: SideEffectCallback) {
    this.callback = callback;
  }

  afterMutation(
    action: Action,
    _prevState: Readonly<AppState>,
    nextState: Readonly<AppState>,
  ): void {
    switch (action.type) {
      case 'workspace.create': {
        // Find the newly created workspace (last one matching the windowId)
        const workspaces = nextState.workspaces.filter(
          (ws) => ws.windowId === action.payload.windowId,
        );
        const created = workspaces[workspaces.length - 1];
        this.callback({
          type: 'workspace-created',
          workspaceId: created?.id,
          windowId: action.payload.windowId,
          name: action.payload.name ?? 'New Workspace',
        });
        break;
      }
      case 'surface.close': {
        this.callback({
          type: 'surface-closed',
          surfaceId: action.payload.surfaceId,
        });
        break;
      }
      case 'workspace.close': {
        this.callback({
          type: 'workspace-closed',
          workspaceId: action.payload.workspaceId,
        });
        break;
      }
      case 'window.create': {
        const win = nextState.windows[nextState.windows.length - 1];
        this.callback({
          type: 'window-created',
          windowId: win?.id,
        });
        break;
      }
      case 'window.close': {
        this.callback({
          type: 'window-closed',
          windowId: action.payload.windowId,
        });
        break;
      }
      case 'notification.create': {
        this.callback({
          type: 'notification-created',
          title: action.payload.title,
          body: action.payload.body ?? '',
          surfaceId: action.payload.surfaceId,
          workspaceId: action.payload.workspaceId,
        });
        break;
      }
    }
  }
}
