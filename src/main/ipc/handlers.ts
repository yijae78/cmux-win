/**
 * IPC handlers — registers Electron ipcMain handlers for the store.
 *
 * This file ONLY runs in the Electron main process.
 */
import { ipcMain } from 'electron';
import { IPC_CHANNELS } from '../../shared/ipc-channels';
import type { AppStateStore } from '../sot/store';
import type { AppState } from '../../shared/types';

export function registerIpcHandlers(store: AppStateStore): void {
  ipcMain.handle(IPC_CHANNELS.DISPATCH, (_event, rawAction: unknown) => {
    return store.dispatch(rawAction);
  });

  ipcMain.handle(
    IPC_CHANNELS.QUERY_STATE,
    (_event, query: { slice: string }) => {
      const state = store.getState() as Record<string, unknown>;
      return state[query.slice];
    },
  );

  ipcMain.handle(IPC_CHANNELS.GET_INITIAL_STATE, () => {
    return store.getState();
  });
}
