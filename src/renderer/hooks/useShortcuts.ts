import { useEffect } from 'react';
import type { AppState } from '../../shared/types';

declare global {
  interface Window {
    cmuxShortcut?: {
      onShortcut: (callback: (id: string) => void) => () => void;
    };
  }
}

export function useShortcuts(
  appState: AppState | null,
  dispatch: (action: unknown) => Promise<{ ok: boolean }>,
  windowId: string | null,
  callbacks: {
    toggleSidebar: () => void;
    toggleExplorer?: () => void;
    toggleCommandPalette?: () => void;
    toggleSettings?: () => void;
    equalizeHorizontal?: () => void;
    equalizeVertical?: () => void;
  },
): void {
  useEffect(() => {
    if (!appState || !windowId || !window.cmuxShortcut) return;

    const unsub = window.cmuxShortcut.onShortcut((shortcutId: string) => {
      const activePanelId = appState.focus.activePanelId;
      const activeWsId = appState.focus.activeWorkspaceId;
      const currentWin = appState.windows.find((w) => w.id === windowId);

      switch (shortcutId) {
        case 'newWorkspace':
          void dispatch({ type: 'workspace.create', payload: { windowId } });
          break;
        case 'closeWorkspace':
          if (activeWsId)
            void dispatch({ type: 'workspace.close', payload: { workspaceId: activeWsId } });
          break;
        case 'nextWorkspace': {
          if (!currentWin || !activeWsId) break;
          const wsIds = currentWin.workspaceIds;
          const idx = wsIds.indexOf(activeWsId);
          const nextId = wsIds[(idx + 1) % wsIds.length];
          if (nextId) void dispatch({ type: 'workspace.select', payload: { workspaceId: nextId } });
          break;
        }
        case 'prevWorkspace': {
          if (!currentWin || !activeWsId) break;
          const wsIds2 = currentWin.workspaceIds;
          const idx2 = wsIds2.indexOf(activeWsId);
          const prevId = wsIds2[(idx2 - 1 + wsIds2.length) % wsIds2.length];
          if (prevId) void dispatch({ type: 'workspace.select', payload: { workspaceId: prevId } });
          break;
        }
        case 'splitRight':
          if (activePanelId)
            void dispatch({
              type: 'panel.split',
              payload: {
                panelId: activePanelId,
                direction: 'horizontal',
                newPanelType: 'terminal',
              },
            });
          break;
        case 'splitDown':
          if (activePanelId)
            void dispatch({
              type: 'panel.split',
              payload: { panelId: activePanelId, direction: 'vertical', newPanelType: 'terminal' },
            });
          break;
        case 'closePanel':
          if (activePanelId)
            void dispatch({ type: 'panel.close', payload: { panelId: activePanelId } });
          break;
        case 'toggleZoom':
          if (activePanelId)
            void dispatch({ type: 'panel.zoom', payload: { panelId: activePanelId } });
          break;
        case 'toggleSidebar':
          callbacks.toggleSidebar();
          break;
        case 'toggleExplorer':
          callbacks.toggleExplorer?.();
          break;
        case 'commandPalette':
          callbacks.toggleCommandPalette?.();
          break;
        case 'openSettings':
          callbacks.toggleSettings?.();
          break;
        case 'equalizeHorizontal':
          callbacks.equalizeHorizontal?.();
          break;
        case 'equalizeVertical':
          callbacks.equalizeVertical?.();
          break;
        case 'newSurface':
          if (activePanelId)
            void dispatch({
              type: 'surface.create',
              payload: { panelId: activePanelId, surfaceType: 'terminal' },
            });
          break;
        case 'closeSurface': {
          const panel = appState.panels.find((p) => p.id === activePanelId);
          if (panel)
            void dispatch({
              type: 'surface.close',
              payload: { surfaceId: panel.activeSurfaceId },
            });
          break;
        }
        case 'nextSurface': {
          const panel2 = appState.panels.find((p) => p.id === activePanelId);
          if (!panel2) break;
          const sids = panel2.surfaceIds;
          const si = sids.indexOf(panel2.activeSurfaceId);
          const nextSid = sids[(si + 1) % sids.length];
          if (nextSid) void dispatch({ type: 'surface.focus', payload: { surfaceId: nextSid } });
          break;
        }
        case 'prevSurface': {
          const panel3 = appState.panels.find((p) => p.id === activePanelId);
          if (!panel3) break;
          const sids2 = panel3.surfaceIds;
          const si2 = sids2.indexOf(panel3.activeSurfaceId);
          const prevSid = sids2[(si2 - 1 + sids2.length) % sids2.length];
          if (prevSid) void dispatch({ type: 'surface.focus', payload: { surfaceId: prevSid } });
          break;
        }
        case 'focusLeft':
        case 'focusUp': {
          const panels = appState.panels.filter((p) => p.workspaceId === activeWsId);
          const idx3 = panels.findIndex((p) => p.id === activePanelId);
          const prev = panels[(idx3 - 1 + panels.length) % panels.length];
          if (prev) void dispatch({ type: 'panel.focus', payload: { panelId: prev.id } });
          break;
        }
        case 'focusRight':
        case 'focusDown': {
          const panels2 = appState.panels.filter((p) => p.workspaceId === activeWsId);
          const idx4 = panels2.findIndex((p) => p.id === activePanelId);
          const next = panels2[(idx4 + 1) % panels2.length];
          if (next) void dispatch({ type: 'panel.focus', payload: { panelId: next.id } });
          break;
        }
        case 'find':
          // TODO: toggle find overlay
          break;
        case 'renameWorkspace':
          // TODO: open rename dialog
          break;
        case 'newWindow':
          // TODO: multi-window support
          break;
        case 'closeWindow':
          window.cmuxWin?.close();
          break;
      }
    });

    return unsub;
  }, [appState, dispatch, windowId, callbacks]);
}
