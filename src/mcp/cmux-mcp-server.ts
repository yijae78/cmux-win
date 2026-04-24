#!/usr/bin/env node
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
    process.env.APPDATA ||
    path.join(process.env.USERPROFILE || '', 'AppData', 'Roaming');

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
    const home = process.env.USERPROFILE || process.env.HOME || '';
    const projectDir = path.join(
      home,
      'OneDrive - the presbyerian church of korea',
      '바탕 화면',
      'cmux-win',
    );

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

  // 1.3: stale token 감지 + 폴링 내 소켓 정리
  private async _doConnect(): Promise<void> {
    this.disconnect();
    let info = findSocketToken();

    if (info) {
      // 토큰 있음 → 먼저 연결 시도
      try {
        await this.connectAndAuth(info);
        return; // 성공
      } catch {
        // 실패 → stale token, auto-launch로 진행
        console.log('[mcp] Stale token detected, attempting auto-launch...');
        this.disconnect();
      }
    } else {
      console.log('[mcp] No token found, attempting auto-launch...');
    }

    // auto-launch
    await launchCmuxWin();

    // Wait up to 15s for connection
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 500));
      info = findSocketToken();
      if (info) {
        try {
          await this.connectAndAuth(info);
          console.log('[mcp] cmux-win launched successfully, connected!');
          return;
        } catch {
          this.disconnect(); // 폴링 내 실패 소켓 정리
        }
      }
    }
    throw new Error('cmux-win 자동 실행을 시도했으나 연결할 수 없습니다. 앱을 수동으로 시작해주세요.');
  }

  // 1.2: 10초 타임아웃 + 모든 경로 clearTimeout
  private connectAndAuth(info: { token: string; port: number }): Promise<void> {
    return new Promise((resolve, reject) => {
      const sock = new net.Socket();
      this.socket = sock;
      this.buffer = '';
      this.authenticated = false;

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
        reject(new Error(`cmux-win 연결 실패: ${err.message}`));
      });

      sock.on('close', () => {
        clearTimeout(authTimeout);
        this.authenticated = false;
        for (const [, p] of this.pending) {
          p.reject(new Error('cmux-win 연결이 끊어졌습니다'));
        }
        this.pending.clear();
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
    .replace(/\x1B\[[0-9;?]*[a-zA-Z]/g, '')
    .replace(/\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)/g, '')
    .replace(/\x1BP[^\x1B]*\x1B\\/g, '')
    .replace(/\x1B[()][0-9A-B]/g, '')
    .replace(/\x1B[>=<N~}{F|7-8]/g, '')
    .replace(/[\x00-\x08\x0B-\x0C\x0E-\x1F]/g, '');
}

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

const server = new McpServer(
  { name: 'cmux-win', version: '2.0.0' },
  {
    instructions:
      '이 MCP 서버는 "cmux-win" (별칭: 씨윈, Cw, SeaWin, cmux) 앱을 원격 제어합니다. ' +
      'cmux 도구 하나로 모든 기능을 사용합니다. action 파라미터로 기능을 선택하세요. ' +
      'send_and_wait가 status="running"을 반환하면 반드시 get_result를 반복 호출하세요. ' +
      '꺼져있어도 자동 실행됩니다.',
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

// ── Helper: 에이전트 서피스 찾기 ──
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
      '씨윈(cmux-win/Cw/SeaWin) 원격 제어 통합 도구. action으로 기능 선택.\n' +
      '■ action 목록:\n' +
      '- status: 상태 조회\n' +
      '- send: 작업 전송 (task 필수, agentType?)\n' +
      '- read: 패널 화면 읽기 (agentType?, lines?)\n' +
      '- spawn: 에이전트 생성 (agentType 필수, task?)\n' +
      '- send_and_wait: 작업+완료대기 (task 필수, timeout?)\n' +
      '- get_result: 작업 결과 확인 (task_id 필수)\n' +
      '- approve: 승인 전송 (agentType?)\n' +
      '- notifications: 알림 조회\n' +
      '■ 규칙: send_and_wait가 status="running" 반환 시 반드시 get_result를 "done"까지 반복 호출.\n' +
      '■ 씨윈이 꺼져있어도 자동 실행됩니다.',
    inputSchema: z.object({
      action: z.enum([
        'status', 'send', 'read', 'spawn',
        'send_and_wait', 'get_result', 'approve', 'notifications',
      ]).describe('실행할 기능'),
      task: z.string().optional().describe('작업 내용 (send, spawn, send_and_wait)'),
      agentType: z.string().optional().describe('에이전트 (claude, gemini, codex)'),
      surfaceId: z.string().optional().describe('서피스 ID'),
      lines: z.number().optional().describe('읽을 줄 수 (read)'),
      timeout: z.number().optional().describe('대기 초 (send_and_wait, 기본50)'),
      task_id: z.string().optional().describe('작업 ID (get_result)'),
      workspaceId: z.string().optional().describe('워크스페이스 ID (spawn)'),
    }),
  },
  async (params, extra) => {
    try {
      switch (params.action) {
        // ── status ──
        case 'status':
          return text(await client.call('system.tree'));

        // ── send ──
        case 'send': {
          if (!params.task) return text({ error: true, message: 'task 파라미터가 필요합니다.' });
          const agent = params.agentType ?? 'claude';
          const sid = params.surfaceId ?? await findAgentSurface(agent);
          if (!sid) return text(`${agent} 에이전트를 찾을 수 없습니다. spawn action으로 먼저 생성하세요.`);
          try {
            await client.call('agent.send_task', { surfaceId: sid, task: params.task });
            return text({ ok: true, surfaceId: sid, method: 'agent.send_task' });
          } catch {
            await client.call('surface.send_text', { surfaceId: sid, text: params.task + '\r' });
            return text({ ok: true, surfaceId: sid, method: 'surface.send_text' });
          }
        }

        // ── read ──
        case 'read': {
          const sid = params.surfaceId ?? await findAgentSurface(params.agentType);
          if (!sid) return text(`${params.agentType ?? '지정된'} 에이전트를 찾을 수 없습니다.`);
          const p: Record<string, unknown> = { surfaceId: sid };
          if (params.lines !== undefined) p.lines = params.lines;
          const result = await client.call('surface.read', p);
          return text(result.content ?? result);
        }

        // ── spawn ──
        case 'spawn': {
          if (!params.agentType) return text({ error: true, message: 'agentType 파라미터가 필요합니다.' });
          let wsId = params.workspaceId;
          if (!wsId) {
            const tree = await client.call('system.tree');
            const ws = (tree.workspaces ?? [])[0];
            if (!ws) return text('워크스페이스가 없습니다.');
            wsId = ws.id;
          }
          const p: Record<string, unknown> = { agentType: params.agentType, workspaceId: wsId };
          if (params.task) p.task = params.task;
          return text(await client.call('agent.spawn', p));
        }

        // ── send_and_wait ──
        case 'send_and_wait': {
          if (!params.task) return text({ error: true, message: 'task 파라미터가 필요합니다.' });
          const agent = params.agentType ?? 'claude';
          const sid = params.surfaceId ?? await findAgentSurface(agent);
          if (!sid) return text(`${agent} 에이전트를 찾을 수 없습니다. spawn action으로 먼저 생성하세요.`);

          // 작업 전송
          try {
            await client.call('agent.send_task', { surfaceId: sid, task: params.task });
          } catch {
            await client.call('surface.send_text', { surfaceId: sid, text: params.task + '\r' });
          }

          const maxWait = Math.min(params.timeout ?? 50, 50);
          const interval = 5;
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
            } catch { /* best effort */ }

            try {
              const screen = await client.call('surface.read', { surfaceId: sid });
              const content = typeof screen === 'string' ? screen : (screen.content ?? JSON.stringify(screen));
              if (isAgentIdle(content, agent)) {
                const cleanResult = stripAnsi(content).trim();
                const lastLines = cleanResult.split('\n').slice(-30).join('\n');
                return text({ status: 'done', agentType: agent, surfaceId: sid, result: lastLines });
              }
            } catch { /* 폴링 계속 */ }
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
            instruction: '⚠️ 작업 진행중. 반드시 get_result action을 task_id와 함께 호출하여 완료 확인하세요.',
          });
        }

        // ── get_result ──
        case 'get_result': {
          if (!params.task_id) return text({ error: true, message: 'task_id 파라미터가 필요합니다.' });
          const entry = taskStore.get(params.task_id);
          if (!entry) return text({ status: 'error', message: `task_id "${params.task_id}"를 찾을 수 없습니다.` });
          if (entry.status === 'done') return text({ status: 'done', result: entry.result });

          try {
            const screen = await client.call('surface.read', { surfaceId: entry.surfaceId });
            const content = typeof screen === 'string' ? screen : (screen.content ?? JSON.stringify(screen));
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
              instruction: '⚠️ 아직 진행중입니다. 10초 후 get_result를 다시 호출하세요.',
            });
          } catch (e: any) {
            entry.status = 'error';
            return text({ status: 'error', message: e.message });
          }
        }

        // ── approve ──
        case 'approve': {
          const sid = params.surfaceId ?? await findAgentSurface(params.agentType);
          if (!sid) return text(`${params.agentType ?? '지정된'} 에이전트를 찾을 수 없습니다.`);
          await client.call('surface.send_text', { surfaceId: sid, text: '\r' });
          return text({ ok: true, surfaceId: sid, approved: true });
        }

        // ── notifications ──
        case 'notifications':
          return text(await client.call('notification.list'));

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
