import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

/**
 * Panel handlers.
 * BUG-18: panel.close properly cleans up surfaces associated with the panel.
 */
export function registerPanelHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('panel.list', () => {
    return { panels: store.getState().panels };
  });

  router.register('panel.focus', (params) => {
    const p = params as { panelId: string };
    if (!p?.panelId) throw new Error('panelId is required');
    const result = store.dispatch({
      type: 'panel.focus',
      payload: { panelId: p.panelId },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to focus panel');
    }
    return { ok: true };
  });

  router.register('panel.split', (params) => {
    const p = params as { panelId: string; direction: string; newPanelType?: string };
    if (!p?.panelId) throw new Error('panelId is required');
    if (!p?.direction) throw new Error('direction is required');

    const panelsBefore = store.getState().panels.length;

    const result = store.dispatch({
      type: 'panel.split',
      payload: {
        panelId: p.panelId,
        direction: p.direction as 'horizontal' | 'vertical',
        newPanelType: (p.newPanelType as 'terminal' | 'browser' | 'markdown') ?? 'terminal',
      },
    });
    if (!result.ok) throw new Error(result.error ?? 'Failed to split panel');

    // GAP-3: return new panel info so split-window can report the pane_id
    const newPanels = store.getState().panels.slice(panelsBefore);
    const newPanel = newPanels[0];
    return {
      ok: true,
      paneIndex: newPanel?.paneIndex,
      panelId: newPanel?.id,
      surfaceId: newPanel?.activeSurfaceId,
    };
  });

  router.register('panel.resize', (params) => {
    const p = params as { panelId: string; ratio: number };
    if (!p?.panelId) throw new Error('panelId is required');
    if (p?.ratio === undefined) throw new Error('ratio is required');
    const result = store.dispatch({
      type: 'panel.resize',
      payload: { panelId: p.panelId, ratio: p.ratio },
    });
    if (!result.ok) throw new Error(result.error ?? 'Failed to resize panel');
    return { ok: true };
  });

  router.register('panel.zoom', (params) => {
    const p = params as { panelId: string };
    if (!p?.panelId) throw new Error('panelId is required');
    const result = store.dispatch({
      type: 'panel.zoom',
      payload: { panelId: p.panelId },
    });
    if (!result.ok) throw new Error(result.error ?? 'Failed to zoom panel');
    return { ok: true };
  });

  /**
   * BUG-18: panel.close dispatches panel.close action which also removes
   * associated surfaces from state (handled in store reducer).
   */
  router.register('panel.close', (params) => {
    const p = params as { panelId: string };
    if (!p?.panelId) throw new Error('panelId is required');
    const result = store.dispatch({
      type: 'panel.close',
      payload: { panelId: p.panelId },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to close panel');
    }
    return { ok: true };
  });
}
