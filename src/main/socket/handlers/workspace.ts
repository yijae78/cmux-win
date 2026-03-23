import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

export function registerWorkspaceHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('workspace.list', () => {
    return { workspaces: store.getState().workspaces };
  });

  router.register('workspace.current', () => {
    const state = store.getState();
    const activeId = state.focus.activeWorkspaceId;
    const workspace = activeId
      ? state.workspaces.find((ws) => ws.id === activeId) ?? null
      : null;
    return { workspace };
  });

  router.register('workspace.create', (params) => {
    const p = params as { windowId: string; name?: string; cwd?: string };
    if (!p?.windowId) throw new Error('windowId is required');
    const result = store.dispatch({
      type: 'workspace.create',
      payload: { windowId: p.windowId, name: p.name, cwd: p.cwd },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to create workspace');
    }
    const workspaces = store.getState().workspaces;
    return { workspace: workspaces[workspaces.length - 1] };
  });

  router.register('workspace.select', (params) => {
    const p = params as { workspaceId: string };
    if (!p?.workspaceId) throw new Error('workspaceId is required');
    const result = store.dispatch({
      type: 'workspace.select',
      payload: { workspaceId: p.workspaceId },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to select workspace');
    }
    return { ok: true };
  });

  router.register('workspace.close', (params) => {
    const p = params as { workspaceId: string };
    if (!p?.workspaceId) throw new Error('workspaceId is required');
    const result = store.dispatch({
      type: 'workspace.close',
      payload: { workspaceId: p.workspaceId },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to close workspace');
    }
    return { ok: true };
  });

  router.register('workspace.set_layout', (params) => {
    const p = params as { workspaceId: string; panelLayout: unknown };
    if (!p?.workspaceId) throw new Error('workspaceId is required');
    if (!p?.panelLayout) throw new Error('panelLayout is required');
    const result = store.dispatch({
      type: 'workspace.set_layout',
      payload: { workspaceId: p.workspaceId, panelLayout: p.panelLayout },
    });
    if (!result.ok) throw new Error(result.error ?? 'Failed to set layout');
    return { ok: true };
  });

  router.register('workspace.rename', (params) => {
    const p = params as { workspaceId: string; name: string };
    if (!p?.workspaceId) throw new Error('workspaceId is required');
    if (!p?.name) throw new Error('name is required');
    const result = store.dispatch({
      type: 'workspace.rename',
      payload: { workspaceId: p.workspaceId, name: p.name },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to rename workspace');
    }
    return { ok: true };
  });
}
