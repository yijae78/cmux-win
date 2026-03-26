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
import FileExplorer from '../explorer/FileExplorer';

/* ── SidebarWebLink ──────────────────────────────────────────────────── */
const SidebarWebLink: FC<{ label: string; icon: string; onClick: () => void }> = ({ label, icon, onClick }) => (
  <button
    onClick={onClick}
    title={label}
    style={{
      width: '100%',
      padding: '4px 12px',
      background: 'none',
      border: 'none',
      color: '#999',
      cursor: 'pointer',
      fontSize: '11px',
      textAlign: 'left',
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
    }}
    onMouseEnter={(e) => {
      e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
      e.currentTarget.style.color = '#e0e0e0';
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.background = 'none';
      e.currentTarget.style.color = '#999';
    }}
  >
    <span style={{ fontSize: '12px' }}>{icon}</span>
    <span>{label}</span>
  </button>
);

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
  explorerVisible?: boolean;
  explorerRootPath?: string;
  openedProjects?: string[];
  onProjectSelect?: (path: string) => void;
  onExplorerNavigate?: (dirPath: string) => void;
  onFileOpen?: (filePath: string) => void;
  onExplorerOpenFolder?: () => void;
  onOpenClaudeWeb?: (url: string) => void;
  onEqualizeH?: () => void;
  onEqualizeV?: () => void;
  onTogglePanels?: () => void;
  panelsCollapsed?: boolean;
  onToggleExplorer?: () => void;
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
  explorerVisible,
  explorerRootPath,
  openedProjects,
  onProjectSelect,
  onExplorerNavigate,
  onFileOpen,
  onExplorerOpenFolder,
  onOpenClaudeWeb,
  onEqualizeH,
  onEqualizeV,
  onTogglePanels,
  panelsCollapsed,
  onToggleExplorer,
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

  const handleSpawnAgent = useCallback(async (agentType: string) => {
    if (!activeWorkspaceId) return;
    // Ask for project folder first
    let folderPath: string | undefined;
    if (window.cmuxFile?.openFolderDialog) {
      const result = await window.cmuxFile.openFolderDialog();
      if ('path' in result) {
        folderPath = result.path;
      } else {
        return; // cancelled — don't spawn
      }
    }
    void dispatch({
      type: 'agent.spawn',
      payload: {
        agentType,
        workspaceId: activeWorkspaceId,
        cwd: folderPath,
      },
    });
    // Show explorer with the selected folder
    if (folderPath && onExplorerOpenFolder) {
      // Trigger explorer to show this folder — parent will handle state
    }
  }, [dispatch, activeWorkspaceId, onExplorerOpenFolder]);

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

      {/* Header label + equalize buttons */}
      <div
        style={{
          padding: '0 8px 4px 12px',
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
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
            flex: 1,
          }}
        >
          {t('sidebar.workspaces')}
        </span>
        {onEqualizeH && (
          <button
            onClick={onEqualizeH}
            title="Equal Width (Ctrl+Shift+=)"
            style={{ background: 'rgba(255,255,255,0.08)', border: 'none', color: '#ddd', cursor: 'pointer', fontSize: '15px', padding: '2px 5px', lineHeight: 1, borderRadius: '3px' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = '#0091FF'; e.currentTarget.style.background = 'rgba(0,145,255,0.15)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = '#ddd'; e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; }}
          >
            ⊞
          </button>
        )}
        {onEqualizeV && (
          <button
            onClick={onEqualizeV}
            title="Equal Height (Ctrl+Alt+=)"
            style={{ background: 'rgba(255,255,255,0.08)', border: 'none', color: '#ddd', cursor: 'pointer', fontSize: '15px', padding: '2px 5px', lineHeight: 1, borderRadius: '3px' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = '#0091FF'; e.currentTarget.style.background = 'rgba(0,145,255,0.15)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = '#ddd'; e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; }}
          >
            ⊟
          </button>
        )}
        {onToggleExplorer && (
          <button
            onClick={onToggleExplorer}
            title={explorerVisible ? 'Hide Explorer' : 'Show Explorer'}
            style={{ background: explorerVisible ? 'rgba(0,145,255,0.15)' : 'rgba(255,255,255,0.08)', border: 'none', color: explorerVisible ? '#0091FF' : '#ddd', cursor: 'pointer', fontSize: '15px', padding: '2px 5px', lineHeight: 1, borderRadius: '3px' }}
            onMouseEnter={(e) => { e.currentTarget.style.color = '#0091FF'; e.currentTarget.style.background = 'rgba(0,145,255,0.15)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = explorerVisible ? '#0091FF' : '#ddd'; e.currentTarget.style.background = explorerVisible ? 'rgba(0,145,255,0.15)' : 'rgba(255,255,255,0.08)'; }}
          >
            {explorerVisible ? '◀' : '▶'}
          </button>
        )}
      </div>

      {/* Workspace list — compact when explorer is visible */}
      <div
        style={{
          flexShrink: explorerVisible ? 1 : 0,
          maxHeight: explorerVisible ? '30%' : undefined,
          flex: explorerVisible ? undefined : 1,
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

      {/* File Explorer — shown below workspace list */}
      {explorerVisible && (
        <div
          style={{
            flex: 1,
            minHeight: 0,
            borderTop: '1px solid rgba(255,255,255,0.08)',
            overflow: 'hidden',
          }}
        >
          <FileExplorer
            rootPath={explorerRootPath}
            openedProjects={openedProjects}
            onProjectSelect={onProjectSelect}
            onNavigate={onExplorerNavigate ?? (() => {})}
            onFileOpen={onFileOpen}
            onOpenFolder={onExplorerOpenFolder}
          />
        </div>
      )}

      {/* Quick actions bar — AI services + new workspace */}
      <div style={{ flexShrink: 0, borderTop: '1px solid rgba(255,255,255,0.08)', padding: '4px 0' }}>
        {onOpenClaudeWeb && (
          <>
            <SidebarWebLink label="Claude.ai" icon={'\uD83E\uDDE0'} onClick={() => onOpenClaudeWeb('https://claude.ai')} />
            <SidebarWebLink label="Gemini" icon={'\uD83D\uDC8E'} onClick={() => onOpenClaudeWeb('https://gemini.google.com')} />
            <SidebarWebLink label="ChatGPT" icon={'\uD83E\uDD16'} onClick={() => onOpenClaudeWeb('https://chatgpt.com')} />
          </>
        )}
        <SidebarFooter
          onNewWorkspace={handleCreateWorkspace}
        />
      </div>

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
