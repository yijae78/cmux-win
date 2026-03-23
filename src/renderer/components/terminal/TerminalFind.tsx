import React from 'react';
import { useState, useCallback, type FC } from 'react';
import SearchOverlay from '../search/SearchOverlay';

export interface TerminalFindProps {
  /** Called to perform search in terminal — parent passes xterm addon-search methods */
  onSearch: (query: string) => { matchCount: number };
  onFindNext: () => void;
  onFindPrevious: () => void;
  onClose: () => void;
  visible: boolean;
}

const TerminalFind: FC<TerminalFindProps> = ({
  onSearch,
  onFindNext,
  onFindPrevious,
  onClose,
  visible,
}) => {
  const [matchCount, setMatchCount] = useState<number | undefined>(undefined);
  const [currentMatch, setCurrentMatch] = useState<number | undefined>(undefined);

  const handleSearch = useCallback(
    (query: string) => {
      if (!query) {
        setMatchCount(undefined);
        setCurrentMatch(undefined);
        return;
      }
      const result = onSearch(query);
      setMatchCount(result.matchCount);
      setCurrentMatch(result.matchCount > 0 ? 1 : 0);
    },
    [onSearch],
  );

  const handleNext = useCallback(() => {
    onFindNext();
    setCurrentMatch((prev) =>
      prev !== undefined && matchCount ? (prev % matchCount) + 1 : undefined,
    );
  }, [onFindNext, matchCount]);

  const handlePrev = useCallback(() => {
    onFindPrevious();
    setCurrentMatch((prev) =>
      prev !== undefined && matchCount ? ((prev - 2 + matchCount) % matchCount) + 1 : undefined,
    );
  }, [onFindPrevious, matchCount]);

  if (!visible) return null;

  return (
    <SearchOverlay
      onSearch={handleSearch}
      onNext={handleNext}
      onPrev={handlePrev}
      onClose={onClose}
      matchCount={matchCount}
      currentMatch={currentMatch}
    />
  );
};

export default TerminalFind;
