/**
 * App.tsx — Root renderer component for cmux-win.
 *
 * Matches cmux macOS layout:
 *   ┌──────────────┬────────────────────────────────────┐
 *   │  Sidebar     │  [📁] Workspace 1    [─][□][✕]     │ ← 32px custom titlebar
 *   │  (200px)     ├────────────────────────────────────┤
 *   │              │  Terminal content                   │
 *   │  Vertical    │  (flex: 1)                         │
 *   │  tabs with   │  Split panes with                  │
 *   │  metadata    │  terminals/browsers                │
 *   └──────────────┴────────────────────────────────────┘
 *
 * No bottom status bar — matches cmux macOS.
 * Custom frameless titlebar with window drag region and Windows controls.
 */
import React from 'react';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useAppState } from './hooks/useAppState';
import { useDispatch } from './hooks/useDispatch';
import { useShortcuts } from './hooks/useShortcuts';
import FileExplorer from './components/explorer/FileExplorer';
import type { AppState } from '../shared/types';
import { DEFAULT_SETTINGS } from '../shared/constants';
import { collectLeafIds, rebuildEqualLayout } from '../shared/panel-layout-utils';
import Sidebar from './components/sidebar/Sidebar';
import PanelLayout from './components/panels/PanelLayout';
import PanelContainer from './components/panels/PanelContainer';
import CommandPalette from './components/command-palette/CommandPalette';
import SettingsPanel from './components/settings/SettingsPanel';

// ---------------------------------------------------------------------------
// Global window augmentation for cmuxWindowId and cmuxWin (exposed from preload)
// ---------------------------------------------------------------------------
declare global {
  interface Window {
    cmuxWindowId: {
      onWindowId(callback: (id: string) => void): () => void;
    };
    cmuxWin: {
      platform: string;
      minimize: () => void;
      maximize: () => void;
      close: () => void;
    };
  }
}

// Standalone mode: no Electron (e.g. Cursor Simple Browser, plain browser)
const isStandalone = typeof window === 'undefined' || typeof window.cmuxWindowId === 'undefined';

function createMockState(): AppState {
  const wsId = 'ws-1';
  const panelId = 'panel-1';
  const surfaceId = 'surf-1';
  return {
    windows: [
      {
        id: 'win-1',
        workspaceIds: [wsId],
        geometry: { x: 0, y: 0, width: 1200, height: 800 },
        isActive: true,
      },
    ],
    workspaces: [
      {
        id: wsId,
        windowId: 'win-1',
        name: 'Workspace 1',
        panelLayout: { type: 'leaf', panelId },
        agentPids: {},
        statusEntries: [],
        unreadCount: 0,
        isPinned: false,
      },
    ],
    panels: [
      {
        id: panelId,
        workspaceId: wsId,
        panelType: 'terminal',
        surfaceIds: [surfaceId],
        activeSurfaceId: surfaceId,
        isZoomed: false,
      },
    ],
    surfaces: [{ id: surfaceId, panelId, surfaceType: 'terminal', title: 'Terminal' }],
    agents: [],
    notifications: [],
    settings: structuredClone(DEFAULT_SETTINGS),
    shortcuts: { shortcuts: {} },
    focus: {
      activeWindowId: 'win-1',
      activeWorkspaceId: wsId,
      activePanelId: panelId,
      activeSurfaceId: surfaceId,
      focusTarget: null,
    },
  };
}

// ---------------------------------------------------------------------------
// Window control handler (safe in standalone mode)
// ---------------------------------------------------------------------------
// handleOpenCwd is now handled inline via openFolderDialog

export default function App() {
  const { t } = useTranslation();
  const electronState = useAppState();
  const dispatch = useDispatch();
  const [windowId, setWindowId] = useState<string | null>(isStandalone ? 'win-1' : null);
  const [initialized, setInitialized] = useState(isStandalone);
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [explorerVisible, setExplorerVisible] = useState(false);
  const [explorerRootPath, setExplorerRootPath] = useState<string | undefined>(undefined);
  const [openedProjects, setOpenedProjects] = useState<string[]>([]);
  const [firstFolderOpened, setFirstFolderOpened] = useState(false);
  const [panelsCollapsed, setPanelsCollapsed] = useState(false);
  const [commandPaletteVisible, setCommandPaletteVisible] = useState(false);
  const [settingsVisible, setSettingsVisible] = useState(false);

  const appState = isStandalone ? createMockState() : electronState;

  // Subscribe to windowId from main process
  useEffect(() => {
    if (isStandalone) return;
    const cleanup = window.cmuxWindowId.onWindowId((id) => {
      setWindowId(id);
    });
    return cleanup;
  }, []);

  // Keyboard shortcuts
  const toggleSidebar = useCallback(() => setSidebarVisible((v) => !v), []);
  const toggleExplorer = useCallback(() => setExplorerVisible((v) => !v), []);
  const togglePanels = useCallback(() => setPanelsCollapsed((v) => !v), []);
  const toggleCommandPalette = useCallback(() => setCommandPaletteVisible((v) => !v), []);
  const toggleSettings = useCallback(() => setSettingsVisible((v) => !v), []);
  const equalizeLayout = useCallback(
    (direction: 'horizontal' | 'vertical') => {
      if (!appState) return;
      const activeWs = appState.workspaces.find((w) => w.id === appState.focus.activeWorkspaceId);
      if (!activeWs?.panelLayout) return;
      const panelIds = collectLeafIds(activeWs.panelLayout);
      if (panelIds.length <= 1) return;
      const newLayout = rebuildEqualLayout(panelIds, direction);
      void dispatch({
        type: 'workspace.set_layout',
        payload: { workspaceId: activeWs.id, panelLayout: newLayout },
      });
    },
    [appState, dispatch],
  );
  useShortcuts(appState, dispatch, windowId, {
    toggleSidebar,
    toggleExplorer,
    togglePanels,
    toggleCommandPalette,
    toggleSettings,
    equalizeHorizontal: () => equalizeLayout('horizontal'),
    equalizeVertical: () => equalizeLayout('vertical'),
  });

  // Auto-create initial workspace when state is ready and no workspaces exist
  useEffect(() => {
    if (appState && windowId && appState.workspaces.length === 0 && !initialized) {
      setInitialized(true);
      void dispatch({
        type: 'workspace.create',
        payload: { windowId },
      });
    }
  }, [appState, windowId, initialized, dispatch]);

  // -------------------------------------------------------------------------
  // Derived state
  // -------------------------------------------------------------------------
  const currentWindow = appState?.windows.find((w) => w.id === windowId) ?? null;
  const activeWsId = appState?.focus.activeWorkspaceId ?? null;
  const activeWs = appState?.workspaces.find((ws) => ws.id === activeWsId) ?? null;

  const orderedWorkspaces = useMemo(() => {
    if (!currentWindow || !appState) return [];
    return currentWindow.workspaceIds
      .map((id) => appState.workspaces.find((ws) => ws.id === id))
      .filter(Boolean) as typeof appState.workspaces;
  }, [currentWindow, appState]);

  const zoomedPanel =
    appState?.panels.find((p) => p.workspaceId === activeWsId && p.isZoomed) ?? null;
  const wsPanels = useMemo(
    () => appState?.panels.filter((p) => p.workspaceId === activeWsId) ?? [],
    [appState, activeWsId],
  );

  // Derive active CWD from active surface terminal metadata (for titlebar)
  const activeCwd = useMemo(() => {
    if (!appState) return undefined;
    const activeSurfaceId = appState.focus.activeSurfaceId;
    const activeSurface = activeSurfaceId
      ? appState.surfaces.find((s) => s.id === activeSurfaceId)
      : null;
    return activeSurface?.terminal?.cwd;
  }, [appState]);

  // Sync explorer root with active terminal CWD (auto-switch on focus change)
  useEffect(() => {
    if (activeCwd) {
      setExplorerRootPath(activeCwd);
    }
  }, [activeCwd]);

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------
  if (!appState || !windowId) {
    return (
      <div
        style={{
          color: '#888',
          background: '#272822',
          height: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {t('status.loading')}
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <div
      style={{
        background: '#272822',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Main area: sidebar + content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Sidebar with smooth width transition */}
        <div
          style={{
            width: sidebarVisible ? '200px' : '0px',
            minWidth: sidebarVisible ? '200px' : '0px',
            overflow: 'hidden',
            transition: 'width 0.15s ease-out, min-width 0.15s ease-out',
            flexShrink: 0,
          }}
        >
          <Sidebar
            workspaces={orderedWorkspaces}
            activeWorkspaceId={activeWsId}
            agents={appState.agents}
            notifications={appState.notifications}
            surfaces={appState.surfaces}
            panels={appState.panels}
            windowId={windowId}
            dispatch={dispatch}
            explorerVisible={explorerVisible}
            explorerRootPath={explorerRootPath}
            openedProjects={openedProjects}
            onProjectSelect={(path) => setExplorerRootPath(path)}
            onExplorerNavigate={(dirPath) => {
              const surfaceId = appState?.focus.activeSurfaceId;
              if (surfaceId) {
                void dispatch({
                  type: 'surface.send_text',
                  payload: { surfaceId, text: `cd "${dirPath.replace(/\\/g, '/')}"\r` },
                });
              }
            }}
            onFileOpen={(filePath) => {
              if (filePath.endsWith('.md')) {
                const activePanelId = appState?.focus.activePanelId;
                if (activePanelId) {
                  void dispatch({
                    type: 'panel.split',
                    payload: { panelId: activePanelId, direction: 'horizontal', newPanelType: 'markdown', filePath },
                  });
                }
              }
            }}
            onExplorerOpenFolder={async () => {
              if (!window.cmuxFile?.openFolderDialog) return;
              const result = await window.cmuxFile.openFolderDialog();
              if ('path' in result) {
                const folderPath = result.path;
                setExplorerRootPath(folderPath);
                setExplorerVisible(true);
                setOpenedProjects((prev) =>
                  prev.includes(folderPath) ? prev : [...prev, folderPath],
                );
                const surfaceId = appState?.focus.activeSurfaceId;
                if (surfaceId) {
                  void dispatch({
                    type: 'surface.send_text',
                    payload: { surfaceId, text: `cd "${folderPath.replace(/\\/g, '/')}"\r` },
                  });
                  if (!firstFolderOpened) {
                    setFirstFolderOpened(true);
                    setTimeout(() => {
                      void dispatch({
                        type: 'surface.send_text',
                        payload: { surfaceId, text: 'claude\r' },
                      });
                    }, 500);
                  }
                }
              }
            }}
            onOpenClaudeWeb={(url: string) => {
              const activePanelId = appState?.focus.activePanelId;
              if (activePanelId) {
                void dispatch({
                  type: 'panel.split',
                  payload: { panelId: activePanelId, direction: 'horizontal', newPanelType: 'browser', url },
                });
              }
            }}
            onEqualizeH={() => equalizeLayout('horizontal')}
            onEqualizeV={() => equalizeLayout('vertical')}
            onTogglePanels={togglePanels}
            panelsCollapsed={panelsCollapsed}
          />
        </div>

        {/* Workspace content area: titlebar + panels */}
        <div role="main" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {/* Custom titlebar — window drag region */}
          <div
            style={{
              height: '32px',
              minHeight: '32px',
              background: '#272822',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              padding: '0 0 0 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              flexShrink: 0,
              overflow: 'hidden',
              WebkitAppRegion: 'drag' as unknown as string,
              userSelect: 'none',
            }}
          >
            {/* Left: folder icon — toggle file explorer */}
            <button
              onClick={() => setExplorerVisible((v) => !v)}
              title={explorerVisible ? 'Hide Explorer (Ctrl+E)' : 'Show Explorer (Ctrl+E)'}
              style={{
                background: explorerVisible ? 'rgba(0,145,255,0.15)' : 'none',
                border: 'none',
                color: explorerVisible ? '#0091FF' : '#999',
                cursor: 'pointer',
                fontSize: '14px',
                padding: '0 2px',
                lineHeight: 1,
                WebkitAppRegion: 'no-drag' as unknown as string,
              }}
            >
              {'\u2302'}
            </button>

            {/* Toggle panels (collapse/expand terminals) */}
            <button
              onClick={() => setPanelsCollapsed((v) => !v)}
              title={panelsCollapsed ? 'Show Terminals' : 'Hide Terminals'}
              style={{
                background: panelsCollapsed ? 'rgba(0,145,255,0.15)' : 'none',
                border: 'none',
                color: panelsCollapsed ? '#0091FF' : '#999',
                cursor: 'pointer',
                fontSize: '13px',
                padding: '0 4px',
                lineHeight: 1,
                WebkitAppRegion: 'no-drag' as unknown as string,
              }}
            >
              {panelsCollapsed ? '\u25B6' : '\u25C0'}
            </button>

            {/* Workspace name */}
            <span
              style={{
                fontSize: '13px',
                fontWeight: 600,
                color: '#e0e0e0',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                minWidth: 0,
              }}
            >
              {activeWs?.name ?? 'cmux-win'}
            </span>

            {/* Spacer */}
            <div style={{ flex: 1 }} />

            {/* Window controls (Windows style) */}
            {!isStandalone && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'stretch',
                  height: '32px',
                  flexShrink: 0,
                  WebkitAppRegion: 'no-drag' as unknown as string,
                }}
              >
                {/* Minimize */}
                <button
                  onClick={() => window.cmuxWin.minimize()}
                  aria-label="Minimize window"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#999',
                    fontSize: '16px',
                    width: '46px',
                    height: '32px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontFamily: 'Segoe Fluent Icons, Segoe MDL2 Assets, sans-serif',
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.08)';
                    (e.currentTarget as HTMLButtonElement).style.color = '#fff';
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                    (e.currentTarget as HTMLButtonElement).style.color = '#999';
                  }}
                  title="Minimize"
                >
                  &#xE921;
                </button>
                {/* Maximize / Restore */}
                <button
                  onClick={() => window.cmuxWin.maximize()}
                  aria-label="Maximize window"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#999',
                    fontSize: '16px',
                    width: '46px',
                    height: '32px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontFamily: 'Segoe Fluent Icons, Segoe MDL2 Assets, sans-serif',
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.08)';
                    (e.currentTarget as HTMLButtonElement).style.color = '#fff';
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                    (e.currentTarget as HTMLButtonElement).style.color = '#999';
                  }}
                  title="Maximize"
                >
                  &#xE922;
                </button>
                {/* Close */}
                <button
                  onClick={() => window.cmuxWin.close()}
                  aria-label="Close window"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#999',
                    fontSize: '16px',
                    width: '46px',
                    height: '32px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontFamily: 'Segoe Fluent Icons, Segoe MDL2 Assets, sans-serif',
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = '#e81123';
                    (e.currentTarget as HTMLButtonElement).style.color = '#fff';
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                    (e.currentTarget as HTMLButtonElement).style.color = '#999';
                  }}
                  title="Close"
                >
                  &#xE8BB;
                </button>
              </div>
            )}
          </div>

          {/* Panel content — collapsible with Ctrl+` */}
          <div style={{ flex: panelsCollapsed ? 0 : 1, overflow: 'hidden', display: panelsCollapsed ? 'none' : undefined }}>
            {activeWs && wsPanels.length === 0 ? (
              /* Workspace exists but all panels closed — show new terminal button */
              <div
                style={{
                  color: '#888',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                  gap: '16px',
                }}
              >
                <span>No open terminals</span>
                <button
                  onClick={() =>
                    void dispatch({
                      type: 'panel.split',
                      payload: {
                        panelId: activeWs.panelLayout?.panelId || '',
                        direction: 'horizontal',
                        newPanelType: 'terminal',
                      },
                    }).catch(() =>
                      dispatch({
                        type: 'workspace.create',
                        payload: { windowId: windowId! },
                      }),
                    )
                  }
                  style={{
                    background: '#0091FF',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '10px 24px',
                    fontSize: '14px',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  New Terminal
                </button>
              </div>
            ) : activeWs ? (
              zoomedPanel ? (
                <PanelContainer
                  panel={zoomedPanel}
                  surfaces={appState.surfaces}
                  settings={appState.settings}
                  isActive={true}
                  workspaceId={activeWsId || ''}
                  onFocus={(id) => void dispatch({ type: 'panel.focus', payload: { panelId: id } })}
                  onSurfaceFocus={(id) =>
                    void dispatch({ type: 'surface.focus', payload: { surfaceId: id } })
                  }
                  onSurfaceClose={(id) =>
                    void dispatch({ type: 'surface.close', payload: { surfaceId: id } })
                  }
                  onNewSurface={(id) =>
                    void dispatch({
                      type: 'surface.create',
                      payload: { panelId: id, surfaceType: 'terminal' },
                    })
                  }
                  onOpenFolder={async (targetSurfaceId: string) => {
                    if (!window.cmuxFile?.openFolderDialog) return;
                    const result = await window.cmuxFile.openFolderDialog();
                    if ('path' in result) {
                      const folderPath = result.path;
                      setExplorerRootPath(folderPath);
                      setExplorerVisible(true);
                      setOpenedProjects((prev) =>
                        prev.includes(folderPath) ? prev : [...prev, folderPath],
                      );
                      void dispatch({
                        type: 'surface.send_text',
                        payload: { surfaceId: targetSurfaceId, text: `cd "${folderPath.replace(/\\/g, '/')}"\r` },
                      });
                      if (!firstFolderOpened) {
                        setFirstFolderOpened(true);
                        setTimeout(() => {
                          void dispatch({
                            type: 'surface.send_text',
                            payload: { surfaceId: targetSurfaceId, text: 'claude\r' },
                          });
                        }, 500);
                      }
                    }
                  }}
                  onEqualizeH={() => equalizeLayout('horizontal')}
                  onEqualizeV={() => equalizeLayout('vertical')}
                  onBrowserUrlChange={(sid, u) =>
                    void dispatch({
                      type: 'surface.update_meta',
                      payload: { surfaceId: sid, browser: { url: u } },
                    })
                  }
                  onBrowserTitleChange={(sid, titleVal) =>
                    void dispatch({
                      type: 'surface.update_meta',
                      payload: { surfaceId: sid, title: titleVal },
                    })
                  }
                  dispatch={dispatch}
                />
              ) : (
                <PanelLayout
                  layout={activeWs.panelLayout}
                  panels={wsPanels}
                  surfaces={appState.surfaces}
                  activePanelId={appState.focus.activePanelId}
                  settings={appState.settings}
                  workspaceId={activeWsId || ''}
                  onPanelFocus={(id) =>
                    void dispatch({ type: 'panel.focus', payload: { panelId: id } })
                  }
                  onResize={(id, ratio) =>
                    void dispatch({ type: 'panel.resize', payload: { panelId: id, ratio } })
                  }
                  onSurfaceFocus={(id) =>
                    void dispatch({ type: 'surface.focus', payload: { surfaceId: id } })
                  }
                  onSurfaceClose={(id) =>
                    void dispatch({ type: 'surface.close', payload: { surfaceId: id } })
                  }
                  onNewSurface={(id) =>
                    void dispatch({
                      type: 'surface.create',
                      payload: { panelId: id, surfaceType: 'terminal' },
                    })
                  }
                  onOpenFolder={async (targetSurfaceId: string) => {
                    if (!window.cmuxFile?.openFolderDialog) return;
                    const result = await window.cmuxFile.openFolderDialog();
                    if ('path' in result) {
                      const folderPath = result.path;
                      setExplorerRootPath(folderPath);
                      setExplorerVisible(true);
                      setOpenedProjects((prev) =>
                        prev.includes(folderPath) ? prev : [...prev, folderPath],
                      );
                      void dispatch({
                        type: 'surface.send_text',
                        payload: { surfaceId: targetSurfaceId, text: `cd "${folderPath.replace(/\\/g, '/')}"\r` },
                      });
                      if (!firstFolderOpened) {
                        setFirstFolderOpened(true);
                        setTimeout(() => {
                          void dispatch({
                            type: 'surface.send_text',
                            payload: { surfaceId: targetSurfaceId, text: 'claude\r' },
                          });
                        }, 500);
                      }
                    }
                  }}
                  onEqualizeH={() => equalizeLayout('horizontal')}
                  onEqualizeV={() => equalizeLayout('vertical')}
                  onBrowserUrlChange={(sid, u) =>
                    void dispatch({
                      type: 'surface.update_meta',
                      payload: { surfaceId: sid, browser: { url: u } },
                    })
                  }
                  onBrowserTitleChange={(sid, titleVal) =>
                    void dispatch({
                      type: 'surface.update_meta',
                      payload: { surfaceId: sid, title: titleVal },
                    })
                  }
                  dispatch={dispatch}
                />
              )
            ) : (
              <div
                style={{
                  color: '#888',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                  gap: '16px',
                }}
              >
                <span>{t('status.noWorkspace')}</span>
                <button
                  onClick={() =>
                    void dispatch({
                      type: 'workspace.create',
                      payload: { windowId: windowId! },
                    })
                  }
                  style={{
                    background: '#0091FF',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '10px 24px',
                    fontSize: '14px',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  {t('action.newTerminal', 'New Terminal')}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Overlays */}
      {commandPaletteVisible && (
        <CommandPalette
          onExecute={(id) => {
            if (id === 'toggleSidebar') toggleSidebar();
            else if (id === 'commandPalette') setCommandPaletteVisible(false);
            else if (id === 'openSettings') setSettingsVisible(true);
          }}
          onClose={() => setCommandPaletteVisible(false)}
        />
      )}
      {settingsVisible && appState && (
        <SettingsPanel
          settings={appState.settings}
          onUpdate={(partial) => void dispatch({ type: 'settings.update', payload: partial })}
          onClose={() => setSettingsVisible(false)}
        />
      )}
    </div>
  );
}
