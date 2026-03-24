/**
 * EdgeDropZone — invisible droppable zones on panel edges.
 * During active drag, these become visible on hover to indicate
 * directional split (top/bottom/left/right).
 * Works even for self-drop (split current panel).
 */
import { type FC, useState } from 'react';
import { useDroppable } from '@dnd-kit/core';
import type { DropDirection } from './PanelLayout';

interface EdgeDropZoneProps {
  panelId: string;
  direction: DropDirection;
  isDragActive: boolean;
}

const ZONE_SIZE = '30%';
const HIGHLIGHT = 'rgba(0, 145, 255, 0.25)';
const BORDER_COLOR = '#0091FF';

const positionMap: Record<string, React.CSSProperties> = {
  top: { top: 0, left: 0, right: 0, height: ZONE_SIZE },
  bottom: { bottom: 0, left: 0, right: 0, height: ZONE_SIZE },
  left: { top: 0, left: 0, bottom: 0, width: ZONE_SIZE },
  right: { top: 0, right: 0, bottom: 0, width: ZONE_SIZE },
};

const borderMap: Record<string, string> = {
  top: `3px solid ${BORDER_COLOR}`,
  bottom: `3px solid ${BORDER_COLOR}`,
  left: `3px solid ${BORDER_COLOR}`,
  right: `3px solid ${BORDER_COLOR}`,
};

const radiusMap: Record<string, string> = {
  top: '6px 6px 0 0',
  bottom: '0 0 6px 6px',
  left: '6px 0 0 6px',
  right: '0 6px 6px 0',
};

const labelMap: Record<string, string> = {
  top: '\u2B06',
  bottom: '\u2B07',
  left: '\u2B05',
  right: '\u27A1',
};

const EdgeDropZone: FC<EdgeDropZoneProps> = ({ panelId, direction, isDragActive }) => {
  const { setNodeRef, isOver } = useDroppable({
    id: `edge-${direction}-${panelId}`,
    data: { panelId, direction, isEdgeDrop: true },
  });

  if (!isDragActive) return null;

  return (
    <div
      ref={setNodeRef}
      style={{
        position: 'absolute',
        ...positionMap[direction],
        zIndex: 20,
        pointerEvents: 'auto',
        background: isOver ? HIGHLIGHT : 'transparent',
        border: isOver ? borderMap[direction] : 'none',
        borderRadius: isOver ? radiusMap[direction] : undefined,
        transition: 'background 0.1s, border 0.1s',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {isOver && (
        <span
          style={{
            color: BORDER_COLOR,
            fontSize: '20px',
            fontWeight: 'bold',
            opacity: 0.8,
            textShadow: '0 1px 4px rgba(0,0,0,0.5)',
          }}
        >
          {labelMap[direction]}
        </span>
      )}
    </div>
  );
};

export default EdgeDropZone;
