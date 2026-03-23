import type { BrowserWindow } from 'electron';
import { DEFAULT_SHORTCUTS, matchInput } from '../../shared/shortcuts';
import { IPC_CHANNELS } from '../../shared/ipc-channels';

export function attachShortcutInterceptor(win: BrowserWindow): void {
  win.webContents.on('before-input-event', (event, input) => {
    if (input.type !== 'keyDown') return;

    const shortcutId = matchInput(input, DEFAULT_SHORTCUTS);
    if (shortcutId) {
      event.preventDefault();
      win.webContents.send(IPC_CHANNELS.SHORTCUT, shortcutId);
    }
  });
}
