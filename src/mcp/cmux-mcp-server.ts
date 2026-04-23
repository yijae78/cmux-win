#!/usr/bin/env node
/**
 * cmux-win MCP Server (stdio)
 *
 * 핸드폰 Claude 앱 → Dispatch → Claude Desktop → 이 MCP 서버 → cmux-win 소켓 API
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import * as net from 'node:net';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { spawn } from 'node:child_process';

// ── stdout 보호: console.log → stderr (stdout은 MCP 프로토콜 전용) ──
console.log = (...args: unknown[]) => console.error('[mcp]', ...args);

// ────────────────────────────────────────────
//  Socket Token 탐색
// ────────────────────────────────────────────

function findSocketToken(): { token: string; port: number } | null {
  const appData =
    process.env.APPDATA ||
    path.join(process.env.USERPROFILE || '', 'AppData', 'Roaming');

  // Collect all candidates, pick the most recently modified one
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

/**
 * Auto-launch cmux-win when MCP tools are called but the app isn't running.
 * Tries multiple known paths: dev (electron + out/main), installed (.exe).
 */
function launchCmuxWin(): Promise<void> {
  return new Promise((resolve) => {
    const home = process.env.USERPROFILE || process.env.HOME || '';
    const projectDir = path.join(
      home,
      'OneDrive - the presbyerian church of korea',
      '바탕 화면',
      'cmux-win',
    );

    // 1. Dev mode: node electron/cli.js out/main/index.js
    //    (execFile + .cmd + detached fails on Windows with EINVAL/path-with-spaces,
    //     so we call node → electron/cli.js directly)
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
      }
      resolve();
      return;
    }

    // 2. Installed: cmux-win.exe in AppData
    const appData = process.env.LOCALAPPDATA || path.join(home, 'AppData', 'Local');
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
    resolve();
  });
}

// ────────────────────────────────────────────
//  JSON-RPC 2.0 Socket Client
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
  // H5: deduplicate concurrent ensureConnection() calls
  private connectingPromise: Promise<void> | null = null;

  /** 연결이 살아있지 않으면 자동 재연결 + 재인증 */
  async ensureConnection(): Promise<void> {
    if (this.socket && !this.socket.destroyed && this.authenticated) return;
    if (this.connectingPromise) return this.connectingPromise;

    this.connectingPromise = this._doConnect();
    try {
      await this.connectingPromise;
    } finally {
      this.connectingPromise = null;
    }
  }

  private async _doConnect(): Promise<void> {
    this.disconnect();

    let info = findSocketToken();
    if (!info) {
      // Auto-launch cmux-win if not running
      console.log('[mcp] cmux-win not running — attempting auto-launch...');
      await launchCmuxWin();
      // Wait up to 15s for socket-token to appear
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 500));
        info = findSocketToken();
        if (info) break;
      }
      if (!info) {
        throw new Error(
          'cmux-win 자동 실행을 시도했으나 소켓 토큰이 생성되지 않았습니다. 앱을 수동으로 시작해주세요.',
        );
      }
      console.log('[mcp] cmux-win launched successfully, connecting...');
    }

    await this.connectAndAuth(info);
  }

  private connectAndAuth(info: { token: string; port: number }): Promise<void> {
    return new Promise((resolve, reject) => {
      const sock = new net.Socket();
      this.socket = sock;
      this.buffer = '';
      this.authenticated = false;

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
        this.authenticated = false;
        reject(new Error(`cmux-win 연결 실패: ${err.message}`));
      });

      sock.on('close', () => {
        this.authenticated = false;
        for (const [, p] of this.pending) {
          p.reject(new Error('cmux-win 연결이 끊어졌습니다'));
        }
        this.pending.clear();
      });

      sock.connect(info.port, '127.0.0.1', () => {
        // auth.handshake는 ensureConnection 바깥이므로 직접 write
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
            this.authenticated = true;
            resolve();
          },
          reject: (e) => reject(new Error(`cmux-win 인증 실패: ${e.message}`)),
        });

        sock.write(authMsg);
      });
    });
  }

  /** JSON-RPC 호출. 연결이 끊겼으면 자동 재연결. */
  async call(method: string, params: Record<string, unknown> = {}): Promise<any> {
    await this.ensureConnection();

    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`요청 시간 초과 (15s): ${method}`));
      }, 15_000);

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

      this.socket!.write(
        JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n',
      );
    });
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
    .replace(/\x1B\[[0-9;?]*[a-zA-Z]/g, '')           // CSI sequences (incl. ? private modes)
    .replace(/\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)/g, '') // OSC sequences (BEL or ST terminator)
    .replace(/\x1BP[^\x1B]*\x1B\\/g, '')               // DCS sequences
    .replace(/\x1B[()][0-9A-B]/g, '')                   // Character set designations
    .replace(/\x1B[>=<N~}{F|7-8]/g, '')                 // Misc single-char escapes (DECPNM, save/restore)
    .replace(/[\x00-\x08\x0B-\x0C\x0E-\x1F]/g, '');   // C0 control chars
}

// 3-2: Idle patterns — loaded from external config, fallback to defaults
const DEFAULT_IDLE_PATTERNS: Record<string, string[]> = {
  gemini: ['Type your message', 'Enter your prompt', 'What can I help'],
  codex: ['What would you like', 'Enter a prompt'],
  claude: ['❯ ', '> '],
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

/**
 * M1: Improved idle detection — pattern must appear in last 3 lines of output
 * to avoid false positives from mid-output '> ' strings (e.g., error messages).
 */
function isAgentIdle(screenText: string, agentType: string): boolean {
  const clean = stripAnsi(screenText);
  // Only check last 3 non-empty lines for prompt patterns
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

// H1: TTL-based cleanup — purge completed tasks older than 10 minutes (runs every 60s)
const TASK_TTL_MS = 10 * 60 * 1000;
setInterval(() => {
  const now = Date.now();
  for (const [id, entry] of taskStore) {
    if (entry.status === 'done' && now - entry.startedAt > TASK_TTL_MS) {
      taskStore.delete(id);
    }
  }
}, 60_000);

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

// ────────────────────────────────────────────
//  MCP Server + 9 Tools
// ────────────────────────────────────────────

const client = new CmuxSocketClient();

const server = new McpServer(
  { name: 'cmux-win', version: '1.0.0' },
  {
    instructions:
      '이 MCP 서버는 "cmux-win" (별칭: 씨윈, Cw, C-Win, SeaWin, 씨뮥스, cmux) 앱을 원격 제어합니다. ' +
      '사용자가 "씨윈", "Cw", "cmux", "씨뮥스", "C-Win", "SeaWin" 등의 단어를 사용하면 이 서버의 도구를 사용하세요. ' +
      '씨윈은 Windows용 AI 터미널 멀티플렉서로, 여러 AI CLI(Claude, Gemini, Codex)를 동시에 실행하고 협업시킵니다. ' +
      '상태 확인은 cmux_status, 작업 지시는 cmux_send_task 또는 cmux_send_task_and_wait, 화면 읽기는 cmux_read_panel, ' +
      '에이전트 생성은 cmux_spawn_agent, 알림은 cmux_notifications, 승인은 cmux_approve를 사용합니다. ' +
      '★ 씨윈이 꺼져있어도 걱정하지 마세요 — 아무 도구를 호출하면 씨윈이 자동으로 실행됩니다. ' +
      '"씨윈 열어", "씨윈 켜" 등의 요청에는 cmux_status를 호출하세요 (자동 실행 후 상태 보고). ' +
      '★ 중요: cmux_send_task_and_wait가 status="running"을 반환하면, 반드시 cmux_get_result를 호출하여 ' +
      'status가 "done"이 될 때까지 반복하세요. 완료되면 결과를 사용자에게 보고하세요. ' +
      '절대 polling을 건너뛰지 마세요. 사용자가 핸드폰으로 결과를 기다리고 있습니다.',
  },
);

function text(data: unknown) {
  return {
    content: [
      {
        type: 'text' as const,
        text: typeof data === 'string' ? data : JSON.stringify(data, null, 2),
      },
    ],
  };
}

// ── 0. cmux_launch (씨윈 실행 전용) ──
server.registerTool(
  'cmux_launch',
  {
    title: '씨윈 실행/열기',
    description:
      '씨윈(cmux-win/Cw/SeaWin)을 실행합니다. 씨윈이 이미 실행 중이면 상태를 반환하고, 꺼져 있으면 자동으로 실행한 후 상태를 반환합니다. ' +
      '"씨윈 열어", "씨윈 켜", "씨윈 실행해", "씨윈 시작", "Cw 열어", "cmux 실행" 등의 요청에 반드시 이 도구를 사용하세요. ' +
      '★ 이 도구는 씨윈이 꺼져있어도 호출 가능합니다 — 자동으로 앱을 실행합니다.',
  },
  async () => {
    try {
      const tree = await client.call('system.tree');
      return text({ status: 'running', ...tree });
    } catch (e: any) {
      return text({ status: 'launch_attempted', message: '씨윈 자동 실행을 시도했습니다. 잠시 후 cmux_status로 확인하세요.', error: e.message });
    }
  },
);

// ── 1. cmux_status ──
server.registerTool(
  'cmux_status',
  {
    title: '씨윈 상태 조회',
    description:
      '씨윈(cmux-win/Cw/SeaWin) 전체 상태를 조회합니다. 워크스페이스, 패널, 에이전트, 포커스 정보를 반환합니다. ' +
      '"씨윈 상태", "cmux 상태", "Cw 뭐 하고 있어?" 등의 요청에 사용하세요. ' +
      '★ 씨윈이 꺼져있어도 호출 가능 — 자동으로 실행 후 연결합니다.',
  },
  async () => text(await client.call('system.tree')),
);

// ── 2. cmux_send_task ──
server.registerTool(
  'cmux_send_task',
  {
    title: '씨윈 작업 지시',
    description:
      '씨윈(cmux-win/Cw) 안의 AI 에이전트에게 작업을 전달합니다. agentType으로 대상 지정 가능 (claude, gemini, codex). 생략 시 Claude를 자동 탐색합니다. ' +
      '"씨윈에 작업 시켜", "씨윈 Gemini에게 전달해", "Cw Claude한테 이거 해달라고 해" 등의 요청에 사용하세요. ' +
      '★ 씨윈이 꺼져있어도 호출 가능 — 자동으로 실행 후 연결합니다.',
    inputSchema: z.object({
      task: z.string().describe('전달할 작업 내용'),
      agentType: z.string().optional().describe('대상 에이전트 타입 (claude, gemini, codex). 생략 시 claude'),
      surfaceId: z.string().optional().describe('대상 서피스 ID (생략 시 agentType으로 자동 탐색)'),
    }),
  },
  async ({ task, agentType, surfaceId }) => {
    if (!surfaceId) {
      surfaceId = await findAgentSurface(agentType ?? 'claude');
      if (!surfaceId) {
        return text(`${agentType ?? 'claude'} 에이전트를 찾을 수 없습니다. 먼저 cmux_spawn_agent로 생성하거나 surfaceId를 직접 지정해주세요.`);
      }
    }
    try {
      await client.call('agent.send_task', { surfaceId, task });
      return text({ ok: true, surfaceId, method: 'agent.send_task' });
    } catch {
      await client.call('surface.send_text', { surfaceId, text: task + '\r' });
      return text({ ok: true, surfaceId, method: 'surface.send_text (fallback)' });
    }
  },
);

// ── 3. cmux_read_panel ──
server.registerTool(
  'cmux_read_panel',
  {
    title: '씨윈 패널 읽기',
    description:
      '씨윈(cmux-win/Cw) 터미널/패널 화면의 텍스트를 읽습니다. agentType으로 대상 지정 가능. ' +
      '"씨윈 화면 보여줘", "씨윈 Gemini 화면 읽어", "Cw 터미널 읽어" 등의 요청에 사용하세요. ' +
      '★ 씨윈이 꺼져있어도 호출 가능 — 자동으로 실행 후 연결합니다.',
    inputSchema: z.object({
      agentType: z.string().optional().describe('대상 에이전트 타입 (claude, gemini, codex)'),
      surfaceId: z.string().optional().describe('서피스 ID (생략 시 agentType으로 자동 탐색)'),
      lines: z.number().optional().describe('읽을 줄 수 (기본: 전체)'),
    }),
  },
  async ({ agentType, surfaceId, lines }) => {
    if (!surfaceId) {
      surfaceId = await findAgentSurface(agentType);
      if (!surfaceId) {
        return text(`${agentType ?? '지정된'} 에이전트를 찾을 수 없습니다.`);
      }
    }
    const params: Record<string, unknown> = { surfaceId };
    if (lines !== undefined) params.lines = lines;
    const result = await client.call('surface.read', params);
    return text(result.content ?? result);
  },
);

// ── 4. cmux_spawn_agent ──
server.registerTool(
  'cmux_spawn_agent',
  {
    title: '씨윈 에이전트 생성',
    description:
      '씨윈(cmux-win/Cw)에 새 AI 에이전트(gemini, codex 등)를 패널에 생성합니다. workspaceId 생략 시 자동 탐색합니다. ' +
      '"씨윈에 Gemini 띄워", "Cw에 Codex 추가해", "cmux에 에이전트 하나 더 만들어" 등의 요청에 사용하세요. ' +
      '★ 씨윈이 꺼져있어도 호출 가능 — 자동으로 실행 후 연결합니다.',
    inputSchema: z.object({
      agentType: z.string().describe('에이전트 타입 (gemini, codex, claude)'),
      task: z.string().optional().describe('초기 작업 내용'),
      workspaceId: z.string().optional().describe('워크스페이스 ID (생략 시 자동)'),
    }),
  },
  async ({ agentType, task, workspaceId }) => {
    if (!workspaceId) {
      const tree = await client.call('system.tree');
      const ws = (tree.workspaces ?? [])[0];
      if (!ws) return text('워크스페이스가 없습니다.');
      workspaceId = ws.id;
    }
    const params: Record<string, unknown> = { agentType, workspaceId };
    if (task) params.task = task;
    return text(await client.call('agent.spawn', params));
  },
);

// ── 5. cmux_notifications ──
server.registerTool(
  'cmux_notifications',
  {
    title: '씨윈 알림 조회',
    description:
      '씨윈(cmux-win/Cw) 알림 목록을 조회합니다. "씨윈 알림 있어?", "Cw 알림 확인", "cmux 노티피케이션" 등의 요청에 사용하세요. ' +
      '★ 씨윈이 꺼져있어도 호출 가능 — 자동으로 실행 후 연결합니다.',
  },
  async () => text(await client.call('notification.list')),
);

// ── 6. cmux_send_task_and_wait ──
server.registerTool(
  'cmux_send_task_and_wait',
  {
    title: '씨윈 작업 지시 + 완료 대기',
    description:
      '씨윈(cmux-win/Cw) AI 에이전트에게 작업을 전달하고 완료될 때까지 대기합니다. ' +
      '완료되면 결과를 반환하고, 시간이 오래 걸리면 task_id를 반환합니다. ' +
      'task_id를 받으면 반드시 cmux_get_result를 반복 호출하여 최종 결과를 받으세요. ' +
      '"씨윈에 작업 시키고 결과 알려줘", "Cw Gemini한테 이거 하고 결과 보고해" 등의 요청에 사용하세요. ' +
      '★ 씨윈이 꺼져있어도 호출 가능 — 자동으로 실행 후 연결합니다.',
    inputSchema: z.object({
      task: z.string().describe('전달할 작업 내용'),
      agentType: z.string().optional().describe('대상 에이전트 타입 (claude, gemini, codex). 생략 시 claude'),
      surfaceId: z.string().optional().describe('대상 서피스 ID (생략 시 자동 탐색)'),
      timeout: z.number().optional().describe('최대 대기 시간(초). 기본 50초'),
    }),
  },
  async ({ task, agentType, surfaceId, timeout }) => {
    const agent = agentType ?? 'claude';
    if (!surfaceId) {
      surfaceId = await findAgentSurface(agent);
      if (!surfaceId) {
        return text(`${agent} 에이전트를 찾을 수 없습니다. cmux_spawn_agent로 먼저 생성하세요.`);
      }
    }

    // 작업 전송
    try {
      await client.call('agent.send_task', { surfaceId, task });
    } catch {
      await client.call('surface.send_text', { surfaceId, text: task + '\r' });
    }

    const maxWait = Math.min(timeout ?? 50, 50); // 최대 50초 (60초 타임아웃 안전 마진)
    const interval = 5;

    // 작업 전송 후 잠시 대기 (에이전트가 작업 시작할 시간)
    await sleep(3000);

    // 폴링: 완료까지 대기
    for (let elapsed = 3; elapsed < maxWait; elapsed += interval) {
      await sleep(interval * 1000);

      try {
        // Progress 로그 전송 (타임아웃 리셋 시도)
        await server.sendLoggingMessage({
          level: 'info',
          data: `씨윈 작업 진행중... ${elapsed + interval}초 경과`,
        });
      } catch { /* best effort */ }

      try {
        const screen = await client.call('surface.read', { surfaceId });
        const content = typeof screen === 'string' ? screen : (screen.content ?? JSON.stringify(screen));

        if (isAgentIdle(content, agent)) {
          // 완료! 결과 반환
          const cleanResult = stripAnsi(content).trim();
          const lastLines = cleanResult.split('\n').slice(-30).join('\n');
          return text({
            status: 'done',
            agentType: agent,
            surfaceId,
            result: lastLines,
          });
        }
      } catch { /* surface.read 실패 시 계속 폴링 */ }
    }

    // 50초 안에 미완료 → task_id 발급, 백그라운드 체크용
    const taskId = `task_${++taskSeq}_${Date.now()}`;
    taskStore.set(taskId, {
      surfaceId: surfaceId!,
      agentType: agent,
      task,
      status: 'running',
      startedAt: Date.now(),
    });

    return text({
      status: 'running',
      task_id: taskId,
      agentType: agent,
      elapsed_sec: maxWait,
      instruction: '⚠️ 작업이 아직 진행중입니다. 반드시 cmux_get_result 도구를 task_id와 함께 호출하여 완료를 확인하세요.',
    });
  },
);

// ── 7. cmux_get_result ──
server.registerTool(
  'cmux_get_result',
  {
    title: '씨윈 작업 결과 확인',
    description:
      '씨윈(cmux-win/Cw) 진행 중인 작업의 완료 여부와 결과를 확인합니다. ' +
      'cmux_send_task_and_wait가 status="running"을 반환했을 때 사용합니다. ' +
      'status가 "done"이 될 때까지 반복 호출하세요. 절대 중단하지 마세요.',
    inputSchema: z.object({
      task_id: z.string().describe('cmux_send_task_and_wait에서 반환된 task_id'),
    }),
  },
  async ({ task_id }) => {
    const entry = taskStore.get(task_id);
    if (!entry) {
      return text({ status: 'error', message: `task_id "${task_id}"를 찾을 수 없습니다.` });
    }

    if (entry.status === 'done') {
      return text({ status: 'done', result: entry.result });
    }

    try {
      const screen = await client.call('surface.read', { surfaceId: entry.surfaceId });
      const content = typeof screen === 'string' ? screen : (screen.content ?? JSON.stringify(screen));

      if (isAgentIdle(content, entry.agentType)) {
        const cleanResult = stripAnsi(content).trim();
        const lastLines = cleanResult.split('\n').slice(-30).join('\n');
        entry.status = 'done';
        entry.result = lastLines;

        return text({
          status: 'done',
          agentType: entry.agentType,
          result: lastLines,
        });
      }

      const elapsed = Math.round((Date.now() - entry.startedAt) / 1000);
      return text({
        status: 'running',
        task_id,
        agentType: entry.agentType,
        elapsed_sec: elapsed,
        instruction: '⚠️ 아직 진행중입니다. 10초 후 cmux_get_result를 다시 호출하세요. 절대 중단하지 마세요.',
      });
    } catch (e: any) {
      entry.status = 'error';
      return text({ status: 'error', message: e.message });
    }
  },
);

// ── 8. cmux_test_timeout ──
server.registerTool(
  'cmux_test_timeout',
  {
    title: '씨윈 타임아웃 테스트',
    description:
      'MCP 도구 타임아웃 리셋 테스트용. 지정 시간(초) 동안 대기하며 progress를 전송합니다. ' +
      '60초 이상 생존하면 progress 리셋이 작동하는 것입니다.',
    inputSchema: z.object({
      waitSeconds: z.number().describe('대기 시간(초). 예: 70'),
    }),
  },
  async ({ waitSeconds }) => {
    const start = Date.now();
    const rounds = Math.ceil(waitSeconds / 5);

    for (let i = 0; i < rounds; i++) {
      await sleep(5000);
      const elapsed = Math.round((Date.now() - start) / 1000);
      try {
        await server.sendLoggingMessage({
          level: 'info',
          data: `타임아웃 테스트: ${elapsed}초 경과 / ${waitSeconds}초 목표`,
        });
      } catch { /* best effort */ }
    }

    const totalElapsed = Math.round((Date.now() - start) / 1000);
    return text({
      status: 'survived',
      elapsed_sec: totalElapsed,
      target_sec: waitSeconds,
      message: `${totalElapsed}초 생존! Progress 리셋 ${totalElapsed > 60 ? '작동 확인!' : '미확인 (60초 미만)'}`,
    });
  },
);

// ── 9. cmux_approve ──
server.registerTool(
  'cmux_approve',
  {
    title: '씨윈 수동 승인',
    description:
      '씨윈(cmux-win/Cw)에서 승인 대기 중인 에이전트에 Enter를 전송하여 승인합니다. agentType으로 대상 지정 가능. ' +
      '"씨윈 승인해줘", "씨윈 Gemini 승인", "Cw approve" 등의 요청에 사용하세요. ' +
      '★ 씨윈이 꺼져있어도 호출 가능 — 자동으로 실행 후 연결합니다.',
    inputSchema: z.object({
      agentType: z.string().optional().describe('대상 에이전트 타입 (claude, gemini, codex)'),
      surfaceId: z.string().optional().describe('승인할 서피스 ID (생략 시 agentType으로 자동 탐색)'),
    }),
  },
  async ({ agentType, surfaceId }) => {
    if (!surfaceId) {
      surfaceId = await findAgentSurface(agentType);
      if (!surfaceId) {
        return text(`${agentType ?? '지정된'} 에이전트를 찾을 수 없습니다.`);
      }
    }
    await client.call('surface.send_text', { surfaceId, text: '\r' });
    return text({ ok: true, surfaceId, approved: true });
  },
);

// ────────────────────────────────────────────
//  Helpers
// ────────────────────────────────────────────

async function findAgentSurface(agentType?: string): Promise<string | undefined> {
  try {
    const tree = await client.call('system.tree');
    if (!tree || typeof tree !== 'object') return undefined;
    for (const ws of (tree as { workspaces?: { agents?: { agentType?: string; surfaceId?: string }[] }[] }).workspaces ?? []) {
      for (const agent of ws.agents ?? []) {
        const t = (agent.agentType ?? '').toLowerCase();
        if (!agentType || t === agentType.toLowerCase()) {
          return agent.surfaceId;
        }
      }
    }
  } catch {
    // M6: connection failure or malformed response — return undefined
  }
  return undefined;
}

// ────────────────────────────────────────────
//  Start
// ────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('[cmux-mcp] Server started (stdio transport)');
}

main().catch((err) => {
  console.error('[cmux-mcp] Fatal:', err);
  process.exit(1);
});
