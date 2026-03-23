import React from 'react';
import { type FC, useState, useEffect, useRef, useCallback, useContext } from 'react';
import type { PanelState, SurfaceState, SettingsState } from '../../../shared/types';
import type { Action } from '../../../shared/actions';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import XTermWrapper from '../terminal/XTermWrapper';
import BrowserSurface from '../browser/BrowserSurface';
import MarkdownViewer from '../markdown/MarkdownViewer';
import PanelTabBar from './PanelTabBar';
import { DropTargetContext, type DropDirection } from './PanelLayout';

/* ------------------------------------------------------------------ */
/*  Constants -- Bonsplit design                                        */
/* ------------------------------------------------------------------ */
const OVERLAY_BG = 'rgba(0,0,0,0.15)';
const FOCUS_ANIM_DURATION = 900; // ms -- matches 0.9s keyframe
const DROP_HIGHLIGHT = 'rgba(0, 145, 255, 0.25)';
const DROP_BORDER_COLOR = '#0091FF';

/* ------------------------------------------------------------------ */
/*  Helper: compute overlay style for directional indicator             */
/* ------------------------------------------------------------------ */
function getDirectionalOverlayStyle(direction: DropDirection): React.CSSProperties {
  const base: React.CSSProperties = {
    position: 'absolute',
    pointerEvents: 'none',
    zIndex: 10,
    transition: 'all 0.15s ease',
  };

  switch (direction) {
    case 'left':
      return {
        ...base,
        top: 0,
        left: 0,
        bottom: 0,
        width: '50%',
        background: DROP_HIGHLIGHT,
        borderLeft: `4px solid ${DROP_BORDER_COLOR}`,
        borderTop: `4px solid ${DROP_BORDER_COLOR}`,
        borderBottom: `4px solid ${DROP_BORDER_COLOR}`,
        borderRight: `2px dashed ${DROP_BORDER_COLOR}`,
        borderRadius: '8px 0 0 8px',
        boxShadow: 'inset 0 0 20px rgba(0, 145, 255, 0.15)',
      };
    case 'right':
      return {
        ...base,
        top: 0,
        right: 0,
        bottom: 0,
        width: '50%',
        background: DROP_HIGHLIGHT,
        borderRight: `4px solid ${DROP_BORDER_COLOR}`,
        borderTop: `4px solid ${DROP_BORDER_COLOR}`,
        borderBottom: `4px solid ${DROP_BORDER_COLOR}`,
        borderLeft: `2px dashed ${DROP_BORDER_COLOR}`,
        borderRadius: '0 8px 8px 0',
        boxShadow: 'inset 0 0 20px rgba(0, 145, 255, 0.15)',
      };
    case 'top':
      return {
        ...base,
        top: 0,
        left: 0,
        right: 0,
        height: '50%',
        background: DROP_HIGHLIGHT,
        borderTop: `4px solid ${DROP_BORDER_COLOR}`,
        borderLeft: `4px solid ${DROP_BORDER_COLOR}`,
        borderRight: `4px solid ${DROP_BORDER_COLOR}`,
        borderBottom: `2px dashed ${DROP_BORDER_COLOR}`,
        borderRadius: '8px 8px 0 0',
        boxShadow: 'inset 0 0 20px rgba(0, 145, 255, 0.15)',
      };
    case 'bottom':
      return {
        ...base,
        bottom: 0,
        left: 0,
        right: 0,
        height: '50%',
        background: DROP_HIGHLIGHT,
        borderBottom: `4px solid ${DROP_BORDER_COLOR}`,
        borderLeft: `4px solid ${DROP_BORDER_COLOR}`,
        borderRight: `4px solid ${DROP_BORDER_COLOR}`,
        borderTop: `2px dashed ${DROP_BORDER_COLOR}`,
        borderRadius: '0 0 8px 8px',
        boxShadow: 'inset 0 0 20px rgba(0, 145, 255, 0.15)',
      };
    case 'center':
    default:
      return {
        ...base,
        inset: '4px',
        border: `3px dashed ${DROP_BORDER_COLOR}`,
        borderRadius: '8px',
        background: 'rgba(0, 145, 255, 0.10)',
        boxShadow: 'inset 0 0 20px rgba(0, 145, 255, 0.1)',
      };
  }
}

function getDirectionalLabel(direction: DropDirection): string {
  switch (direction) {
    case 'left': return '\u2190 Insert Left';
    case 'right': return '\u2192 Insert Right';
    case 'top': return '\u2191 Insert Top';
    case 'bottom': return '\u2193 Insert Bottom';
    case 'center': return '\u21C4 Swap';
  }
}

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
  onBrowserUrlChange,
  onBrowserTitleChange,
  dispatch,
}) => {
  const panelSurfaces = surfaces.filter((s) => panel.surfaceIds.includes(s.id));
  const activeSurface = surfaces.find((s) => s.id === panel.activeSurfaceId);

  /* ---- Drop target context ---- */
  const dropTarget = useContext(DropTargetContext);
  const isDropTarget = dropTarget !== null && dropTarget.panelId === panel.id;
  const dropDirection = isDropTarget ? dropTarget.direction : null;

  /* ---- Drag-and-drop ---- */
  const {
    attributes: dragAttributes,
    listeners: dragListeners,
    setNodeRef: setDragHandleRef,
    isDragging,
  } = useDraggable({
    id: `panel-drag-${panel.id}`,
    data: { panelId: panel.id },
  });

  const {
    setNodeRef: setDropRef,
    isOver,
  } = useDroppable({
    id: `panel-drop-${panel.id}`,
    data: { panelId: panel.id },
  });

  /* ---- Focus flash animation ---- */
  const [flashing, setFlashing] = useState(false);
  const prevActive = useRef(isActive);

  useEffect(() => {
    // Trigger flash when panel transitions from inactive to active
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

  // Determine if we should show the directional drop indicator
  const showDropIndicator = isOver && !isDragging && isDropTarget && dropDirection !== null;

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
        opacity: isDragging ? 0.4 : 1,
        transition: 'opacity 0.2s ease',
      }}
    >
      {/* Tab bar -- always visible (cmux Bonsplit style: split buttons on right) */}
      <PanelTabBar
        surfaceIds={panel.surfaceIds}
        surfaces={panelSurfaces}
        activeSurfaceId={panel.activeSurfaceId}
        onSurfaceFocus={onSurfaceFocus}
        onSurfaceClose={onSurfaceClose}
        onNewSurface={() => onNewSurface(panel.id)}
        onSplitRight={
          dispatch
            ? () =>
                void dispatch({
                  type: 'panel.split',
                  payload: { panelId: panel.id, direction: 'horizontal', newPanelType: 'terminal' },
                })
            : undefined
        }
        onSplitDown={
          dispatch
            ? () =>
                void dispatch({
                  type: 'panel.split',
                  payload: { panelId: panel.id, direction: 'vertical', newPanelType: 'terminal' },
                })
            : undefined
        }
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

      {/* Unfocused pane overlay: semi-transparent 15% opacity */}
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

      {/* Directional drop indicator */}
      {showDropIndicator && (
        <div style={getDirectionalOverlayStyle(dropDirection)}>
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              color: DROP_BORDER_COLOR,
              fontSize: '14px',
              fontWeight: 'bold',
              opacity: 0.8,
              whiteSpace: 'nowrap',
              textShadow: '0 1px 3px rgba(0,0,0,0.5)',
            }}
          >
            {getDirectionalLabel(dropDirection)}
          </div>
        </div>
      )}

      {/* Fallback: uniform blue overlay when isOver but no directional context */}
      {isOver && !isDragging && !showDropIndicator && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            border: `4px solid ${DROP_BORDER_COLOR}`,
            background: DROP_HIGHLIGHT,
            borderRadius: '8px',
            pointerEvents: 'none',
            zIndex: 10,
            boxShadow: `inset 0 0 20px rgba(0, 145, 255, 0.15), 0 0 15px rgba(0, 145, 255, 0.3)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <span style={{ color: '#0091FF', fontSize: '24px', fontWeight: 'bold', opacity: 0.7 }}>
            {'\u2B07 Drop here'}
          </span>
        </div>
      )}
    </div>
  );
};

export default PanelContainer;
