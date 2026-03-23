/**
 * GAP-I: Performance benchmarks for SOT dispatch latency.
 *
 * Run with: npx vitest bench
 */
import { bench, describe } from 'vitest';
import { AppStateStore } from '../../src/main/sot/store';

describe('Performance', () => {
  bench('SOT dispatch latency', () => {
    const store = new AppStateStore();
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;
    store.dispatch({ type: 'workspace.create', payload: { windowId: winId, name: 'bench' } });
  });

  bench('notification create 100x', () => {
    const store = new AppStateStore();
    for (let i = 0; i < 100; i++) {
      store.dispatch({ type: 'notification.create', payload: { title: `N${i}` } });
    }
  });
});
