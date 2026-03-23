import { describe, it, expect, beforeEach } from 'vitest';
import { AppStateStore } from '../../../src/main/sot/store';
import { createDefaultState } from '../../../src/main/sot/create-default-state';
import type { AppState } from '../../../src/shared/types';

function stateWithWorkspace(): AppState {
  const state = createDefaultState();
  state.windows.push({
    id: 'win-1',
    workspaceIds: ['ws-1'],
    geometry: { x: 0, y: 0, width: 1200, height: 800 },
    isActive: true,
  });
  state.workspaces.push({
    id: 'ws-1',
    windowId: 'win-1',
    name: 'Test',
    panelLayout: { type: 'leaf', panelId: 'panel-1' },
    agentPids: {},
    statusEntries: [],
    unreadCount: 0,
    isPinned: false,
  });
  state.panels.push({
    id: 'panel-1',
    workspaceId: 'ws-1',
    panelType: 'terminal',
    surfaceIds: ['surf-1'],
    activeSurfaceId: 'surf-1',
    isZoomed: false,
  });
  state.surfaces.push({
    id: 'surf-1',
    panelId: 'panel-1',
    surfaceType: 'terminal',
    title: 'Terminal',
  });
  return state;
}

describe('agent.spawn', () => {
  let store: AppStateStore;

  beforeEach(() => {
    store = new AppStateStore(stateWithWorkspace());
  });

  it('creates new panel and surface', () => {
    store.dispatch({
      type: 'agent.spawn',
      payload: { agentType: 'claude', workspaceId: 'ws-1' },
    });
    expect(store.getState().panels.length).toBe(2);
    expect(store.getState().surfaces.length).toBe(2);
  });

  it('adds split to panelLayout', () => {
    store.dispatch({
      type: 'agent.spawn',
      payload: { agentType: 'claude', workspaceId: 'ws-1' },
    });
    const ws = store.getState().workspaces[0];
    expect(ws.panelLayout.type).toBe('split');
  });

  it('registers agent in agents[]', () => {
    store.dispatch({
      type: 'agent.spawn',
      payload: { agentType: 'codex', workspaceId: 'ws-1' },
    });
    expect(store.getState().agents.length).toBe(1);
    expect(store.getState().agents[0].agentType).toBe('codex');
    expect(store.getState().agents[0].status).toBe('running');
  });

  it('sets pendingCommand on new surface', () => {
    store.dispatch({
      type: 'agent.spawn',
      payload: { agentType: 'claude', workspaceId: 'ws-1', task: 'write tests' },
    });
    const newSurface = store.getState().surfaces.find((s) => s.title === 'claude agent');
    expect(newSurface?.pendingCommand).toBe('claude "write tests"\n');
  });

  it('sets default pendingCommand without task', () => {
    store.dispatch({
      type: 'agent.spawn',
      payload: { agentType: 'gemini', workspaceId: 'ws-1' },
    });
    const newSurface = store.getState().surfaces.find((s) => s.title === 'gemini agent');
    expect(newSurface?.pendingCommand).toBe('gemini\n');
  });

  it('ignores nonexistent workspaceId', () => {
    const before = store.getState();
    store.dispatch({
      type: 'agent.spawn',
      payload: { agentType: 'claude', workspaceId: 'nonexistent' },
    });
    expect(store.getState().panels.length).toBe(before.panels.length);
  });
});
