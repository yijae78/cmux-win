/**
 * BridgeWatcher — Cowork Bridge for cmux-win.
 *
 * File-system mailbox pattern: external processes (e.g. Claude Desktop, Dispatch)
 * drop task.json files into inbox/, BridgeWatcher picks them up, sends the prompt
 * to the target panel via store.dispatch, polls for output, and writes results
 * to outbox/.
 *
 * Folders:
 *   inbox/      ← *.task.json dropped by external process
 *   outbox/     ← {id}.result.json written by BridgeWatcher
 *   processed/  ← completed tasks moved here
 *   heartbeat.json ← periodic alive signal
 */
import fs from 'fs';
import path from 'path';
import os from 'os';
import type { AppStateStore } from './sot/store';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface BridgeTask {
  id: string;
  target_panel: number;
  prompt: string;
  mode: 'leader' | 'direct';
  timeout_sec: number;
  created_at: string;
}

interface BridgeResult {
  id: string;
  status: 'completed' | 'timeout' | 'error';
  output: string;
  started_at: string;
  ended_at: string;
  panel: number;
}

interface ActivePoller {
  timer: NodeJS.Timeout;
  accumulatedOutput: string;
  lastBufferLength: number;
  lastNewOutputTime: number;
}

// ---------------------------------------------------------------------------
// BridgeWatcher
// ---------------------------------------------------------------------------
export class BridgeWatcher {
  private store: AppStateStore;
  private basePath = '';
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private scanTimer: NodeJS.Timeout | null = null;
  private activePollers = new Map<string, ActivePoller>();

  constructor(store: AppStateStore) {
    this.store = store;
  }

  // ── Lifecycle ────────────────────────────────────────────────────────

  start(): void {
    const settings = this.store.getState().settings.bridge;
    this.basePath = settings.basePath || path.join(os.homedir(), 'cmux-bridge');
    this.ensureDirs();

    // Poll inbox every 1 second
    this.scanTimer = setInterval(() => this.scanInbox(), 1000);

    // Heartbeat
    const hbMs = settings.heartbeatIntervalSec * 1000;
    this.heartbeatTimer = setInterval(() => this.writeHeartbeat(), hbMs);
    this.writeHeartbeat(); // immediate first write

    console.warn(`[bridge] Watching ${path.join(this.basePath, 'inbox')}`);
  }

  stop(): void {
    if (this.scanTimer) {
      clearInterval(this.scanTimer);
      this.scanTimer = null;
    }
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    for (const [, poller] of this.activePollers) {
      clearInterval(poller.timer);
    }
    this.activePollers.clear();
  }

  // ── Directory setup ──────────────────────────────────────────────────

  private ensureDirs(): void {
    for (const dir of ['inbox', 'outbox', 'processed']) {
      const p = path.join(this.basePath, dir);
      if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
    }
  }

  // ── Inbox scanning ──────────────────────────────────────────────────

  private scanInbox(): void {
    const inboxPath = path.join(this.basePath, 'inbox');
    let files: string[];
    try {
      files = fs.readdirSync(inboxPath).filter((f) => f.endsWith('.task.json'));
    } catch {
      return;
    }

    for (const file of files) {
      const filePath = path.join(inboxPath, file);
      // Hostname-scoped lock — prevents duplicate processing via OneDrive sync
      const lockPath = filePath.replace('.task.json', `.${os.hostname()}.processing`);

      try {
        fs.renameSync(filePath, lockPath); // atomic lock
      } catch {
        continue; // another process grabbed it first
      }

      try {
        const content = fs.readFileSync(lockPath, 'utf8');
        const task: BridgeTask = JSON.parse(content);
        this.processTask(task, lockPath);
      } catch (err) {
        console.error('[bridge] Failed to parse task:', err);
        this.writeResult({
          id: 'parse-error',
          status: 'error',
          output: `Parse error: ${err}`,
          started_at: new Date().toISOString(),
          ended_at: new Date().toISOString(),
          panel: -1,
        });
        this.moveToProcessed(lockPath);
      }
    }
  }

  // ── Task processing ─────────────────────────────────────────────────

  private processTask(task: BridgeTask, lockPath: string): void {
    const state = this.store.getState();
    const panel = state.panels.find((p) => p.paneIndex === task.target_panel);

    if (!panel) {
      this.writeResult({
        id: task.id,
        status: 'error',
        output: `Panel %${task.target_panel} not found`,
        started_at: new Date().toISOString(),
        ended_at: new Date().toISOString(),
        panel: task.target_panel,
      });
      this.moveToProcessed(lockPath);
      return;
    }

    const surfaceId = panel.activeSurfaceId;
    const startedAt = new Date().toISOString();

    // Leader mode: prepend orchestration prefix
    let prompt = task.prompt;
    if (task.mode === 'leader') {
      prompt =
        '다음 작업을 수행해. 필요하면 tmux split-window -h로 ' +
        '다른 AI(gemini, codex)를 실행해서 협업해:\n' +
        prompt;
    }

    // Dispatch surface.send_text — triggers side-effect → writeToPty
    // Verified: store.ts:101 emits 'side-effect' → index.ts:194 calls writeToPty()
    // No renderer broadcast (state unchanged)
    this.store.dispatch({
      type: 'surface.send_text',
      payload: { surfaceId, text: prompt + '\r' },
    });

    console.warn(`[bridge] Task ${task.id} → panel %${task.target_panel} (${task.mode})`);

    this.startPolling(task.id, surfaceId, startedAt, task.timeout_sec, lockPath, task.target_panel);
  }

  // ── Result polling (polled-diff pattern — buffer overflow safe) ─────

  private startPolling(
    taskId: string,
    surfaceId: string,
    startedAt: string,
    timeoutSec: number,
    lockPath: string,
    panelIndex: number,
  ): void {
    const pollMs = this.store.getState().settings.bridge.pollIntervalSec * 1000;
    const deadline = Date.now() + timeoutSec * 1000;
    const liveBuffers = (globalThis as Record<string, unknown>)
      .__cmuxLiveBuffers as Map<string, string> | undefined;

    const poller: ActivePoller = {
      timer: null as unknown as NodeJS.Timeout,
      accumulatedOutput: '',
      lastBufferLength: (liveBuffers?.get(surfaceId) ?? '').length,
      lastNewOutputTime: Date.now(),
    };

    poller.timer = setInterval(() => {
      const buf = liveBuffers?.get(surfaceId) ?? '';

      // Buffer overflow detection: if current length < last recorded,
      // the buffer was truncated (MAX_LIVE_BUFFER=100KB) — reset baseline
      if (buf.length < poller.lastBufferLength) {
        poller.lastBufferLength = 0;
      }

      // Extract only new data since last poll
      const newPart = buf.slice(poller.lastBufferLength);
      poller.lastBufferLength = buf.length;

      if (newPart.length > 0) {
        poller.accumulatedOutput += newPart;
        poller.lastNewOutputTime = Date.now();
      }

      // Strip ANSI escape sequences for clean text analysis
      const clean = poller.accumulatedOutput.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '');

      // Termination: (marker + 3s idle) OR timeout
      // Double condition prevents false positives from mid-output "DONE" text
      const hasMarker =
        clean.includes('===BRIDGE_DONE===') ||
        clean.includes('===END===') ||
        clean.includes('작업완료') ||
        clean.includes('DONE');
      const isIdle = Date.now() - poller.lastNewOutputTime > 3000;
      const isTimeout = Date.now() > deadline;

      if ((hasMarker && isIdle) || isTimeout) {
        clearInterval(poller.timer);
        this.activePollers.delete(taskId);

        this.writeResult({
          id: taskId,
          status: isTimeout ? 'timeout' : 'completed',
          output: clean,
          started_at: startedAt,
          ended_at: new Date().toISOString(),
          panel: panelIndex,
        });
        this.moveToProcessed(lockPath);

        console.warn(
          `[bridge] Task ${taskId} ${isTimeout ? 'timed out' : 'completed'} (${Math.round((Date.now() - new Date(startedAt).getTime()) / 1000)}s)`,
        );
      }
    }, pollMs);

    this.activePollers.set(taskId, poller);
  }

  // ── Result writing ──────────────────────────────────────────────────

  private writeResult(result: BridgeResult): void {
    const outPath = path.join(this.basePath, 'outbox', `${result.id}.result.json`);
    try {
      fs.writeFileSync(outPath, JSON.stringify(result, null, 2));
    } catch (err) {
      console.error('[bridge] Failed to write result:', err);
    }
  }

  private moveToProcessed(lockPath: string): void {
    const dest = path.join(this.basePath, 'processed', path.basename(lockPath));
    try {
      fs.renameSync(lockPath, dest);
    } catch {
      try {
        fs.unlinkSync(lockPath);
      } catch {}
    }
  }

  // ── Heartbeat ───────────────────────────────────────────────────────

  private writeHeartbeat(): void {
    const state = this.store.getState();
    const heartbeat = {
      alive: true,
      ts: new Date().toISOString(),
      hostname: os.hostname(),
      panels: state.panels.map((p) => ({
        index: p.paneIndex,
        type: p.panelType,
        surface: p.activeSurfaceId,
      })),
      agents: state.agents.map((a) => ({
        type: a.agentType,
        status: a.status,
        surface: a.surfaceId,
      })),
    };
    try {
      fs.writeFileSync(path.join(this.basePath, 'heartbeat.json'), JSON.stringify(heartbeat, null, 2));
    } catch {}
  }
}
