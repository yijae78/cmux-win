import React from 'react';
import { useRef, useState, type FC } from 'react';

const DIVIDER_SIZE = 8;

export interface PanelDividerProps {
  direction: 'horizontal' | 'vertical';
  onDrag: (ratio: number) => void;
}

const PanelDivider: FC<PanelDividerProps> = ({ direction, onDrag }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(false);
  const isH = direction === 'horizontal';

  return (
    <div
      ref={ref}
      data-no-dnd="true"
      style={{
        width: isH ? DIVIDER_SIZE : '100%',
        height: isH ? '100%' : DIVIDER_SIZE,
        cursor: isH ? 'col-resize' : 'row-resize',
        background: active ? '#0091FF' : '#444',
        flexShrink: 0,
        zIndex: 5,
        touchAction: 'none',
      }}
      onMouseDown={(e) => {
        if (e.button !== 0) return;
        e.preventDefault();

        const grid = ref.current?.parentElement;
        if (!grid) return;

        setActive(true);

        const overlay = document.createElement('div');
        overlay.style.cssText =
          `position:fixed;inset:0;z-index:99999;cursor:${isH ? 'col-resize' : 'row-resize'}`;
        document.body.appendChild(overlay);

        const move = (ev: MouseEvent) => {
          const r = grid.getBoundingClientRect();
          let ratio = isH
            ? (ev.clientX - r.left) / r.width
            : (ev.clientY - r.top) / r.height;
          ratio = Math.max(0.1, Math.min(0.9, ratio));
          onDrag(ratio);
        };

        const up = () => {
          setActive(false);
          overlay.remove();
          document.removeEventListener('mousemove', move);
          document.removeEventListener('mouseup', up);
        };

        document.addEventListener('mousemove', move);
        document.addEventListener('mouseup', up);
      }}
    />
  );
};

export default PanelDivider;
