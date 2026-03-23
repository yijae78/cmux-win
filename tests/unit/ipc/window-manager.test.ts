import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  WindowManager,
  type ManagedWindow,
} from '../../../src/main/window/window-manager';

function createMockWindow(webContentsId: number): ManagedWindow {
  return {
    id: webContentsId + 1000,
    isDestroyed: () => false,
    webContents: {
      id: webContentsId,
      send: vi.fn(),
    },
  };
}

describe('WindowManager', () => {
  let manager: WindowManager;

  beforeEach(() => {
    manager = new WindowManager();
  });

  it('register + get returns the window', () => {
    const win = createMockWindow(1);
    const onClose = vi.fn();
    manager.register('win-1', win, onClose);

    expect(manager.get('win-1')).toBe(win);
  });

  it('get returns undefined for unknown windowId', () => {
    expect(manager.get('nonexistent')).toBeUndefined();
  });

  it('register + getAll returns all entries', () => {
    const win1 = createMockWindow(1);
    const win2 = createMockWindow(2);
    manager.register('win-1', win1, vi.fn());
    manager.register('win-2', win2, vi.fn());

    const all = manager.getAll();
    expect(all).toHaveLength(2);
    expect(all.map(([id]) => id).sort()).toEqual(['win-1', 'win-2']);
    expect(all.find(([id]) => id === 'win-1')![1]).toBe(win1);
    expect(all.find(([id]) => id === 'win-2')![1]).toBe(win2);
  });

  it('findByWebContentsId returns the correct window', () => {
    const win1 = createMockWindow(10);
    const win2 = createMockWindow(20);
    manager.register('win-1', win1, vi.fn());
    manager.register('win-2', win2, vi.fn());

    expect(manager.findByWebContentsId(20)).toBe(win2);
    expect(manager.findByWebContentsId(10)).toBe(win1);
    expect(manager.findByWebContentsId(99)).toBeUndefined();
  });

  it('unregister invokes onClose callback and removes entry', () => {
    const win = createMockWindow(1);
    const onClose = vi.fn();
    manager.register('win-1', win, onClose);

    expect(manager.get('win-1')).toBe(win);

    manager.unregister('win-1');

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(manager.get('win-1')).toBeUndefined();
  });

  it('unregister is a no-op for unknown windowId', () => {
    // Should not throw
    manager.unregister('nonexistent');
  });

  it('register replaces existing entry for same windowId', () => {
    const win1 = createMockWindow(1);
    const win2 = createMockWindow(2);
    const onClose1 = vi.fn();
    const onClose2 = vi.fn();

    manager.register('win-1', win1, onClose1);
    manager.register('win-1', win2, onClose2);

    expect(manager.get('win-1')).toBe(win2);
    expect(manager.getAll()).toHaveLength(1);
  });

  it('getAll returns empty array when no windows registered', () => {
    expect(manager.getAll()).toEqual([]);
  });
});
