import { JsonRpcRouter } from '../router';
import type { AppStateStore } from '../../sot/store';
import crypto from 'node:crypto';

// ---------------------------------------------------------------------------
// Electron imports — conditional to keep vitest compatibility
// ---------------------------------------------------------------------------
let ipcMainModule: {
  on(channel: string, listener: (event: unknown, ...args: unknown[]) => void): void;
} | null = null;
let BrowserWindowModule: {
  getAllWindows(): {
    isDestroyed(): boolean;
    webContents: { send(channel: string, ...args: unknown[]): void };
  }[];
} | null = null;

try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const electron = require('electron');
  ipcMainModule = electron.ipcMain;
  BrowserWindowModule = electron.BrowserWindow;
} catch {
  // vitest environment — electron not available
}

// ---------------------------------------------------------------------------
// Pending request-response map for IPC round-trips
// ---------------------------------------------------------------------------
const pendingRequests = new Map<
  string,
  {
    resolve: (value: unknown) => void;
    reject: (error: Error) => void;
    timeout: ReturnType<typeof setTimeout>;
  }
>();

let resultListenerRegistered = false;

function ensureResultListener(): void {
  if (resultListenerRegistered || !ipcMainModule) return;
  resultListenerRegistered = true;

  ipcMainModule.on(
    'cmux:browser-execute-result',
    (_event: unknown, requestId: string, result: unknown, error?: string) => {
      const pending = pendingRequests.get(requestId);
      if (!pending) return;
      clearTimeout(pending.timeout);
      pendingRequests.delete(requestId);
      if (error) {
        pending.reject(new Error(error));
      } else {
        pending.resolve(result);
      }
    },
  );
}

// ---------------------------------------------------------------------------
// executeOnWebview — send JS code to a renderer webview via IPC
// ---------------------------------------------------------------------------
async function executeOnWebview(
  surfaceId: string,
  code: string,
  timeoutMs = 10000,
): Promise<unknown> {
  // Graceful degradation when Electron is not available (vitest, etc.)
  if (!BrowserWindowModule) return null;

  ensureResultListener();
  const requestId = crypto.randomUUID();

  // Broadcast to all windows — the renderer filters by surfaceId
  for (const win of BrowserWindowModule.getAllWindows()) {
    if (!win.isDestroyed()) {
      win.webContents.send('cmux:browser-execute', requestId, surfaceId, code);
    }
  }

  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pendingRequests.delete(requestId);
      reject(new Error('Browser execute timeout'));
    }, timeoutMs);
    pendingRequests.set(requestId, { resolve, reject, timeout });
  });
}

// ---------------------------------------------------------------------------
// Handler registration
// ---------------------------------------------------------------------------
export function registerBrowserHandlers(router: JsonRpcRouter, _store: AppStateStore): void {
  router.register('browser.eval', async (params) => {
    const p = params as { surfaceId?: string; code?: string };
    if (!p?.surfaceId) throw new Error('surfaceId required');
    if (!p?.code) throw new Error('code required');
    const result = await executeOnWebview(p.surfaceId, p.code);
    return { ok: true, result };
  });

  router.register('browser.snapshot', async (params) => {
    const p = params as { surfaceId?: string };
    if (!p?.surfaceId) throw new Error('surfaceId required');
    const snapshot = await executeOnWebview(p.surfaceId, 'document.documentElement.outerHTML');
    return { ok: true, snapshot };
  });

  router.register('browser.screenshot', async (params) => {
    const p = params as { surfaceId?: string; format?: string };
    if (!p?.surfaceId) throw new Error('surfaceId required');

    // Actual image capture requires webview.capturePage() via dedicated IPC (future).
    // Current implementation: capture DOM HTML snapshot as a text representation.
    const html = await executeOnWebview(p.surfaceId, 'document.documentElement.outerHTML');
    return {
      ok: true,
      format: 'html',
      data: typeof html === 'string' ? html : '',
      note: 'Image capture requires webview.capturePage IPC (future)',
    };
  });

  router.register('browser.click', async (params) => {
    const p = params as { surfaceId?: string; ref?: string };
    if (!p?.surfaceId) throw new Error('surfaceId required');
    if (!p?.ref) throw new Error('ref required');
    await executeOnWebview(
      p.surfaceId,
      `document.querySelector('[data-cmux-ref="${p.ref}"]')?.click()`,
    );
    return { ok: true };
  });

  router.register('browser.type', async (params) => {
    const p = params as { surfaceId?: string; text?: string };
    if (!p?.surfaceId) throw new Error('surfaceId required');
    if (!p?.text) throw new Error('text required');
    const escapedText = JSON.stringify(p.text);
    await executeOnWebview(
      p.surfaceId,
      `(() => {
        const el = document.activeElement;
        if (el) {
          el.value = (el.value || '') + ${escapedText};
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }
      })()`,
    );
    return { ok: true };
  });

  router.register('browser.fill', async (params) => {
    const p = params as { surfaceId?: string; ref?: string; value?: string };
    if (!p?.surfaceId) throw new Error('surfaceId required');
    if (!p?.ref) throw new Error('ref required');
    await executeOnWebview(
      p.surfaceId,
      `(() => {
        const el = document.querySelector('[data-cmux-ref="${p.ref}"]');
        if (el) {
          el.value = ${JSON.stringify(p.value || '')};
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }
      })()`,
    );
    return { ok: true };
  });

  router.register('browser.press', async (params) => {
    const p = params as { surfaceId?: string; key?: string };
    if (!p?.surfaceId) throw new Error('surfaceId required');
    if (!p?.key) throw new Error('key required');
    await executeOnWebview(
      p.surfaceId,
      `(() => {
        const el = document.activeElement;
        if (el) {
          el.dispatchEvent(new KeyboardEvent('keydown', { key: ${JSON.stringify(p.key)}, bubbles: true }));
          el.dispatchEvent(new KeyboardEvent('keyup', { key: ${JSON.stringify(p.key)}, bubbles: true }));
        }
      })()`,
    );
    return { ok: true };
  });

  router.register('browser.wait', async (params) => {
    const p = params as { surfaceId?: string; selector?: string; timeout?: number };
    if (!p?.surfaceId) throw new Error('surfaceId required');
    if (p.selector) {
      const timeoutMs = p.timeout || 5000;
      await executeOnWebview(
        p.surfaceId,
        `new Promise((resolve, reject) => {
          const el = document.querySelector(${JSON.stringify(p.selector)});
          if (el) { resolve(true); return; }
          const observer = new MutationObserver(() => {
            if (document.querySelector(${JSON.stringify(p.selector)})) {
              observer.disconnect();
              resolve(true);
            }
          });
          observer.observe(document.body, { childList: true, subtree: true });
          setTimeout(() => { observer.disconnect(); reject('Timeout waiting for ' + ${JSON.stringify(p.selector)}); }, ${timeoutMs});
        })`,
        timeoutMs + 2000, // IPC timeout slightly longer than JS timeout
      );
    }
    return { ok: true };
  });
}
