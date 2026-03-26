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

function waitForExit(surfaceId: string, timeoutMs: number): Promise<{ exitCode: number | null; timeout: boolean }> {
  return new Promise((resolve) => {
    const onExit = (sid: string, exitInfo: { exitCode: number }) => {
      if (sid === surfaceId) {
        clearTimeout(timer);
        ptyEvents.removeListener('pty-exit', onExit);
        resolve({ exitCode: exitInfo.exitCode, timeout: false });
      }
    };
    const timer = setTimeout(() => {
      ptyEvents.removeListener('pty-exit', onExit);
      resolve({ exitCode: null, timeout: true });
    }, timeoutMs);
    ptyEvents.on('pty-exit', onExit);
  });
}

function readOutput(surfaceId: string, lines: number): string {
  const g = globalThis as Record<string, unknown>;
  const liveBuffers = g.__cmuxLiveBuffers as Map<string, string> | undefined;
  const scrollbackStore = g.__cmuxScrollbackStore as Map<string, string> | undefined;
  const raw = liveBuffers?.get(surfaceId) ?? scrollbackStore?.get(surfaceId) ?? '';
  const ansiRe = /[\x1b\x9b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nq-uy=><~]/g;
  const oscRe = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g;
  const clean = raw.replace(oscRe, '').replace(ansiRe, '');
  return clean.split('\n').slice(-lines).join('\n');
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

      // 2. Wait for non-interactive agents (gemini, codex)
      if (step.agent === 'gemini' || step.agent === 'codex') {
        const waitResult = await waitForExit(surfaceId, stepTimeout);
        const output = readOutput(surfaceId, 30);
        results.push({
          step: i,
          agent: step.agent,
          task: step.task,
          exitCode: waitResult.exitCode,
          timeout: waitResult.timeout,
          output,
        });
      } else {
        // Claude/opencode: interactive, don't wait for exit
        results.push({
          step: i,
          agent: step.agent,
          task: step.task,
          exitCode: null,
          timeout: false,
          output: '(interactive agent — not waiting for exit)',
        });
      }
    }

    return {
      name: p.name ?? 'unnamed',
      stepsCompleted: results.filter((r) => r.exitCode === 0).length,
      stepsTotal: p.steps.length,
      results,
    };
  });
}
