import React from 'react';
import { useState, useEffect, useRef, useCallback, type FC } from 'react';
import { markdownToHtml } from '../../../shared/markdown-parser';

declare global {
  interface Window {
    cmuxFile?: {
      readFile(filePath: string): Promise<{ content: string } | { error: string }>;
      watchFile?(filePath: string, callback: (changedPath: string) => void): () => void;
    };
  }
}

export interface MarkdownViewerProps {
  filePath: string;
}

const POLL_INTERVAL_MS = 2000;

const MarkdownViewer: FC<MarkdownViewerProps> = ({ filePath }) => {
  const [html, setHtml] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const lastContentRef = useRef<string>('');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadFile = useCallback(async (fp: string) => {
    if (!window.cmuxFile) {
      setHtml(
        markdownToHtml(
          '# File viewing requires Electron\n\nThe markdown viewer needs the Electron IPC bridge (`window.cmuxFile`) to read files from disk.\n\nRunning in standalone/browser mode is not supported for file viewing.',
        ),
      );
      setError(null);
      return;
    }

    try {
      const result = await window.cmuxFile.readFile(fp);
      if ('error' in result) {
        setError(result.error);
        setHtml('');
        return;
      }
      // Only re-render if content changed
      if (result.content !== lastContentRef.current) {
        lastContentRef.current = result.content;
        setHtml(markdownToHtml(result.content));
        setError(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to read file');
    }
  }, []);

  useEffect(() => {
    // Cleanup previous timer
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    // Reset state
    lastContentRef.current = '';
    setHtml('');
    setError(null);

    if (!filePath) {
      setHtml('<p style="color:#888">No file selected</p>');
      return;
    }

    // Initial load
    setLoading(true);
    loadFile(filePath).finally(() => setLoading(false));

    // M9: Use fs.watch via IPC instead of polling; fall back to polling if unavailable
    let unwatchFn: (() => void) | null = null;
    if (window.cmuxFile?.watchFile) {
      unwatchFn = window.cmuxFile.watchFile(filePath, () => {
        loadFile(filePath);
      });
    } else {
      timerRef.current = setInterval(() => {
        loadFile(filePath);
      }, POLL_INTERVAL_MS);
    }

    return () => {
      if (unwatchFn) unwatchFn();
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [filePath, loadFile]);

  if (loading && !html) {
    return <div style={{ color: '#888', padding: '16px' }}>Loading...</div>;
  }

  if (error) return <div style={{ color: '#f44', padding: '16px' }}>{error}</div>;

  return (
    <div
      style={{
        padding: '16px',
        color: '#ccc',
        overflow: 'auto',
        height: '100%',
        fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
        lineHeight: 1.6,
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};

export default MarkdownViewer;
