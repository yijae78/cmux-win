import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';
import {
  saveTokens,
  loadTokens,
  deleteTokens,
  KakaoTokens,
} from '../../notifications/kakao-token-store';
import { KakaoTalkService } from '../../notifications/kakao-talk';

export function registerNotificationHandlers(
  router: JsonRpcRouter,
  store: AppStateStore,
  appDataDir?: string,
  kakaoTalk?: KakaoTalkService,
): void {
  // KakaoTalk token management
  if (appDataDir) {
    router.register('kakao.set_tokens', (params) => {
      const p = params as {
        accessToken: string;
        refreshToken: string;
        restApiKey: string;
        expiresAt?: string;
      };
      if (!p?.accessToken || !p?.refreshToken || !p?.restApiKey) {
        throw new Error('accessToken, refreshToken, and restApiKey are required');
      }
      const tokens: KakaoTokens = {
        accessToken: p.accessToken,
        refreshToken: p.refreshToken,
        restApiKey: p.restApiKey,
        expiresAt: p.expiresAt || new Date(Date.now() + 21600000).toISOString(),
      };
      const ok = saveTokens(appDataDir, tokens);
      if (!ok) throw new Error('Failed to save tokens (encryption unavailable)');
      if (kakaoTalk) kakaoTalk.configure(tokens);
      return { ok: true };
    });

    router.register('kakao.get_status', () => {
      const tokens = loadTokens(appDataDir);
      return {
        hasTokens: tokens !== null,
        expiresAt: tokens?.expiresAt ?? null,
      };
    });

    router.register('kakao.delete_tokens', () => {
      deleteTokens(appDataDir);
      return { ok: true };
    });

    router.register('kakao.test', async () => {
      if (!kakaoTalk) throw new Error('KakaoTalk service not available');
      const tokens = loadTokens(appDataDir);
      if (!tokens) throw new Error('No kakao tokens configured');
      kakaoTalk.configure(tokens);
      await kakaoTalk.sendNotification('Test', 'cmux-win 카카오톡 연동 테스트 성공!');
      return { ok: true, message: 'Test message sent' };
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
