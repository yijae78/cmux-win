import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AppStateStore } from '../../../src/main/sot/store';

describe('AppStateStore', () => {
  let store: AppStateStore;

  beforeEach(() => {
    store = new AppStateStore();
  });

  it('initializes with default state', () => {
    const state = store.getState();
    expect(state.windows).toEqual([]);
    expect(state.workspaces).toEqual([]);
    expect(state.settings.terminal.defaultShell).toBe('powershell');
  });

  // BUG-2: window.create
  it('dispatches window.create', () => {
    store.dispatch({
      type: 'window.create',
      payload: { geometry: { x: 0, y: 0, width: 1200, height: 800 } },
    });
    expect(store.getState().windows).toHaveLength(1);
    expect(store.getState().windows[0].isActive).toBe(true);
  });

  it('dispatches window.close', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;
    store.dispatch({ type: 'window.close', payload: { windowId: winId } });
    expect(store.getState().windows).toHaveLength(0);
  });

  it('workspace.create links to window', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;
    store.dispatch({ type: 'workspace.create', payload: { windowId: winId, name: 'Test' } });
    expect(store.getState().windows[0].workspaceIds).toHaveLength(1);
    expect(store.getState().workspaces[0].name).toBe('Test');
  });

  it('workspace CRUD', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;

    store.dispatch({ type: 'workspace.create', payload: { windowId: winId, name: 'WS' } });
    expect(store.getState().workspaces).toHaveLength(1);

    const wsId = store.getState().workspaces[0].id;
    store.dispatch({ type: 'workspace.rename', payload: { workspaceId: wsId, name: 'Renamed' } });
    expect(store.getState().workspaces[0].name).toBe('Renamed');

    store.dispatch({ type: 'workspace.select', payload: { workspaceId: wsId } });
    expect(store.getState().focus.activeWorkspaceId).toBe(wsId);

    store.dispatch({ type: 'workspace.close', payload: { workspaceId: wsId } });
    expect(store.getState().workspaces).toHaveLength(0);
  });

  it('rejects invalid action', () => {
    const result = store.dispatch({ type: 'invalid', payload: {} });
    expect(result.ok).toBe(false);
  });

  it('emits change event', () => {
    let emitted = false;
    store.on('change', () => {
      emitted = true;
    });
    store.dispatch({ type: 'window.create', payload: {} });
    expect(emitted).toBe(true);
  });

  it('maintains history', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    store.dispatch({ type: 'window.create', payload: {} });
    expect(store.getHistory()).toHaveLength(2);
  });

  it('agent CRUD', () => {
    store.dispatch({
      type: 'agent.session_start',
      payload: { sessionId: 'a1', agentType: 'claude', workspaceId: 'ws-1', surfaceId: 'sf-1' },
    });
    expect(store.getState().agents).toHaveLength(1);
    expect(store.getState().agents[0].status).toBe('running');

    store.dispatch({ type: 'agent.status_update', payload: { sessionId: 'a1', status: 'idle' } });
    expect(store.getState().agents[0].status).toBe('idle');

    store.dispatch({ type: 'agent.session_end', payload: { sessionId: 'a1' } });
    expect(store.getState().agents).toHaveLength(0);
  });

  it('notification CRUD', () => {
    store.dispatch({ type: 'notification.create', payload: { title: 'Hi' } });
    expect(store.getState().notifications).toHaveLength(1);
    store.dispatch({ type: 'notification.clear', payload: {} });
    expect(store.getState().notifications).toHaveLength(0);
  });

  // BUG-10: post middleware try-catch
  it('calls post middleware after successful dispatch', () => {
    const postFn = vi.fn();
    store.use({ post: postFn });
    store.dispatch({ type: 'window.create', payload: {} });
    expect(postFn).toHaveBeenCalledTimes(1);
  });

  it('does not call post middleware on validation failure', () => {
    const postFn = vi.fn();
    store.use({ post: postFn });
    store.dispatch({ type: 'invalid', payload: {} });
    expect(postFn).not.toHaveBeenCalled();
  });

  it('continues post middleware chain even if one throws (BUG-10)', () => {
    const order: string[] = [];
    store.use({
      post: () => {
        throw new Error('boom');
      },
    });
    store.use({
      post: () => {
        order.push('second');
      },
    });
    store.dispatch({ type: 'window.create', payload: {} });
    expect(order).toEqual(['second']);
  });

  // BUG-12: side-effect for surface.send_text
  it('emits side-effect for surface.send_text', () => {
    const handler = vi.fn();
    store.on('side-effect', handler);
    store.dispatch({
      type: 'surface.send_text',
      payload: { surfaceId: 's-1', text: 'hello' },
    });
    expect(handler).toHaveBeenCalledWith({
      type: 'pty-write',
      surfaceId: 's-1',
      text: 'hello',
    });
  });

  // BUG-14: adoptOrphanWorkspaces
  it('adoptOrphanWorkspaces reassigns orphan workspaces to new window', () => {
    // Simulate restored state with orphan workspace
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;
    store.dispatch({ type: 'workspace.create', payload: { windowId: winId, name: 'Orphan' } });

    // Simulate restart: remove old window, create new
    store.dispatch({ type: 'window.close', payload: { windowId: winId } });
    // workspace was also deleted by window.close — recreate for adoption test
    // Instead, test with a workspace that has a stale windowId
    const store2 = new AppStateStore({
      ...store.getState(),
      workspaces: [
        {
          id: 'ws-orphan',
          windowId: 'dead-window',
          name: 'Orphan',
          panelLayout: { type: 'leaf', panelId: 'p1' },
          agentPids: {},
          statusEntries: [],
          unreadCount: 0,
          isPinned: false,
        },
      ],
      windows: [],
    });

    store2.dispatch({ type: 'window.create', payload: {} });
    const newWinId = store2.getState().windows[0].id;
    store2.adoptOrphanWorkspaces(newWinId);

    expect(store2.getState().workspaces[0].windowId).toBe(newWinId);
    expect(store2.getState().windows[0].workspaceIds).toContain('ws-orphan');
  });

  // beforeMutation middleware
  it('beforeMutation can abort dispatch', () => {
    store.use({
      beforeMutation: () => ({ abort: true, reason: 'blocked' }),
    });
    const result = store.dispatch({ type: 'window.create', payload: {} });
    expect(result.ok).toBe(false);
    expect(result.error).toBe('blocked');
    expect(store.getState().windows).toHaveLength(0);
  });
});
