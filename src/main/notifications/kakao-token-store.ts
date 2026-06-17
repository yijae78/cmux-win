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
