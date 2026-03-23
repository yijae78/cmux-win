import React, { type FC, useState, useCallback, useRef, useEffect } from 'react';
import { isUrl, inputToUrl, type SearchEngine } from '../../../shared/url-utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OmnibarProps {
  currentUrl: string;
  onNavigate: (url: string) => void;
  surfaceId: string;
  searchEngine?: SearchEngine;
}

interface Suggestion {
  url: string;
  title?: string;
}

// Augment Window for the optional queryHistory API
declare global {
  interface Window {
    cmuxBrowser?: Window['cmuxBrowser'] & {
      queryHistory?: (prefix: string) => Promise<Suggestion[]>;
    };
  }
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_SUGGESTIONS = 8;
const DEBOUNCE_MS = 150;

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const INPUT_STYLE_BASE: React.CSSProperties = {
  flex: 1,
  height: '24px',
  background: '#272822',
  border: '1px solid #3c3c3c',
  borderRadius: '4px',
  color: '#e0e0e0',
  fontSize: '12px',
  padding: '0 8px',
  outline: 'none',
  fontFamily: 'inherit',
};

const INPUT_STYLE_FOCUSED: React.CSSProperties = {
  ...INPUT_STYLE_BASE,
  border: '1px solid #007acc',
};

const DROPDOWN_STYLE: React.CSSProperties = {
  position: 'absolute',
  top: '100%',
  left: 0,
  right: 0,
  background: '#272822',
  border: '1px solid #3c3c3c',
  borderTop: 'none',
  borderRadius: '0 0 4px 4px',
  zIndex: 9999,
  maxHeight: '240px',
  overflowY: 'auto',
  boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
};

const SUGGESTION_STYLE: React.CSSProperties = {
  padding: '4px 8px',
  fontSize: '12px',
  color: '#e0e0e0',
  cursor: 'pointer',
  display: 'flex',
  flexDirection: 'column',
  gap: '1px',
  overflow: 'hidden',
};

const SUGGESTION_ACTIVE_STYLE: React.CSSProperties = {
  ...SUGGESTION_STYLE,
  background: '#3c3c3c',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const Omnibar: FC<OmnibarProps> = ({
  currentUrl,
  onNavigate,
  surfaceId: _surfaceId,
  searchEngine = 'google',
}) => {
  const [inputValue, setInputValue] = useState(currentUrl);
  const [isFocused, setIsFocused] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync external URL changes when not focused
  useEffect(() => {
    if (!isFocused) {
      setInputValue(currentUrl);
    }
  }, [currentUrl, isFocused]);

  // ---------------------------------------------------------------------------
  // History autocomplete query (debounced)
  // ---------------------------------------------------------------------------

  const fetchSuggestions = useCallback((prefix: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!prefix.trim()) {
      setSuggestions([]);
      setShowDropdown(false);
      setActiveIndex(-1);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      const queryFn = window.cmuxBrowser?.queryHistory;
      if (typeof queryFn === 'function') {
        try {
          const results = await queryFn(prefix);
          const limited = (results || []).slice(0, MAX_SUGGESTIONS);
          setSuggestions(limited);
          setShowDropdown(limited.length > 0);
          setActiveIndex(-1);
        } catch {
          setSuggestions([]);
          setShowDropdown(false);
        }
      } else {
        // No history API available -- build local placeholder suggestions
        // based on whether the input looks like a URL or a search query
        const builtIn: Suggestion[] = [];
        if (isUrl(prefix)) {
          builtIn.push({ url: inputToUrl(prefix, searchEngine), title: 'Navigate to URL' });
        } else {
          builtIn.push({
            url: inputToUrl(prefix, searchEngine),
            title: `Search ${searchEngine}: "${prefix}"`,
          });
        }
        setSuggestions(builtIn.slice(0, MAX_SUGGESTIONS));
        setShowDropdown(builtIn.length > 0);
        setActiveIndex(-1);
      }
    }, DEBOUNCE_MS);
  }, [searchEngine]);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setInputValue(val);
      fetchSuggestions(val);
    },
    [fetchSuggestions],
  );

  const submitValue = useCallback(
    (value: string) => {
      const resolved = inputToUrl(value.trim(), searchEngine);
      onNavigate(resolved);
      setShowDropdown(false);
      setSuggestions([]);
      setActiveIndex(-1);
      inputRef.current?.blur();
    },
    [searchEngine, onNavigate],
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (activeIndex >= 0 && activeIndex < suggestions.length) {
        submitValue(suggestions[activeIndex].url);
      } else {
        submitValue(inputValue);
      }
    },
    [inputValue, activeIndex, suggestions, submitValue],
  );

  const handleSuggestionClick = useCallback(
    (suggestion: Suggestion) => {
      setInputValue(suggestion.url);
      submitValue(suggestion.url);
    },
    [submitValue],
  );

  const handleFocus = useCallback(() => {
    setIsFocused(true);
    // Select all text on focus for quick editing
    requestAnimationFrame(() => inputRef.current?.select());
  }, []);

  const handleBlur = useCallback(() => {
    // Delay hiding dropdown so click events on suggestions can fire
    setTimeout(() => {
      setIsFocused(false);
      setShowDropdown(false);
      setActiveIndex(-1);
    }, 150);
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowDropdown(false);
        setSuggestions([]);
        setActiveIndex(-1);
        inputRef.current?.blur();
        return;
      }

      if (!showDropdown || suggestions.length === 0) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((prev) => (prev + 1) % suggestions.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1));
      }
    },
    [showDropdown, suggestions.length],
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div ref={containerRef} style={{ flex: 1, position: 'relative', display: 'flex' }}>
      <form onSubmit={handleSubmit} style={{ flex: 1, display: 'flex' }}>
        <input
          ref={inputRef}
          value={inputValue}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          style={isFocused ? INPUT_STYLE_FOCUSED : INPUT_STYLE_BASE}
          placeholder="Search or enter URL"
          spellCheck={false}
          autoComplete="off"
        />
      </form>

      {showDropdown && suggestions.length > 0 && (
        <div style={DROPDOWN_STYLE}>
          {suggestions.map((suggestion, idx) => (
            <div
              key={`${suggestion.url}-${idx}`}
              style={idx === activeIndex ? SUGGESTION_ACTIVE_STYLE : SUGGESTION_STYLE}
              onMouseDown={(e) => {
                // Prevent input blur from firing before the click registers
                e.preventDefault();
              }}
              onClick={() => handleSuggestionClick(suggestion)}
              onMouseEnter={() => setActiveIndex(idx)}
            >
              {suggestion.title && (
                <span
                  style={{
                    fontSize: '11px',
                    color: '#888',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {suggestion.title}
                </span>
              )}
              <span
                style={{
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  color: '#6cb6ff',
                  fontSize: '11px',
                }}
              >
                {suggestion.url}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Omnibar;
