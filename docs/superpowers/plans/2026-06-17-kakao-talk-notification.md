# 카카오톡 알림 연동 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 씨윈의 모든 알림을 카카오톡 "나에게 보내기" API로 핸드폰에 전달한다.

**Architecture:** notification-created side-effect 이벤트에서 카카오 API를 호출하는 KakaoTalkService를 추가한다. 토큰은 Electron safeStorage로 암호화 저장하고, access_token 만료 시 refresh_token으로 자동 갱신한다. 외부 라이브러리 없이 Node.js 내장 fetch만 사용한다.

**Tech Stack:** TypeScript, Electron safeStorage, Kakao REST API, Node.js fetch

**Spec:** `docs/superpowers/specs/2026-06-17-kakao-talk-notification-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/main/notifications/kakao-token-store.ts` | 토큰 암호화 저장/로드/삭제 |
| Create | `src/main/notifications/kakao-talk.ts` | 카카오 API 호출 + 토큰 자동 갱신 + 디바운스 |
| Modify | `src/main/index.ts` | KakaoTalkService 초기화 + 알림 이벤트 연동 |
| Modify | `src/main/socket/handlers/notification.ts` | kakao.* 소켓 핸들러 4개 등록 |
| Create | `tests/unit/notifications/kakao-token-store.test.ts` | 토큰 저장/로드/삭제 테스트 |
| Create | `tests/unit/notifications/kakao-talk.test.ts` | 메시지 전송/갱신/디바운스/에러 테스트 |

---

### Task 1: kakao-token-store.ts — 토큰 암호화 저장

**Files:**
- Create: `src/main/notifications/kakao-token-store.ts`
- Create: `tests/unit/notifications/kakao-token-store.test.ts`

- [ ] **Step 1: Write failing tests**

```typescript
// tests/unit/notifications/kakao-token-store.test.ts
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

// Mock Electron safeStorage
vi.mock('electron', () => ({
  safeStorage: {
    isEncryptionAvailable: vi.fn(() => true),
    encryptString: vi.fn((s: string) => Buffer.from(`enc:${s}`)),
    decryptString: vi.fn((buf: Buffer) => buf.toString().replace('enc:', '')),
  },
}));

import { saveTokens, loadTokens, deleteTokens, KakaoTokens } from '../../../src/main/notifications/kakao-token-store';

describe('kakao-token-store', () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'kakao-test-'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  const sampleTokens: KakaoTokens = {
    accessToken: 'access_123',
    refreshToken: 'refresh_456',
    restApiKey: 'key_789',
    expiresAt: '2026-06-17T22:00:00.000Z',
  };

  it('saves and loads tokens', () => {
    const ok = saveTokens(tmpDir, sampleTokens);
    expect(ok).toBe(true);
    const loaded = loadTokens(tmpDir);
    expect(loaded).toEqual(sampleTokens);
  });

  it('returns null when no tokens saved', () => {
    expect(loadTokens(tmpDir)).toBeNull();
  });

  it('deletes tokens', () => {
    saveTokens(tmpDir, sampleTokens);
    deleteTokens(tmpDir);
    expect(loadTokens(tmpDir)).toBeNull();
  });

  it('returns false when encryption unavailable', () => {
    const { safeStorage } = require('electron');
    safeStorage.isEncryptionAvailable.mockReturnValueOnce(false);
    expect(saveTokens(tmpDir, sampleTokens)).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run tests/unit/notifications/kakao-token-store.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Implement kakao-token-store.ts**

```typescript
// src/main/notifications/kakao-token-store.ts
import { safeStorage } from 'electron';
import * as fs from 'fs';
import * as path from 'path';

const TOKEN_FILENAME = 'kakao-tokens.enc';

export interface KakaoTokens {
  accessToken: string;
  refreshToken: string;
  restApiKey: string;
  expiresAt: string; // ISO 8601
}

export function saveTokens(appDataDir: string, tokens: KakaoTokens): boolean {
  if (!safeStorage.isEncryptionAvailable()) {
    console.warn('[kakao] safeStorage encryption not available — cannot save tokens');
    return false;
  }
  try {
    const json = JSON.stringify(tokens);
    const encrypted = safeStorage.encryptString(json);
    const filePath = path.join(appDataDir, TOKEN_FILENAME);
    fs.writeFileSync(filePath, encrypted);
    return true;
  } catch (err) {
    console.error('[kakao] Failed to save tokens:', err);
    return false;
  }
}

export function loadTokens(appDataDir: string): KakaoTokens | null {
  try {
    const filePath = path.join(appDataDir, TOKEN_FILENAME);
    if (!fs.existsSync(filePath)) return null;
    if (!safeStorage.isEncryptionAvailable()) {
      console.warn('[kakao] safeStorage encryption not available — cannot load tokens');
      return null;
    }
    const encrypted = fs.readFileSync(filePath);
    const json = safeStorage.decryptString(encrypted);
    return JSON.parse(json) as KakaoTokens;
  } catch (err) {
    console.error('[kakao] Failed to load tokens:', err);
    return null;
  }
}

export function deleteTokens(appDataDir: string): void {
  try {
    const filePath = path.join(appDataDir, TOKEN_FILENAME);
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
  } catch (err) {
    console.error('[kakao] Failed to delete tokens:', err);
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/unit/notifications/kakao-token-store.test.ts`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/main/notifications/kakao-token-store.ts tests/unit/notifications/kakao-token-store.test.ts
git commit -m "feat: kakao-token-store — 카카오 토큰 암호화 저장/로드/삭제"
```

---

### Task 2: kakao-talk.ts — 메시지 전송 서비스

**Files:**
- Create: `src/main/notifications/kakao-talk.ts`
- Create: `tests/unit/notifications/kakao-talk.test.ts`

- [ ] **Step 1: Write failing tests**

```typescript
// tests/unit/notifications/kakao-talk.test.ts
import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

// Mock kakao-token-store
vi.mock('../../../src/main/notifications/kakao-token-store', () => ({
  saveTokens: vi.fn(() => true),
  loadTokens: vi.fn(),
  deleteTokens: vi.fn(),
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
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('sends kakao message when configured', async () => {
    mockFetch.mockResolvedValueOnce({
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

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(url).toBe('https://kapi.kakao.com/v2/api/talk/memo/send');
    expect(opts.headers['Authorization']).toBe('Bearer tok');
  });

  it('refreshes token on 401 and retries', async () => {
    // First call: 401
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ code: -401 }),
    });
    // Token refresh call
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: 'new_tok',
        expires_in: 21600,
        refresh_token: 'new_ref',
      }),
    });
    // Retry with new token
    mockFetch.mockResolvedValueOnce({
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

    expect(mockFetch).toHaveBeenCalledTimes(3);
  });

  it('debounces duplicate notifications within 3s', async () => {
    mockFetch.mockResolvedValue({
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

    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('formats message with workspace and timestamp', async () => {
    mockFetch.mockResolvedValueOnce({
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

    const body = mockFetch.mock.calls[0][1].body as URLSearchParams;
    const tmpl = JSON.parse(body.get('template_object')!);
    expect(tmpl.object_type).toBe('text');
    expect(tmpl.text).toContain('[cmux-win] Alert');
    expect(tmpl.text).toContain('Something happened');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run tests/unit/notifications/kakao-talk.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Implement kakao-talk.ts**

```typescript
// src/main/notifications/kakao-talk.ts
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
      this.tokens.expiresAt = new Date(
        Date.now() + data.expires_in * 1000,
      ).toISOString();

      if (data.refresh_token) {
        this.tokens.refreshToken = data.refresh_token;
      }

      saveTokens(this.appDataDir, this.tokens);
    } catch (err) {
      console.warn('[kakao] token refresh error:', (err as Error).message);
    }
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run tests/unit/notifications/kakao-talk.test.ts`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/main/notifications/kakao-talk.ts tests/unit/notifications/kakao-talk.test.ts
git commit -m "feat: kakao-talk — 카카오톡 나에게 보내기 메시지 전송 서비스"
```

---

### Task 3: index.ts 연동 — 알림 이벤트에서 카카오톡 호출

**Files:**
- Modify: `src/main/index.ts:77-78` (import 추가)
- Modify: `src/main/index.ts:195` (서비스 인스턴스 생성)
- Modify: `src/main/index.ts:211-222` (notification-created 핸들러에 카카오 호출 추가)
- Modify: `src/main/index.ts:459` (app.whenReady 안에서 토큰 로드 + configure)

- [ ] **Step 1: Add imports**

`src/main/index.ts` — import 블록에 추가 (line 77 `showToast` import 다음):

```typescript
import { KakaoTalkService } from './notifications/kakao-talk';
import { loadTokens as loadKakaoTokens } from './notifications/kakao-token-store';
```

- [ ] **Step 2: Create service instance**

`src/main/index.ts` — `store.on('side-effect', ...)` 블록 바로 위에 추가:

```typescript
// KakaoTalk notification service (initialized in app.whenReady)
const kakaoTalk = new KakaoTalkService('');
```

- [ ] **Step 3: Add kakao call in notification-created handler**

`src/main/index.ts` — `notification-created` 블록 안, tray badge 업데이트 후:

```typescript
      // Forward to KakaoTalk (fire-and-forget)
      kakaoTalk
        .sendNotification(title, body, {
          workspaceId: effect.workspaceId,
          surfaceId: effect.surfaceId,
        })
        .catch((err: Error) => console.warn('[kakao] send failed:', err.message));
```

- [ ] **Step 4: Initialize in app.whenReady**

`src/main/index.ts` — Cowork Bridge 초기화 바로 위에 추가:

```typescript
  // KakaoTalk initialization
  const kakaoAppDataDir = app.getPath('userData');
  (kakaoTalk as any).appDataDir = kakaoAppDataDir;
  const kakaoTokens = loadKakaoTokens(kakaoAppDataDir);
  if (kakaoTokens) {
    kakaoTalk.configure(kakaoTokens);
    console.log('[kakao] Configured with existing tokens');
  }
```

- [ ] **Step 5: Commit**

```bash
git add src/main/index.ts
git commit -m "feat: index.ts에 카카오톡 알림 서비스 연동"
```

---

### Task 4: 소켓 핸들러 — kakao.* API 4개 등록

**Files:**
- Modify: `src/main/socket/handlers/notification.ts`

- [ ] **Step 1: Add imports and appDataDir parameter**

`src/main/socket/handlers/notification.ts` — 상단 import 및 함수 시그니처 변경:

```typescript
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
```

- [ ] **Step 2: Add kakao.* handlers before notification.create**

```typescript
  // KakaoTalk token management
  if (appDataDir) {
    router.register('kakao.set_tokens', (params) => {
      const p = params as {
        accessToken: string;
        refreshToken: string;
        restApiKey: string;
        expiresAt: string;
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
      await kakaoTalk.sendNotification(
        'Test',
        'cmux-win 카카오톡 연동 테스트 성공!',
      );
      return { ok: true, message: 'Test message sent' };
    });
  }
```

- [ ] **Step 3: Update registerNotificationHandlers call in index.ts**

`src/main/index.ts` — line 258:

```typescript
registerNotificationHandlers(router, store, app.getPath('userData'), kakaoTalk);
```

- [ ] **Step 4: Commit**

```bash
git add src/main/socket/handlers/notification.ts src/main/index.ts
git commit -m "feat: kakao.* 소켓 핸들러 4개 — set_tokens/get_status/delete_tokens/test"
```

---

### Task 5: 초기 설정 스크립트 — 토큰 발급 도우미

**Files:**
- Create: `scripts/kakao-setup.js`

- [ ] **Step 1: Create setup script**

이 스크립트는 신교수님이 1회 실행하여 카카오 토큰을 발급받는 도우미입니다.

```javascript
// scripts/kakao-setup.js
// 사용법: node scripts/kakao-setup.js <REST_API_KEY>
//
// 1단계: 브라우저에서 인가코드 발급 URL을 열어줌
// 2단계: 리다이렉트된 URL에서 인가코드를 복사해서 입력
// 3단계: 토큰 교환 후 씨윈 소켓 API로 저장
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const readline = require('readline');

const REST_API_KEY = process.argv[2];
if (!REST_API_KEY) {
  console.error('Usage: node scripts/kakao-setup.js <REST_API_KEY>');
  process.exit(1);
}

const REDIRECT_URI = 'http://localhost:3939/callback';
const AUTH_URL = `https://kauth.kakao.com/oauth/authorize?client_id=${REST_API_KEY}&redirect_uri=${encodeURIComponent(REDIRECT_URI)}&response_type=code&scope=talk_message`;

async function main() {
  console.log('\n=== 카카오톡 알림 초기 설정 ===\n');
  console.log('브라우저가 열립니다. 카카오 로그인 후 동의해주세요.\n');

  // Start local callback server
  const code = await new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url, `http://localhost:3939`);
      const authCode = url.searchParams.get('code');
      if (authCode) {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end('<h1>인증 완료! 이 창을 닫아도 됩니다.</h1>');
        server.close();
        resolve(authCode);
      } else {
        res.writeHead(400);
        res.end('Error: no code');
      }
    });
    server.listen(3939, () => {
      console.log('콜백 서버 대기중 (localhost:3939)...');
      execSync(`start "" "${AUTH_URL}"`);
    });
  });

  console.log(`\n인가코드 수신: ${code.substring(0, 10)}...`);

  // Exchange code for tokens
  const tokenRes = await fetch('https://kauth.kakao.com/oauth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: REST_API_KEY,
      redirect_uri: REDIRECT_URI,
      code,
    }),
  });

  if (!tokenRes.ok) {
    console.error('토큰 교환 실패:', await tokenRes.text());
    process.exit(1);
  }

  const tokenData = await tokenRes.json();
  console.log('\n토큰 발급 성공!');

  const tokens = {
    accessToken: tokenData.access_token,
    refreshToken: tokenData.refresh_token,
    restApiKey: REST_API_KEY,
    expiresAt: new Date(Date.now() + tokenData.expires_in * 1000).toISOString(),
  };

  // Save to cmux-win via socket API
  const socketTokenPath = path.join(
    process.env.APPDATA || '',
    'cmux-win', // electron uses app name for getPath('userData') in packaged mode
    'socket-token',
  );
  // Also check Electron dev path
  const electronTokenPath = path.join(
    process.env.APPDATA || '',
    'Electron',
    'socket-token',
  );

  let socketToken = null;
  for (const p of [socketTokenPath, electronTokenPath]) {
    try {
      socketToken = fs.readFileSync(p, 'utf8').split('\n')[0].trim();
      if (socketToken) break;
    } catch {}
  }

  if (socketToken) {
    // Connect to cmux-win socket and save tokens
    const net = require('net');
    const client = new net.Socket();
    let id = 0;

    client.connect(19840, '127.0.0.1', () => {
      // Auth
      client.write(JSON.stringify({
        jsonrpc: '2.0', id: id++,
        method: 'auth.handshake', token: socketToken,
      }) + '\n');
      // Set tokens
      setTimeout(() => {
        client.write(JSON.stringify({
          jsonrpc: '2.0', id: id++,
          method: 'kakao.set_tokens', params: tokens,
        }) + '\n');
        // Test
        setTimeout(() => {
          client.write(JSON.stringify({
            jsonrpc: '2.0', id: id++,
            method: 'kakao.test',
          }) + '\n');
          setTimeout(() => {
            console.log('\n설정 완료! 카카오톡에서 테스트 메시지를 확인하세요.');
            client.destroy();
            process.exit(0);
          }, 2000);
        }, 1000);
      }, 500);
    });

    client.on('data', (data) => {
      const lines = data.toString().split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          const msg = JSON.parse(line);
          if (msg.error) console.error('Socket error:', msg.error);
          else console.log('Socket OK:', JSON.stringify(msg.result));
        } catch {}
      }
    });

    client.on('error', (err) => {
      console.error('소켓 연결 실패. 씨윈이 실행 중인지 확인하세요.');
      // Fallback: print tokens for manual setup
      console.log('\n수동 설정용 토큰:');
      console.log(JSON.stringify(tokens, null, 2));
      process.exit(1);
    });
  } else {
    console.log('\n씨윈 소켓 토큰을 찾을 수 없습니다.');
    console.log('씨윈 실행 후 아래 토큰을 kakao.set_tokens로 전달하세요:');
    console.log(JSON.stringify(tokens, null, 2));
  }
}

main().catch(console.error);
```

- [ ] **Step 2: Commit**

```bash
git add scripts/kakao-setup.js
git commit -m "feat: 카카오톡 초기 설정 스크립트 (1회 토큰 발급 도우미)"
```

---

### Task 6: 통합 테스트 + 최종 커밋

- [ ] **Step 1: Run all tests**

Run: `npx vitest run tests/unit/notifications/`
Expected: All tests PASS

- [ ] **Step 2: Build check**

Run: `npm run build`
Expected: Build succeeds (no type errors, no missing imports)

- [ ] **Step 3: Final commit + push**

```bash
git add -A
git commit -m "feat: 카카오톡 나에게 보내기 알림 연동 완료"
git push
```
