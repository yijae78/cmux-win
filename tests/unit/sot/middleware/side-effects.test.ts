import { describe, it, expect, beforeEach, vi } from 'vitest';
import { AppStateStore } from '../../../../src/main/sot/store';
import {
  SideEffectsMiddleware,
  type SideEffectEvent,
} from '../../../../src/main/sot/middleware/side-effects';

describe('SideEffectsMiddleware', () => {
  let store: AppStateStore;
  let callback: ReturnType<typeof vi.fn<(event: SideEffectEvent) => void>>;

  beforeEach(() => {
    store = new AppStateStore();
    callback = vi.fn<(event: SideEffectEvent) => void>();
    store.use(new SideEffectsMiddleware(callback));
  });

  it('calls callback with workspace-created on workspace.create', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;

    store.dispatch({
      type: 'workspace.create',
      payload: { windowId: winId, name: 'My WS' },
    });

    expect(callback).toHaveBeenCalledTimes(2); // window-created + workspace-created
    const wsEvent = callback.mock.calls.find(
      (c) => (c[0] as SideEffectEvent).type === 'workspace-created',
    );
    expect(wsEvent).toBeDefined();
    const payload = wsEvent![0] as SideEffectEvent;
    expect(payload.type).toBe('workspace-created');
    expect(payload.windowId).toBe(winId);
    expect(payload.name).toBe('My WS');
    expect(payload.workspaceId).toBeDefined();
  });

  it('calls callback with surface-closed on surface.close', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;
    store.dispatch({
      type: 'workspace.create',
      payload: { windowId: winId },
    });
    const surfaceId = store.getState().surfaces[0].id;

    callback.mockClear();
    store.dispatch({
      type: 'surface.close',
      payload: { surfaceId },
    });

    expect(callback).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'surface-closed',
        surfaceId,
      }),
    );
  });

  it('calls callback with window-created on window.create', () => {
    store.dispatch({ type: 'window.create', payload: {} });

    expect(callback).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'window-created',
      }),
    );
  });

  it('calls callback with window-closed on window.close', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;

    callback.mockClear();
    store.dispatch({ type: 'window.close', payload: { windowId: winId } });

    expect(callback).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'window-closed',
        windowId: winId,
      }),
    );
  });

  it('does not use EventEmitter inheritance (BUG-12)', () => {
    const mw = new SideEffectsMiddleware(callback);
    // SideEffectsMiddleware should NOT have EventEmitter methods
    expect('on' in mw).toBe(false);
    expect('emit' in mw).toBe(false);
    expect('addListener' in mw).toBe(false);
  });
});
