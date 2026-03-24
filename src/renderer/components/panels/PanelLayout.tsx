import React from 'react';
import { type FC, createContext, useCallback, useEffect, useRef, useState } from 'react';
import type {
  PanelLayoutTree,
  PanelState,
  SurfaceState,
  SettingsState,
} from '../../../shared/types';
import type { Action } from '../../../shared/actions';
import {
  DndContext,
  DragOverlay,
  MouseSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import type { DragStartEvent, DragEndEvent, DragOverEvent } from '@dnd-kit/core';
import PanelContainer from './PanelContainer';
import PanelDivider from './PanelDivider';

/**
 * B1: FilteredMouseSensor — data-no-dnd="true" 요소에서 시작된 이벤트를 무시.
 * S1: button === 0 (좌클릭만) 체크 포함.
 */
class FilteredMouseSensor extends MouseSensor {
  static activators = [
    {
      eventName: 'onMouseDown' as const,
      handler: ({ nativeEvent }: { nativeEvent: MouseEvent }) => {
        if (nativeEvent.button !== 0) return false;
        let el = nativeEvent.target as HTMLElement | null;
        while (el) {
          if (el.dataset?.noDnd === 'true') return false;
          el = el.parentElement;
        }
        return true;
      },
    },
  ];
}

/* ------------------------------------------------------------------ */
/*  Drop direction types & context                                     */
/* ------------------------------------------------------------------ */
export type DropDirection = 'left' | 'right' | 'top' | 'bottom' | 'center';

export interface DropTarget {
  panelId: string;
  direction: DropDirection;
}

export const DropTargetContext = createContext<DropTarget | null>(null);

/* ------------------------------------------------------------------ */
/*  Focus-flash keyframes injected once into <head>                    */
/* ------------------------------------------------------------------ */
const FOCUS_FLASH_ID = 'cmux-focus-flash-style';

function ensureFocusFlashStyle(): void {
  if (document.getElementById(FOCUS_FLASH_ID)) return;
  const style = document.createElement('style');
  style.id = FOCUS_FLASH_ID;
  style.textContent = `
@keyframes cmux-focus-flash {
  0%   { box-shadow: inset 0 0 0 0px rgba(0,145,255,0); }
  20%  { box-shadow: inset 0 0 0 6px rgba(0,145,255,0.4); }
  40%  { box-shadow: inset 0 0 0 0px rgba(0,145,255,0); }
  60%  { box-shadow: inset 0 0 0 6px rgba(0,145,255,0.4); }
  80%  { box-shadow: inset 0 0 0 0px rgba(0,145,255,0); }
  100% { box-shadow: inset 0 0 0 0px rgba(0,145,255,0); }
}`;
  document.head.appendChild(style);
}

/* ------------------------------------------------------------------ */
/*  Helper: compute drop direction from pointer position               */
/*  Uses VS Code's 33% threshold algorithm                             */
/* ------------------------------------------------------------------ */
function computeDropDirection(
  pointerX: number,
  pointerY: number,
  rect: DOMRect,
): DropDirection {
  // Pixel distance from each edge
  const pxLeft = pointerX - rect.left;
  const pxRight = rect.right - pointerX;
  const pxTop = pointerY - rect.top;
  const pxBottom = rect.bottom - pointerY;

  // Use absolute pixel distance (not relative %)
  // This way narrow-but-tall panels can still detect top/bottom
  const edgeThreshold = 60; // pixels from edge to trigger directional drop
  const minPx = Math.min(pxLeft, pxRight, pxTop, pxBottom);

  if (minPx > edgeThreshold) return 'center';

  if (minPx === pxTop) return 'top';
  if (minPx === pxBottom) return 'bottom';
  if (minPx === pxLeft) return 'left';
  return 'right';
}

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */
export interface PanelLayoutProps {
  layout: PanelLayoutTree;
  panels: PanelState[];
  surfaces: SurfaceState[];
  activePanelId: string | null;
  settings: SettingsState;
  workspaceId?: string;
  onPanelFocus: (panelId: string) => void;
  onResize: (panelId: string, ratio: number) => void;
  onSurfaceFocus: (surfaceId: string) => void;
  onSurfaceClose: (surfaceId: string) => void;
  onNewSurface: (panelId: string) => void;
  onOpenFolder?: () => void;
  onEqualizeH?: () => void;
  onEqualizeV?: () => void;
  onBrowserUrlChange?: (surfaceId: string, url: string) => void;
  onBrowserTitleChange?: (surfaceId: string, title: string) => void;
  dispatch?: (action: Action) => Promise<{ ok: boolean }>;
}

/* ------------------------------------------------------------------ */
/*  Inner recursive component (no DndContext -- safe for recursion)     */
/* ------------------------------------------------------------------ */
const PanelLayoutInner: FC<PanelLayoutProps> = ({
  layout,
  panels,
  surfaces,
  activePanelId,
  settings,
  workspaceId,
  onPanelFocus,
  onResize,
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
  // ALL hooks must be called unconditionally (before any early returns)
  // to satisfy React's rules of hooks.
  const firstLeafPanelId = layout.type === 'split' ? getFirstLeafPanelId(layout.children[0]) : null;

  const handleDrag = useCallback(
    (newRatio: number) => {
      if (firstLeafPanelId) onResize(firstLeafPanelId, newRatio);
    },
    [firstLeafPanelId, onResize],
  );

  /* ---- Leaf node ---- */
  if (layout.type === 'leaf') {
    const panel = panels.find((p) => p.id === layout.panelId);
    if (!panel) return null;

    return (
      <PanelContainer
        panel={panel}
        surfaces={surfaces}
        settings={settings}
        isActive={panel.id === activePanelId}
        workspaceId={workspaceId}
        onFocus={onPanelFocus}
        onSurfaceFocus={onSurfaceFocus}
        onSurfaceClose={onSurfaceClose}
        onNewSurface={onNewSurface}
        onOpenFolder={onOpenFolder}
        onEqualizeH={onEqualizeH}
        onEqualizeV={onEqualizeV}
        onBrowserUrlChange={onBrowserUrlChange}
        onBrowserTitleChange={onBrowserTitleChange}
        dispatch={dispatch}
      />
    );
  }

  /* ---- Split node: check if children have any live panels (recursive) ---- */
  const hasLivePanels = (node: typeof layout): boolean => {
    if (node.type === 'leaf') return panels.some((p) => p.id === node.panelId);
    return hasLivePanels(node.children[0]) || hasLivePanels(node.children[1]);
  };
  const leftHasPanel = hasLivePanels(layout.children[0]);
  const rightHasPanel = hasLivePanels(layout.children[1]);
  // Collapse: render only the side that has panels
  if (!leftHasPanel && !rightHasPanel) return null;
  const innerProps = { panels, surfaces, activePanelId, settings, workspaceId, onPanelFocus, onResize, onSurfaceFocus, onSurfaceClose, onNewSurface, onOpenFolder, onEqualizeH, onEqualizeV, onBrowserUrlChange, onBrowserTitleChange, dispatch };
  if (!leftHasPanel) return <PanelLayoutInner layout={layout.children[1]} {...innerProps} />;
  if (!rightHasPanel) return <PanelLayoutInner layout={layout.children[0]} {...innerProps} />;

  /* ---- Split node: recursive CSS Grid with 6px divider ---- */
  const isHorizontal = layout.direction === 'horizontal';
  const gridTemplate = isHorizontal
    ? { gridTemplateColumns: `${layout.ratio}fr 8px ${1 - layout.ratio}fr` }
    : { gridTemplateRows: `${layout.ratio}fr 8px ${1 - layout.ratio}fr` };

  return (
    <div
      role="group"
      aria-label="Panel layout"
      style={{
        display: 'grid',
        ...gridTemplate,
        width: '100%',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      <PanelLayoutInner
        layout={layout.children[0]}
        panels={panels}
        surfaces={surfaces}
        activePanelId={activePanelId}
        settings={settings}
        workspaceId={workspaceId}
        onPanelFocus={onPanelFocus}
        onResize={onResize}
        onSurfaceFocus={onSurfaceFocus}
        onSurfaceClose={onSurfaceClose}
        onNewSurface={onNewSurface}
        onOpenFolder={onOpenFolder}
        onEqualizeH={onEqualizeH}
        onEqualizeV={onEqualizeV}
        onBrowserUrlChange={onBrowserUrlChange}
        onBrowserTitleChange={onBrowserTitleChange}
        dispatch={dispatch}
      />
      <PanelDivider direction={isHorizontal ? 'horizontal' : 'vertical'} onDrag={handleDrag} />
      <PanelLayoutInner
        layout={layout.children[1]}
        panels={panels}
        surfaces={surfaces}
        activePanelId={activePanelId}
        settings={settings}
        workspaceId={workspaceId}
        onPanelFocus={onPanelFocus}
        onResize={onResize}
        onSurfaceFocus={onSurfaceFocus}
        onSurfaceClose={onSurfaceClose}
        onNewSurface={onNewSurface}
        onOpenFolder={onOpenFolder}
        onEqualizeH={onEqualizeH}
        onEqualizeV={onEqualizeV}
        onBrowserUrlChange={onBrowserUrlChange}
        onBrowserTitleChange={onBrowserTitleChange}
        dispatch={dispatch}
      />
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  Top-level component -- wraps with DndContext + DragOverlay          */
/* ------------------------------------------------------------------ */
const PanelLayout: FC<PanelLayoutProps> = (props) => {
  const {
    panels,
    surfaces,
    dispatch,
  } = props;

  // Inject keyframes once on first mount
  const injected = useRef(false);
  if (!injected.current) {
    ensureFocusFlashStyle();
    injected.current = true;
  }

  // Track the currently dragged panel for DragOverlay
  const [activeDragPanelId, setActiveDragPanelId] = useState<string | null>(null);

  // Track the current drop target with directional info
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null);

  // Track global pointer position during drag for directional detection
  const pointerPos = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Track pointer position + continuously update drop direction during drag
  const lastOverIdRef = useRef<string | null>(null);
  const lastOverRectRef = useRef<DOMRect | null>(null);

  useEffect(() => {
    if (!activeDragPanelId) {
      lastOverIdRef.current = null;
      lastOverRectRef.current = null;
      return;
    }
    const handler = (e: PointerEvent) => {
      pointerPos.current = { x: e.clientX, y: e.clientY };
      // Continuously recompute drop direction while hovering over a droppable
      if (lastOverIdRef.current && lastOverRectRef.current) {
        const direction = computeDropDirection(e.clientX, e.clientY, lastOverRectRef.current);
        setDropTarget({ panelId: lastOverIdRef.current, direction });
      }
    };
    window.addEventListener('pointermove', handler);
    return () => window.removeEventListener('pointermove', handler);
  }, [activeDragPanelId]);

  // Require 8px of movement before starting a drag -- prevents accidental drags
  const mouseSensor = useSensor(FilteredMouseSensor, {
    activationConstraint: { distance: 5 },
  });
  const sensors = useSensors(mouseSensor);

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const panelId = event.active.data.current?.panelId as string | undefined;
    if (panelId) setActiveDragPanelId(panelId);
  }, []);

  const handleDragOver = useCallback(
    (event: DragOverEvent) => {
      const fromPanelId = event.active.data.current?.panelId as string | undefined;
      const overPanelId = event.over?.data.current?.panelId as string | undefined;

      if (!overPanelId || !fromPanelId || fromPanelId === overPanelId) {
        setDropTarget(null);
        lastOverIdRef.current = null;
        lastOverRectRef.current = null;
        return;
      }

      // Cache the droppable rect so pointermove can recompute direction in real-time
      const dropNode = event.over?.rect;
      if (dropNode) {
        lastOverRectRef.current = new DOMRect(dropNode.left, dropNode.top, dropNode.width, dropNode.height);
      }
      lastOverIdRef.current = overPanelId;

      const rect = lastOverRectRef.current;
      if (!rect) {
        setDropTarget({ panelId: overPanelId, direction: 'center' });
        return;
      }
      const direction = computeDropDirection(pointerPos.current.x, pointerPos.current.y, rect);
      setDropTarget({ panelId: overPanelId, direction });
    },
    [],
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      // Now clear state
      setActiveDragPanelId(null);
      setDropTarget(null);
      lastOverIdRef.current = null;
      lastOverRectRef.current = null;

      const fromPanelId = event.active.data.current?.panelId as string | undefined;
      if (!fromPanelId || !dispatch) return;

      // Check if dropped on an edge zone (EdgeDropZone provides direction directly)
      const overData = event.over?.data.current as { panelId?: string; direction?: DropDirection; isEdgeDrop?: boolean } | undefined;
      if (overData?.isEdgeDrop && overData.panelId && overData.direction) {
        const toPanelId = overData.panelId;
        const direction = overData.direction;
        if (fromPanelId === toPanelId) {
          // Self-drop: split this panel in the given direction
          void dispatch({
            type: 'panel.split',
            payload: { panelId: fromPanelId, direction: direction === 'left' || direction === 'right' ? 'horizontal' : 'vertical', newPanelType: 'terminal' },
          });
        } else {
          void dispatch({
            type: 'panel.move',
            payload: { sourcePanelId: fromPanelId, targetPanelId: toPanelId, direction },
          });
        }
        return;
      }

      // Fallback: dropped on panel body (center = swap)
      const toPanelId = overData?.panelId;
      if (!toPanelId || fromPanelId === toPanelId) return;

      void dispatch({
        type: 'panel.swap',
        payload: { panelId1: fromPanelId, panelId2: toPanelId },
      });
    },
    [dispatch],
  );

  const handleDragCancel = useCallback(() => {
    setActiveDragPanelId(null);
    setDropTarget(null);
  }, []);

  // Build the drag overlay content
  const draggedPanel = activeDragPanelId ? panels.find((p) => p.id === activeDragPanelId) : null;
  const draggedSurface = draggedPanel
    ? surfaces.find((s) => s.id === draggedPanel.activeSurfaceId)
    : null;

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <DropTargetContext.Provider value={dropTarget}>
        <PanelLayoutInner {...props} />
      </DropTargetContext.Provider>

      {/* Ghost card that follows the cursor while dragging */}
      <DragOverlay dropAnimation={null}>
        {activeDragPanelId && draggedPanel ? (
          <div
            style={{
              width: 320,
              height: 180,
              background: 'rgba(30, 30, 30, 0.9)',
              border: '3px solid #0091FF',
              borderRadius: '10px',
              boxShadow: '0 12px 40px rgba(0, 145, 255, 0.3), 0 4px 12px rgba(0,0,0,0.6)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              pointerEvents: 'none',
              cursor: 'grabbing',
            }}
          >
            {/* Mini tab bar */}
            <div
              style={{
                height: 32,
                background: '#252526',
                borderBottom: '2px solid #0091FF',
                display: 'flex',
                alignItems: 'center',
                padding: '0 12px',
                gap: '8px',
                fontSize: '13px',
                color: '#fff',
                fontWeight: 600,
              }}
            >
              <span style={{ color: '#0091FF' }}>{'\u2630'}</span>
              {draggedSurface?.title ?? draggedPanel.panelType}
            </div>
            {/* Content placeholder with terminal-like lines */}
            <div
              style={{
                flex: 1,
                background: '#1e1e1e',
                padding: '8px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
              }}
            >
              <div style={{ height: '8px', width: '60%', background: '#333', borderRadius: '4px' }} />
              <div style={{ height: '8px', width: '80%', background: '#2a2a2a', borderRadius: '4px' }} />
              <div style={{ height: '8px', width: '45%', background: '#333', borderRadius: '4px' }} />
              <div style={{ height: '8px', width: '70%', background: '#2a2a2a', borderRadius: '4px' }} />
            </div>
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
};

function getFirstLeafPanelId(tree: PanelLayoutTree): string | null {
  if (tree.type === 'leaf') return tree.panelId;
  return getFirstLeafPanelId(tree.children[0]);
}

export default PanelLayout;
