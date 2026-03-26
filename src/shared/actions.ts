import { z } from 'zod';
import { GeometrySchema, PanelTypeEnum } from './schemas';

// ===== Window =====
export const WindowCreateAction = z.object({
  type: z.literal('window.create'),
  payload: z.object({ geometry: GeometrySchema.optional() }),
});
export const WindowCloseAction = z.object({
  type: z.literal('window.close'),
  payload: z.object({ windowId: z.string() }),
});

// ===== Workspace =====
export const WorkspaceCreateAction = z.object({
  type: z.literal('workspace.create'),
  payload: z.object({
    windowId: z.string(),
    name: z.string().optional(),
    cwd: z.string().optional(),
  }),
});
export const WorkspaceCloseAction = z.object({
  type: z.literal('workspace.close'),
  payload: z.object({ workspaceId: z.string() }),
});
export const WorkspaceSelectAction = z.object({
  type: z.literal('workspace.select'),
  payload: z.object({ workspaceId: z.string() }),
});
export const WorkspaceRenameAction = z.object({
  type: z.literal('workspace.rename'),
  payload: z.object({ workspaceId: z.string(), name: z.string() }),
});

// ===== Panel =====
export const PanelSplitAction = z.object({
  type: z.literal('panel.split'),
  payload: z.object({
    panelId: z.string(),
    direction: z.enum(['horizontal', 'vertical']),
    newPanelType: PanelTypeEnum,
    url: z.string().optional(),
    filePath: z.string().optional(),
  }),
});
export const PanelCloseAction = z.object({
  type: z.literal('panel.close'),
  payload: z.object({ panelId: z.string() }),
});
export const PanelFocusAction = z.object({
  type: z.literal('panel.focus'),
  payload: z.object({ panelId: z.string() }),
});
export const PanelResizeAction = z.object({
  type: z.literal('panel.resize'),
  payload: z.object({ panelId: z.string(), ratio: z.number().min(0).max(1) }),
});

// ===== Surface =====
export const SurfaceCreateAction = z.object({
  type: z.literal('surface.create'),
  payload: z.object({ panelId: z.string(), surfaceType: PanelTypeEnum }),
});
export const SurfaceCloseAction = z.object({
  type: z.literal('surface.close'),
  payload: z.object({ surfaceId: z.string() }),
});
export const SurfaceFocusAction = z.object({
  type: z.literal('surface.focus'),
  payload: z.object({ surfaceId: z.string() }),
});
export const SurfaceSendTextAction = z.object({
  type: z.literal('surface.send_text'),
  payload: z.object({ surfaceId: z.string(), text: z.string() }),
});

// ===== Surface Meta =====
export const SurfaceUpdateMetaAction = z.object({
  type: z.literal('surface.update_meta'),
  payload: z.object({
    surfaceId: z.string(),
    title: z.string().optional(),
    pendingCommand: z.string().nullable().optional(),
    terminal: z
      .object({
        cwd: z.string().optional(),
        gitBranch: z.string().optional(),
        gitDirty: z.boolean().optional(),
        exitCode: z.number().optional(),
      })
      .optional(),
    browser: z
      .object({
        url: z.string().optional(),
        isLoading: z.boolean().optional(),
      })
      .optional(),
  }),
});

// ===== Agent =====
export const AgentSpawnAction = z.object({
  type: z.literal('agent.spawn'),
  payload: z.object({
    agentType: z.enum(['claude', 'codex', 'gemini', 'opencode']),
    workspaceId: z.string(),
    task: z.string().optional(),
    cwd: z.string().optional(),
  }),
});
export const AgentSessionStartAction = z.object({
  type: z.literal('agent.session_start'),
  payload: z.object({
    sessionId: z.string(),
    agentType: z.enum(['claude', 'codex', 'gemini', 'opencode']),
    workspaceId: z.string(),
    surfaceId: z.string(),
    pid: z.number().optional(),
  }),
});
export const AgentStatusUpdateAction = z.object({
  type: z.literal('agent.status_update'),
  payload: z.object({
    sessionId: z.string(),
    status: z.enum(['running', 'idle', 'needs_input', 'done', 'error']),
    icon: z.string().optional(),
    color: z.string().optional(),
  }),
});
export const AgentSessionEndAction = z.object({
  type: z.literal('agent.session_end'),
  payload: z.object({ sessionId: z.string() }),
});

// ===== Notification =====
export const NotificationCreateAction = z.object({
  type: z.literal('notification.create'),
  payload: z.object({
    title: z.string(),
    subtitle: z.string().optional(),
    body: z.string().optional(),
    workspaceId: z.string().optional(),
    surfaceId: z.string().optional(),
  }),
});
export const NotificationClearAction = z.object({
  type: z.literal('notification.clear'),
  payload: z.object({ workspaceId: z.string().optional() }),
});

// ===== Panel Zoom (P2-BUG-2) =====
export const PanelZoomAction = z.object({
  type: z.literal('panel.zoom'),
  payload: z.object({ panelId: z.string() }),
});

// ===== Panel Swap (drag-and-drop reorder) =====
export const PanelSwapAction = z.object({
  type: z.literal('panel.swap'),
  payload: z.object({ panelId1: z.string(), panelId2: z.string() }),
});

// ===== Panel Move (directional drag-and-drop) =====
export const PanelMoveAction = z.object({
  type: z.literal('panel.move'),
  payload: z.object({
    sourcePanelId: z.string(),
    targetPanelId: z.string(),
    direction: z.enum(['left', 'right', 'top', 'bottom']),
  }),
});

// ===== Surface Reorder (P2-BUG-2) =====
export const SurfaceReorderAction = z.object({
  type: z.literal('surface.reorder'),
  payload: z.object({
    surfaceId: z.string(),
    panelId: z.string(),
    newIndex: z.number().int().min(0),
  }),
});

// ===== Workspace Reorder (P2-BUG-2) =====
export const WorkspaceReorderAction = z.object({
  type: z.literal('workspace.reorder'),
  payload: z.object({
    workspaceId: z.string(),
    windowId: z.string(),
    newIndex: z.number().int().min(0),
  }),
});

// ===== Workspace Set Layout =====
export const WorkspaceSetLayoutAction = z.object({
  type: z.literal('workspace.set_layout'),
  payload: z.object({
    workspaceId: z.string(),
    panelLayout: z.any(),
  }),
});

// ===== Focus =====
export const FocusUpdateAction = z.object({
  type: z.literal('focus.update'),
  payload: z.object({
    activeWindowId: z.string().nullable().optional(),
    activeWorkspaceId: z.string().nullable().optional(),
    activePanelId: z.string().nullable().optional(),
    activeSurfaceId: z.string().nullable().optional(),
    focusTarget: z
      .enum(['terminal', 'browser_webview', 'browser_omnibar', 'browser_find', 'terminal_find'])
      .nullable()
      .optional(),
  }),
});

// ===== Settings =====
export const SettingsUpdateAction = z.object({
  type: z.literal('settings.update'),
  payload: z.record(z.string(), z.unknown()),
});

// ===== Discriminated Union =====
export const ActionSchema = z.discriminatedUnion('type', [
  WindowCreateAction,
  WindowCloseAction,
  WorkspaceCreateAction,
  WorkspaceCloseAction,
  WorkspaceSelectAction,
  WorkspaceRenameAction,
  WorkspaceReorderAction,
  WorkspaceSetLayoutAction,
  PanelSplitAction,
  PanelCloseAction,
  PanelFocusAction,
  PanelResizeAction,
  PanelZoomAction,
  PanelSwapAction,
  PanelMoveAction,
  SurfaceCreateAction,
  SurfaceCloseAction,
  SurfaceFocusAction,
  SurfaceSendTextAction,
  SurfaceReorderAction,
  SurfaceUpdateMetaAction,
  AgentSpawnAction,
  AgentSessionStartAction,
  AgentStatusUpdateAction,
  AgentSessionEndAction,
  NotificationCreateAction,
  NotificationClearAction,
  FocusUpdateAction,
  SettingsUpdateAction,
]);

export type Action = z.infer<typeof ActionSchema>;
