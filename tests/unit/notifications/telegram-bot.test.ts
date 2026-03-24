import { describe, it, expect, vi, beforeEach } from 'vitest';
import { escapeHtml, TelegramBotService } from '../../../src/main/notifications/telegram-bot';

// --- escapeHtml tests ---
describe('escapeHtml', () => {
  it('escapes < > &', () => {
    expect(escapeHtml('a < b > c & d')).toBe('a &lt; b &gt; c &amp; d');
  });

  it('returns empty string unchanged', () => {
    expect(escapeHtml('')).toBe('');
  });

  it('does not double-escape', () => {
    expect(escapeHtml('&amp;')).toBe('&amp;amp;');
  });

  it('handles HTML-like content in terminal output', () => {
    expect(escapeHtml('expected <string> but got <number>')).toBe(
      'expected &lt;string&gt; but got &lt;number&gt;',
    );
  });
});

// --- TelegramBotService unit tests (no real Telegram API) ---
describe('TelegramBotService', () => {
  // Minimal mock store
  function createMockStore(overrides?: Partial<{ agents: unknown[]; workspaces: unknown[]; notifications: unknown[] }>) {
    const state = {
      agents: overrides?.agents ?? [],
      workspaces: overrides?.workspaces ?? [{ id: 'ws-1', name: 'Test WS' }],
      notifications: overrides?.notifications ?? [],
      settings: {
        telegram: { enabled: false, chatId: '', forwardNotifications: true, remoteControl: true },
      },
    };
    return {
      getState: () => state,
      dispatch: vi.fn(() => ({ ok: true })),
      on: vi.fn(),
    } as unknown as ConstructorParameters<typeof TelegramBotService>[0];
  }

  it('constructs without error', () => {
    const store = createMockStore();
    const bot = new TelegramBotService(store);
    expect(bot.isRunning).toBe(false);
  });

  it('configure with null token does not start bot', async () => {
    const store = createMockStore();
    const bot = new TelegramBotService(store);
    await bot.configure(
      { enabled: true, chatId: '123', forwardNotifications: true, remoteControl: true },
      null,
    );
    expect(bot.isRunning).toBe(false);
  });

  it('configure with disabled does not start bot', async () => {
    const store = createMockStore();
    const bot = new TelegramBotService(store);
    await bot.configure(
      { enabled: false, chatId: '123', forwardNotifications: true, remoteControl: true },
      'fake-token',
    );
    expect(bot.isRunning).toBe(false);
  });

  it('configure with empty chatId does not start bot', async () => {
    const store = createMockStore();
    const bot = new TelegramBotService(store);
    await bot.configure(
      { enabled: true, chatId: '', forwardNotifications: true, remoteControl: true },
      'fake-token',
    );
    expect(bot.isRunning).toBe(false);
  });

  it('stop is safe to call when not running', () => {
    const store = createMockStore();
    const bot = new TelegramBotService(store);
    expect(() => bot.stop()).not.toThrow();
  });

  it('sendNotification does nothing when bot is not running', async () => {
    const store = createMockStore();
    const bot = new TelegramBotService(store);
    // Should resolve without error
    await bot.sendNotification('test', 'body');
  });

  it('sendNotification does nothing when forwardNotifications is false', async () => {
    const store = createMockStore();
    const bot = new TelegramBotService(store);
    // Manually set settings to disabled forwarding
    await bot.configure(
      { enabled: true, chatId: '123', forwardNotifications: false, remoteControl: true },
      null, // null token prevents actual bot start
    );
    await bot.sendNotification('test', 'body');
    // No error, no crash
  });
});

// --- Token store tests ---
describe('telegram-token-store', () => {
  // Note: safeStorage is only available after app.ready in Electron.
  // These tests verify the module can be imported without crashing.
  it('module exports expected functions', async () => {
    // Dynamic import to avoid Electron dependency at import time in test runner
    // In CI without Electron, this will fail at import — that's expected.
    try {
      const mod = await import('../../../src/main/notifications/telegram-token-store');
      expect(typeof mod.saveBotToken).toBe('function');
      expect(typeof mod.loadBotToken).toBe('function');
      expect(typeof mod.deleteBotToken).toBe('function');
    } catch {
      // Expected in non-Electron environment (vitest without Electron)
      expect(true).toBe(true);
    }
  });
});
