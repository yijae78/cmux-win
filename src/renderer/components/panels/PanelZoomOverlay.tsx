import React from 'react';
import { type FC } from 'react';

interface PanelZoomOverlayProps {
  isZoomed: boolean;
  onExit: () => void;
}

/**
 * Shows a small overlay badge when a panel is zoomed,
 * indicating the user can press Escape or Ctrl+Shift+Enter to exit.
 */
const PanelZoomOverlay: FC<PanelZoomOverlayProps> = ({ isZoomed, onExit }) => {
  if (!isZoomed) return null;

  return (
    <div
      style={{
        position: 'absolute',
        top: 8,
        right: 8,
        zIndex: 50,
        background: 'rgba(0,0,0,0.7)',
        color: '#ccc',
        padding: '4px 12px',
        borderRadius: '4px',
        fontSize: '11px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        pointerEvents: 'auto',
      }}
    >
      <span>Zoomed</span>
      <button
        onClick={onExit}
        style={{
          background: 'transparent',
          border: '1px solid #666',
          color: '#ccc',
          padding: '2px 8px',
          borderRadius: '3px',
          cursor: 'pointer',
          fontSize: '10px',
        }}
      >
        ESC
      </button>
    </div>
  );
};

export default PanelZoomOverlay;
