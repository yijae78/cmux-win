/**
 * useDispatch — React hook that dispatches actions via the preload bridge.
 *
 * Note: Does NOT import IPC_CHANNELS — calls through window.cmuxIpc.dispatch() instead.
 */
import { useCallback } from 'react';
import type { Action } from '../../shared/actions';

declare global {
  interface Window {
    cmuxIpc: {
      dispatch(action: Action): Promise<{ ok: boolean; error?: string }>;
      queryState(query: { slice: string }): Promise<unknown>;
      getInitialState(): Promise<unknown>;
      onStateUpdate(callback: (slice: string, data: unknown) => void): () => void;
    };
  }
}

export function useDispatch() {
  return useCallback((action: Action) => {
    if (typeof window.cmuxIpc === 'undefined') {
      // Standalone mode — no Electron
      console.log('[standalone dispatch]', action.type);
      return Promise.resolve({ ok: true });
    }
    return window.cmuxIpc.dispatch(action);
  }, []);
}
