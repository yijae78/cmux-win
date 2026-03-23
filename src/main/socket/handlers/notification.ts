import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';

export function registerNotificationHandlers(router: JsonRpcRouter, store: AppStateStore): void {
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
