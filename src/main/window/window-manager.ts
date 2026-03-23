/**
 * WindowManager — tracks BrowserWindow-like objects by windowId.
 *
 * IMPORTANT: This file must NOT import from 'electron'.
 * It uses a generic interface so it can be tested without Electron.
 */

export interface ManagedWindow {
  readonly id: number;
  isDestroyed(): boolean;
  webContents: {
    readonly id: number;
    send(channel: string, ...args: unknown[]): void;
  };
}

interface WindowEntry {
  windowId: string;
  win: ManagedWindow;
  onClose: () => void;
}

export class WindowManager {
  private entries = new Map<string, WindowEntry>();

  /**
   * Register a window with an associated windowId and close callback.
   */
  register(
    windowId: string,
    win: ManagedWindow,
    onClose: () => void,
  ): void {
    this.entries.set(windowId, { windowId, win, onClose });
  }

  /**
   * Get a managed window by its windowId.
   */
  get(windowId: string): ManagedWindow | undefined {
    return this.entries.get(windowId)?.win;
  }

  /**
   * Get all registered entries as an array of [windowId, ManagedWindow] tuples.
   */
  getAll(): Array<[string, ManagedWindow]> {
    return Array.from(this.entries.entries()).map(([id, entry]) => [
      id,
      entry.win,
    ]);
  }

  /**
   * Find a window entry by its webContents id.
   */
  findByWebContentsId(webContentsId: number): ManagedWindow | undefined {
    for (const entry of this.entries.values()) {
      if (entry.win.webContents.id === webContentsId) {
        return entry.win;
      }
    }
    return undefined;
  }

  /**
   * Unregister a window, invoking its onClose callback and removing it.
   */
  unregister(windowId: string): void {
    const entry = this.entries.get(windowId);
    if (entry) {
      entry.onClose();
      this.entries.delete(windowId);
    }
  }
}
