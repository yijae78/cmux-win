import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

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
  router.register('surface.read', (params) => {
    const p = params as { surfaceId: string; lines?: number };
    if (!p?.surfaceId) throw new Error('surfaceId is required');
    // Read from scrollbackStore if available (populated by scrollback persistence)
    const scrollbackStore = (globalThis as Record<string, unknown>).__cmuxScrollbackStore as
      | Map<string, string>
      | undefined;
    const content = scrollbackStore?.get(p.surfaceId) ?? '';
    if (p.lines && p.lines > 0) {
      const allLines = content.split('\n');
      return { content: allLines.slice(-p.lines).join('\n') };
    }
    return { content };
  });
}
