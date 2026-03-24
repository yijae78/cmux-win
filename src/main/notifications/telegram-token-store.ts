/**
 * Encrypted storage for Telegram bot token using Electron safeStorage.
 *
 * C4: Bot token MUST NOT be stored in plain-text SettingsState.
 * safeStorage uses Windows DPAPI for encryption at rest.
 */
import { safeStorage } from 'electron';
import fs from 'node:fs';
import path from 'node:path';

const TOKEN_FILENAME = 'telegram-token.enc';

function getTokenPath(appDataDir: string): string {
  return path.join(appDataDir, TOKEN_FILENAME);
}

/**
 * Save bot token encrypted to disk.
 * Returns true on success.
 */
export function saveBotToken(appDataDir: string, token: string): boolean {
  if (!safeStorage.isEncryptionAvailable()) {
    console.warn('[telegram] safeStorage encryption not available — cannot save token');
    return false;
  }
  try {
    const dir = appDataDir;
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const encrypted = safeStorage.encryptString(token);
    fs.writeFileSync(getTokenPath(dir), encrypted);
    return true;
  } catch (err) {
    console.error('[telegram] Failed to save bot token:', err);
    return false;
  }
}

/**
 * Load and decrypt bot token from disk.
 * Returns null if not found, encryption unavailable, or decryption fails.
 */
export function loadBotToken(appDataDir: string): string | null {
  const tokenPath = getTokenPath(appDataDir);
  if (!fs.existsSync(tokenPath)) return null;
  if (!safeStorage.isEncryptionAvailable()) {
    console.warn('[telegram] safeStorage encryption not available — cannot load token');
    return null;
  }
  try {
    const encrypted = fs.readFileSync(tokenPath);
    return safeStorage.decryptString(encrypted);
  } catch (err) {
    console.error('[telegram] Failed to load bot token:', err);
    return null;
  }
}

/**
 * Delete the stored bot token.
 */
export function deleteBotToken(appDataDir: string): void {
  const tokenPath = getTokenPath(appDataDir);
  try {
    if (fs.existsSync(tokenPath)) fs.unlinkSync(tokenPath);
  } catch {
    /* ignore */
  }
}
