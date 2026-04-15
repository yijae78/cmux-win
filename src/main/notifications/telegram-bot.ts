/**
 * TelegramBotService — Telegram Bot integration for cmux-win.
 *
 * Outbound: Forward notification.create events to Telegram with InlineKeyboard.
 * Inbound: /status, /approve, /reject, /send, /agents, /help commands.
 *
 * Critical safety measures:
 * - C1: bot.catch() — never re-throw (would crash Electron)
 * - C3: bot.stop() on app quit — prevent process hang
 * - H2: auto-retry + debounce — respect Telegram rate limits
 * - H3: escapeHtml() — prevent API parse errors
 * - H4: explicit commands only — no auto-forwarding of plain text
 * - H6: configure() serialized — await stop before start
 * - M1: callback expiry — reject buttons older than 5 minutes
 */
import { Bot, GrammyError, HttpError, InlineKeyboard } from 'grammy';
import { autoRetry } from '@grammyjs/auto-retry';
import type { AppStateStore } from '../sot/store';

const DEBOUNCE_MS = 3000;
const CALLBACK_EXPIRY_MS = 5 * 60 * 1000; // 5 minutes

export interface TelegramSettings {
  enabled: boolean;
  chatId: string;
  forwardNotifications: boolean;
  remoteControl: boolean;
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export class TelegramBotService {
  private bot: Bot | null = null;
  private store: AppStateStore;
  private chatId: string = '';
  private settings: TelegramSettings = {
    enabled: false,
    chatId: '',
    forwardNotifications: true,
    remoteControl: true,
  };
  private debounceTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private networkErrorCount = 0;

  constructor(store: AppStateStore) {
    this.store = store;
  }

  /**
   * H6: Serialized configure — await stop before start.
   * Safe to call multiple times (settings change, etc.).
   */
  async configure(settings: TelegramSettings, botToken: string | null): Promise<void> {
    // Always stop existing bot first
    if (this.bot) {
      try {
        this.bot.stop();
      } catch {
        /* ignore stop errors */
      }
      this.bot = null;
    }

    this.settings = { ...settings };
    this.chatId = settings.chatId;

    if (!settings.enabled || !botToken || !settings.chatId) {
      return;
    }

    const bot = new Bot(botToken);

    // H2: auto-retry for 429 rate limit errors
    bot.api.config.use(autoRetry({ maxRetryAttempts: 3, maxDelaySeconds: 60 }));

    // C1: CRITICAL — catch all errors to prevent app crash
    bot.catch((err) => {
      const e = err.error;
      if (e instanceof GrammyError) {
        console.warn(`[telegram] API error ${e.error_code}: ${e.description}`);
      } else if (e instanceof HttpError) {
        this.networkErrorCount++;
        // M3: Suppress repeated network error logs
        if (this.networkErrorCount <= 3 || this.networkErrorCount % 100 === 0) {
          console.warn(`[telegram] Network error (#${this.networkErrorCount}):`, e.message);
        }
      } else {
        console.warn('[telegram] Unexpected error:', e);
      }
    });

    // Set up command handlers if remote control enabled
    if (settings.remoteControl) {
      this.setupCommands(bot);
    }

    // H4: Block plain text messages — only explicit commands
    bot.on('message:text', async (ctx) => {
      if (!ctx.message.text.startsWith('/')) {
        if (String(ctx.chat.id) !== this.chatId) return; // ignore unauthorized
        await ctx.reply(
          '명령어를 입력해주세요.\n\n' +
            '/status — 워크스페이스 상태\n' +
            '/agents — 에이전트 목록\n' +
            '/approve — 대기 중인 에이전트 승인\n' +
            '/reject — 대기 중인 에이전트 거부\n' +
            '/send &lt;text&gt; — 텍스트 전송\n' +
            '/help — 도움말',
          { parse_mode: 'HTML' },
        );
      }
    });

    this.bot = bot;

    // Start polling — non-blocking, drops pending updates from previous session
    bot.start({
      drop_pending_updates: true,
      allowed_updates: ['message', 'callback_query'],
      onStart: () => {
        this.networkErrorCount = 0;
        console.warn('[telegram] Bot polling started');
      },
    });
  }

  /**
   * Send notification to Telegram with InlineKeyboard.
   * H1: Must be called with .catch() — never let rejection propagate.
   * H2: Debounced per workspaceId (3 seconds).
   * H3: HTML escaped.
   */
  async sendNotification(
    title: string,
    body: string,
    meta?: { workspaceId?: string; surfaceId?: string },
  ): Promise<void> {
    if (!this.bot || !this.chatId || !this.settings.forwardNotifications) return;

    const key = meta?.workspaceId ?? 'global';

    // H2: Debounce — clear previous timer for same workspace
    const existing = this.debounceTimers.get(key);
    if (existing) clearTimeout(existing);

    return new Promise<void>((resolve) => {
      const timer = setTimeout(async () => {
        this.debounceTimers.delete(key);
        try {
          const safeTitle = escapeHtml(title);
          const safeBody = escapeHtml(body || '');

          // Build workspace context line
          let context = '';
          if (meta?.workspaceId) {
            const ws = this.store
              .getState()
              .workspaces.find((w) => w.id === meta.workspaceId);
            if (ws) context = `\n\n📂 <b>${escapeHtml(ws.name)}</b>`;
          }

          // M1: Timestamp in callback_data for expiry detection
          const now = Date.now();
          const keyboard = new InlineKeyboard()
            .text('✅ 승인', `approve:${meta?.surfaceId ?? ''}:${now}`)
            .text('❌ 거부', `reject:${meta?.surfaceId ?? ''}:${now}`)
            .row()
            .text('📊 상태', 'status');

          await this.bot!.api.sendMessage(
            this.chatId,
            `🔔 <b>${safeTitle}</b>\n\n${safeBody}${context}`,
            { parse_mode: 'HTML', reply_markup: keyboard },
          );
        } catch (err) {
          console.warn('[telegram] sendNotification failed:', (err as Error).message);
        }
        resolve();
      }, DEBOUNCE_MS);

      this.debounceTimers.set(key, timer);
    });
  }

  /**
   * C3: Stop bot polling — MUST be called on app quit.
   * Synchronous for use in before-quit handler.
   */
  stop(): void {
    if (this.bot) {
      try {
        this.bot.stop();
      } catch {
        /* ignore */
      }
      this.bot = null;
    }
    // Clear all debounce timers
    for (const timer of this.debounceTimers.values()) clearTimeout(timer);
    this.debounceTimers.clear();
  }

  get isRunning(): boolean {
    return this.bot !== null;
  }

  // ---- Private: Inbound command handlers ----

  private setupCommands(bot: Bot): void {
    // Auth guard middleware — reject unauthorized chat IDs
    bot.use(async (ctx, next) => {
      if (String(ctx.chat?.id) !== this.chatId) return; // silently ignore
      await next();
    });

    bot.command('status', async (ctx) => {
      const state = this.store.getState();
      const lines: string[] = ['📊 <b>cmux-win 상태</b>\n'];

      for (const ws of state.workspaces) {
        const wsAgents = state.agents.filter((a) => a.workspaceId === ws.id);
        const agentInfo =
          wsAgents.length > 0
            ? wsAgents.map((a) => `  ${a.statusIcon} ${a.agentType} (${a.status})`).join('\n')
            : '  (에이전트 없음)';
        lines.push(`📂 <b>${escapeHtml(ws.name)}</b>\n${agentInfo}`);
      }

      if (state.workspaces.length === 0) {
        lines.push('워크스페이스가 없습니다.');
      }

      await ctx.reply(lines.join('\n'), { parse_mode: 'HTML' });
    });

    bot.command('agents', async (ctx) => {
      const agents = this.store.getState().agents;
      if (agents.length === 0) {
        await ctx.reply('실행 중인 에이전트가 없습니다.');
        return;
      }

      const lines = agents.map(
        (a) => `${a.statusIcon} <b>${a.agentType}</b> — ${a.status}`,
      );
      await ctx.reply(lines.join('\n'), { parse_mode: 'HTML' });
    });

    bot.command('approve', async (ctx) => {
      const agent = this.findNeedsInputAgent();
      if (!agent) {
        await ctx.reply('대기 중인 에이전트가 없습니다.');
        return;
      }
      this.sendTextToSurface(agent.surfaceId, 'y\r');
      await ctx.reply(`✅ ${agent.agentType} 에이전트에 승인(y) 전송 완료`);
    });

    bot.command('reject', async (ctx) => {
      const agent = this.findNeedsInputAgent();
      if (!agent) {
        await ctx.reply('대기 중인 에이전트가 없습니다.');
        return;
      }
      this.sendTextToSurface(agent.surfaceId, 'n\r');
      await ctx.reply(`❌ ${agent.agentType} 에이전트에 거부(n) 전송 완료`);
    });

    // E4: /send with optional agent targeting
    // Usage: /send <text>           → first active agent
    //        /send claude <text>    → specific agent type
    //        /send gemini <text>    → specific agent type
    bot.command('send', async (ctx) => {
      const raw = ctx.match?.trim();
      if (!raw) {
        await ctx.reply(
          '사용법:\n/send &lt;텍스트&gt; — 활성 에이전트에 전송\n/send claude &lt;텍스트&gt; — 특정 에이전트에 전송',
          { parse_mode: 'HTML' },
        );
        return;
      }

      const agentTypes = ['claude', 'gemini', 'codex', 'opencode'];
      const firstWord = raw.split(/\s+/)[0].toLowerCase();
      let targetType: string | null = null;
      let text = raw;

      if (agentTypes.includes(firstWord)) {
        targetType = firstWord;
        text = raw.slice(firstWord.length).trim();
        if (!text) {
          await ctx.reply('전송할 텍스트를 입력하세요.');
          return;
        }
      }

      const agents = this.store.getState().agents;
      let agent = targetType
        ? agents.find((a) => a.agentType === targetType && a.status !== 'done' && a.status !== 'error')
        : this.findNeedsInputAgent() ?? agents.find((a) => a.status === 'running');

      if (!agent) {
        await ctx.reply(targetType ? `활성 ${targetType} 에이전트가 없습니다.` : '활성 에이전트가 없습니다.');
        return;
      }

      const keyboard = new InlineKeyboard()
        .text('✅ 전송', `send_confirm:${agent.surfaceId}:${encodeURIComponent(text)}`)
        .text('취소', 'send_cancel');
      await ctx.reply(
        `<code>${escapeHtml(text)}</code>\n\n위 텍스트를 <b>${escapeHtml(agent.agentType)}</b> 에이전트에 전송할까요?`,
        { parse_mode: 'HTML', reply_markup: keyboard },
      );
    });

    // E4: /task — Claude 리더에게 작업 지시 (첫 번째 Claude 에이전트)
    bot.command('task', async (ctx) => {
      const text = ctx.match?.trim();
      if (!text) {
        await ctx.reply('사용법: /task &lt;작업 내용&gt;', { parse_mode: 'HTML' });
        return;
      }

      const agents = this.store.getState().agents;
      const claude = agents.find((a) => a.agentType === 'claude' && a.status !== 'done' && a.status !== 'error');
      if (!claude) {
        // Claude가 없으면 첫 번째 surface에 직접 전송
        const surfaces = this.store.getState().surfaces;
        if (surfaces.length === 0) {
          await ctx.reply('활성 터미널이 없습니다.');
          return;
        }
        this.sendTextToSurface(surfaces[0].id, text + '\r');
        await ctx.reply(`✅ 첫 번째 터미널에 작업 전송 완료`);
        return;
      }

      this.sendTextToSurface(claude.surfaceId, text + '\r');
      await ctx.reply(`✅ Claude 리더에게 작업 전송 완료:\n<code>${escapeHtml(text)}</code>`, { parse_mode: 'HTML' });
    });

    bot.command('help', async (ctx) => {
      await ctx.reply(
        '<b>cmux-win 텔레그램 봇</b>\n\n' +
          '/status — 워크스페이스 + 에이전트 상태\n' +
          '/agents — 에이전트 목록\n' +
          '/approve — 대기 중인 에이전트 승인 (y)\n' +
          '/reject — 대기 중인 에이전트 거부 (n)\n' +
          '/send &lt;text&gt; — 에이전트에 텍스트 전송\n' +
          '/send gemini &lt;text&gt; — 특정 에이전트에 전송\n' +
          '/task &lt;text&gt; — Claude 리더에게 작업 지시\n' +
          '/help — 이 도움말',
        { parse_mode: 'HTML' },
      );
    });

    // Callback query handler (inline keyboard buttons)
    bot.on('callback_query:data', async (ctx) => {
      const data = ctx.callbackQuery.data;

      // M1: Check expiry for approve/reject buttons
      if (data.startsWith('approve:') || data.startsWith('reject:')) {
        const parts = data.split(':');
        const surfaceId = parts[1];
        const timestamp = parseInt(parts[2], 10);

        if (Date.now() - timestamp > CALLBACK_EXPIRY_MS) {
          await ctx.answerCallbackQuery({ text: '⏰ 만료된 버튼입니다.', show_alert: true });
          return;
        }

        // M2: Check agent is still in needs_input state
        const agent = surfaceId
          ? this.store.getState().agents.find((a) => a.surfaceId === surfaceId)
          : this.findNeedsInputAgent();

        if (!agent || agent.status !== 'needs_input') {
          await ctx.answerCallbackQuery({
            text: '에이전트가 더 이상 입력 대기 상태가 아닙니다.',
            show_alert: true,
          });
          return;
        }

        const isApprove = data.startsWith('approve:');
        this.sendTextToSurface(agent.surfaceId, isApprove ? 'y\r' : 'n\r');
        await ctx.answerCallbackQuery({
          text: isApprove ? '✅ 승인됨' : '❌ 거부됨',
        });
        await ctx.editMessageReplyMarkup({ reply_markup: undefined });
        return;
      }

      if (data === 'status') {
        await ctx.answerCallbackQuery();
        // Re-trigger /status by calling the handler logic
        const state = this.store.getState();
        const lines: string[] = ['📊 <b>cmux-win 상태</b>\n'];
        for (const ws of state.workspaces) {
          const wsAgents = state.agents.filter((a) => a.workspaceId === ws.id);
          const agentInfo =
            wsAgents.length > 0
              ? wsAgents
                  .map((a) => `  ${a.statusIcon} ${a.agentType} (${a.status})`)
                  .join('\n')
              : '  (에이전트 없음)';
          lines.push(`📂 <b>${escapeHtml(ws.name)}</b>\n${agentInfo}`);
        }
        await ctx.reply(lines.join('\n'), { parse_mode: 'HTML' });
        return;
      }

      if (data.startsWith('send_confirm:')) {
        const parts = data.split(':');
        const surfaceId = parts[1];
        const text = decodeURIComponent(parts.slice(2).join(':'));
        this.sendTextToSurface(surfaceId, text + '\r');
        await ctx.answerCallbackQuery({ text: '✅ 전송됨' });
        await ctx.editMessageReplyMarkup({ reply_markup: undefined });
        return;
      }

      if (data === 'send_cancel') {
        await ctx.answerCallbackQuery({ text: '취소됨' });
        await ctx.editMessageReplyMarkup({ reply_markup: undefined });
        return;
      }

      await ctx.answerCallbackQuery();
    });
  }

  private findNeedsInputAgent() {
    return this.store.getState().agents.find((a) => a.status === 'needs_input') ?? null;
  }

  private sendTextToSurface(surfaceId: string, text: string): void {
    this.store.dispatch({
      type: 'surface.send_text',
      payload: { surfaceId, text },
    });
  }
}
