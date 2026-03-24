import React from 'react';
import { type FC, useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { inputToUrl, type SearchEngine } from '../../../shared/url-utils';
import NavigationBar from './NavigationBar';

// Electron webview element type
type WebviewHTMLAttributes = React.DetailedHTMLProps<
  React.HTMLAttributes<HTMLElement> & {
    src?: string;
    partition?: string;
    allowpopups?: string;
    webpreferences?: string;
    useragent?: string;
  },
  HTMLElement
>;

// Extend JSX to recognize the Electron <webview> tag
declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace JSX {
    interface IntrinsicElements {
      webview: WebviewHTMLAttributes;
    }
  }
}

// Electron Webview element interface for ref typing
interface WebviewElement extends HTMLElement {
  getURL(): string;
  setZoomFactor(factor: number): void;
  getZoomFactor(): number;
  setUserAgent(ua: string): void;
  getUserAgent(): string;
  canGoBack(): boolean;
  canGoForward(): boolean;
  goBack(): void;
  goForward(): void;
  reload(): void;
  stop(): void;
  loadURL(url: string): void;
  isDevToolsOpened(): boolean;
  openDevTools(): void;
  closeDevTools(): void;
  executeJavaScript(code: string): Promise<unknown>;
}

// Window augmentation for cmuxBrowser (exposed from preload)
declare global {
  interface Window {
    cmuxBrowser?: {
      onExecuteRequest(
        callback: (requestId: string, surfaceId: string, code: string) => void,
      ): () => void;
      sendExecuteResult(requestId: string, result: unknown, error?: string): void;
    };
  }
}

export interface BrowserSurfaceProps {
  surfaceId: string;
  initialUrl: string;
  profileId: string;
  searchEngine?: SearchEngine;
  onUrlChange?: (url: string) => void;
  onTitleChange?: (title: string) => void;
}

const MAX_CRASHES = 3;

const BrowserSurface: FC<BrowserSurfaceProps> = ({
  surfaceId,
  initialUrl,
  profileId,
  searchEngine = 'google',
  onUrlChange,
  onTitleChange,
}) => {
  const { t } = useTranslation();
  const webviewRef = useRef<WebviewElement>(null);
  const callbacksRef = useRef({ onUrlChange, onTitleChange });
  callbacksRef.current = { onUrlChange, onTitleChange };

  const [currentUrl, setCurrentUrl] = useState(initialUrl);
  const [isLoading, setIsLoading] = useState(false);
  const [canGoBack, setCanGoBack] = useState(false);
  const [canGoForward, setCanGoForward] = useState(false);
  const [crashCount, setCrashCount] = useState(0);
  const [isCrashed, setIsCrashed] = useState(false);

  // Attach webview event listeners (re-run when webview mounts after size is known)
  useEffect(() => {
    const wv = webviewRef.current;
    if (!wv) return;

    // No CSS injection — use zoom factor for responsive fit.

    const onDidNavigate = () => {
      const url = wv.getURL();
      setCurrentUrl(url);
      setCanGoBack(wv.canGoBack());
      setCanGoForward(wv.canGoForward());
      callbacksRef.current.onUrlChange?.(url);
    };

    const onDidNavigateInPage = () => {
      const url = wv.getURL();
      setCurrentUrl(url);
      setCanGoBack(wv.canGoBack());
      setCanGoForward(wv.canGoForward());
      callbacksRef.current.onUrlChange?.(url);
    };

    const onPageTitleUpdated = (e: Event) => {
      const title = (e as Event & { title?: string }).title;
      if (typeof title === 'string') {
        callbacksRef.current.onTitleChange?.(title);
      }
    };

    const onDidStartLoading = () => setIsLoading(true);

    const onDidStopLoading = () => {
      setIsLoading(false);
      setCanGoBack(wv.canGoBack());
      setCanGoForward(wv.canGoForward());
    };

    const onCrashed = () => {
      const url = wv.getURL();
      console.error(`[BrowserSurface] webview crashed: ${url}`);
      setCrashCount((prev) => {
        const next = prev + 1;
        if (next >= MAX_CRASHES) {
          setIsCrashed(true);
        } else {
          // Auto-retry
          try {
            wv.reload();
          } catch {
            setIsCrashed(true);
          }
        }
        return next;
      });
    };

    wv.addEventListener('did-navigate', onDidNavigate);
    wv.addEventListener('did-navigate-in-page', onDidNavigateInPage);
    wv.addEventListener('page-title-updated', onPageTitleUpdated);
    wv.addEventListener('did-start-loading', onDidStartLoading);
    wv.addEventListener('did-stop-loading', onDidStopLoading);
    wv.addEventListener('crashed', onCrashed);

    // Browser automation IPC: listen for executeJavaScript requests from main
    const cleanupBrowser = window.cmuxBrowser?.onExecuteRequest(
      async (requestId, targetSurfaceId, code) => {
        if (targetSurfaceId !== surfaceId) return; // ignore requests for other surfaces
        const webview = webviewRef.current;
        if (!webview) {
          window.cmuxBrowser?.sendExecuteResult(requestId, null, 'webview not available');
          return;
        }
        try {
          const result = await webview.executeJavaScript(code);
          window.cmuxBrowser?.sendExecuteResult(requestId, result);
        } catch (err) {
          window.cmuxBrowser?.sendExecuteResult(requestId, null, String(err));
        }
      },
    );

    return () => {
      wv.removeEventListener('did-navigate', onDidNavigate);
      wv.removeEventListener('did-navigate-in-page', onDidNavigateInPage);
      wv.removeEventListener('page-title-updated', onPageTitleUpdated);
      wv.removeEventListener('did-start-loading', onDidStartLoading);
      wv.removeEventListener('did-stop-loading', onDidStopLoading);
      wv.removeEventListener('crashed', onCrashed);
      cleanupBrowser?.();
    };
  }, [surfaceId]);

  const handleNavigate = useCallback(
    (url: string) => {
      const wv = webviewRef.current;
      if (!wv) return;
      const resolved = inputToUrl(url, searchEngine);
      wv.loadURL(resolved);
      setCurrentUrl(resolved);
    },
    [searchEngine],
  );

  const handleBack = useCallback(() => {
    webviewRef.current?.goBack();
  }, []);

  const handleForward = useCallback(() => {
    webviewRef.current?.goForward();
  }, []);

  const handleReload = useCallback(() => {
    webviewRef.current?.reload();
  }, []);

  const handleStop = useCallback(() => {
    webviewRef.current?.stop();
  }, []);

  const handleDevTools = useCallback(() => {
    const wv = webviewRef.current;
    if (!wv) return;
    if (wv.isDevToolsOpened()) {
      wv.closeDevTools();
    } else {
      wv.openDevTools();
    }
  }, []);

  const handleRetry = useCallback(() => {
    setCrashCount(0);
    setIsCrashed(false);
    const wv = webviewRef.current;
    if (wv) {
      try {
        wv.reload();
      } catch {
        // If reload fails after crash reset, try loading the current URL
        try {
          wv.loadURL(currentUrl);
        } catch {
          // webview may be fully broken
        }
      }
    }
  }, [currentUrl]);

  if (isCrashed) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          color: '#ccc',
          gap: '12px',
        }}
      >
        <div style={{ fontSize: '16px' }}>{t('notifications.pageCrashed')}</div>
        <div style={{ fontSize: '12px', color: '#888' }}>
          The page crashed {crashCount} time{crashCount !== 1 ? 's' : ''}.
        </div>
        <button
          onClick={handleRetry}
          style={{
            padding: '6px 16px',
            background: '#007acc',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '13px',
          }}
        >
          {t('notifications.retry')}
        </button>
      </div>
    );
  }

  // claude.ai: mobile UA for responsive layout. Others: default desktop UA.
  const isClaude = initialUrl.includes('claude.ai');
  const mobileUA = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
      <NavigationBar
        url={currentUrl}
        isLoading={isLoading}
        canGoBack={canGoBack}
        canGoForward={canGoForward}
        searchEngine={searchEngine}
        surfaceId={surfaceId}
        onNavigate={handleNavigate}
        onBack={handleBack}
        onForward={handleForward}
        onReload={handleReload}
        onStop={handleStop}
        onDevTools={handleDevTools}
      />
      <webview
        ref={webviewRef}
        src={initialUrl}
        partition={`persist:${profileId}`}
        useragent={isClaude ? mobileUA : undefined}
        allowpopups=""
        webpreferences="contextIsolation=yes"
        style={{ flex: 1, width: '100%', border: 'none' }}
      />
    </div>
  );
};

export default BrowserSurface;
