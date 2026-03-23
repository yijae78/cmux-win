/**
 * Windows toast notification wrapper using Electron's Notification API.
 *
 * Runs in the main process only. Provides a simple `showToast` function
 * that creates and displays a native Windows notification with an optional
 * click handler (typically used to focus the relevant workspace window).
 */
import { BrowserWindow, Notification } from 'electron';

export interface ToastOptions {
  title: string;
  body: string;
  /** Called when the user clicks the toast notification. */
  onClick?: () => void;
}

/**
 * Show a native Windows toast notification.
 *
 * @param title  - Notification title (bold line)
 * @param body   - Notification body text
 * @param onClick - Optional callback invoked when the toast is clicked.
 *                  When omitted and a BrowserWindow exists, the first
 *                  visible window will be focused as a sensible default.
 */
export function showToast(title: string, body: string, onClick?: () => void): void {
  if (!Notification.isSupported()) return;

  const notification = new Notification({
    title,
    body: body || '',
    silent: false,
  });

  notification.on('click', () => {
    if (onClick) {
      onClick();
    } else {
      // Default: focus any existing window so the user sees the app
      focusFirstWindow();
    }
  });

  notification.show();
}

/**
 * Focus (and restore if minimized) the first BrowserWindow.
 * Useful as a default toast click handler.
 */
export function focusFirstWindow(): void {
  const wins = BrowserWindow.getAllWindows();
  if (wins.length === 0) return;
  const win = wins[0];
  if (win.isMinimized()) win.restore();
  win.focus();
}

/**
 * Focus a specific BrowserWindow by its Electron id.
 * Returns true if the window was found and focused.
 */
export function focusWindowById(electronWindowId: number): boolean {
  const win = BrowserWindow.fromId(electronWindowId);
  if (!win) return false;
  if (win.isMinimized()) win.restore();
  win.focus();
  return true;
}
