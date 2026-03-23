import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

export function registerAgentHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('agent.spawn', (params) => {
    const p = params as { agentType: string; workspaceId: string; task?: string };
    if (!p?.agentType) throw new Error('agentType is required');
    if (!p?.workspaceId) throw new Error('workspaceId is required');

    // Snapshot panel count before spawn to identify newly created panel
    const panelsBefore = store.getState().panels.length;

    const result = store.dispatch({
      type: 'agent.spawn',
      payload: {
        agentType: p.agentType,
        workspaceId: p.workspaceId,
        task: p.task,
      },
    });
    if (!result.ok) throw new Error(result.error ?? 'Failed to spawn agent');

    // GAP-3: return the new panel's paneIndex and surfaceId
    const newPanels = store.getState().panels.slice(panelsBefore);
    const newPanel = newPanels[0];
    return {
      ok: true,
      paneIndex: newPanel?.paneIndex,
      panelId: newPanel?.id,
      surfaceId: newPanel?.activeSurfaceId,
    };
  });

  router.register('agent.session_start', (params) => {
    const p = params as {
      sessionId: string;
      agentType: 'claude' | 'codex' | 'gemini' | 'opencode';
      workspaceId: string;
      surfaceId: string;
      pid?: number;
    };
    if (!p?.sessionId) throw new Error('sessionId is required');
    if (!p?.agentType) throw new Error('agentType is required');
    if (!p?.workspaceId) throw new Error('workspaceId is required');
    if (!p?.surfaceId) throw new Error('surfaceId is required');
    const result = store.dispatch({
      type: 'agent.session_start',
      payload: {
        sessionId: p.sessionId,
        agentType: p.agentType,
        workspaceId: p.workspaceId,
        surfaceId: p.surfaceId,
        pid: p.pid,
      },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to start agent session');
    }
    return { ok: true };
  });

  router.register('agent.status_update', (params) => {
    const p = params as {
      sessionId: string;
      status: 'running' | 'idle' | 'needs_input';
      icon?: string;
      color?: string;
    };
    if (!p?.sessionId) throw new Error('sessionId is required');
    if (!p?.status) throw new Error('status is required');
    const result = store.dispatch({
      type: 'agent.status_update',
      payload: {
        sessionId: p.sessionId,
        status: p.status,
        icon: p.icon,
        color: p.color,
      },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to update agent status');
    }
    return { ok: true };
  });

  router.register('agent.session_end', (params) => {
    const p = params as { sessionId: string };
    if (!p?.sessionId) throw new Error('sessionId is required');
    const result = store.dispatch({
      type: 'agent.session_end',
      payload: { sessionId: p.sessionId },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to end agent session');
    }
    return { ok: true };
  });
}
