import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';
import { saveBotToken, loadBotToken, deleteBotToken } from '../../notifications/telegram-token-store';

/**
 * @param appDataDir - Pass app.getPath('userData') from caller to avoid
 *   importing 'electron' here (breaks vitest without Electron runtime).
 */
export function registerNotificationHandlers(
  router: JsonRpcRouter,
  store: AppStateStore,
  appDataDir?: string,
): void {
  // Telegram bot token management via safeStorage (C4: never in plain-text state)
  if (appDataDir) {
    router.register('telegram.set_token', (params) => {
      const p = params as { token: string };
      if (!p?.token) throw new Error('token is required');
      const ok = saveBotToken(appDataDir, p.token);
      if (!ok) throw new Error('Failed to save token (encryption unavailable)');
      return { ok: true };
    });

    router.register('telegram.get_token_status', () => {
      const token = loadBotToken(appDataDir);
      return { hasToken: token !== null };
    });

    router.register('telegram.delete_token', () => {
      deleteBotToken(appDataDir);
      return { ok: true };
    });

    router.register('telegram.test', async () => {
      const token = loadBotToken(appDataDir);
      if (!token) throw new Error('No bot token configured');
      const chatId = store.getState().settings.telegram.chatId;
      if (!chatId) throw new Error('No chat ID configured');
      return { ok: true, message: 'Token and chatId present' };
    });
  }

  router.register('notification.create', (params) => {
    const p = params as {
      title: string;
      subtitle?: string;
      body?: string;
      workspaceId?: string;
      surfaceId?: string;
    };
    if (!p?.title) throw new Error('title is required');
    const result = store.dispatch({
      type: 'notification.create',
      payload: {
        title: p.title,
        subtitle: p.subtitle,
        body: p.body,
        workspaceId: p.workspaceId,
        surfaceId: p.surfaceId,
      },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to create notification');
    }
    const notifications = store.getState().notifications;
    return { notification: notifications[notifications.length - 1] };
  });

  router.register('notification.list', () => {
    return { notifications: store.getState().notifications };
  });

  router.register('notification.clear', (params) => {
    const p = (params ?? {}) as { workspaceId?: string };
    const result = store.dispatch({
      type: 'notification.clear',
      payload: { workspaceId: p.workspaceId },
    });
    if (!result.ok) {
      throw new Error(result.error ?? 'Failed to clear notifications');
    }
    return { ok: true };
  });
}
