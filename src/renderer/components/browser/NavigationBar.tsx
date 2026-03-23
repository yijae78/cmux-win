import React from 'react';
import { type FC } from 'react';
import { type SearchEngine } from '../../../shared/url-utils';
import Omnibar from './Omnibar';

export interface NavigationBarProps {
  url: string;
  isLoading: boolean;
  canGoBack: boolean;
  canGoForward: boolean;
  searchEngine: SearchEngine;
  surfaceId: string;
  onNavigate: (url: string) => void;
  onBack: () => void;
  onForward: () => void;
  onReload: () => void;
  onStop: () => void;
  onDevTools: () => void;
}

const NAV_BUTTON_STYLE: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#ccc',
  fontSize: '14px',
  cursor: 'pointer',
  padding: '2px 6px',
  borderRadius: '4px',
  lineHeight: 1,
};

const NAV_BUTTON_DISABLED_STYLE: React.CSSProperties = {
  ...NAV_BUTTON_STYLE,
  color: '#555',
  cursor: 'default',
};

const NavigationBar: FC<NavigationBarProps> = ({
  url,
  isLoading,
  canGoBack,
  canGoForward,
  searchEngine,
  surfaceId,
  onNavigate,
  onBack,
  onForward,
  onReload,
  onStop,
  onDevTools,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        height: '36px',
        background: '#252526',
        borderBottom: '1px solid #3c3c3c',
        padding: '0 4px',
        gap: '2px',
        flexShrink: 0,
      }}
    >
      {/* Back */}
      <button
        onClick={onBack}
        disabled={!canGoBack}
        style={canGoBack ? NAV_BUTTON_STYLE : NAV_BUTTON_DISABLED_STYLE}
        title="Back"
      >
        &#x2190;
      </button>

      {/* Forward */}
      <button
        onClick={onForward}
        disabled={!canGoForward}
        style={canGoForward ? NAV_BUTTON_STYLE : NAV_BUTTON_DISABLED_STYLE}
        title="Forward"
      >
        &#x2192;
      </button>

      {/* Reload / Stop */}
      <button
        onClick={isLoading ? onStop : onReload}
        style={NAV_BUTTON_STYLE}
        title={isLoading ? 'Stop' : 'Reload'}
      >
        {isLoading ? '\u2715' : '\u21BB'}
      </button>

      {/* Omnibar (URL / search input with autocomplete) */}
      <Omnibar
        currentUrl={url}
        onNavigate={onNavigate}
        surfaceId={surfaceId}
        searchEngine={searchEngine}
      />

      {/* DevTools */}
      <button onClick={onDevTools} style={NAV_BUTTON_STYLE} title="Developer Tools">
        &#x2699;
      </button>
    </div>
  );
};

export default NavigationBar;
