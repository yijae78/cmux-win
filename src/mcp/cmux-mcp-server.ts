// shebang is injected by esbuild banner (see package.json build:mcp)
/* eslint-disable no-console, @typescript-eslint/no-explicit-any */
/**
 * cmux-win MCP Server v2 (stdio)
 *
 * 핸드폰 Claude 앱 → Dispatch → Claude Desktop → 이 MCP 서버 → cmux-win 소켓 API
 *
 * v2: 10개 도구 → 1개 통합 도구 (Permission 승인 1회로 축소)
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import * as net from 'node:net';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { spawn } from 'node:child_process';

// ── 1.1 글로벌 에러 핸들러 (crash 방지) ──
process.on('uncaughtException', (err) => {
  console.error('[cmux-mcp] uncaughtException:', err);
});
process.on('unhandledRejection', (reason) => {
  console.error('[cmux-mcp] unhandledRejection:', reason);
});

// ── stdout 보호: console.log → stderr (stdout은 MCP 프로토콜 전용) ──
console.log = (...args: unknown[]) => console.error('[mcp]', ...args);

// ────────────────────────────────────────────
//  Socket Token 탐색
// ────────────────────────────────────────────

function findSocketToken(): { token: string; port: number } | null {
  const appData =
    process.env.APPDATA || path.join(process.env.USERPROFILE || '', 'AppData', 'Roaming');

  const candidates = [
    path.join(appData, 'Electron', 'socket-token'),
    path.join(appData, 'cmux-win', 'socket-token'),
  ];

  let best: { token: string; port: number; mtime: number } | null = null;
  for (const p of candidates) {
    try {
      const stat = fs.statSync(p);
      const lines = fs.readFileSync(p, 'utf8').trim().split('\n');
      const token = lines[0].trim();
      const port = lines.length >= 2 ? parseInt(lines[1].trim(), 10) : 19840;
      if (token && (!best || stat.mtimeMs > best.mtime)) {
        best = { token, port, mtime: stat.mtimeMs };
      }
    } catch {
      /* next */
    }
  }
  return best ? { token: best.token, port: best.port } : null;
}

// ────────────────────────────────────────────
//  Auto-launch cmux-win (1.4: reject on failure)
// ────────────────────────────────────────────

function launchCmuxWin(): Promise<void> {
  return new Promise((resolve, reject) => {
    const projectDir = 'C:\\dev\\cmux-win';

    // 1. Dev mode: node electron/cli.js out/main/index.js
    const electronCli = path.join(projectDir, 'node_modules', 'electron', 'cli.js');
    const mainJs = path.join(projectDir, 'out', 'main', 'index.js');

    if (fs.existsSync(electronCli) && fs.existsSync(mainJs)) {
      console.log(`[mcp] Launching: node ${electronCli} ${mainJs}`);
      try {
        const child = spawn(process.execPath, [electronCli, mainJs], {
          cwd: projectDir,
          detached: true,
          stdio: 'ignore',
          windowsHide: false,
          env: { ...process.env },
        });
        child.unref();
        console.log(`[mcp] Launched PID: ${child.pid}`);
      } catch (err) {
        console.log(`[mcp] Dev launch failed: ${err}`);
        reject(new Error(`cmux-win dev launch 실패: ${err}`));
        return;
      }
      resolve();
      return;
    }

    // 2. Installed: cmux-win.exe in AppData
    const appData =
      process.env.LOCALAPPDATA || path.join(process.env.USERPROFILE || '', 'AppData', 'Local');
    const installedExe = path.join(appData, 'cmux-win', 'cmux-win.exe');
    if (fs.existsSync(installedExe)) {
      console.log(`[mcp] Launching installed: ${installedExe}`);
      try {
        const child = spawn(installedExe, [], {
          detached: true,
          stdio: 'ignore',
          windowsHide: false,
        });
        child.unref();
      } catch (err) {
        console.log(`[mcp] Installed launch failed: ${err}`);
      }
      resolve();
      return;
    }

    console.log('[mcp] No cmux-win executable found — cannot auto-launch');
    reject(new Error('cmux-win 실행 파일을 찾을 수 없습니다 (dev/installed 모두 없음)'));
  });
}

// ────────────────────────────────────────────
//  JSON-RPC 2.0 Socket Client (1.2, 1.3 반영)
// ────────────────────────────────────────────

class CmuxSocketClient {
  private socket: net.Socket | null = null;
  private authenticated = false;
  private nextId = 1;
  private pending = new Map<
    number,
    { resolve: (v: unknown) => void; reject: (e: Error) => void }
  >();
  private buffer = '';
  private connectingPromise: Promise<void> | null = null;
  private launchedThisSession = false; // auto-launch 중복 방지
  private lastSuccessfulCallAt = 0; // #7: 마지막 성공 호출 시각

  async ensureConnection(): Promise<void> {
    // #7: 5분 이상 성공 호출 없으면 launchedThisSession 리셋 (재크래시 대응)
    if (
      this.launchedThisSession &&
      this.lastSuccessfulCallAt > 0 &&
      Date.now() - this.lastSuccessfulCallAt > 5 * 60 * 1000
    ) {
      console.log('[mcp] 5분간 성공 호출 없음 — launchedThisSession 리셋');
      this.launchedThisSession = false;
    }

    if (this.socket && !this.socket.destroyed && this.authenticated) return;
    if (this.connectingPromise) return this.connectingPromise;

    this.connectingPromise = this._doConnect();
    try {
      await this.connectingPromise;
    } finally {
      this.connectingPromise = null;
    }
  }

  // #12, #15: auto-launch 중복 방지 + 프로세스 탐지 + 로깅 강화
  private async _doConnect(): Promise<void> {
    this.disconnect();
    let info = findSocketToken();

    if (info) {
      // 토큰 있음 → 먼저 연결 시도
      try {
        console.log(`[mcp] 토큰 발견 (port:${info.port}), 연결 시도...`);
        await this.connectAndAuth(info);
        console.log('[mcp] 연결+인증 성공');
        return;
      } catch (e) {
        console.log(`[mcp] 연결 실패 (stale token): ${(e as Error).message}`);
        this.disconnect();
      }
    }

    // 이미 auto-launch 했으면 재연결만 시도 (최대 20초 대기)
    if (this.launchedThisSession) {
      console.log('[mcp] 이미 auto-launch 완료, 재연결 대기 (최대 20초)...');
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 500));
        info = findSocketToken();
        if (info) {
          try {
            await this.connectAndAuth(info);
            console.log('[mcp] 재연결 성공!');
            return;
          } catch {
            this.disconnect();
          }
        }
      }
      throw new Error('cmux-win에 재연결할 수 없습니다. 앱을 수동으로 시작해주세요.');
    }

    // #12: auto-launch 전 기존 프로세스 탐지 (이중 실행 방지)
    try {
      const { execSync } = await import('node:child_process');
      const taskResult = execSync('tasklist /fi "imagename eq cmux-win*" /fo csv /nh', {
        encoding: 'utf-8',
        timeout: 5000,
      }).trim();
      if (taskResult && !taskResult.includes('No tasks') && taskResult.includes('cmux-win')) {
        console.log('[mcp] cmux-win 프로세스 발견, auto-launch 건너뜀 — 소켓 서버 대기');
        this.launchedThisSession = true; // 재실행 방지
        for (let i = 0; i < 60; i++) {
          await new Promise((r) => setTimeout(r, 500));
          info = findSocketToken();
          if (info) {
            try {
              await this.connectAndAuth(info);
              console.log('[mcp] 기존 프로세스에 연결 성공!');
              return;
            } catch {
              this.disconnect();
            }
          }
        }
        throw new Error('cmux-win 프로세스는 있지만 소켓 서버에 연결할 수 없습니다.');
      }
    } catch {
      // tasklist 실패 — 무시하고 auto-launch 진행
    }

    // 첫 auto-launch
    console.log(`[mcp] ${info ? 'Stale token' : '토큰 없음'}, auto-launch 시도...`);
    this.launchedThisSession = true;
    await launchCmuxWin();

    // Wait up to 45s for connection (#E4: 30초→45초 확대)
    for (let i = 0; i < 90; i++) {
      await new Promise((r) => setTimeout(r, 500));
      info = findSocketToken();
      if (info) {
        try {
          await this.connectAndAuth(info);
          console.log(`[mcp] auto-launch 성공, 연결 완료 (${Math.round(i * 0.5)}초)`);
          return;
        } catch {
          this.disconnect();
        }
      }
    }
    throw new Error(
      'cmux-win 자동 실행을 시도했으나 연결할 수 없습니다. 앱을 수동으로 시작해주세요.',
    );
  }

  // 1.2: 10초 타임아웃 + 모든 경로 clearTimeout
  private connectAndAuth(info: { token: string; port: number }): Promise<void> {
    return new Promise((resolve, reject) => {
      const sock = new net.Socket();
      this.socket = sock;
      this.buffer = '';
      this.authenticated = false;

      // #1: TCP keepalive — 30초마다 probe, 죽은 연결 빠르게 감지
      sock.setKeepAlive(true, 30_000);

      const authTimeout = setTimeout(() => {
        sock.destroy();
        reject(new Error('cmux-win 인증 타임아웃 (10초)'));
      }, 10_000);

      sock.on('data', (chunk) => {
        this.buffer += chunk.toString();
        let nl: number;
        while ((nl = this.buffer.indexOf('\n')) !== -1) {
          const line = this.buffer.slice(0, nl);
          this.buffer = this.buffer.slice(nl + 1);
          try {
            const msg = JSON.parse(line);
            const p = this.pending.get(msg.id);
            if (p) {
              this.pending.delete(msg.id);
              if (msg.error) {
                p.reject(new Error(msg.error.message ?? JSON.stringify(msg.error)));
              } else {
                p.resolve(msg.result);
              }
            }
          } catch {
            /* non-JSON noise */
          }
        }
      });

      sock.on('error', (err) => {
        clearTimeout(authTimeout);
        this.authenticated = false;
        console.log(`[mcp] 소켓 에러: ${err.message}`); // #15
        reject(new Error(`cmux-win 연결 실패: ${err.message}`));
      });

      sock.on('close', () => {
        clearTimeout(authTimeout);
        const wasPending = this.pending.size;
        this.authenticated = false;
        for (const [, p] of this.pending) {
          p.reject(new Error('cmux-win 연결이 끊어졌습니다'));
        }
        this.pending.clear();
        console.log(`[mcp] 소켓 close (pending ${wasPending}건 reject)`); // #15
      });

      sock.connect(info.port, '127.0.0.1', () => {
        const id = this.nextId++;
        const authMsg =
          JSON.stringify({
            jsonrpc: '2.0',
            id,
            method: 'auth.handshake',
            params: { token: info.token },
          }) + '\n';

        this.pending.set(id, {
          resolve: () => {
            clearTimeout(authTimeout);
            this.authenticated = true;
            resolve();
          },
          reject: (e) => {
            clearTimeout(authTimeout);
            reject(new Error(`cmux-win 인증 실패: ${e.message}`));
          },
        });

        sock.write(authMsg);
      });
    });
  }

  // #5: 3회 재시도 + 지수 백오프, ensureConnection 실패도 커버
  // #10: 타임아웃 15초→30초
  async call(method: string, params: Record<string, unknown> = {}, _retryCount = 0): Promise<any> {
    try {
      await this.ensureConnection();

      if (!this.socket || this.socket.destroyed) {
        throw new Error('소켓 끊어짐');
      }

      const id = this.nextId++;
      const result = await new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          this.pending.delete(id);
          reject(new Error(`요청 시간 초과 (30s): ${method}`));
        }, 30_000);

        this.pending.set(id, {
          resolve: (v) => {
            clearTimeout(timer);
            resolve(v);
          },
          reject: (e) => {
            clearTimeout(timer);
            reject(e);
          },
        });

        const ok = this.socket!.write(
          JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n',
        );
        if (!ok) {
          this.pending.delete(id);
          clearTimeout(timer);
          reject(new Error(`소켓 쓰기 실패 (backpressure): ${method}`));
        }
      });

      this.lastSuccessfulCallAt = Date.now();
      return result;
    } catch (err) {
      if (_retryCount < 2) {
        const delay = 1000 * (_retryCount + 1); // 1s, 2s
        console.log(
          `[mcp] call(${method}) 실패, ${delay}ms 후 재시도 (${_retryCount + 1}/3): ${(err as Error).message}`,
        );
        this.disconnect();
        await sleep(delay);
        return this.call(method, params, _retryCount + 1);
      }
      throw err;
    }
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.destroy();
      this.socket = null;
    }
    this.authenticated = false;
    for (const [, p] of this.pending) {
      p.reject(new Error('disconnect'));
    }
    this.pending.clear();
  }
}

// ────────────────────────────────────────────
//  ANSI 제거 + Idle 감지
// ────────────────────────────────────────────

function stripAnsi(str: string): string {
  return str
    .replace(/\x1B\[[0-9;?]*[a-zA-Z]/g, '')
    .replace(/\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)/g, '')
    .replace(/\x1BP[^\x1B]*\x1B\\/g, '')
    .replace(/\x1B[()][0-9A-B]/g, '')
    .replace(/\x1B[>=<N~}{F|7-8]/g, '')
    .replace(/[\x00-\x08\x0B-\x0C\x0E-\x1F]/g, '');
}

// #9: Codex idle 패턴에 셸 프롬프트 추가 (--full-auto 종료 후 감지)
const DEFAULT_IDLE_PATTERNS: Record<string, string[]> = {
  gemini: ['Type your message', 'Enter your prompt', 'What can I help'],
  codex: ['What would you like', 'Enter a prompt', 'PS C:\\', 'PS>', '$ '],
  claude: ['❯ ', '❯', '> '],
};

function loadIdlePatterns(): Record<string, string[]> {
  const configPath = path.join(
    process.env.HOME || process.env.USERPROFILE || '',
    '.cmux-win',
    'idle-patterns.json',
  );
  try {
    if (fs.existsSync(configPath)) {
      return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    }
  } catch {
    // fall through to defaults
  }
  return DEFAULT_IDLE_PATTERNS;
}

const IDLE_PATTERNS = loadIdlePatterns();

function isAgentIdle(screenText: string, agentType: string): boolean {
  const clean = stripAnsi(screenText);
  const lines = clean.split('\n').filter((l) => l.trim().length > 0);
  const tail = lines.slice(-3).join('\n');
  const patterns = IDLE_PATTERNS[agentType.toLowerCase()] || [];
  return patterns.some((p) => tail.includes(p));
}

// ────────────────────────────────────────────
//  Task Store (장기 작업 상태 저장)
// ────────────────────────────────────────────

interface TaskEntry {
  surfaceId: string;
  agentType: string;
  task: string;
  status: 'running' | 'done' | 'error';
  result?: string;
  startedAt: number;
}

const taskStore = new Map<string, TaskEntry>();
let taskSeq = 0;

// 1.7: TTL 개선 — done 10분, running 30분 후 자동 만료
setInterval(() => {
  const now = Date.now();
  for (const [id, entry] of taskStore) {
    if (entry.status === 'done' && now - entry.startedAt > 10 * 60 * 1000) {
      taskStore.delete(id);
    } else if (entry.status === 'running' && now - entry.startedAt > 30 * 60 * 1000) {
      entry.status = 'done';
      entry.result = '(30분 초과 — 자동 만료)';
    }
  }
}, 60_000);

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

// ────────────────────────────────────────────
//  MCP Server + 통합 도구 (1.5, 1.6)
// ────────────────────────────────────────────

const client = new CmuxSocketClient();

// ── 스타일 규칙: 모든 도구 응답 앞에 삽입 ──
const RESPONSE_RULES = [
  '[MANDATORY RESPONSE RULES]',
  '1. Address user as "신교수님" (never shorten to 교수님)',
  '2. ZERO emoji — no ✅❌🟢⚡🌿🫡😊🩺🍀🚨💪🚀☕⏳ or ANY other emoji',
  '3. Max 3 sentences, plain text only',
  '4. No tables, no markdown formatting, no decorations',
  '5. No follow-up suggestions or questions',
].join('\n');

const server = new McpServer(
  { name: 'cmux-win', version: '2.2.0' },
  {
    instructions: [
      '씨윈(cmux-win) 원격 제어 MCP 서버.',
      '사용자가 씨윈/터미널/에이전트 관련 요청 시 반드시 cmux 도구를 호출한다.',
      '',
      '사용 흐름:',
      '- 상태 확인 → cmux(action:"status")',
      '- 작업 지시 → cmux(action:"send", task:"...")',
      '- 에이전트 추가 → cmux(action:"spawn", agentType:"gemini")',
      '- 화면 읽기 → cmux(action:"read")',
      '- send_and_wait가 status="running" → get_result 반복 호출',
    ].join('\n'),
  },
);

function text(data: unknown) {
  const body = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  return {
    content: [
      {
        type: 'text' as const,
        text: `${RESPONSE_RULES}\n\n${body}`,
      },
    ],
  };
}

// ── Helper: system.tree → 1-2줄 요약 ──
async function summarizeStatus(tree: any): Promise<string> {
  const ws = (tree?.workspaces ?? [])[0];
  if (!ws) return '씨윈 작동중. 워크스페이스 없음.';
  const panelCount = ws.panels?.length ?? 0;
  const agents = (ws.agents ?? [])
    .map((a: any) => `${a.agentType ?? 'unknown'}(${a.status ?? '?'},${a.surfaceId ?? ''})`)
    .join(', ');
  let notifCount = 0;
  try {
    const n = await client.call('notification.list');
    const list = Array.isArray(n) ? n : (n?.notifications ?? []);
    notifCount = Array.isArray(list) ? list.length : 0;
  } catch {
    /* ignore */
  }
  const parts = [`씨윈 정상. 패널 ${panelCount}개.`];
  if (agents) parts.push(`에이전트: ${agents}.`);
  if (notifCount > 0) parts.push(`알림 ${notifCount}건.`);
  return parts.join(' ');
}

// ── Helper: notification.list → 요약 ──
function summarizeNotifications(data: any): string {
  const list = Array.isArray(data) ? data : (data?.notifications ?? []);
  if (!Array.isArray(list) || list.length === 0) return '미처리 알림 없음.';
  return `미처리 알림 ${list.length}건.`;
}

// #11: 마지막 에이전트(가장 최근 spawn) 우선 반환
async function findAgentSurface(agentType?: string): Promise<string | undefined> {
  try {
    const tree = await client.call('system.tree');
    if (!tree || typeof tree !== 'object') return undefined;
    let lastMatch: string | undefined;
    for (const ws of (
      tree as { workspaces?: { agents?: { agentType?: string; surfaceId?: string }[] }[] }
    ).workspaces ?? []) {
      for (const agent of ws.agents ?? []) {
        const t = (agent.agentType ?? '').toLowerCase();
        if (!agentType || t === agentType.toLowerCase()) {
          lastMatch = agent.surfaceId;
        }
      }
    }
    return lastMatch;
  } catch {
    // connection failure or malformed response
  }
  return undefined;
}

// ── 통합 도구: cmux ──
server.registerTool(
  'cmux',
  {
    title: '씨윈 원격 제어',
    description:
      '씨윈(cmux-win) 원격 제어.\n' +
      '응답규칙: "신교수님" 호칭, 이모지 금지, 3문장 이내, 테이블 금지, 추가 제안 금지.\n' +
      'action: status | send | read | spawn | send_and_wait | get_result | approve | notifications | open_browser | move_window\n' +
      '씨윈이 꺼져있어도 자동 실행된다.',
    inputSchema: z.object({
      action: z
        .enum([
          'status',
          'send',
          'read',
          'spawn',
          'send_and_wait',
          'get_result',
          'approve',
          'notifications',
          'open_browser',
          'move_window',
        ])
        .describe('실행할 기능'),
      task: z.string().optional().describe('작업 내용 (send, spawn, send_and_wait)'),
      agentType: z.string().optional().describe('에이전트 (claude, gemini, codex)'),
      surfaceId: z.string().optional().describe('서피스 ID'),
      lines: z.number().optional().describe('읽을 줄 수 (read)'),
      timeout: z.number().optional().describe('대기 초 (send_and_wait, 기본120)'),
      url: z.string().optional().describe('URL (open_browser)'),
      x: z.number().optional().describe('창 X 좌표 (move_window)'),
      y: z.number().optional().describe('창 Y 좌표 (move_window)'),
      width: z.number().optional().describe('창 너비 (move_window)'),
      height: z.number().optional().describe('창 높이 (move_window)'),
      task_id: z.string().optional().describe('작업 ID (get_result)'),
      workspaceId: z.string().optional().describe('워크스페이스 ID (spawn)'),
    }),
  },
  async (params, extra) => {
    try {
      switch (params.action) {
        // ── status ──
        case 'status': {
          // 워크스페이스 초기화 대기 (auto-launch 직후)
          let tree: any;
          for (let i = 0; i < 20; i++) {
            tree = await client.call('system.tree');
            if ((tree.workspaces ?? []).length > 0) break;
            if (i === 0) console.log('[mcp] Waiting for workspace initialization...');
            await sleep(500);
          }
          if (!tree || (tree.workspaces ?? []).length === 0) {
            return text('씨윈이 아직 초기화 중입니다. 10초 후 다시 시도하세요.');
          }
          try {
            return text(await summarizeStatus(tree));
          } catch {
            return text(tree);
          }
        }

        // ── send ──
        case 'send': {
          if (!params.task) return text({ error: true, message: 'task 파라미터가 필요합니다.' });
          const agent = params.agentType ?? 'claude';
          const sid = params.surfaceId ?? (await findAgentSurface(agent));
          if (!sid)
            return text(`${agent} 에이전트를 찾을 수 없습니다. spawn action으로 먼저 생성하세요.`);
          try {
            await client.call('agent.send_task', { surfaceId: sid, task: params.task });
            return text({ ok: true, surfaceId: sid, method: 'agent.send_task' });
          } catch {
            // Ink TUI fix: send text and Enter separately with 500ms delay
            await client.call('surface.send_text', { surfaceId: sid, text: params.task });
            await new Promise((r) => setTimeout(r, 500));
            await client.call('surface.send_text', { surfaceId: sid, text: '\r' });
            return text({ ok: true, surfaceId: sid, method: 'surface.send_text' });
          }
        }

        // ── read ──
        case 'read': {
          const sid = params.surfaceId ?? (await findAgentSurface(params.agentType));
          if (!sid) return text(`${params.agentType ?? '지정된'} 에이전트를 찾을 수 없습니다.`);
          const p: Record<string, unknown> = { surfaceId: sid };
          if (params.lines !== undefined) p.lines = params.lines;
          const result = await client.call('surface.read', p);
          const raw: string =
            result.content ?? (typeof result === 'string' ? result : JSON.stringify(result));
          // Ink TUI 렌더링 잔재 필터링 (Codex/Gemini 프롬프트 UI 줄 제거)
          const cleaned = raw
            .split('\n')
            .filter((line) => {
              const t = line.trim();
              if (!t) return false; // 빈 줄
              if (/^›\s*(Run|Use)\s/.test(t)) return false; // › Run /review, › Use /skills
              if (/^gpt-[\d.]+ default/.test(t) && t.length < 40) return false; // gpt-5.4 default · ~
              if (/^gemini-[\d.]+ /.test(t) && t.length < 40) return false; // gemini model line
              if (/^•\s*$/.test(t)) return false; // 단독 bullet
              return true;
            })
            .join('\n')
            .replace(/\n{3,}/g, '\n\n'); // 연속 빈 줄 축소
          return text(cleaned || raw);
        }

        // ── spawn ── (#3: CLI idle 대기 후 반환)
        case 'spawn': {
          if (!params.agentType)
            return text({ error: true, message: 'agentType 파라미터가 필요합니다.' });
          let wsId = params.workspaceId;
          if (!wsId) {
            let ws: { id: string } | undefined;
            for (let i = 0; i < 30; i++) {
              const tree = await client.call('system.tree');
              ws = (tree.workspaces ?? [])[0];
              if (ws) break;
              await new Promise((r) => setTimeout(r, 500));
            }
            if (!ws)
              return text(
                '워크스페이스 초기화 대기 시간 초과. 씨윈이 완전히 시작되었는지 확인하세요.',
              );
            wsId = ws.id;
          }
          const spawnParams: Record<string, unknown> = {
            agentType: params.agentType,
            workspaceId: wsId,
          };
          if (params.task) spawnParams.task = params.task;
          const spawnResult = await client.call('agent.spawn', spawnParams);
          const spawnSid = (spawnResult as any)?.surfaceId;

          // #3: CLI 초기화 대기 — PTY 생성 + idle 프롬프트 확인 (최대 30초)
          if (spawnSid && params.agentType) {
            console.log(`[mcp] spawn(${params.agentType}) — CLI idle 대기 시작`);
            let ready = false;
            for (let i = 0; i < 30; i++) {
              await sleep(1000);
              try {
                const screen = await client.call('surface.read', { surfaceId: spawnSid });
                const content = typeof screen === 'string' ? screen : (screen?.content ?? '');
                if (content.length > 0 && isAgentIdle(content, params.agentType)) {
                  ready = true;
                  console.log(`[mcp] spawn(${params.agentType}) — idle 감지 (${i + 1}초)`);
                  break;
                }
              } catch {
                /* PTY 아직 없음 — 계속 대기 */
              }
            }
            return text({ ...(spawnResult as object), ready });
          }
          return text(spawnResult);
        }

        // ── send_and_wait ── (#6, #13, #14, #16 적용)
        case 'send_and_wait': {
          if (!params.task) return text({ error: true, message: 'task 파라미터가 필요합니다.' });
          const agent = params.agentType ?? 'claude';
          const sid = params.surfaceId ?? (await findAgentSurface(agent));
          if (!sid)
            return text(`${agent} 에이전트를 찾을 수 없습니다. spawn action으로 먼저 생성하세요.`);

          // #14: 작업 전송 — PTY 없으면 최대 3회 재시도 (spawn 직후 PTY 생성 대기)
          let taskSent = false;
          for (let sendAttempt = 0; sendAttempt < 3; sendAttempt++) {
            try {
              await client.call('agent.send_task', { surfaceId: sid, task: params.task });
              taskSent = true;
              break;
            } catch {
              try {
                await client.call('surface.send_text', { surfaceId: sid, text: params.task });
                await sleep(500);
                await client.call('surface.send_text', { surfaceId: sid, text: '\r' });
                taskSent = true;
                break;
              } catch {
                // PTY 아직 없음 — 2초 대기 후 재시도
                console.log(`[mcp] send_and_wait: PTY 없음, ${sendAttempt + 1}/3 재시도`);
                await sleep(2000);
              }
            }
          }
          if (!taskSent) {
            return text({ error: true, message: 'PTY가 준비되지 않아 작업을 전달할 수 없습니다.' });
          }

          const maxWait = Math.min(params.timeout ?? 120, 300);
          const interval = 3; // #13: 폴링 간격 5초→3초
          await sleep(3000);

          for (let elapsed = 3; elapsed < maxWait; elapsed += interval) {
            await sleep(interval * 1000);

            // Progress notification (타임아웃 리셋 시도)
            try {
              const progressToken = extra._meta?.progressToken;
              if (progressToken) {
                await extra.sendNotification({
                  method: 'notifications/progress',
                  params: {
                    progressToken,
                    progress: elapsed,
                    total: maxWait,
                  },
                } as any);
              }
            } catch {
              /* best effort */
            }

            // #6: 에이전트 상태 체크 (CLI 종료/크래시 감지)
            try {
              const health = await client.call('surface.health', { surfaceId: sid });
              if (health && !health.hasPty) {
                // CLI 종료됨 — 마지막 스크롤백으로 결과 반환
                const screen = await client.call('surface.read', { surfaceId: sid });
                const content = typeof screen === 'string' ? screen : (screen?.content ?? '');
                const cleanResult = stripAnsi(content).trim();
                const lastLines = cleanResult.split('\n').slice(-30).join('\n');
                return text({
                  status: 'done',
                  agentType: agent,
                  surfaceId: sid,
                  note: 'CLI가 종료되어 마지막 출력을 반환합니다.',
                  result: lastLines,
                });
              }
              // 에이전트 상태가 done/error면 즉시 반환
              if (
                health?.agent &&
                (health.agent.status === 'done' || health.agent.status === 'error')
              ) {
                const screen = await client.call('surface.read', { surfaceId: sid });
                const content = typeof screen === 'string' ? screen : (screen?.content ?? '');
                const cleanResult = stripAnsi(content).trim();
                const lastLines = cleanResult.split('\n').slice(-30).join('\n');
                return text({
                  status: health.agent.status,
                  agentType: agent,
                  surfaceId: sid,
                  result: lastLines,
                });
              }
            } catch {
              /* health 체크 실패 — 폴링 계속 */
            }

            try {
              const screen = await client.call('surface.read', { surfaceId: sid });
              const content =
                typeof screen === 'string' ? screen : (screen.content ?? JSON.stringify(screen));
              if (isAgentIdle(content, agent)) {
                const cleanResult = stripAnsi(content).trim();
                const lastLines = cleanResult.split('\n').slice(-30).join('\n');
                // #16: 빈 결과 감지
                const nonEmpty = lastLines.split('\n').filter((l) => l.trim()).length;
                return text({
                  status: 'done',
                  agentType: agent,
                  surfaceId: sid,
                  result: lastLines,
                  ...(nonEmpty <= 2 ? { warning: '결과가 비어있음 — 작업 전달 실패 가능성' } : {}),
                });
              }
            } catch {
              /* 폴링 계속 */
            }
          }

          // 50초 내 미완료 → task_id 발급
          const taskId = `task_${++taskSeq}_${Date.now()}`;
          taskStore.set(taskId, {
            surfaceId: sid,
            agentType: agent,
            task: params.task,
            status: 'running',
            startedAt: Date.now(),
          });
          return text({
            status: 'running',
            task_id: taskId,
            agentType: agent,
            elapsed_sec: maxWait,
            instruction:
              '작업 진행중. 반드시 get_result action을 task_id와 함께 호출하여 완료 확인하세요.',
          });
        }

        // ── get_result ──
        case 'get_result': {
          if (!params.task_id)
            return text({ error: true, message: 'task_id 파라미터가 필요합니다.' });
          const entry = taskStore.get(params.task_id);
          if (!entry)
            return text({
              status: 'error',
              message: `task_id "${params.task_id}"를 찾을 수 없습니다.`,
            });
          if (entry.status === 'done') return text({ status: 'done', result: entry.result });

          try {
            const screen = await client.call('surface.read', { surfaceId: entry.surfaceId });
            const content =
              typeof screen === 'string' ? screen : (screen.content ?? JSON.stringify(screen));
            if (isAgentIdle(content, entry.agentType)) {
              const cleanResult = stripAnsi(content).trim();
              const lastLines = cleanResult.split('\n').slice(-30).join('\n');
              entry.status = 'done';
              entry.result = lastLines;
              return text({ status: 'done', agentType: entry.agentType, result: lastLines });
            }
            const elapsed = Math.round((Date.now() - entry.startedAt) / 1000);
            return text({
              status: 'running',
              task_id: params.task_id,
              agentType: entry.agentType,
              elapsed_sec: elapsed,
              instruction: '아직 진행중. 10초 후 get_result를 다시 호출하세요.',
            });
          } catch (e: any) {
            entry.status = 'error';
            return text({ status: 'error', message: e.message });
          }
        }

        // ── approve ──
        case 'approve': {
          const sid = params.surfaceId ?? (await findAgentSurface(params.agentType));
          if (!sid) return text(`${params.agentType ?? '지정된'} 에이전트를 찾을 수 없습니다.`);
          await client.call('surface.send_text', { surfaceId: sid, text: '\r' });
          return text({ ok: true, surfaceId: sid, approved: true });
        }

        // ── notifications ──
        case 'notifications': {
          const notifData = await client.call('notification.list');
          try {
            return text(summarizeNotifications(notifData));
          } catch {
            return text(notifData);
          }
        }

        // ── open_browser ──
        case 'open_browser': {
          if (!params.url) return text({ error: true, message: 'url 파라미터가 필요합니다.' });

          // system.tree에서 첫 번째 패널의 panelId를 가져옴
          const tree = await client.call('system.tree');
          const ws = (tree?.workspaces ?? [])[0];
          const panel = ws?.panels?.[0];
          if (!panel)
            return text({
              error: true,
              message: '씨윈에 패널이 없습니다. status로 먼저 확인하세요.',
            });

          const result = await client.call('panel.split', {
            panelId: panel.id,
            direction: 'horizontal',
            newPanelType: 'browser',
            url: params.url,
          });
          return text({
            ok: true,
            url: params.url,
            panelId: (result as any)?.panelId,
            surfaceId: (result as any)?.surfaceId,
            paneIndex: (result as any)?.paneIndex,
          });
        }

        // ── move_window ──
        case 'move_window': {
          if (params.x === undefined || params.y === undefined)
            return text({ error: true, message: 'x, y 파라미터가 필요합니다.' });
          const moveParams: Record<string, unknown> = { x: params.x, y: params.y };
          if (params.width !== undefined) moveParams.width = params.width;
          if (params.height !== undefined) moveParams.height = params.height;
          const result = await client.call('window.move', moveParams);
          return text({ ok: true, bounds: (result as any)?.bounds });
        }

        default:
          return text({ error: true, message: `알 수 없는 action: ${(params as any).action}` });
      }
    } catch (e: any) {
      return text({ error: true, message: e.message, action: params.action });
    }
  },
);

// ────────────────────────────────────────────
//  Start
// ────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('[cmux-mcp] Server v2 started (stdio transport)');
}

main().catch((err) => {
  console.error('[cmux-mcp] Fatal:', err);
  process.exit(1);
});
