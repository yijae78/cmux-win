import React from 'react';
import { type FC, useState } from 'react';
import type { SurfaceState } from '../../../shared/types';

/* ------------------------------------------------------------------ */
/*  Constants — Bonsplit design                                        */
/* ------------------------------------------------------------------ */
const TAB_BAR_HEIGHT = 32;
const TAB_BAR_BG = '#1e1e1e';
const BORDER_COLOR = '#3c3c3c';
const ACCENT = '#0091FF';
const TEXT_NORMAL = '#ccc';
const TEXT_SELECTED = '#fff';
const TEXT_INACTIVE = '#888';

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */
export interface PanelTabBarProps {
  surfaceIds: string[];
  surfaces: SurfaceState[];
  activeSurfaceId: string;
  onSurfaceFocus: (surfaceId: string) => void;
  onSurfaceClose: (surfaceId: string) => void;
  onNewSurface: () => void;
  onOpenFolder?: () => void;
  onSplitRight?: () => void;
  onSplitDown?: () => void;
  onPanelClose?: () => void;
  dragHandleRef?: React.Ref<HTMLDivElement>;
  dragHandleListeners?: Record<string, unknown>;
  dragHandleAttributes?: Record<string, unknown>;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
const PanelTabBar: FC<PanelTabBarProps> = ({
  surfaceIds,
  surfaces,
  activeSurfaceId,
  onSurfaceFocus,
  onSurfaceClose,
  onNewSurface,
  onOpenFolder,
  onSplitRight,
  onSplitDown,
  onPanelClose,
  dragHandleRef,
  dragHandleListeners,
  dragHandleAttributes,
}) => {
  const [dragHandleHovered, setDragHandleHovered] = useState(false);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        height: `${TAB_BAR_HEIGHT}px`,
        background: TAB_BAR_BG,
        borderBottom: `1px solid ${BORDER_COLOR}`,
        overflowX: 'auto',
        overflowY: 'hidden',
        flexShrink: 0,
        scrollbarWidth: 'none',
      }}
    >
      {/* Drag handle — always visible on every panel */}
      <div
        ref={dragHandleRef as React.RefObject<HTMLDivElement>}
        {...(dragHandleListeners as React.HTMLAttributes<HTMLDivElement>)}
        {...(dragHandleAttributes as React.HTMLAttributes<HTMLDivElement>)}
        onMouseEnter={() => setDragHandleHovered(true)}
        onMouseLeave={() => setDragHandleHovered(false)}
        title="Drag to reorder panel"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '24px',
          height: '100%',
          cursor: 'grab',
          color: dragHandleHovered ? TEXT_SELECTED : '#0091FF',
          fontSize: '14px',
          flexShrink: 0,
          userSelect: 'none',
          touchAction: 'none',
          transition: 'color 0.15s ease',
          background: dragHandleHovered ? 'rgba(0, 145, 255, 0.1)' : 'transparent',
        }}
      >
        {'\u2630'}
      </div>
      {surfaceIds.map((sid) => {
        const surface = surfaces.find((s) => s.id === sid);
        if (!surface) return null;
        const isActive = sid === activeSurfaceId;

        return (
          <TabItem
            key={sid}
            surface={surface}
            isActive={isActive}
            onFocus={() => onSurfaceFocus(sid)}
            onClose={() => onSurfaceClose(sid)}
          />
        );
      })}

      {/* [+] New surface tab */}
      <NewSurfaceButton onClick={onNewSurface} />

      {/* Spacer pushes split buttons to the right */}
      <div style={{ flex: 1 }} />

      {/* Open folder button */}
      {onOpenFolder && (
        <SplitButton
          icon={<span style={{ fontSize: '12px' }}>{'\uD83D\uDCC2'}</span>}
          label=""
          tooltip="Open Folder"
          onClick={onOpenFolder}
        />
      )}

      {/* Split buttons */}
      {onSplitRight && (
        <SplitButton
          icon={<SplitRightIcon />}
          label="Split Right"
          tooltip="Split Right (Ctrl+D)"
          onClick={onSplitRight}
        />
      )}
      {onSplitDown && (
        <SplitButton
          icon={<SplitDownIcon />}
          label="Split Down"
          tooltip="Split Down (Ctrl+Shift+D)"
          onClick={onSplitDown}
        />
      )}

      {/* Close panel button */}
      {onPanelClose && (
        <PanelCloseButton onClick={onPanelClose} />
      )}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  TabItem sub-component                                              */
/* ------------------------------------------------------------------ */
interface TabItemProps {
  surface: SurfaceState;
  isActive: boolean;
  onFocus: () => void;
  onClose: () => void;
}

const TabItem: FC<TabItemProps> = ({ surface, isActive, onFocus, onClose }) => {
  const [hovered, setHovered] = useState(false);
  const [closeHovered, setCloseHovered] = useState(false);

  return (
    <div
      onClick={onFocus}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '0 12px',
        height: '100%',
        cursor: 'pointer',
        background: 'transparent',
        color: isActive ? TEXT_SELECTED : TEXT_NORMAL,
        fontSize: '11px',
        fontWeight: 500,
        whiteSpace: 'nowrap',
        borderBottom: isActive ? `2px solid ${ACCENT}` : '2px solid transparent',
        boxSizing: 'border-box',
        position: 'relative',
      }}
    >
      <span>{surface.title}</span>

      {/* Close button (x) — visible on hover */}
      <span
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        onMouseEnter={() => setCloseHovered(true)}
        onMouseLeave={() => setCloseHovered(false)}
        style={{
          cursor: 'pointer',
          opacity: hovered || isActive ? (closeHovered ? 1 : 0.5) : 0,
          fontSize: '10px',
          lineHeight: 1,
          transition: 'opacity 0.15s ease',
          color: closeHovered ? TEXT_SELECTED : TEXT_NORMAL,
        }}
      >
        {'\u00D7'}
      </span>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  NewSurfaceButton sub-component                                     */
/* ------------------------------------------------------------------ */
interface NewSurfaceButtonProps {
  onClick: () => void;
}

const NewSurfaceButton: FC<NewSurfaceButtonProps> = ({ onClick }) => {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: '0 8px',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        cursor: 'pointer',
        color: hovered ? TEXT_SELECTED : TEXT_INACTIVE,
        fontSize: '14px',
        transition: 'color 0.15s ease',
        flexShrink: 0,
      }}
    >
      +
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  SplitIcon — Cursor-style mini layout diagram                       */
/* ------------------------------------------------------------------ */
const SplitRightIcon: FC = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
    <rect x="1" y="2" width="14" height="12" rx="1" stroke="currentColor" strokeWidth="1.2" />
    <line x1="8" y1="2" x2="8" y2="14" stroke="currentColor" strokeWidth="1.2" />
  </svg>
);

const SplitDownIcon: FC = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
    <rect x="1" y="2" width="14" height="12" rx="1" stroke="currentColor" strokeWidth="1.2" />
    <line x1="1" y1="8" x2="15" y2="8" stroke="currentColor" strokeWidth="1.2" />
  </svg>
);

/* ------------------------------------------------------------------ */
/*  SplitButton sub-component — Cursor-style split buttons             */
/* ------------------------------------------------------------------ */
interface SplitButtonProps {
  icon: React.ReactNode;
  label: string;
  tooltip: string;
  onClick: () => void;
}

const SplitButton: FC<SplitButtonProps> = ({ icon, label, tooltip, onClick }) => {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title={tooltip}
      style={{
        height: '24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '0 6px',
        cursor: 'pointer',
        color: hovered ? '#fff' : '#bbb',
        background: hovered ? ACCENT : 'rgba(255,255,255,0.06)',
        border: `1px solid ${hovered ? ACCENT : 'rgba(255,255,255,0.15)'}`,
        borderRadius: '4px',
        transition: 'all 0.15s ease',
        flexShrink: 0,
        margin: '0 3px',
        fontSize: '11px',
        fontWeight: 500,
      }}
    >
      {icon}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  PanelCloseButton — closes the entire panel                         */
/* ------------------------------------------------------------------ */
const PanelCloseButton: FC<{ onClick: () => void }> = ({ onClick }) => {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title="Close Panel"
      aria-label="Close panel"
      style={{
        height: '24px',
        width: '28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        color: hovered ? '#fff' : '#888',
        background: hovered ? '#e81123' : 'transparent',
        borderRadius: '4px',
        transition: 'all 0.15s ease',
        flexShrink: 0,
        margin: '0 3px',
        fontSize: '14px',
        fontWeight: 'bold',
      }}
    >
      {'\u00D7'}
    </div>
  );
};

export default PanelTabBar;
