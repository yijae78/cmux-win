import React from 'react';
import { type FC } from 'react';
import SearchOverlay from '../search/SearchOverlay';

export interface BrowserFindProps {
  /** Call webview.findInPage(text) */
  onSearch: (query: string) => void;
  /** Call webview.findInPage(text, { forward: true, findNext: true }) */
  onFindNext: () => void;
  /** Call webview.findInPage(text, { forward: false, findNext: true }) */
  onFindPrevious: () => void;
  /** Call webview.stopFindInPage('clearSelection') */
  onClose: () => void;
  visible: boolean;
  matchCount?: number;
  activeMatchOrdinal?: number;
}

const BrowserFind: FC<BrowserFindProps> = ({
  onSearch,
  onFindNext,
  onFindPrevious,
  onClose,
  visible,
  matchCount,
  activeMatchOrdinal,
}) => {
  if (!visible) return null;

  return (
    <SearchOverlay
      onSearch={onSearch}
      onNext={onFindNext}
      onPrev={onFindPrevious}
      onClose={onClose}
      matchCount={matchCount}
      currentMatch={activeMatchOrdinal}
    />
  );
};

export default BrowserFind;
