import { describe, it, expect } from 'vitest';
import { AppStateStore } from '../../../src/main/sot/store';
import { createDefaultState } from '../../../src/main/sot/create-default-state';

describe('surface.update_meta', () => {
  function makeStore() {
    const state = createDefaultState();
    state.surfaces.push({ id: 'sf-1', panelId: 'p-1', surfaceType: 'terminal', title: 'Terminal' });
    return new AppStateStore(state);
  }

  it('updates title', () => {
    const store = makeStore();
    store.dispatch({
      type: 'surface.update_meta',
      payload: { surfaceId: 'sf-1', title: 'New Title' },
    });
    expect(store.getState().surfaces[0].title).toBe('New Title');
  });

  it('updates terminal.cwd', () => {
    const store = makeStore();
    store.dispatch({
      type: 'surface.update_meta',
      payload: { surfaceId: 'sf-1', terminal: { cwd: '/home/user' } },
    });
    expect(store.getState().surfaces[0].terminal?.cwd).toBe('/home/user');
  });

  it('updates terminal.gitBranch', () => {
    const store = makeStore();
    store.dispatch({
      type: 'surface.update_meta',
      payload: { surfaceId: 'sf-1', terminal: { gitBranch: 'main', gitDirty: true } },
    });
    expect(store.getState().surfaces[0].terminal?.gitBranch).toBe('main');
    expect(store.getState().surfaces[0].terminal?.gitDirty).toBe(true);
  });

  it('clears pendingCommand with null', () => {
    const state = createDefaultState();
    state.surfaces.push({
      id: 'sf-1',
      panelId: 'p-1',
      surfaceType: 'terminal',
      title: 'T',
      pendingCommand: 'claude\n',
    });
    const store = new AppStateStore(state);
    store.dispatch({
      type: 'surface.update_meta',
      payload: { surfaceId: 'sf-1', pendingCommand: null },
    });
    expect(store.getState().surfaces[0].pendingCommand).toBeUndefined();
  });

  it('ignores nonexistent surfaceId', () => {
    const store = makeStore();
    store.dispatch({
      type: 'surface.update_meta',
      payload: { surfaceId: 'nonexistent', title: 'X' },
    });
    expect(store.getState().surfaces[0].title).toBe('Terminal');
  });
});
