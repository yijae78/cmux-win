import React from 'react';
import { useEffect, type FC } from 'react';

export interface ShortcutEntry {
  key: string;
  description: string;
  category: string;
}

interface ShortcutHintOverlayProps {
  shortcuts: ShortcutEntry[];
  visible: boolean;
  onClose: () => void;
}

const ShortcutHintOverlay: FC<ShortcutHintOverlayProps> = ({ shortcuts, visible, onClose }) => {
  useEffect(() => {
    if (!visible) return;
    const handler = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [visible, onClose]);

  if (!visible) return null;

  const categories = [...new Set(shortcuts.map((s) => s.category))];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 300,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#1e1e1e',
          borderRadius: '8px',
          border: '1px solid #3c3c3c',
          padding: '24px',
          maxWidth: '600px',
          width: '90%',
          maxHeight: '70vh',
          overflowY: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
          <span style={{ color: '#ccc', fontSize: '15px', fontWeight: 'bold' }}>
            Keyboard Shortcuts
          </span>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#888',
              cursor: 'pointer',
              fontSize: '16px',
            }}
          >
            &#x2715;
          </button>
        </div>
        {categories.map((cat) => (
          <div key={cat} style={{ marginBottom: '16px' }}>
            <div
              style={{
                color: '#888',
                fontSize: '11px',
                textTransform: 'uppercase',
                marginBottom: '8px',
              }}
            >
              {cat}
            </div>
            {shortcuts
              .filter((s) => s.category === cat)
              .map((s) => (
                <div
                  key={s.key}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '4px 0',
                  }}
                >
                  <span style={{ color: '#ccc', fontSize: '12px' }}>{s.description}</span>
                  <kbd
                    style={{
                      background: '#333',
                      color: '#aaa',
                      padding: '2px 8px',
                      borderRadius: '3px',
                      fontSize: '11px',
                      border: '1px solid #555',
                      fontFamily: 'monospace',
                    }}
                  >
                    {s.key}
                  </kbd>
                </div>
              ))}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ShortcutHintOverlay;
