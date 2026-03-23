import React from 'react';
import { type FC, useState, useRef, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import type {
  WorkspaceState,
  AgentSessionState,
  NotificationState,
  SurfaceState,
  PanelState,
} from '../../../shared/types';
import WorkspaceItem from './WorkspaceItem';
import SidebarFooter from './SidebarFooter';

/* ── Color constants ─────────────────────────────────────────────────── */
const SIDEBAR_BG = '#1a1a2e';
const DIVIDER = '#3c3c3c';
const TEXT_PRIMARY = '#e0e0e0';

/* ── Layout constants ────────────────────────────────────────────────── */
const DEFAULT_WIDTH = 200;
const MIN_WIDTH = 120;
const MAX_WIDTH = 400;
const HANDLE_WIDTH = 6;
const TOP_PADDING = 28; // macOS traffic-light clearance (kept for visual consistency)
const LIST_PADDING_Y = 8;
const ITEM_GAP = 2;

export interface SidebarProps {
  workspaces: WorkspaceState[];
  activeWorkspaceId: string | null;
  agents: AgentSessionState[];
  notifications: NotificationState[];
  surfaces?: SurfaceState[];
  panels?: PanelState[];
  windowId: string;
  dispatch: (action: unknown) => Promise<{ ok: boolean }>;
}

const Sidebar: FC<SidebarProps> = ({
  workspaces,
  activeWorkspaceId,
  agents,
  notifications,
  surfaces,
  panels,
  windowId,
  dispatch,
}) => {
  const { t } = useTranslation();
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const resizing = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(DEFAULT_WIDTH);

  /* ── Resize logic ──────────────────────────────────────────────────── */
  const onResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      resizing.current = true;
      startX.current = e.clientX;
      startWidth.current = width;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    },
    [width],
  );

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!resizing.current) return;
      const delta = e.clientX - startX.current;
      const next = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startWidth.current + delta));
      setWidth(next);
    };
    const onMouseUp = () => {
      if (!resizing.current) return;
      resizing.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  /* ── Handlers ──────────────────────────────────────────────────────── */
  const handleCreateWorkspace = useCallback(() => {
    void dispatch({ type: 'workspace.create', payload: { windowId } });
  }, [dispatch, windowId]);

  const handleSpawnAgent = useCallback((agentType: string) => {
    if (!activeWorkspaceId) return;
    void dispatch({
      type: 'agent.spawn',
      payload: { agentType, workspaceId: activeWorkspaceId },
    });
  }, [dispatch, activeWorkspaceId]);

  return (
    <div
      role="navigation"
      aria-label="Workspace sidebar"
      style={
        {
          '--sidebar-width': `${width}px`,
          width: `${width}px`,
          minWidth: `${width}px`,
          height: '100%',
          background: SIDEBAR_BG,
          borderRight: `1px solid ${DIVIDER}`,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          position: 'relative',
        } as React.CSSProperties
      }
    >
      {/* Top padding (traffic-light clearance zone) */}
      <div style={{ height: `${TOP_PADDING}px`, flexShrink: 0 }} />

      {/* Header label */}
      <div
        style={{
          padding: '0 12px 4px',
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: '10px',
            fontWeight: 600,
            color: TEXT_PRIMARY,
            textTransform: 'uppercase',
            letterSpacing: '0.8px',
            opacity: 0.5,
          }}
        >
          {t('sidebar.workspaces')}
        </span>
      </div>

      {/* Scrollable tab list */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          paddingTop: `${LIST_PADDING_Y}px`,
          paddingBottom: `${LIST_PADDING_Y}px`,
          display: 'flex',
          flexDirection: 'column',
          gap: `${ITEM_GAP}px`,
        }}
      >
        {workspaces.map((ws, index) => (
          <WorkspaceItem
            key={ws.id}
            workspace={ws}
            index={index}
            isActive={ws.id === activeWorkspaceId}
            agents={agents}
            notifications={notifications}
            surfaces={surfaces}
            panels={panels}
            onSelect={(id) =>
              void dispatch({ type: 'workspace.select', payload: { workspaceId: id } })
            }
            onClose={(id) =>
              void dispatch({ type: 'workspace.close', payload: { workspaceId: id } })
            }
            onRename={(id) => {
              const name = window.prompt(t('sidebar.workspaceNamePrompt'));
              if (name)
                void dispatch({
                  type: 'workspace.rename',
                  payload: { workspaceId: id, name },
                });
            }}
          />
        ))}
      </div>

      {/* Footer */}
      <SidebarFooter
        onNewWorkspace={handleCreateWorkspace}
        onNewAgent={handleSpawnAgent}
        hasActiveWorkspace={activeWorkspaceId !== null}
      />

      {/* Resize handle (right edge) */}
      <div
        onMouseDown={onResizeStart}
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          width: `${HANDLE_WIDTH}px`,
          height: '100%',
          cursor: 'col-resize',
          zIndex: 10,
        }}
      />
    </div>
  );
};

export default Sidebar;
