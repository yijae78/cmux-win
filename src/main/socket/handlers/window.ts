import { BrowserWindow } from 'electron';
import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

export function registerWindowHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('window.list', () => {
    return { windows: store.getState().windows };
  });

  router.register('window.current', () => {
    const state = store.getState();
    const activeId = state.focus.activeWindowId;
    const window = activeId ? (state.windows.find((w) => w.id === activeId) ?? null) : null;
    return { window };
  });

  router.register('window.create', (params) => {
    const p = (params ?? {}) as {
      geometry?: { x: number; y: number; width: number; height: number };
    };
    const result = store.dispatch({ type: 'window.create', payload: { geometry: p.geometry } });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to create window');
    }
    const windows = store.getState().windows;
    return { window: windows[windows.length - 1] };
  });

  router.register('window.move', (params) => {
    const p = params as { x: number; y: number; width?: number; height?: number };
    if (p?.x === undefined || p?.y === undefined) throw new Error('x and y are required');
    const wins = BrowserWindow.getAllWindows();
    if (wins.length === 0) throw new Error('No window found');
    const win = wins[0];
    const width = p.width ?? win.getBounds().width;
    const height = p.height ?? win.getBounds().height;
    win.setBounds({ x: p.x, y: p.y, width, height });
    return { ok: true, bounds: win.getBounds() };
  });

  router.register('window.close', (params) => {
    const p = params as { windowId: string };
    if (!p?.windowId) throw new Error('windowId is required');
    const result = store.dispatch({ type: 'window.close', payload: { windowId: p.windowId } });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to close window');
    }
    return { ok: true };
  });
}
