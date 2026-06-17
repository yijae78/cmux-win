import { saveTokens, KakaoTokens } from './kakao-token-store';

const SEND_URL = 'https://kapi.kakao.com/v2/api/talk/memo/send';
const TOKEN_URL = 'https://kauth.kakao.com/oauth/token';
const DEBOUNCE_MS = 3000;
const MAX_RETRIES = 3;

export class KakaoTalkService {
  private tokens: KakaoTokens | null = null;
  private appDataDir: string;
  private debounceTimers = new Map<string, number>();

  constructor(appDataDir: string) {
    this.appDataDir = appDataDir;
  }

  setAppDataDir(dir: string): void {
    this.appDataDir = dir;
  }

  configure(tokens: KakaoTokens): void {
    this.tokens = { ...tokens };
  }

  async sendNotification(
    title: string,
    body: string,
    meta?: { workspaceId?: string; surfaceId?: string },
  ): Promise<void> {
    if (!this.tokens) return;

    const key = meta?.workspaceId ?? 'global';
    const now = Date.now();
    const lastSent = this.debounceTimers.get(key) ?? 0;
    if (now - lastSent < DEBOUNCE_MS) return;
    this.debounceTimers.set(key, now);

    const timestamp = new Date().toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
    const text = `[cmux-win] ${title}\n\n${body}\n\n${timestamp}`;

    await this.sendWithRetry(text);
  }

  private async sendWithRetry(text: string, attempt = 0): Promise<void> {
    if (!this.tokens) return;

    // Refresh if expired
    if (new Date(this.tokens.expiresAt) <= new Date()) {
      await this.refreshAccessToken();
    }

    const templateObject = JSON.stringify({
      object_type: 'text',
      text,
      link: { web_url: 'https://github.com/manaflow-ai/cmux-win' },
    });

    const params = new URLSearchParams({ template_object: templateObject });

    try {
      const res = await fetch(SEND_URL, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.tokens.accessToken}`,
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: params,
      });

      if (res.status === 401 && attempt === 0) {
        await this.refreshAccessToken();
        return this.sendWithRetry(text, 1);
      }

      if (!res.ok && attempt < MAX_RETRIES) {
        const delay = Math.pow(2, attempt) * 1000;
        await new Promise((r) => setTimeout(r, delay));
        return this.sendWithRetry(text, attempt + 1);
      }

      if (!res.ok) {
        console.warn(`[kakao] send failed: HTTP ${res.status}`);
      }
    } catch (err) {
      if (attempt < MAX_RETRIES) {
        const delay = Math.pow(2, attempt) * 1000;
        await new Promise((r) => setTimeout(r, delay));
        return this.sendWithRetry(text, attempt + 1);
      }
      console.warn('[kakao] send failed:', (err as Error).message);
    }
  }

  private async refreshAccessToken(): Promise<void> {
    if (!this.tokens) return;

    try {
      const params = new URLSearchParams({
        grant_type: 'refresh_token',
        client_id: this.tokens.restApiKey,
        refresh_token: this.tokens.refreshToken,
      });

      const res = await fetch(TOKEN_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params,
      });

      if (!res.ok) {
        console.warn(`[kakao] token refresh failed: HTTP ${res.status}`);
        return;
      }

      const data = (await res.json()) as {
        access_token: string;
        expires_in: number;
        refresh_token?: string;
      };

      this.tokens.accessToken = data.access_token;
      this.tokens.expiresAt = new Date(Date.now() + data.expires_in * 1000).toISOString();

      if (data.refresh_token) {
        this.tokens.refreshToken = data.refresh_token;
      }

      saveTokens(this.appDataDir, this.tokens);
    } catch (err) {
      console.warn('[kakao] token refresh error:', (err as Error).message);
    }
  }
}
