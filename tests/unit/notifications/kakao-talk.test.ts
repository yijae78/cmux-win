import { describe, it, expect, beforeEach, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(),
  saveTokens: vi.fn(() => true),
  loadTokens: vi.fn(),
  deleteTokens: vi.fn(),
}));

vi.stubGlobal('fetch', mocks.fetch);

vi.mock('../../../src/main/notifications/kakao-token-store', () => ({
  saveTokens: mocks.saveTokens,
  loadTokens: mocks.loadTokens,
  deleteTokens: mocks.deleteTokens,
}));

import { KakaoTalkService } from '../../../src/main/notifications/kakao-talk';

describe('KakaoTalkService', () => {
  let service: KakaoTalkService;

  beforeEach(() => {
    vi.clearAllMocks();
    service = new KakaoTalkService('/fake/appdata');
  });

  it('does nothing when not configured', async () => {
    await service.sendNotification('title', 'body');
    expect(mocks.fetch).not.toHaveBeenCalled();
  });

  it('sends kakao message when configured', async () => {
    mocks.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ result_code: 0 }),
    });

    service.configure({
      accessToken: 'tok',
      refreshToken: 'ref',
      restApiKey: 'key',
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    });

    await service.sendNotification('Test Title', 'Test Body');

    expect(mocks.fetch).toHaveBeenCalledTimes(1);
    const [url, opts] = mocks.fetch.mock.calls[0];
    expect(url).toBe('https://kapi.kakao.com/v2/api/talk/memo/send');
    expect(opts.headers['Authorization']).toBe('Bearer tok');
  });

  it('refreshes token on 401 and retries', async () => {
    // First call: 401
    mocks.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ code: -401 }),
    });
    // Token refresh call
    mocks.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: 'new_tok',
        expires_in: 21600,
        refresh_token: 'new_ref',
      }),
    });
    // Retry with new token
    mocks.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ result_code: 0 }),
    });

    service.configure({
      accessToken: 'old_tok',
      refreshToken: 'ref',
      restApiKey: 'key',
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    });

    await service.sendNotification('Title', 'Body');

    expect(mocks.fetch).toHaveBeenCalledTimes(3);
  });

  it('debounces duplicate notifications within 3s', async () => {
    mocks.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ result_code: 0 }),
    });

    service.configure({
      accessToken: 'tok',
      refreshToken: 'ref',
      restApiKey: 'key',
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    });

    await service.sendNotification('T', 'B', { workspaceId: 'ws1' });
    await service.sendNotification('T', 'B', { workspaceId: 'ws1' });

    expect(mocks.fetch).toHaveBeenCalledTimes(1);
  });

  it('formats message with workspace and timestamp', async () => {
    mocks.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ result_code: 0 }),
    });

    service.configure({
      accessToken: 'tok',
      refreshToken: 'ref',
      restApiKey: 'key',
      expiresAt: new Date(Date.now() + 3600000).toISOString(),
    });

    await service.sendNotification('Alert', 'Something happened');

    const body = mocks.fetch.mock.calls[0][1].body as URLSearchParams;
    const tmpl = JSON.parse(body.get('template_object')!);
    expect(tmpl.object_type).toBe('text');
    expect(tmpl.text).toContain('[cmux-win] Alert');
    expect(tmpl.text).toContain('Something happened');
  });
});
