/**
 * Tray notification helpers — pure logic for computing unread counts
 * and formatting the tray title badge.
 *
 * The Electron Tray instance itself lives in main/index.ts; these helpers
 * are kept separate so they can be unit-tested without Electron imports.
 */

export function computeUnreadCount(
  notifications: ReadonlyArray<{ isRead: boolean }>,
): number {
  if (!notifications || notifications.length === 0) return 0;
  const count = notifications.filter((n) => !n.isRead).length;
  return Math.max(0, count);
}

export function formatTrayTitle(
  unreadCount: number,
  appName = 'cmux-win',
): string {
  if (unreadCount <= 0) return appName;
  return `(${unreadCount}) ${appName}`;
}
