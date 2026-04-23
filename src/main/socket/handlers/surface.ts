import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

// BUG-D + F4-FIX: strip ANSI/CSI and OSC escape sequences from raw PTY output.
// M8: Comprehensive ANSI stripping — CSI, OSC, DCS, charset, misc escapes, C0 controls
// eslint-disable-next-line no-control-regex
const CSI_RE = /\x1B\[[0-9;?]*[a-zA-Z]/g;
// eslint-disable-next-line no-control-regex
const OSC_RE = /\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)/g;
// eslint-disable-next-line no-control-regex
const DCS_RE = /\x1BP[^\x1B]*\x1B\\/g;
// eslint-disable-next-line no-control-regex
const CHARSET_RE = /\x1B[()][0-9A-B]/g;
// eslint-disable-next-line no-control-regex
const MISC_ESC_RE = /\x1B[>=<N~}{F|7-8]/g;
// eslint-disable-next-line no-control-regex
const C0_RE = /[\x00-\x08\x0B-\x0C\x0E-\x1F]/g;
function stripAnsiEscapes(s: string): string {
  return s.replace(OSC_RE, '').replace(DCS_RE, '').replace(CSI_RE, '')
    .replace(CHARSET_RE, '').replace(MISC_ESC_RE, '').replace(C0_RE, '');
}

export function registerSurfaceHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('surface.list', () => {
    return { surfaces: store.getState().surfaces };
  });

  router.register('surface.create', (params) => {
    const p = params as { panelId: string; surfaceType: 'terminal' | 'browser' | 'markdown' };
    if (!p?.panelId) throw new Error('panelId is required');
    const surfaceType = p.surfaceType ?? 'terminal';
    const result = store.dispatch({
      type: 'surface.create',
      payload: { panelId: p.panelId, surfaceType },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to create surface');
    }
    const surfaces = store.getState().surfaces;
    return { surface: surfaces[surfaces.length - 1] };
  });

  router.register('surface.close', (params) => {
    const p = params as { surfaceId: string };
    if (!p?.surfaceId) throw new Error('surfaceId is required');
    const result = store.dispatch({
      type: 'surface.close',
      payload: { surfaceId: p.surfaceId },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to close surface');
    }
    return { ok: true };
  });

  router.register('surface.focus', (params) => {
    const p = params as { surfaceId: string };
    if (!p?.surfaceId) throw new Error('surfaceId is required');
    const result = store.dispatch({
      type: 'surface.focus',
      payload: { surfaceId: p.surfaceId },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to focus surface');
    }
    return { ok: true };
  });

  router.register('surface.send_text', (params) => {
    const p = params as { surfaceId: string; text: string };
    if (!p?.surfaceId) throw new Error('surfaceId is required');
    if (p.text === undefined || p.text === null) throw new Error('text is required');
    const result = store.dispatch({
      type: 'surface.send_text',
      payload: { surfaceId: p.surfaceId, text: p.text },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to send text');
    }
    return { ok: true };
  });

  // R6: surface.read — read scrollback content (used by tmux capture-pane)
  // BUG-D fix: prefer live PTY buffer (real-time) over scrollbackStore (30s stale).
  router.register('surface.read', (params) => {
    const p = params as { surfaceId: string; lines?: number };
    if (!p?.surfaceId) throw new Error('surfaceId is required');

    const g = globalThis as Record<string, unknown>;
    const liveBuffers = g.__cmuxLiveBuffers as Map<string, string> | undefined;
    const scrollbackStore = g.__cmuxScrollbackStore as Map<string, string> | undefined;

    // Live buffer has real-time raw PTY output; scrollbackStore is renderer-processed
    // (clean text, no ANSI escapes). Prefer live buffer for freshness.
    const liveRaw = liveBuffers?.get(p.surfaceId);
    const content = liveRaw
      ? stripAnsiEscapes(liveRaw)
      : (scrollbackStore?.get(p.surfaceId) ?? '');

    if (p.lines && p.lines > 0) {
      const allLines = content.split('\n');
      return { content: allLines.slice(-p.lines).join('\n') };
    }
    return { content };
  });

  // L3: surface.health — PTY status + agent info
  router.register('surface.health', (params) => {
    const p = params as { surfaceId: string };
    if (!p?.surfaceId) throw new Error('surfaceId is required');

    const state = store.getState();
    const surface = state.surfaces.find((s) => s.id === p.surfaceId);
    if (!surface) throw new Error('Surface not found');

    const g = globalThis as Record<string, unknown>;
    const liveBuffers = g.__cmuxLiveBuffers as Map<string, string> | undefined;
    const liveBuffer = liveBuffers?.get(p.surfaceId);

    const agent = state.agents.find((a) => a.surfaceId === p.surfaceId);

    return {
      surfaceId: p.surfaceId,
      surfaceType: surface.surfaceType,
      title: surface.title,
      hasPty: !!liveBuffer,
      bufferSize: liveBuffer?.length ?? 0,
      terminal: surface.terminal,
      agent: agent
        ? {
            sessionId: agent.sessionId,
            agentType: agent.agentType,
            status: agent.status,
            lastActivity: agent.lastActivity,
          }
        : null,
    };
  });
}
