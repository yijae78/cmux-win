import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';
import { ptyEvents } from '../../terminal/pty-manager';

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
      status: 'running' | 'idle' | 'needs_input' | 'done' | 'error';
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

  // F8: Re-run agent in existing panel — sends a new CLI command to a surface
  // that has already completed (done/error). Resets agent status to running.
  router.register('agent.rerun', (params) => {
    const p = params as { surfaceId: string; task: string; agentType?: string };
    if (!p?.surfaceId) throw new Error('surfaceId is required');
    if (!p?.task) throw new Error('task is required');

    const state = store.getState();
    const surface = state.surfaces.find((s) => s.id === p.surfaceId);
    if (!surface) throw new Error('Surface not found');

    const agent = state.agents.find((a) => a.surfaceId === p.surfaceId);
    const agentType = p.agentType || agent?.agentType || 'gemini';

    // Build the CLI command based on agent type
    let cmd: string;
    if (agentType === 'gemini') {
      cmd = `gemini -p "${p.task.replace(/"/g, '\\"')}" -y`;
    } else if (agentType === 'codex') {
      cmd = `codex --full-auto "${p.task.replace(/"/g, '\\"')}"`;
    } else {
      cmd = `${agentType} "${p.task.replace(/"/g, '\\"')}"`;
    }

    // Send command to the surface's PTY (shell should be at prompt)
    store.dispatch({
      type: 'surface.send_text',
      payload: { surfaceId: p.surfaceId, text: cmd + '\r' },
    });

    // Update or create agent entry
    if (agent) {
      store.dispatch({
        type: 'agent.status_update',
        payload: {
          sessionId: agent.sessionId,
          status: 'running',
          icon: '⚡',
          color: '#4C8DFF',
        },
      });
    }

    return { ok: true, surfaceId: p.surfaceId };
  });

  // L10: agent.wait — block until PTY exits or timeout
  router.register('agent.wait', (params) => {
    const p = params as { surfaceId: string; timeout?: number };
    if (!p?.surfaceId) throw new Error('surfaceId is required');
    const timeoutMs = p.timeout ?? 300000; // 5 min default
    const startTime = Date.now();

    return new Promise((resolve) => {
      const onExit = (sid: string, exitInfo: { exitCode: number }) => {
        if (sid === p.surfaceId) {
          clearTimeout(timer);
          ptyEvents.removeListener('pty-exit', onExit);
          resolve({ exitCode: exitInfo.exitCode, elapsed: Date.now() - startTime, timeout: false });
        }
      };
      const timer = setTimeout(() => {
        ptyEvents.removeListener('pty-exit', onExit);
        resolve({ exitCode: null, elapsed: timeoutMs, timeout: true });
      }, timeoutMs);
      ptyEvents.on('pty-exit', onExit);

      // Check if already exited (agent status is done/error)
      const agent = store.getState().agents.find((a) => a.surfaceId === p.surfaceId);
      if (agent && (agent.status === 'done' || agent.status === 'error')) {
        clearTimeout(timer);
        ptyEvents.removeListener('pty-exit', onExit);
        resolve({ exitCode: agent.status === 'done' ? 0 : 1, elapsed: 0, timeout: false });
      }
    });
  });

  // L10: agent.output — read last N lines from agent's terminal
  router.register('agent.output', (params) => {
    const p = params as { surfaceId: string; lines?: number };
    if (!p?.surfaceId) throw new Error('surfaceId is required');
    const lines = p.lines ?? 50;

    const g = globalThis as Record<string, unknown>;
    const liveBuffers = g.__cmuxLiveBuffers as Map<string, string> | undefined;
    const scrollbackStore = g.__cmuxScrollbackStore as Map<string, string> | undefined;

    const liveRaw = liveBuffers?.get(p.surfaceId);
    // Strip ANSI escapes for clean text
    const ansiRe = /[\x1b\x9b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nq-uy=><~]/g;
    const oscRe = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g;
    const raw = liveRaw ?? scrollbackStore?.get(p.surfaceId) ?? '';
    const clean = raw.replace(oscRe, '').replace(ansiRe, '');
    const allLines = clean.split('\n');
    return { content: allLines.slice(-lines).join('\n') };
  });
}
