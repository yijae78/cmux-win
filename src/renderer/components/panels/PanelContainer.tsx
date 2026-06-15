import React from 'react';
import { type FC, useState, useEffect, useRef } from 'react';
import type { PanelState, SurfaceState, SettingsState } from '../../../shared/types';
import type { Action } from '../../../shared/actions';
import { useDraggable, useDroppable, useDndContext } from '@dnd-kit/core';
import XTermWrapper from '../terminal/XTermWrapper';
import BrowserSurface from '../browser/BrowserSurface';
import MarkdownViewer from '../markdown/MarkdownViewer';
import PanelTabBar from './PanelTabBar';
import EdgeDropZone from './EdgeDropZone';

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */
const OVERLAY_BG = 'rgba(0,0,0,0.15)';
const FOCUS_ANIM_DURATION = 900;

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */
export interface PanelContainerProps {
  panel: PanelState;
  surfaces: SurfaceState[];
  settings: SettingsState;
  isActive: boolean;
  workspaceId?: string;
  onFocus: (panelId: string) => void;
  onSurfaceFocus: (surfaceId: string) => void;
  onSurfaceClose: (surfaceId: string) => void;
  onNewSurface: (panelId: string) => void;
  onOpenFolder?: (surfaceId: string) => void;
  onEqualizeH?: () => void;
  onEqualizeV?: () => void;
  onBrowserUrlChange?: (surfaceId: string, url: string) => void;
  onBrowserTitleChange?: (surfaceId: string, title: string) => void;
  dispatch?: (action: Action) => Promise<{ ok: boolean }>;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
const PanelContainer: FC<PanelContainerProps> = ({
  panel,
  surfaces,
  settings,
  isActive,
  workspaceId,
  onFocus,
  onSurfaceFocus,
  onSurfaceClose,
  onNewSurface,
  onOpenFolder,
  onEqualizeH,
  onEqualizeV,
  onBrowserUrlChange,
  onBrowserTitleChange,
  dispatch,
}) => {
  const panelSurfaces = surfaces.filter((s) => panel.surfaceIds.includes(s.id));
  const activeSurface = surfaces.find((s) => s.id === panel.activeSurfaceId);
  // Master 패널은 분할 불가
  const isMasterPanel = panelSurfaces.some((s) => s.label === 'Master');

  /* ---- Drag-and-drop ---- */
  const {
    attributes: dragAttributes,
    listeners: dragListeners,
    setNodeRef: setDragHandleRef,
  } = useDraggable({
    id: `panel-drag-${panel.id}`,
    data: { panelId: panel.id },
  });

  const { setNodeRef: setDropRef } = useDroppable({
    id: `panel-drop-${panel.id}`,
    data: { panelId: panel.id },
  });

  /* ---- Detect if any drag is active (for edge drop zones) ---- */
  const { active: dndActive } = useDndContext();
  const isDragActiveGlobal = dndActive !== null;

  /* ---- Focus flash animation ---- */
  const [flashing, setFlashing] = useState(false);
  const prevActive = useRef(isActive);

  useEffect(() => {
    if (isActive && !prevActive.current) {
      setFlashing(true);
      const timer = setTimeout(() => setFlashing(false), FOCUS_ANIM_DURATION);
      return () => clearTimeout(timer);
    }
    prevActive.current = isActive;
  }, [isActive]);

  const handleClick = () => {
    if (!isActive) {
      onFocus(panel.id);
    }
  };

  return (
    <div
      ref={setDropRef}
      role="tabpanel"
      aria-label={`${panel.panelType} panel -- ${activeSurface?.title ?? 'empty'}`}
      onClick={handleClick}
      style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        borderRadius: flashing ? '10px' : undefined,
        animation: flashing ? 'cmux-focus-flash 0.9s ease-in-out forwards' : undefined,
        /* Do NOT change opacity — WebGL context loss crashes xterm.js */
      }}
    >
      {/* Tab bar */}
      <PanelTabBar
        surfaceIds={panel.surfaceIds}
        surfaces={panelSurfaces}
        activeSurfaceId={panel.activeSurfaceId}
        onSurfaceFocus={onSurfaceFocus}
        onSurfaceClose={onSurfaceClose}
        onNewSurface={() => onNewSurface(panel.id)}
        onOpenFolder={onOpenFolder ? () => onOpenFolder(panel.activeSurfaceId) : undefined}
        onEqualizeH={onEqualizeH}
        onEqualizeV={onEqualizeV}
        onSplitRight={
          dispatch && !isMasterPanel
            ? () =>
                void dispatch({
                  type: 'panel.split',
                  payload: { panelId: panel.id, direction: 'horizontal', newPanelType: 'terminal' },
                })
            : undefined
        }
        onSplitDown={
          dispatch && !isMasterPanel
            ? () =>
                void dispatch({
                  type: 'panel.split',
                  payload: { panelId: panel.id, direction: 'vertical', newPanelType: 'terminal' },
                })
            : undefined
        }
        onZoomToggle={
          dispatch
            ? () => void dispatch({ type: 'panel.zoom', payload: { panelId: panel.id } })
            : undefined
        }
        isZoomed={panel.isZoomed}
        onPanelClose={
          dispatch
            ? () => void dispatch({ type: 'panel.close', payload: { panelId: panel.id } })
            : undefined
        }
        dragHandleRef={setDragHandleRef}
        dragHandleListeners={dragListeners}
        dragHandleAttributes={dragAttributes}
      />

      {/* Surface content area */}
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        {activeSurface?.surfaceType === 'terminal' && (
          <XTermWrapper
            surfaceId={activeSurface.id}
            workspaceId={workspaceId}
            paneIndex={panel.paneIndex}
            fontSize={settings.terminal.fontSize}
            fontFamily={settings.terminal.fontFamily}
            cursorStyle={settings.terminal.cursorStyle}
            themeName={settings.terminal.themeName}
            screenReaderMode={settings.accessibility.screenReaderMode}
            pendingCommand={activeSurface?.pendingCommand}
            dispatch={dispatch}
          />
        )}
        {activeSurface?.surfaceType === 'browser' && (
          <BrowserSurface
            surfaceId={activeSurface.id}
            initialUrl={activeSurface.browser?.url || 'about:blank'}
            profileId={activeSurface.browser?.profileId || 'default'}
            searchEngine={settings.browser.searchEngine}
            onUrlChange={(u) => onBrowserUrlChange?.(activeSurface.id, u)}
            onTitleChange={(t) => onBrowserTitleChange?.(activeSurface.id, t)}
          />
        )}
        {activeSurface?.surfaceType === 'markdown' && (
          <MarkdownViewer filePath={activeSurface.markdown?.filePath || ''} />
        )}
      </div>

      {/* Unfocused pane overlay */}
      {!isActive && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: OVERLAY_BG,
            pointerEvents: 'none',
            zIndex: 1,
          }}
        />
      )}

      {/* Edge drop zones — visible during any active drag */}
      <EdgeDropZone panelId={panel.id} direction="top" isDragActive={isDragActiveGlobal} />
      <EdgeDropZone panelId={panel.id} direction="bottom" isDragActive={isDragActiveGlobal} />
      <EdgeDropZone panelId={panel.id} direction="left" isDragActive={isDragActiveGlobal} />
      <EdgeDropZone panelId={panel.id} direction="right" isDragActive={isDragActiveGlobal} />
    </div>
  );
};

export default PanelContainer;
