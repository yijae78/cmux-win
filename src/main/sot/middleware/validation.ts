import type { Middleware } from '../store';
import type { Action } from '../../../shared/actions';
import type { AppState } from '../../../shared/types';

/**
 * ValidationMiddleware: rejects close actions when the target entity doesn't exist.
 */
export class ValidationMiddleware implements Middleware {
  beforeMutation(
    action: Action,
    state: Readonly<AppState>,
  ): { abort?: boolean; reason?: string } {
    switch (action.type) {
      case 'workspace.close': {
        const exists = state.workspaces.some(
          (ws) => ws.id === action.payload.workspaceId,
        );
        if (!exists) {
          return {
            abort: true,
            reason: `Workspace not found: ${action.payload.workspaceId}`,
          };
        }
        break;
      }
      case 'window.close': {
        const exists = state.windows.some(
          (w) => w.id === action.payload.windowId,
        );
        if (!exists) {
          return {
            abort: true,
            reason: `Window not found: ${action.payload.windowId}`,
          };
        }
        break;
      }
      case 'surface.close': {
        const exists = state.surfaces.some(
          (s) => s.id === action.payload.surfaceId,
        );
        if (!exists) {
          return {
            abort: true,
            reason: `Surface not found: ${action.payload.surfaceId}`,
          };
        }
        break;
      }
    }
    return {};
  }
}
