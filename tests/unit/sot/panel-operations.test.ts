import { describe, it, expect, beforeEach } from 'vitest';
import { AppStateStore } from '../../../src/main/sot/store';
import { createDefaultState } from '../../../src/main/sot/create-default-state';
import type { AppState } from '../../../src/shared/types';

function stateWithWorkspace(): AppState {
  const state = createDefaultState();
  const winId = 'win-1';
  const wsId = 'ws-1';
  const panelId = 'panel-1';
  const surfaceId = 'surf-1';
  state.windows.push({
    id: winId,
    workspaceIds: [wsId],
    geometry: { x: 0, y: 0, width: 1200, height: 800 },
    isActive: true,
  });
  state.workspaces.push({
    id: wsId,
    windowId: winId,
    name: 'Test',
    panelLayout: { type: 'leaf', panelId },
    agentPids: {},
    statusEntries: [],
    unreadCount: 0,
    isPinned: false,
  });
  state.panels.push({
    id: panelId,
    workspaceId: wsId,
    panelType: 'terminal',
    surfaceIds: [surfaceId],
    activeSurfaceId: surfaceId,
    isZoomed: false,
  });
  state.surfaces.push({ id: surfaceId, panelId, surfaceType: 'terminal', title: 'Terminal' });
  return state;
}

describe('panel.split', () => {
  let store: AppStateStore;

  beforeEach(() => {
    store = new AppStateStore(stateWithWorkspace());
  });

  it('splits leaf into horizontal split with two children', () => {
    store.dispatch({
      type: 'panel.split',
      payload: { panelId: 'panel-1', direction: 'horizontal', newPanelType: 'terminal' },
    });
    const ws = store.getState().workspaces[0];
    expect(ws.panelLayout.type).toBe('split');
    if (ws.panelLayout.type === 'split') {
      expect(ws.panelLayout.direction).toBe('horizontal');
      expect(ws.panelLayout.ratio).toBe(0.5);
      expect(ws.panelLayout.children[0]).toEqual({ type: 'leaf', panelId: 'panel-1' });
      expect(ws.panelLayout.children[1].type).toBe('leaf');
    }
  });

  it('splits leaf into vertical split', () => {
    store.dispatch({
      type: 'panel.split',
      payload: { panelId: 'panel-1', direction: 'vertical', newPanelType: 'terminal' },
    });
    const ws = store.getState().workspaces[0];
    if (ws.panelLayout.type === 'split') {
      expect(ws.panelLayout.direction).toBe('vertical');
    }
  });

  it('creates nested split (split within split)', () => {
    store.dispatch({
      type: 'panel.split',
      payload: { panelId: 'panel-1', direction: 'horizontal', newPanelType: 'terminal' },
    });
    const ws1 = store.getState().workspaces[0];
    const newPanelId =
      ws1.panelLayout.type === 'split'
        ? (ws1.panelLayout.children[1] as { type: 'leaf'; panelId: string }).panelId
        : '';
    store.dispatch({
      type: 'panel.split',
      payload: { panelId: newPanelId, direction: 'vertical', newPanelType: 'terminal' },
    });
    const ws2 = store.getState().workspaces[0];
    // F11: rebuildEqualLayout creates balanced tree — 3 panels in a
    // split(split(leaf, leaf), leaf) structure with equal ratios
    if (ws2.panelLayout.type === 'split') {
      // Verify all 3 panels are in the layout
      const allLeafs: string[] = [];
      function collect(n: typeof ws2.panelLayout) {
        if (n.type === 'leaf') allLeafs.push(n.panelId);
        else n.children.forEach(collect);
      }
      collect(ws2.panelLayout);
      expect(allLeafs.length).toBe(3);
    }
  });

  it('creates new panel and surface', () => {
    const before = store.getState();
    store.dispatch({
      type: 'panel.split',
      payload: { panelId: 'panel-1', direction: 'horizontal', newPanelType: 'terminal' },
    });
    const after = store.getState();
    expect(after.panels.length).toBe(before.panels.length + 1);
    expect(after.surfaces.length).toBe(before.surfaces.length + 1);
  });

  it('does nothing for nonexistent panel', () => {
    const before = store.getState();
    store.dispatch({
      type: 'panel.split',
      payload: { panelId: 'nonexistent', direction: 'horizontal', newPanelType: 'terminal' },
    });
    const after = store.getState();
    expect(after.panels.length).toBe(before.panels.length);
  });
});

describe('panel.resize', () => {
  let store: AppStateStore;

  beforeEach(() => {
    store = new AppStateStore(stateWithWorkspace());
    store.dispatch({
      type: 'panel.split',
      payload: { panelId: 'panel-1', direction: 'horizontal', newPanelType: 'terminal' },
    });
  });

  it('changes ratio of split containing target panel', () => {
    store.dispatch({ type: 'panel.resize', payload: { panelId: 'panel-1', ratio: 0.7 } });
    const ws = store.getState().workspaces[0];
    if (ws.panelLayout.type === 'split') {
      expect(ws.panelLayout.ratio).toBe(0.7);
    }
  });

  it('clamps ratio to 0.1-0.9', () => {
    store.dispatch({ type: 'panel.resize', payload: { panelId: 'panel-1', ratio: 0.01 } });
    const ws = store.getState().workspaces[0];
    if (ws.panelLayout.type === 'split') {
      expect(ws.panelLayout.ratio).toBe(0.1);
    }
  });

  it('does nothing for leaf-only layout', () => {
    const freshStore = new AppStateStore(stateWithWorkspace());
    freshStore.dispatch({ type: 'panel.resize', payload: { panelId: 'panel-1', ratio: 0.7 } });
    const ws = freshStore.getState().workspaces[0];
    expect(ws.panelLayout.type).toBe('leaf');
  });
});

describe('panel.zoom', () => {
  it('toggles isZoomed on panel', () => {
    const store = new AppStateStore(stateWithWorkspace());
    expect(store.getState().panels[0].isZoomed).toBe(false);
    store.dispatch({ type: 'panel.zoom', payload: { panelId: 'panel-1' } });
    expect(store.getState().panels[0].isZoomed).toBe(true);
    store.dispatch({ type: 'panel.zoom', payload: { panelId: 'panel-1' } });
    expect(store.getState().panels[0].isZoomed).toBe(false);
  });
});

describe('panel.close (P2-BUG-8)', () => {
  it('removes leaf from panelLayout tree and promotes sibling', () => {
    const store = new AppStateStore(stateWithWorkspace());
    store.dispatch({
      type: 'panel.split',
      payload: { panelId: 'panel-1', direction: 'horizontal', newPanelType: 'terminal' },
    });
    const ws1 = store.getState().workspaces[0];
    const newPanelId =
      ws1.panelLayout.type === 'split'
        ? (ws1.panelLayout.children[1] as { type: 'leaf'; panelId: string }).panelId
        : '';
    store.dispatch({ type: 'panel.close', payload: { panelId: newPanelId } });
    const ws2 = store.getState().workspaces[0];
    expect(ws2.panelLayout).toEqual({ type: 'leaf', panelId: 'panel-1' });
  });
});

describe('surface.reorder', () => {
  it('moves surface to new index within panel', () => {
    const state = stateWithWorkspace();
    state.panels[0].surfaceIds = ['s1', 's2', 's3'];
    state.surfaces = [
      { id: 's1', panelId: 'panel-1', surfaceType: 'terminal', title: 'T1' },
      { id: 's2', panelId: 'panel-1', surfaceType: 'terminal', title: 'T2' },
      { id: 's3', panelId: 'panel-1', surfaceType: 'terminal', title: 'T3' },
    ];
    const store = new AppStateStore(state);
    store.dispatch({
      type: 'surface.reorder',
      payload: { surfaceId: 's3', panelId: 'panel-1', newIndex: 0 },
    });
    expect(store.getState().panels[0].surfaceIds).toEqual(['s3', 's1', 's2']);
  });
});

describe('workspace.reorder', () => {
  it('moves workspace to new index within window', () => {
    const state = stateWithWorkspace();
    state.windows[0].workspaceIds = ['ws-1', 'ws-2', 'ws-3'];
    const store = new AppStateStore(state);
    store.dispatch({
      type: 'workspace.reorder',
      payload: { workspaceId: 'ws-3', windowId: 'win-1', newIndex: 0 },
    });
    expect(store.getState().windows[0].workspaceIds).toEqual(['ws-3', 'ws-1', 'ws-2']);
  });
});
