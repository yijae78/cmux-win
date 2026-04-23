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

  /** 연결이 살아있지 않으면 자동 재연결 + 재인증 */
  async ensureConnection(): Promise<void> {
    if (this.socket && !this.socket.destroyed && this.authenticated) return;
    this.disconnect();

    const info = findSocketToken();
    if (!info) {
      throw new Error(
        'cmux-win이 실행 중이 아닙니다. 앱을 먼저 시작해주세요. (socket-token 파일 없음)',
      );
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
//  MCP Server + 6 Tools
// ────────────────────────────────────────────

const client = new CmuxSocketClient();

const server = new McpServer({
  name: 'cmux-win',
  version: '1.0.0',
});

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

// ── 1. cmux_status ──
server.registerTool(
  'cmux_status',
  {
    title: '상태 조회',
    description:
      'cmux-win 전체 상태 — 워크스페이스, 패널, 에이전트, 포커스 정보를 반환합니다.',
  },
  async () => text(await client.call('system.tree')),
);

// ── 2. cmux_send_task ──
server.registerTool(
  'cmux_send_task',
  {
    title: '작업 지시',
    description:
      'AI 에이전트에게 작업을 전달합니다. surfaceId 생략 시 첫 번째 Claude 에이전트를 자동 탐색합니다.',
    inputSchema: z.object({
      task: z.string().describe('전달할 작업 내용'),
      surfaceId: z.string().optional().describe('대상 서피스 ID (생략 시 자동 탐색)'),
    }),
  },
  async ({ task, surfaceId }) => {
    if (!surfaceId) {
      surfaceId = await findClaudeSurface();
      if (!surfaceId) {
        return text('Claude 에이전트를 찾을 수 없습니다. surfaceId를 직접 지정해주세요.');
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
    title: '패널 읽기',
    description: '터미널/패널 화면의 텍스트를 읽습니다.',
    inputSchema: z.object({
      surfaceId: z.string().describe('서피스 ID'),
      lines: z.number().optional().describe('읽을 줄 수 (기본: 전체)'),
    }),
  },
  async ({ surfaceId, lines }) => {
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
    title: '에이전트 생성',
    description:
      '새 AI 에이전트(gemini, codex 등)를 패널에 생성합니다. workspaceId 생략 시 자동 탐색합니다.',
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
    title: '알림 조회',
    description: 'cmux-win 알림 목록을 조회합니다.',
  },
  async () => text(await client.call('notification.list')),
);

// ── 6. cmux_approve ──
server.registerTool(
  'cmux_approve',
  {
    title: '수동 승인',
    description: '승인 대기 중인 에이전트에 Enter를 전송하여 승인합니다.',
    inputSchema: z.object({
      surfaceId: z.string().describe('승인할 서피스 ID'),
    }),
  },
  async ({ surfaceId }) => {
    await client.call('surface.send_text', { surfaceId, text: '\r' });
    return text({ ok: true, surfaceId, approved: true });
  },
);

// ────────────────────────────────────────────
//  Helpers
// ────────────────────────────────────────────

async function findClaudeSurface(): Promise<string | undefined> {
  const tree = await client.call('system.tree');
  for (const ws of tree.workspaces ?? []) {
    for (const panel of ws.panels ?? []) {
      for (const surf of panel.surfaces ?? []) {
        const t = (surf.agent?.type ?? surf.agent?.cli ?? '').toLowerCase();
        if (t === 'claude') return surf.id;
      }
    }
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
