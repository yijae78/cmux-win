import { describe, it, expect, beforeEach, vi } from 'vitest';
import { AppStateStore } from '../../../../src/main/sot/store';
import {
  IpcBroadcastMiddleware,
  type BroadcastTarget,
} from '../../../../src/main/sot/middleware/ipc-broadcast';
import { IPC_CHANNELS } from '../../../../src/shared/ipc-channels';

function createMockTarget(): BroadcastTarget & { send: ReturnType<typeof vi.fn> } {
  const send = vi.fn();
  return {
    isDestroyed: () => false,
    webContents: { send },
    send,
  };
}

function createDestroyedTarget(): BroadcastTarget {
  return {
    isDestroyed: () => true,
    webContents: { send: vi.fn() },
  };
}

describe('IpcBroadcastMiddleware', () => {
  let store: AppStateStore;
  let mw: IpcBroadcastMiddleware;

  beforeEach(() => {
    store = new AppStateStore();
    mw = new IpcBroadcastMiddleware();
    store.use(mw);
  });

  it('broadcasts state slice to registered windows on dispatch', () => {
    const target = createMockTarget();
    const onClose = vi.fn();
    mw.registerWindow('win-1', target, onClose);

    store.dispatch({ type: 'window.create', payload: {} });

    // BUG-9: 'window' action type → 'windows' slice
    expect(target.send).toHaveBeenCalledWith(
      IPC_CHANNELS.STATE_UPDATE,
      'windows',
      store.getState().windows,
    );
  });

  it('broadcasts workspace slice for workspace actions', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;

    const target = createMockTarget();
    mw.registerWindow('win-1', target, vi.fn());

    store.dispatch({
      type: 'workspace.create',
      payload: { windowId: winId, name: 'Test' },
    });

    expect(target.send).toHaveBeenCalledWith(
      IPC_CHANNELS.STATE_UPDATE,
      'workspaces',
      store.getState().workspaces,
    );
  });

  it('sends to multiple registered windows', () => {
    const target1 = createMockTarget();
    const target2 = createMockTarget();
    mw.registerWindow('win-1', target1, vi.fn());
    mw.registerWindow('win-2', target2, vi.fn());

    store.dispatch({ type: 'window.create', payload: {} });

    expect(target1.send).toHaveBeenCalled();
    expect(target2.send).toHaveBeenCalled();
  });

  it('skips destroyed windows and calls onClose', () => {
    const destroyed = createDestroyedTarget();
    const onClose = vi.fn();
    mw.registerWindow('win-dead', destroyed, onClose);

    const alive = createMockTarget();
    mw.registerWindow('win-alive', alive, vi.fn());

    store.dispatch({ type: 'window.create', payload: {} });

    // Destroyed target should not receive send
    expect((destroyed.webContents.send as ReturnType<typeof vi.fn>)).not.toHaveBeenCalled();
    // Alive target should
    expect(alive.send).toHaveBeenCalled();
    // onClose callback should be called for destroyed window
    expect(onClose).toHaveBeenCalled();
  });

  it('does not import from electron (BUG-11)', async () => {
    // Verify the module source doesn't have actual import statements from electron
    const fs = await import('node:fs');
    const path = await import('node:path');
    const modulePath = path.resolve(
      __dirname,
      '../../../../src/main/sot/middleware/ipc-broadcast.ts',
    );
    const source = fs.readFileSync(modulePath, 'utf-8');
    // Check for actual import/require statements, not comments
    expect(source).not.toMatch(/^import\s.*from\s+['"]electron['"]/m);
    expect(source).not.toMatch(/require\(['"]electron['"]\)/);
  });

  it('unregisterWindow removes window and calls onClose', () => {
    const target = createMockTarget();
    const onClose = vi.fn();
    mw.registerWindow('win-1', target, onClose);

    mw.unregisterWindow('win-1');
    expect(onClose).toHaveBeenCalled();

    // After unregister, dispatch should not send to removed window
    target.send.mockClear();
    store.dispatch({ type: 'window.create', payload: {} });
    expect(target.send).not.toHaveBeenCalled();
  });

  it('maps focus.update to focus slice', () => {
    const target = createMockTarget();
    mw.registerWindow('win-1', target, vi.fn());

    store.dispatch({
      type: 'focus.update',
      payload: { activeWindowId: 'w-1' },
    });

    expect(target.send).toHaveBeenCalledWith(
      IPC_CHANNELS.STATE_UPDATE,
      'focus',
      store.getState().focus,
    );
  });
});
