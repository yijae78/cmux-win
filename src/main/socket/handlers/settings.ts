import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

/**
 * Settings handlers.
 * BUG-18: settings.update validates partial settings and applies them safely.
 */
export function registerSettingsHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('settings.get', () => {
    return { settings: store.getState().settings };
  });

  /**
   * BUG-18: settings.update accepts a partial settings object and merges
   * it into the current settings via the store's settings.update action.
   */
  router.register('settings.update', (params) => {
    const p = params as Record<string, unknown>;
    if (!p || typeof p !== 'object' || Object.keys(p).length === 0) {
      throw new Error('settings object is required');
    }
    const result = store.dispatch({
      type: 'settings.update',
      payload: p,
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to update settings');
    }
    return { settings: store.getState().settings };
  });
}
