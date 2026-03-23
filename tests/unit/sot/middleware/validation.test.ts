import { describe, it, expect, beforeEach } from 'vitest';
import { AppStateStore } from '../../../../src/main/sot/store';
import { ValidationMiddleware } from '../../../../src/main/sot/middleware/validation';

describe('ValidationMiddleware', () => {
  let store: AppStateStore;

  beforeEach(() => {
    store = new AppStateStore();
    store.use(new ValidationMiddleware());
  });

  it('aborts workspace.close when workspace not found', () => {
    const result = store.dispatch({
      type: 'workspace.close',
      payload: { workspaceId: 'nonexistent-ws' },
    });
    expect(result.ok).toBe(false);
    expect(result.error).toContain('Workspace not found');
  });

  it('allows workspace.close when workspace exists', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;
    store.dispatch({
      type: 'workspace.create',
      payload: { windowId: winId, name: 'Test WS' },
    });
    const wsId = store.getState().workspaces[0].id;

    const result = store.dispatch({
      type: 'workspace.close',
      payload: { workspaceId: wsId },
    });
    expect(result.ok).toBe(true);
    expect(store.getState().workspaces).toHaveLength(0);
  });

  it('aborts window.close when window not found', () => {
    const result = store.dispatch({
      type: 'window.close',
      payload: { windowId: 'nonexistent-win' },
    });
    expect(result.ok).toBe(false);
    expect(result.error).toContain('Window not found');
  });

  it('allows window.close when window exists', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;

    const result = store.dispatch({
      type: 'window.close',
      payload: { windowId: winId },
    });
    expect(result.ok).toBe(true);
    expect(store.getState().windows).toHaveLength(0);
  });

  it('aborts surface.close when surface not found', () => {
    const result = store.dispatch({
      type: 'surface.close',
      payload: { surfaceId: 'nonexistent-surface' },
    });
    expect(result.ok).toBe(false);
    expect(result.error).toContain('Surface not found');
  });

  it('allows surface.close when surface exists', () => {
    // Create window + workspace (which auto-creates a panel and surface)
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;
    store.dispatch({
      type: 'workspace.create',
      payload: { windowId: winId },
    });
    const surfaceId = store.getState().surfaces[0].id;

    const result = store.dispatch({
      type: 'surface.close',
      payload: { surfaceId },
    });
    expect(result.ok).toBe(true);
    expect(store.getState().surfaces).toHaveLength(0);
  });

  it('does not interfere with unrelated actions', () => {
    const result = store.dispatch({ type: 'window.create', payload: {} });
    expect(result.ok).toBe(true);
    expect(store.getState().windows).toHaveLength(1);
  });
});
