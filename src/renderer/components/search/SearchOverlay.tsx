import React from 'react';
import { useState, useRef, useEffect, type FC } from 'react';

export interface SearchOverlayProps {
  onSearch: (query: string) => void;
  onNext: () => void;
  onPrev: () => void;
  onClose: () => void;
  matchCount?: number;
  currentMatch?: number;
}

const SearchOverlay: FC<SearchOverlayProps> = ({
  onSearch,
  onNext,
  onPrev,
  onClose,
  matchCount,
  currentMatch,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        right: 0,
        background: '#252526',
        border: '1px solid #3c3c3c',
        padding: '4px 8px',
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        borderRadius: '0 0 0 4px',
        zIndex: 100,
      }}
    >
      <input
        ref={inputRef}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          onSearch(e.target.value);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            if (e.shiftKey) {
              onPrev();
            } else {
              onNext();
            }
          }
          if (e.key === 'Escape') {
            onClose();
          }
        }}
        style={{
          width: '200px',
          padding: '2px 6px',
          fontSize: '12px',
          background: '#3c3c3c',
          color: '#ccc',
          border: '1px solid #555',
          borderRadius: '3px',
          outline: 'none',
        }}
        placeholder="Find..."
      />
      {matchCount !== undefined && (
        <span style={{ fontSize: '11px', color: '#888' }}>
          {currentMatch ?? 0}/{matchCount}
        </span>
      )}
      <button onClick={onPrev} style={btnStyle}>
        ↑
      </button>
      <button onClick={onNext} style={btnStyle}>
        ↓
      </button>
      <button onClick={onClose} style={btnStyle}>
        ✕
      </button>
    </div>
  );
};

const btnStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#ccc',
  cursor: 'pointer',
  fontSize: '12px',
  padding: '2px 4px',
};

export default SearchOverlay;
