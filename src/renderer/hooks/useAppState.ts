/**
 * useAppState — React hook that subscribes to the full AppState.
 *
 * Fetches initial state on mount, then merges incremental slice updates
 * received via STATE_UPDATE IPC.
 */
import { useState, useEffect } from 'react';
import type { AppState } from '../../shared/types';

export function useAppState(): AppState | null {
  const [state, setState] = useState<AppState | null>(null);

  useEffect(() => {
    // Standalone mode — no Electron IPC
    if (typeof window.cmuxIpc === 'undefined') return;

    // Fetch initial state
    window.cmuxIpc.getInitialState().then((initial) => {
      setState(initial as AppState);
    });

    // Subscribe to incremental updates
    const unsubscribe = window.cmuxIpc.onStateUpdate((slice: string, data: unknown) => {
      setState((prev) => {
        if (!prev) return prev;
        return { ...prev, [slice]: data };
      });
    });

    return unsubscribe;
  }, []);

  return state;
}
