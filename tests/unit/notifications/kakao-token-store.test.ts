import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

const mocks = vi.hoisted(() => ({
  isEncryptionAvailable: vi.fn(() => true),
  encryptString: vi.fn((s: string) => Buffer.from(`enc:${s}`)),
  decryptString: vi.fn((buf: Buffer) => buf.toString().replace('enc:', '')),
}));

vi.mock('electron', () => ({
  safeStorage: {
    isEncryptionAvailable: mocks.isEncryptionAvailable,
    encryptString: mocks.encryptString,
    decryptString: mocks.decryptString,
  },
}));

import {
  saveTokens,
  loadTokens,
  deleteTokens,
  KakaoTokens,
} from '../../../src/main/notifications/kakao-token-store';

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
    mocks.isEncryptionAvailable.mockReturnValueOnce(false);
    expect(saveTokens(tmpDir, sampleTokens)).toBe(false);
  });
});
