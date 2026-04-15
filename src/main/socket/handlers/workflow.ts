/**
 * workflow.ts — Workflow execution engine.
 * Allows any AI (including Gemini/Codex) to be a "planning leader"
 * by generating a workflow JSON that the app executes step-by-step.
 *
 * Usage:
 *   cmux run-workflow workflow.json
 *
 * Workflow JSON format:
 *   {
 *     "name": "Build website",
 *     "workspaceId": "...",
 *     "steps": [
 *       { "agent": "gemini", "task": "Create index.html", "cwd": "/path" },
 *       { "agent": "claude", "task": "Review and fix", "cwd": "/path" }
 *     ]
 *   }
 */
import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';
import { ptyEvents } from '../../terminal/pty-manager';

// ANSI escape regexes (shared by readOutput and waitForIdle)
const ansiRe = /[\x1b\x9b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nq-uy=><~]/g;
const oscRe = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g;

function readOutput(surfaceId: string, lines: number): string {
  const g = globalThis as Record<string, unknown>;
  const liveBuffers = g.__cmuxLiveBuffers as Map<string, string> | undefined;
  const scrollbackStore = g.__cmuxScrollbackStore as Map<string, string> | undefined;
  const raw = liveBuffers?.get(surfaceId) ?? scrollbackStore?.get(surfaceId) ?? '';
  const clean = raw.replace(oscRe, '').replace(ansiRe, '');
  return clean.split('\n').slice(-lines).join('\n');
}

/**
 * waitForIdle — Detect when an interactive agent finishes its current task.
 * Uses dual conditions: idle pattern match + output stabilization.
 * Also monitors pty-exit in parallel (agent crash safety — risk ②).
 */
function waitForIdle(
  surfaceId: string,
  agentType: string,
  timeoutMs: number,
): Promise<{ idle: boolean; timeout: boolean; exited: boolean; output: string }> {
  return new Promise((resolve) => {
    const g = globalThis as Record<string, unknown>;
    const liveBuffers = g.__cmuxLiveBuffers as Map<string, string> | undefined;

    const startLen = (liveBuffers?.get(surfaceId) ?? '').length;
    let lastLen = startLen;
    let stableCount = 0;

    // Risk ②: Monitor pty-exit in parallel (agent crash)
    const onExit = (sid: string) => {
      if (sid !== surfaceId) return;
      cleanup();
      resolve({ idle: false, timeout: false, exited: true,
               output: readOutput(surfaceId, 30) });
    };
    ptyEvents.on('pty-exit', onExit);

    // Risk ⑤: Multiple idle patterns per agent type (version-proof)
    const idlePatterns: Record<string, string[]> = {
      gemini: ['Type your message', 'Enter your prompt', 'What can I help'],
      codex: ['What would you like', 'Enter a prompt'],
    };
    const patterns = idlePatterns[agentType] || [];

    const interval = setInterval(() => {
      const raw = liveBuffers?.get(surfaceId) ?? '';
      // Search last 500 chars of clean text for idle patterns
      const tail = raw.slice(-500).replace(ansiRe, '');

      const patternMatch = patterns.some(p => tail.includes(p))
                           && raw.length > startLen;

      const outputStable = raw.length === lastLen && raw.length > startLen;
      if (outputStable) stableCount++;
      else stableCount = 0;

      // Dual condition: (pattern AND 1s stable) OR (5s stable without pattern)
      if ((patternMatch && stableCount >= 2) || stableCount >= 10) {
        cleanup();
        resolve({ idle: true, timeout: false, exited: false,
                 output: readOutput(surfaceId, 30) });
      }

      lastLen = raw.length;
    }, 500);

    const timer = setTimeout(() => {
      cleanup();
      resolve({ idle: false, timeout: true, exited: false,
               output: readOutput(surfaceId, 30) });
    }, timeoutMs);

    function cleanup() {
      clearInterval(interval);
      clearTimeout(timer);
      ptyEvents.removeListener('pty-exit', onExit);
    }
  });
}

export function registerWorkflowHandlers(router: JsonRpcRouter, store: AppStateStore): void {
  router.register('workflow.run', async (params) => {
    const p = params as {
      name?: string;
      workspaceId?: string;
      steps: Array<{ agent: string; task: string; cwd?: string }>;
      timeout?: number;
    };

    if (!p?.steps || !Array.isArray(p.steps) || p.steps.length === 0) {
      throw new Error('steps array is required');
    }

    const state = store.getState();
    const workspaceId = p.workspaceId || state.focus.activeWorkspaceId || state.workspaces[0]?.id;
    if (!workspaceId) throw new Error('No workspace available');

    const stepTimeout = p.timeout ?? 300000; // 5 min per step
    const results: Array<{
      step: number;
      agent: string;
      task: string;
      exitCode: number | null;
      timeout: boolean;
      output: string;
    }> = [];

    for (let i = 0; i < p.steps.length; i++) {
      const step = p.steps[i];

      // 1. Spawn agent
      const panelsBefore = store.getState().panels.length;
      const spawnResult = store.dispatch({
        type: 'agent.spawn',
        payload: {
          agentType: step.agent as 'claude' | 'gemini' | 'codex' | 'opencode',
          workspaceId,
          task: step.task,
          cwd: step.cwd,
        },
      });
      if (!spawnResult.ok) {
        results.push({ step: i, agent: step.agent, task: step.task, exitCode: -1, timeout: false, output: `Spawn failed: ${spawnResult.error}` });
        continue;
      }

      // Get new surface ID
      const newPanels = store.getState().panels.slice(panelsBefore);
      const surfaceId = newPanels[0]?.activeSurfaceId;
      if (!surfaceId) {
        results.push({ step: i, agent: step.agent, task: step.task, exitCode: -1, timeout: false, output: 'No surface created' });
        continue;
      }

      // 2. All agents are now interactive — wait for idle state
      const idleResult = await waitForIdle(surfaceId, step.agent, stepTimeout);
      results.push({
        step: i,
        agent: step.agent,
        task: step.task,
        exitCode: idleResult.exited ? 1 : (idleResult.idle ? 0 : null),
        timeout: idleResult.timeout,
        output: idleResult.output,
      });
    }

    return {
      name: p.name ?? 'unnamed',
      stepsCompleted: results.filter((r) => r.exitCode === 0).length,
      stepsTotal: p.steps.length,
      results,
    };
  });
}
