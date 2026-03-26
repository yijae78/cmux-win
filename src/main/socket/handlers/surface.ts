import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

// BUG-D + F4-FIX: strip ANSI/CSI and OSC escape sequences from raw PTY output.
// CSI: \x1b[ ... finalByte    (colors, cursor, etc.)
// OSC: \x1b] ... ST           (title, CWD, prompt markers — \x07 or \x1b\\)
// Simple escapes: \x1b followed by single char (e.g. \x1b=, \x1b>)
// eslint-disable-next-line no-control-regex
const ANSI_RE = /[\x1b\x9b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nq-uy=><~]/g;
// eslint-disable-next-line no-control-regex
const OSC_RE = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g;
// eslint-disable-next-line no-control-regex
const SIMPLE_ESC_RE = /\x1b[=>#(AB]/g;
function stripAnsiEscapes(s: string): string {
  return s.replace(OSC_RE, '').replace(ANSI_RE, '').replace(SIMPLE_ESC_RE, '');
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
}
