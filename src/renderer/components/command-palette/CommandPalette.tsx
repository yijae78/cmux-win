import React from 'react';
import { useState, useRef, useEffect, useCallback, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { fuzzySearch } from '../../../shared/fuzzy-search';
import { buildCommandList } from '../../../shared/command-registry';
import { DEFAULT_SHORTCUTS } from '../../../shared/shortcuts';

export interface CommandPaletteProps {
  onExecute: (commandId: string) => void;
  onClose: () => void;
}

const CommandPalette: FC<CommandPaletteProps> = ({ onExecute, onClose }) => {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);

  const commands = buildCommandList(DEFAULT_SHORTCUTS);
  const results = fuzzySearch(commands, query, (c) => c.label);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      }
      if (e.key === 'Enter' && results[selectedIndex]) {
        onExecute(results[selectedIndex].item.id);
        onClose();
      }
    },
    [results, selectedIndex, onExecute, onClose],
  );

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t('commandPalette.title', 'Command Palette')}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex',
        justifyContent: 'center',
        paddingTop: '20vh',
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '500px',
          maxHeight: '400px',
          background: '#252526',
          border: '1px solid #3c3c3c',
          borderRadius: '6px',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`> ${t('commandPalette.placeholder')}`}
          style={{
            width: '100%',
            padding: '10px 14px',
            fontSize: '14px',
            background: '#1e1e1e',
            color: '#ccc',
            border: 'none',
            borderBottom: '1px solid #3c3c3c',
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
        <div style={{ maxHeight: '340px', overflowY: 'auto' }}>
          {results.map((r, i) => (
            <div
              key={r.item.id}
              onClick={() => {
                onExecute(r.item.id);
                onClose();
              }}
              style={{
                padding: '6px 14px',
                cursor: 'pointer',
                fontSize: '13px',
                display: 'flex',
                justifyContent: 'space-between',
                background: i === selectedIndex ? '#37373d' : 'transparent',
                color: i === selectedIndex ? '#fff' : '#ccc',
              }}
            >
              <span>{r.item.label}</span>
              {r.item.shortcut && (
                <span style={{ color: '#888', fontSize: '11px' }}>{r.item.shortcut}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CommandPalette;
