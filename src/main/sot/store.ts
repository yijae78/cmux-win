import { EventEmitter } from 'node:events';
import { produce } from 'immer';
import { ActionSchema, type Action } from '../../shared/actions';
import type { AppState, PanelLayoutTree } from '../../shared/types';
import { STATE_HISTORY_MAX } from '../../shared/constants';
import { createDefaultState } from './create-default-state';
import crypto from 'node:crypto';
import {
  findLeaf,
  replaceLeaf,
  updateRatioForPanel,
  removeLeaf,
} from '../../shared/panel-layout-utils';

export interface DispatchResult {
  ok: boolean;
  error?: string;
}

export interface HistoryEntry {
  action: Action;
  timestamp: number;
}

// 6단계 미들웨어 인터페이스 (설계안 §3)
export interface Middleware {
  // 1단계: 검증 후, 변경 전 (중단 가능)
  beforeMutation?: (
    action: Action,
    state: Readonly<AppState>,
  ) => { abort?: boolean; reason?: string };
  // 3단계: 변경 후, 사이드이펙트
  afterMutation?: (
    action: Action,
    prevState: Readonly<AppState>,
    nextState: Readonly<AppState>,
  ) => void;
  // 4~6단계: 비동기 후처리 (persistence, broadcast, audit)
  post?: (action: Action, prevState: Readonly<AppState>, nextState: Readonly<AppState>) => void;
}

export class AppStateStore extends EventEmitter {
  private state: AppState;
  private history: HistoryEntry[] = [];
  private middlewares: Middleware[] = [];

  constructor(initialState?: AppState) {
    super();
    this.state = initialState ?? createDefaultState();
  }

  getState(): Readonly<AppState> {
    return this.state;
  }

  getHistory(): ReadonlyArray<HistoryEntry> {
    return this.history;
  }

  use(mw: Middleware): void {
    this.middlewares.push(mw);
  }

  // BUG-14: 세션 복원 시 고아 워크스페이스를 새 윈도우에 입양
  adoptOrphanWorkspaces(windowId: string): void {
    this.state = produce(this.state, (draft) => {
      const win = draft.windows.find((w) => w.id === windowId);
      if (!win) return;
      for (const ws of draft.workspaces) {
        if (!ws.windowId || !draft.windows.some((w) => w.id === ws.windowId)) {
          ws.windowId = windowId;
          if (!win.workspaceIds.includes(ws.id)) {
            win.workspaceIds.push(ws.id);
          }
        }
      }
    });
    this.emit('change', { type: 'session.restore' });
  }

  dispatch(rawAction: unknown): DispatchResult {
    // ===== 1단계: Validation =====
    const parsed = ActionSchema.safeParse(rawAction);
    if (!parsed.success) return { ok: false, error: parsed.error.message };
    const action = parsed.data;

    // beforeMutation 미들웨어 (추가 검증, 중단 가능)
    for (const mw of this.middlewares) {
      if (mw.beforeMutation) {
        const result = mw.beforeMutation(action, this.state);
        if (result.abort) return { ok: false, error: result.reason ?? 'Aborted by middleware' };
      }
    }

    const prevState = this.state;

    try {
      // ===== 3단계: SideEffects 전용 액션 =====
      if (action.type === 'surface.send_text') {
        this.emit('side-effect', {
          type: 'pty-write',
          surfaceId: action.payload.surfaceId,
          text: action.payload.text,
        });
        // BUG-10: try-catch로 감싸서 체인 보호
        for (const mw of this.middlewares) {
          try {
            mw.afterMutation?.(action, prevState, prevState);
          } catch (err) {
            console.error('[Middleware] afterMutation error:', err);
          }
        }
        for (const mw of this.middlewares) {
          try {
            mw.post?.(action, prevState, prevState);
          } catch (err) {
            console.error('[Middleware] post error:', err);
          }
        }
        return { ok: true };
      }

      // ===== 2단계: Mutation (Immer) =====
      this.state = produce(this.state, (draft) => {
        this.applyAction(draft, action);
      });

      // 히스토리
      this.history.push({ action, timestamp: Date.now() });
      if (this.history.length > STATE_HISTORY_MAX) this.history.shift();

      // ===== 3단계: afterMutation 미들웨어 (BUG-10: try-catch) =====
      for (const mw of this.middlewares) {
        try {
          mw.afterMutation?.(action, prevState, this.state);
        } catch (err) {
          console.error('[Middleware] afterMutation error:', err);
        }
      }

      // ===== 4~6단계: post 미들웨어 (BUG-10: try-catch) =====
      for (const mw of this.middlewares) {
        try {
          mw.post?.(action, prevState, this.state);
        } catch (err) {
          console.error('[Middleware] post error:', err);
        }
      }

      this.emit('change', action);
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : String(err) };
    }
  }

  private applyAction(draft: AppState, action: Action): void {
    switch (action.type) {
      // BUG-2: window.create / window.close
      case 'window.create': {
        const id = crypto.randomUUID();
        const geo = action.payload.geometry ?? { x: 100, y: 100, width: 1200, height: 800 };
        draft.windows.push({ id, workspaceIds: [], geometry: geo, isActive: true });
        draft.focus.activeWindowId = id;
        break;
      }
      case 'window.close': {
        const idx = draft.windows.findIndex((w) => w.id === action.payload.windowId);
        if (idx === -1) break;
        const win = draft.windows[idx];
        for (const wsId of win.workspaceIds) {
          draft.panels = draft.panels.filter((p) => p.workspaceId !== wsId);
          draft.surfaces = draft.surfaces.filter((s) =>
            draft.panels.some((p) => p.id === s.panelId),
          );
        }
        draft.workspaces = draft.workspaces.filter((ws) => !win.workspaceIds.includes(ws.id));
        draft.windows.splice(idx, 1);
        if (draft.focus.activeWindowId === action.payload.windowId) {
          draft.focus.activeWindowId = draft.windows[0]?.id ?? null;
        }
        break;
      }
      case 'workspace.create': {
        const id = crypto.randomUUID();
        const panelId = crypto.randomUUID();
        const surfaceId = crypto.randomUUID();
        draft.workspaces.push({
          id,
          windowId: action.payload.windowId,
          name: action.payload.name ?? 'New Workspace',
          panelLayout: { type: 'leaf', panelId },
          agentPids: {},
          statusEntries: [],
          unreadCount: 0,
          isPinned: false,
        });
        draft.panels.push({
          id: panelId,
          workspaceId: id,
          panelType: 'terminal',
          surfaceIds: [surfaceId],
          activeSurfaceId: surfaceId,
          isZoomed: false,
        });
        draft.surfaces.push({
          id: surfaceId,
          panelId,
          surfaceType: 'terminal',
          title: 'Terminal',
        });
        const win = draft.windows.find((w) => w.id === action.payload.windowId);
        if (win) win.workspaceIds.push(id);
        // Auto-focus the newly created workspace
        draft.focus.activeWorkspaceId = id;
        draft.focus.activeWindowId = action.payload.windowId;
        draft.focus.activePanelId = panelId;
        draft.focus.activeSurfaceId = surfaceId;
        break;
      }
      case 'workspace.close': {
        const wsIdx = draft.workspaces.findIndex((w) => w.id === action.payload.workspaceId);
        if (wsIdx === -1) break;
        draft.panels = draft.panels.filter((p) => p.workspaceId !== action.payload.workspaceId);
        draft.surfaces = draft.surfaces.filter((s) => draft.panels.some((p) => p.id === s.panelId));
        draft.workspaces.splice(wsIdx, 1);
        for (const win of draft.windows) {
          win.workspaceIds = win.workspaceIds.filter((id) => id !== action.payload.workspaceId);
        }
        if (draft.focus.activeWorkspaceId === action.payload.workspaceId) {
          draft.focus.activeWorkspaceId = draft.workspaces[0]?.id ?? null;
        }
        break;
      }
      case 'workspace.select': {
        draft.focus.activeWorkspaceId = action.payload.workspaceId;
        const ws = draft.workspaces.find((w) => w.id === action.payload.workspaceId);
        if (ws) draft.focus.activeWindowId = ws.windowId;
        break;
      }
      case 'workspace.rename': {
        const ws = draft.workspaces.find((w) => w.id === action.payload.workspaceId);
        if (ws) ws.name = action.payload.name;
        break;
      }
      case 'panel.focus': {
        draft.focus.activePanelId = action.payload.panelId;
        break;
      }
      case 'panel.close': {
        const panelId = action.payload.panelId;
        const idx = draft.panels.findIndex((p) => p.id === panelId);
        if (idx === -1) break;
        // Remove surfaces belonging to this panel
        draft.surfaces = draft.surfaces.filter((s) => s.panelId !== panelId);
        // Remove panel from array
        draft.panels.splice(idx, 1);
        // P2-BUG-8: Remove leaf from panelLayout tree + promote sibling
        const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panelId) !== null);
        if (ws) {
          const newLayout = removeLeaf(ws.panelLayout, panelId);
          if (newLayout) ws.panelLayout = newLayout;
        }
        break;
      }
      case 'panel.split': {
        const { panelId, direction, newPanelType } = action.payload;
        const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panelId) !== null);
        if (!ws) break;
        const newPanelId = crypto.randomUUID();
        const newSurfaceId = crypto.randomUUID();
        draft.panels.push({
          id: newPanelId,
          workspaceId: ws.id,
          panelType: newPanelType,
          surfaceIds: [newSurfaceId],
          activeSurfaceId: newSurfaceId,
          isZoomed: false,
        });
        draft.surfaces.push({
          id: newSurfaceId,
          panelId: newPanelId,
          surfaceType: newPanelType,
          title: newPanelType === 'terminal' ? 'Terminal' : 'New Tab',
        });
        ws.panelLayout = replaceLeaf(ws.panelLayout, panelId, {
          type: 'split',
          direction,
          ratio: 0.5,
          children: [
            { type: 'leaf', panelId },
            { type: 'leaf', panelId: newPanelId },
          ],
        });
        break;
      }
      case 'panel.resize': {
        const { panelId, ratio } = action.payload;
        const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panelId) !== null);
        if (!ws) break;
        ws.panelLayout = updateRatioForPanel(ws.panelLayout, panelId, ratio);
        break;
      }
      case 'panel.zoom': {
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (panel) panel.isZoomed = !panel.isZoomed;
        break;
      }
      case 'panel.swap': {
        const { panelId1, panelId2 } = action.payload;
        if (panelId1 === panelId2) break;
        function swapInTree(node: PanelLayoutTree): void {
          if (node.type === 'leaf') {
            if (node.panelId === panelId1) node.panelId = panelId2;
            else if (node.panelId === panelId2) node.panelId = panelId1;
          } else if (node.children) {
            node.children.forEach(swapInTree);
          }
        }
        for (const ws of draft.workspaces) swapInTree(ws.panelLayout);
        break;
      }
      case 'panel.move': {
        const { sourcePanelId, targetPanelId, direction } = action.payload;
        if (sourcePanelId === targetPanelId) break;
        // Find the workspace containing both panels
        const ws = draft.workspaces.find(
          (w) => findLeaf(w.panelLayout, sourcePanelId) !== null && findLeaf(w.panelLayout, targetPanelId) !== null,
        );
        if (!ws) break;
        // Step 1: Remove source panel from layout tree (promote its sibling)
        const layoutAfterRemove = removeLeaf(ws.panelLayout, sourcePanelId);
        if (!layoutAfterRemove) break; // source was the only leaf
        // Step 2: Replace target leaf with a new split containing both source and target
        const splitDirection: 'horizontal' | 'vertical' =
          direction === 'left' || direction === 'right' ? 'horizontal' : 'vertical';
        const sourceFirst = direction === 'left' || direction === 'top';
        const newSplit: PanelLayoutTree = {
          type: 'split',
          direction: splitDirection,
          ratio: 0.5,
          children: sourceFirst
            ? [{ type: 'leaf', panelId: sourcePanelId }, { type: 'leaf', panelId: targetPanelId }]
            : [{ type: 'leaf', panelId: targetPanelId }, { type: 'leaf', panelId: sourcePanelId }],
        };
        ws.panelLayout = replaceLeaf(layoutAfterRemove, targetPanelId, newSplit);
        break;
      }
      case 'surface.create': {
        const newId = crypto.randomUUID();
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (!panel) break;
        draft.surfaces.push({
          id: newId,
          panelId: action.payload.panelId,
          surfaceType: action.payload.surfaceType,
          title: action.payload.surfaceType === 'terminal' ? 'Terminal' : 'New Tab',
        });
        panel.surfaceIds.push(newId);
        panel.activeSurfaceId = newId;
        break;
      }
      case 'surface.close': {
        const si = draft.surfaces.findIndex((s) => s.id === action.payload.surfaceId);
        if (si === -1) break;
        const surf = draft.surfaces[si];
        const panel = draft.panels.find((p) => p.id === surf.panelId);
        if (panel) {
          panel.surfaceIds = panel.surfaceIds.filter((id) => id !== action.payload.surfaceId);
          if (panel.activeSurfaceId === action.payload.surfaceId)
            panel.activeSurfaceId = panel.surfaceIds[0] ?? '';

          // Auto-close panel when last surface is removed — collapse split back
          if (panel.surfaceIds.length === 0) {
            const pIdx = draft.panels.findIndex((p2) => p2.id === panel.id);
            if (pIdx !== -1) draft.panels.splice(pIdx, 1);
            const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panel.id) !== null);
            if (ws) {
              const newLayout = removeLeaf(ws.panelLayout, panel.id);
              if (newLayout) ws.panelLayout = newLayout;
            }
          }
        }
        draft.surfaces.splice(si, 1);
        break;
      }
      case 'surface.focus': {
        draft.focus.activeSurfaceId = action.payload.surfaceId;
        const s = draft.surfaces.find((sf) => sf.id === action.payload.surfaceId);
        if (s) {
          draft.focus.activePanelId = s.panelId;
          const p = draft.panels.find((pp) => pp.id === s.panelId);
          if (p) p.activeSurfaceId = action.payload.surfaceId;
        }
        break;
      }
      case 'surface.reorder': {
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (!panel) break;
        const oldIndex = panel.surfaceIds.indexOf(action.payload.surfaceId);
        if (oldIndex === -1) break;
        panel.surfaceIds.splice(oldIndex, 1);
        panel.surfaceIds.splice(action.payload.newIndex, 0, action.payload.surfaceId);
        break;
      }
      case 'workspace.reorder': {
        const win = draft.windows.find((w) => w.id === action.payload.windowId);
        if (!win) break;
        const oldIdx = win.workspaceIds.indexOf(action.payload.workspaceId);
        if (oldIdx === -1) break;
        win.workspaceIds.splice(oldIdx, 1);
        win.workspaceIds.splice(action.payload.newIndex, 0, action.payload.workspaceId);
        break;
      }
      case 'surface.send_text':
        break; // side-effect only, handled above dispatch
      case 'agent.spawn': {
        const { agentType, workspaceId, task } = action.payload;
        const ws = draft.workspaces.find((w) => w.id === workspaceId);
        if (!ws) break;

        const newPanelId = crypto.randomUUID();
        const newSurfaceId = crypto.randomUUID();

        draft.panels.push({
          id: newPanelId,
          workspaceId,
          panelType: 'terminal',
          surfaceIds: [newSurfaceId],
          activeSurfaceId: newSurfaceId,
          isZoomed: false,
        });
        draft.surfaces.push({
          id: newSurfaceId,
          panelId: newPanelId,
          surfaceType: 'terminal',
          title: `${agentType} agent`,
          pendingCommand: task ? `${agentType} "${task}"\n` : `${agentType}\n`,
        });

        // panelLayout에 split 추가
        ws.panelLayout = {
          type: 'split',
          direction: 'horizontal',
          ratio: 0.5,
          children: [ws.panelLayout, { type: 'leaf', panelId: newPanelId }],
        };

        // agents[] 등록
        draft.agents.push({
          sessionId: crypto.randomUUID(),
          agentType,
          workspaceId,
          surfaceId: newSurfaceId,
          status: 'running',
          statusIcon: '\u26A1',
          statusColor: '#4C8DFF',
          lastActivity: Date.now(),
        });

        break;
      }
      case 'agent.session_start': {
        draft.agents.push({
          sessionId: action.payload.sessionId,
          agentType: action.payload.agentType,
          workspaceId: action.payload.workspaceId,
          surfaceId: action.payload.surfaceId,
          status: 'running',
          statusIcon: '⚡',
          statusColor: 'blue',
          pid: action.payload.pid,
          lastActivity: Date.now(),
        });
        break;
      }
      case 'agent.status_update': {
        const agent = draft.agents.find((a) => a.sessionId === action.payload.sessionId);
        if (agent) {
          agent.status = action.payload.status;
          if (action.payload.icon) agent.statusIcon = action.payload.icon;
          if (action.payload.color) agent.statusColor = action.payload.color;
          agent.lastActivity = Date.now();
        }
        break;
      }
      case 'agent.session_end': {
        draft.agents = draft.agents.filter((a) => a.sessionId !== action.payload.sessionId);
        break;
      }
      case 'notification.create': {
        draft.notifications.push({
          id: crypto.randomUUID(),
          title: action.payload.title,
          subtitle: action.payload.subtitle,
          body: action.payload.body,
          workspaceId: action.payload.workspaceId,
          surfaceId: action.payload.surfaceId,
          createdAt: Date.now(),
          isRead: false,
        });
        break;
      }
      case 'notification.clear': {
        if (action.payload.workspaceId) {
          draft.notifications = draft.notifications.filter(
            (n) => n.workspaceId !== action.payload.workspaceId,
          );
        } else {
          draft.notifications = [];
        }
        break;
      }
      case 'focus.update': {
        const p = action.payload;
        if (p.activeWindowId !== undefined) draft.focus.activeWindowId = p.activeWindowId;
        if (p.activeWorkspaceId !== undefined) draft.focus.activeWorkspaceId = p.activeWorkspaceId;
        if (p.activePanelId !== undefined) draft.focus.activePanelId = p.activePanelId;
        if (p.activeSurfaceId !== undefined) draft.focus.activeSurfaceId = p.activeSurfaceId;
        if (p.focusTarget !== undefined) draft.focus.focusTarget = p.focusTarget;
        break;
      }
      case 'surface.update_meta': {
        const surface = draft.surfaces.find((s) => s.id === action.payload.surfaceId);
        if (!surface) break;
        if (action.payload.title !== undefined) surface.title = action.payload.title;
        if (action.payload.pendingCommand !== undefined) {
          surface.pendingCommand = action.payload.pendingCommand ?? undefined;
        }
        if (action.payload.terminal) {
          const t = action.payload.terminal;
          if (!surface.terminal) surface.terminal = { pid: 0, cwd: '', shell: '' };
          if (t.cwd !== undefined) surface.terminal.cwd = t.cwd;
          if (t.gitBranch !== undefined) surface.terminal.gitBranch = t.gitBranch;
          if (t.gitDirty !== undefined) surface.terminal.gitDirty = t.gitDirty;
          if (t.exitCode !== undefined) surface.terminal.exitCode = t.exitCode;
        }
        if (action.payload.browser) {
          if (!surface.browser)
            surface.browser = { url: '', profileId: 'default', isLoading: false };
          const b = action.payload.browser;
          if (b.url !== undefined) surface.browser.url = b.url;
          if (b.isLoading !== undefined) surface.browser.isLoading = b.isLoading;
        }
        break;
      }
      case 'settings.update': {
        Object.assign(draft.settings, action.payload);
        break;
      }
    }
  }
}
