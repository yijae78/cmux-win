/**
 * XTermWrapper — React component that hosts an xterm.js terminal and
 * connects it to a PTY instance via the preload bridge.
 *
 * BUG-7:  Import from scoped @xterm packages (not the deprecated 'xterm').
 * BUG-13: Separate useEffect for font changes so the terminal re-fits.
 */
import React from 'react';
import { useRef, useEffect, type FC } from 'react';
import { Terminal } from '@xterm/xterm';
import { WebglAddon } from '@xterm/addon-webgl';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import type { Action } from '../../../shared/actions';
import { parseOsc133P, parseOsc7 } from '../../../shared/osc-parser';

/**
 * Detect CLI type and model from PTY output data.
 * Returns { name, icon } or null if no CLI detected.
 */
function detectCliFromOutput(data: string): { name: string; icon: string } | null {
  // Strip ANSI escape sequences before keyword check — cursor positioning
  // (e.g. \x1b[2;15H) breaks up words like "Claude" into individual characters
  const lower = data.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, '').replace(/\x1b\][^\x07]*\x07/g, '').toLowerCase();

  let baseName = '';
  let icon = '';

  if (lower.includes('claude') &&
      (lower.includes('code') || lower.includes('baked') ||
       lower.includes('musing') || lower.includes('\u256D'))) {
    baseName = 'Claude';
    icon = '\uD83E\uDDE0';
    // Model name from PTY banner: "Opus 4.6 (1M context)" / "Sonnet 4.6 with high effort"
    // Use lastIndexOf with banner-format pattern (e.g. "opus 4.") to avoid
    // false positives from notice text like "Opus now defaults to 1M context".
    // Most recent occurrence wins (current model after /model switch).
    const opusIdx = lower.lastIndexOf('opus 4.');
    const sonnetIdx = lower.lastIndexOf('sonnet 4.');
    const haikuIdx = lower.lastIndexOf('haiku 4.');
    const maxIdx = Math.max(opusIdx, sonnetIdx, haikuIdx);
    if (maxIdx >= 0) {
      if (maxIdx === sonnetIdx) baseName = 'Claude (Sonnet)';
      else if (maxIdx === haikuIdx) baseName = 'Claude (Haiku)';
      else baseName = 'Claude (Opus)';
    }
  } else if (lower.includes('gemini') || lower.includes('google ai')) {
    baseName = 'Gemini';
    icon = '\uD83D\uDC8E';
  } else if (lower.includes('codex') || lower.includes('openai')) {
    baseName = 'Codex';
    icon = '\uD83E\uDD16';
  } else if (lower.includes('chatgpt')) {
    baseName = 'ChatGPT';
    icon = '\uD83D\uDCAC';
  }

  return baseName ? { name: baseName, icon } : null;
}
import { BUNDLED_THEMES } from '../../../shared/bundled-themes';
import { extractScrollback } from '../../../shared/scrollback-utils';

// ---------------------------------------------------------------------------
// Module-level scrollback cache — survives React unmount/remount cycles
// (workspace switches) but not app restarts.
// ---------------------------------------------------------------------------
const scrollbackCache = new Map<string, string>();

// ---------------------------------------------------------------------------
// Global window augmentation for ptyBridge (exposed from preload)
// ---------------------------------------------------------------------------
declare global {
  interface Window {
    ptyBridge?: {
      spawn: (
        surfaceId: string,
        options?: {
          shell?: string;
          cwd?: string;
          cols?: number;
          rows?: number;
          workspaceId?: string;
        },
      ) => Promise<{ id: string; pid: number }>;
      write: (surfaceId: string, data: string) => void;
      resize: (surfaceId: string, cols: number, rows: number) => void;
      kill: (surfaceId: string) => void;
      has: (surfaceId: string) => Promise<boolean>;
      onData: (
        surfaceId: string,
        callback: (data: string) => void,
      ) => { dispose: () => void } | void;
      onExit: (
        surfaceId: string,
        callback: (e: { exitCode: number; signal?: number }) => void,
      ) => { dispose: () => void } | void;
      getAvailableShells: () => Promise<string[]>;
    };
    cmuxScrollback?: {
      saveScrollback(surfaceId: string, content: string): void;
      loadScrollback(surfaceId: string): Promise<string | null>;
    };
  }
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
export interface XTermWrapperProps {
  surfaceId: string;
  workspaceId?: string;
  paneIndex?: number;
  shell?: string;
  cwd?: string;
  fontSize?: number;
  fontFamily?: string;
  cursorStyle?: 'block' | 'underline' | 'bar';
  theme?: Record<string, string>;
  themeName?: string;
  screenReaderMode?: boolean;
  pendingCommand?: string;
  dispatch?: (action: Action) => Promise<{ ok: boolean }>;
  onTitleChange?: (title: string) => void;
  onExit?: (exitCode: number) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
const XTermWrapper: FC<XTermWrapperProps> = ({
  surfaceId,
  workspaceId,
  paneIndex,
  shell,
  cwd,
  fontSize = 14,
  fontFamily = 'Consolas, monospace',
  cursorStyle = 'block',
  theme,
  themeName,
  screenReaderMode = false,
  pendingCommand,
  dispatch,
  onTitleChange,
  onExit,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const ptyIdRef = useRef<string | null>(null);
  const scrollbackIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const dispatchRef = useRef(dispatch);
  dispatchRef.current = dispatch;
  // F2-FIX: track PTY listener disposers to prevent leak on workspace switch
  const ptyListenerDisposersRef = useRef<Array<{ dispose: () => void }>>([]);

  // -----------------------------------------------------------------------
  // Main effect: create terminal + PTY on mount / surfaceId change
  // -----------------------------------------------------------------------
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Resolve theme: explicit theme prop > themeName lookup > undefined
    const resolvedTheme = theme ?? (themeName ? BUNDLED_THEMES[themeName] : undefined);

    // Create xterm.js Terminal
    const terminal = new Terminal({
      fontSize,
      fontFamily,
      cursorStyle,
      theme: resolvedTheme as Record<string, string> | undefined,
      allowProposedApi: true,
      screenReaderMode,
      rightClickSelectsWord: true,
    });
    terminalRef.current = terminal;

    // Copy/Paste: Ctrl+Shift+C/V and right-click copy
    terminal.attachCustomKeyEventHandler((e) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'C') {
        const sel = terminal.getSelection();
        if (sel) navigator.clipboard.writeText(sel);
        return false;
      }
      if (e.ctrlKey && e.shiftKey && e.key === 'V') {
        navigator.clipboard.readText().then((text) => {
          if (text) window.ptyBridge?.write(surfaceId, text);
        });
        return false;
      }
      return true;
    });

    // Right-click → copy selection to clipboard
    containerRef.current?.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      const sel = terminal.getSelection();
      if (sel) {
        navigator.clipboard.writeText(sel);
      }
    });

    // Load FitAddon
    const fitAddon = new FitAddon();
    fitAddonRef.current = fitAddon;
    terminal.loadAddon(fitAddon);

    // Open terminal into DOM
    terminal.open(container);

    // L5: Ctrl+Click link detection — open URLs and file paths
    terminal.registerLinkProvider({
      provideLinks(lineNumber: number, callback: (links: Array<{ range: { start: { x: number; y: number }; end: { x: number; y: number } }; text: string; activate: (e: MouseEvent, text: string) => void }> | undefined) => void) {
        const line = terminal.buffer.active.getLine(lineNumber - 1);
        if (!line) { callback(undefined); return; }
        const text = line.translateToString(true);
        const links: Array<{ range: { start: { x: number; y: number }; end: { x: number; y: number } }; text: string; activate: (e: MouseEvent, text: string) => void }> = [];

        // URL pattern
        const urlRe = /https?:\/\/[^\s)\]>'"]+/g;
        let m;
        while ((m = urlRe.exec(text)) !== null) {
          const sx = m.index;
          links.push({
            range: { start: { x: sx + 1, y: lineNumber }, end: { x: sx + m[0].length, y: lineNumber } },
            text: m[0],
            activate(_e, t) { window.cmuxWin?.openExternal?.(t); },
          });
        }

        // File path pattern: C:\... or /... or ./...
        const fileRe = /(?:[A-Z]:\\|\/|\.\/)[^\s:]+(?::\d+)?/gi;
        while ((m = fileRe.exec(text)) !== null) {
          if (text.slice(m.index).match(/^https?:\/\//)) continue; // skip URLs
          const sx = m.index;
          links.push({
            range: { start: { x: sx + 1, y: lineNumber }, end: { x: sx + m[0].length, y: lineNumber } },
            text: m[0],
            activate(_e, t) { window.cmuxWin?.openPath?.(t); },
          });
        }

        callback(links.length > 0 ? links : undefined);
      },
    });

    // Try loading WebGL addon with contextLoss fallback
    try {
      const webglAddon = new WebglAddon();
      webglAddon.onContextLoss(() => {
        webglAddon.dispose();
      });
      terminal.loadAddon(webglAddon);
    } catch {
      // WebGL not available — fall back to canvas renderer (default)
    }

    // Fit to container and auto-focus
    fitAddon.fit();
    terminal.focus();

    // Spawn PTY via preload bridge
    let disposed = false;

    const initPty = async (): Promise<void> => {
      if (!window.ptyBridge) {
        // Standalone mode — show welcome message
        terminal.writeln('\x1b[36m  cmux-win\x1b[0m — AI Agent Orchestration Terminal');
        terminal.writeln('');
        terminal.writeln('  Running in standalone mode (no Electron).');
        terminal.writeln('  Terminal PTY is available in the full Electron app.');
        terminal.writeln('');
        terminal.writeln('  \x1b[33mFeatures:\x1b[0m');
        terminal.writeln('    Ctrl+D        Split Right');
        terminal.writeln('    Ctrl+Shift+P  Command Palette');
        terminal.writeln('    Ctrl+,        Settings');
        terminal.writeln('    Ctrl+B        Toggle Sidebar');
        terminal.writeln('');
        return;
      }
      try {
        // F2-FIX: dispose any stale PTY listeners from previous mount cycle
        for (const d of ptyListenerDisposersRef.current) d.dispose();
        ptyListenerDisposersRef.current = [];

        // CLI detection state — shared between data handler and OSC handlers
        let cliDetected = false;
        let detectedCliName = '';
        let lastDetectTime = 0;

        // Model change detection: rolling buffer of ANSI-stripped PTY data
        // Detects model switches (e.g. /model sonnet) from the raw PTY stream
        // without relying on viewport reads which have timing issues.
        let modelRollingBuf = '';
        const MODEL_BUF_SIZE = 300;
        const checkModelFromStream = (sid: string, rawData: string) => {
          if (!cliDetected || !detectedCliName?.includes('Claude')) return;
          const stripped = rawData.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, '').replace(/\x1b\][^\x07]*\x07/g, '');
          modelRollingBuf = (modelRollingBuf + stripped).slice(-MODEL_BUF_SIZE);
          const lower = modelRollingBuf.toLowerCase();
          const opusIdx = lower.lastIndexOf('opus 4.');
          const sonnetIdx = lower.lastIndexOf('sonnet 4.');
          const haikuIdx = lower.lastIndexOf('haiku 4.');
          const maxIdx = Math.max(opusIdx, sonnetIdx, haikuIdx);
          if (maxIdx < 0) return;
          let newModel = 'Claude (Opus)';
          if (maxIdx === sonnetIdx) newModel = 'Claude (Sonnet)';
          else if (maxIdx === haikuIdx) newModel = 'Claude (Haiku)';
          const newTitle = `\uD83E\uDDE0 ${newModel}`;
          if (detectedCliName !== newTitle && dispatchRef.current) {
            detectedCliName = newTitle;
            void dispatchRef.current({
              type: 'surface.update_meta',
              payload: { surfaceId: sid, title: newTitle },
            });
          }
        };

        // P2-BUG-5: Reattach to existing PTY if it survived workspace switch
        if (await window.ptyBridge.has(surfaceId)) {
          ptyIdRef.current = surfaceId;

          // Restore scrollback: cache first, file fallback
          const cached = scrollbackCache.get(surfaceId);
          if (cached) {
            terminal.write(cached);
            scrollbackCache.delete(surfaceId);
          } else if (window.cmuxScrollback) {
            const fileContent = await window.cmuxScrollback.loadScrollback(surfaceId);
            if (fileContent) terminal.write(fileContent);
          }

          const dataDisposer = window.ptyBridge.onData(surfaceId, (data) => {
            terminal.write(data);
            // Model change detection from raw PTY stream (bypass viewport timing issues)
            checkModelFromStream(surfaceId, data);
            // CLI detection — read clean text from xterm.js buffer (ANSI-free)
            if (dispatchRef.current) {
              const now = Date.now();
              const cooldown = cliDetected ? 5000 : 2000;
              if (now - lastDetectTime > cooldown) {
                lastDetectTime = now;
                // Read current viewport (visible area) — contains banner + prompt
                const buf = terminal.buffer.active;
                let text = '';
                const viewStart = buf.baseY;
                const viewEnd = viewStart + terminal.rows;
                for (let i = viewStart; i < viewEnd; i++) {
                  const line = buf.getLine(i);
                  if (line) text += line.translateToString(true) + ' ';
                }
                const detected = detectCliFromOutput(text);
                if (detected) {
                  const newTitle = `${detected.icon} ${detected.name}`;
                  if (detectedCliName !== newTitle) {
                    detectedCliName = newTitle;
                    cliDetected = true;
                    void dispatchRef.current({
                      type: 'surface.update_meta',
                      payload: { surfaceId, title: newTitle },
                    });
                  }
                }
              }
            }
          });
          if (dataDisposer) ptyListenerDisposersRef.current.push(dataDisposer);
        } else {
          // Restore scrollback from file before spawning new PTY
          if (window.cmuxScrollback) {
            const fileContent = await window.cmuxScrollback.loadScrollback(surfaceId);
            if (fileContent) terminal.write(fileContent);
          }

          // P2-BUG-7: spawn with surfaceId as first argument
          await window.ptyBridge.spawn(surfaceId, {
            shell,
            cwd,
            cols: terminal.cols,
            rows: terminal.rows,
            workspaceId,
            paneIndex,
          });
          if (disposed) {
            window.ptyBridge.kill(surfaceId);
            return;
          }
          ptyIdRef.current = surfaceId;

          // Wire data: PTY → terminal
          const dataDisposer2 = window.ptyBridge.onData(surfaceId, (data) => {
            terminal.write(data);
            // Model change detection from raw PTY stream (bypass viewport timing issues)
            checkModelFromStream(surfaceId, data);
            // CLI detection — read clean text from xterm.js buffer (ANSI-free)
            if (dispatchRef.current) {
              const now = Date.now();
              const cooldown = cliDetected ? 5000 : 2000;
              if (now - lastDetectTime > cooldown) {
                lastDetectTime = now;
                // Read current viewport (visible area) — contains banner + prompt
                const buf = terminal.buffer.active;
                let text = '';
                const viewStart = buf.baseY;
                const viewEnd = viewStart + terminal.rows;
                for (let i = viewStart; i < viewEnd; i++) {
                  const line = buf.getLine(i);
                  if (line) text += line.translateToString(true) + ' ';
                }
                const detected = detectCliFromOutput(text);
                if (detected) {
                  const newTitle = `${detected.icon} ${detected.name}`;
                  if (detectedCliName !== newTitle) {
                    detectedCliName = newTitle;
                    cliDetected = true;
                    void dispatchRef.current({
                      type: 'surface.update_meta',
                      payload: { surfaceId, title: newTitle },
                    });
                  }
                }
              }
            }
          });
          if (dataDisposer2) ptyListenerDisposersRef.current.push(dataDisposer2);

          // Wire exit
          const exitDisposer = window.ptyBridge.onExit(surfaceId, (e) => {
            onExit?.(e.exitCode);
          });
          if (exitDisposer) ptyListenerDisposersRef.current.push(exitDisposer);

          // F20: pendingCommand는 별도 useEffect(R4)에서 처리
        }

        // Wire data: terminal → PTY (surfaceId-based)
        terminal.onData((data) => {
          window.ptyBridge?.write(surfaceId, data);
        });

        // Wire resize: terminal → PTY (surfaceId-based)
        terminal.onResize(({ cols, rows }) => {
          window.ptyBridge?.resize(surfaceId, cols, rows);
        });

        // OSC 133 prompt detection (git branch metadata)
        terminal.parser.registerOscHandler(133, (data) => {
          const meta = parseOsc133P(data);
          if (meta.gitBranch !== undefined && dispatchRef.current) {
            void dispatchRef.current({
              type: 'surface.update_meta',
              payload: {
                surfaceId,
                terminal: { gitBranch: meta.gitBranch, gitDirty: meta.gitDirty },
              },
            });
          }
          return true;
        });

        // OSC 7 current working directory detection
        terminal.parser.registerOscHandler(7, (data) => {
          const parsedCwd = parseOsc7(data);
          if (parsedCwd && dispatchRef.current) {
            void dispatchRef.current({
              type: 'surface.update_meta',
              payload: { surfaceId, terminal: { cwd: parsedCwd } },
            });
          }
          return true;
        });

        // OSC 0/2: Set terminal title (used by shells and CLI tools)
        // Once a CLI is detected, keep the CLI name as sticky title —
        // don't let shell path overwrites hide which AI is running.
        const handleTitleOsc = (data: string) => {
          if (data && dispatchRef.current) {
            if (cliDetected) {
              // CLI detected: keep sticky name, ignore shell path titles
              return true;
            }
            void dispatchRef.current({
              type: 'surface.update_meta',
              payload: { surfaceId, title: data },
            });
          }
          return true;
        };
        terminal.parser.registerOscHandler(0, handleTitleOsc);
        terminal.parser.registerOscHandler(2, handleTitleOsc);

        // OSC 9: iTerm2 notification — data is the notification text
        terminal.parser.registerOscHandler(9, (data) => {
          if (dispatchRef.current) {
            void dispatchRef.current({
              type: 'notification.create',
              payload: { title: 'Terminal', body: data, surfaceId },
            });
          }
          return true;
        });

        // OSC 99: custom notification — data format: "title;body"
        terminal.parser.registerOscHandler(99, (data) => {
          const semicolonIdx = data.indexOf(';');
          const title = semicolonIdx >= 0 ? data.substring(0, semicolonIdx) : 'Terminal';
          const body = semicolonIdx >= 0 ? data.substring(semicolonIdx + 1) : data;
          if (dispatchRef.current) {
            void dispatchRef.current({
              type: 'notification.create',
              payload: { title, body, surfaceId },
            });
          }
          return true;
        });

        // OSC 777: rxvt notification — data format: "notify;title;body"
        terminal.parser.registerOscHandler(777, (data) => {
          const parts = data.split(';');
          if (parts[0] === 'notify' && parts.length >= 3) {
            if (dispatchRef.current) {
              void dispatchRef.current({
                type: 'notification.create',
                payload: { title: parts[1], body: parts.slice(2).join(';'), surfaceId },
              });
            }
          }
          return true;
        });
      } catch (err) {
        console.error('[XTermWrapper] Failed to spawn PTY:', err);
      }
    };

    void initPty();

    // Periodic scrollback save (30s, staggered per surface)
    const staggerMs = (surfaceId.charCodeAt(0) % 10) * 1000;
    const scrollbackTimer = setTimeout(() => {
      scrollbackIntervalRef.current = setInterval(() => {
        const t = terminalRef.current;
        if (!t || !window.cmuxScrollback) return;
        const buffer = t.buffer.active;
        const lines: string[] = [];
        const start = Math.max(0, buffer.length - 10000);
        for (let i = start; i < buffer.length; i++) {
          const line = buffer.getLine(i);
          if (line) lines.push(line.translateToString(true));
        }
        const content = lines.join('\n');
        if (content.length > 0 && content.length <= 1_000_000) {
          window.cmuxScrollback.saveScrollback(surfaceId, content);
        }
      }, 30_000);
    }, staggerMs);

    // Title change
    const titleDisposable = terminal.onTitleChange((title) => {
      onTitleChange?.(title);
    });

    // L3: Single debounced ResizeObserver — 200ms covers both immediate and final sizing
    let resizeTimer: ReturnType<typeof setTimeout> | null = null;
    const doFit = () => {
      if (!disposed && fitAddonRef.current && terminalRef.current) {
        try {
          fitAddonRef.current.fit();
          const t = terminalRef.current;
          window.ptyBridge?.resize(surfaceId, t.cols, t.rows);
        } catch { /* terminal may be disposed */ }
      }
    };
    const resizeObserver = new ResizeObserver(() => {
      if (resizeTimer) clearTimeout(resizeTimer);
      resizeTimer = setTimeout(doFit, 200);
    });
    resizeObserver.observe(container);

    // Cleanup — P2-BUG-5: Do NOT kill PTY on unmount (survives workspace switch)
    // PTY is only killed via surface.close Action
    return () => {
      disposed = true;
      resizeObserver.disconnect();
      if (resizeTimer) clearTimeout(resizeTimer);
      titleDisposable.dispose();
      clearTimeout(scrollbackTimer);
      if (scrollbackIntervalRef.current) clearInterval(scrollbackIntervalRef.current);
      ptyIdRef.current = null;

      // F2-FIX: dispose PTY data/exit listeners to prevent leak across workspace switches
      for (const d of ptyListenerDisposersRef.current) d.dispose();
      ptyListenerDisposersRef.current = [];

      // Save scrollback before disposing terminal so content survives workspace switch
      const scrollback = extractScrollback(terminal.buffer.active);
      if (scrollback.length > 0) {
        scrollbackCache.set(surfaceId, scrollback);
      }

      terminal.dispose();
      terminalRef.current = null;
      fitAddonRef.current = null;
    };
  }, [surfaceId]); // intentionally only re-run on surfaceId change

  // -----------------------------------------------------------------------
  // R4: Separate effect for pendingCommand — react to surface.update_meta
  // Wait for PTY to be ready (ptyIdRef) before writing.
  // BUG-A fix: cleanup all timers on unmount / re-run.
  // BUG-B fix: adaptive delay based on shell type.
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!pendingCommand || !terminalRef.current) return;

    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const schedule = (fn: () => void, ms: number) => {
      const id = setTimeout(() => { if (!cancelled) fn(); }, ms);
      timers.push(id);
    };

    // Adaptive shell init delay: PowerShell is slow (~2-3s), others are fast
    const isPowerShell = shell
      ? /powershell|pwsh/i.test(shell)
      : true; // default to conservative if unknown
    const shellInitDelay = isPowerShell ? 1500 : 500;

    // Split on __DELAY__ marker for sequential command execution (e.g., cd + claude)
    const commandParts = pendingCommand.split('__DELAY__');

    let attempts = 0;
    const maxAttempts = 30; // 300ms × 30 = 9s max wait for PTY
    const tryWrite = () => {
      if (cancelled) return;
      if (ptyIdRef.current) {
        // Write first part after shell init delay
        schedule(() => {
          window.ptyBridge?.write(surfaceId, commandParts[0]);
        }, shellInitDelay);
        // Write subsequent parts with additional delays (1s each)
        for (let i = 1; i < commandParts.length; i++) {
          const part = commandParts[i];
          schedule(() => {
            window.ptyBridge?.write(surfaceId, part);
          }, shellInitDelay + i * 1500);
        }
        // Clear pendingCommand after all parts are sent
        schedule(() => {
          void dispatchRef.current?.({
            type: 'surface.update_meta',
            payload: { surfaceId, pendingCommand: null },
          });
        }, shellInitDelay + commandParts.length * 1500);
      } else if (++attempts < maxAttempts) {
        schedule(tryWrite, 300);
      }
    };
    tryWrite();

    return () => {
      cancelled = true;
      for (const id of timers) clearTimeout(id);
    };
  }, [pendingCommand, surfaceId, shell]);

  // -----------------------------------------------------------------------
  // BUG-13: Separate effect for font / style changes — update + refit
  // -----------------------------------------------------------------------
  useEffect(() => {
    const terminal = terminalRef.current;
    const fitAddon = fitAddonRef.current;
    if (!terminal || !fitAddon) return;

    terminal.options.fontSize = fontSize;
    terminal.options.fontFamily = fontFamily;
    terminal.options.cursorStyle = cursorStyle;

    // Theme live switching
    if (theme) {
      terminal.options.theme = theme;
    } else if (themeName) {
      const t = BUNDLED_THEMES[themeName];
      if (t) terminal.options.theme = t;
    }

    fitAddon.fit();
  }, [fontSize, fontFamily, cursorStyle, theme, themeName]);

  return (
    <div
      ref={containerRef}
      data-surface-id={surfaceId}
      role="application"
      aria-label="Terminal"
      style={{ width: '100%', height: '100%', overflow: 'hidden', background: '#272822' }}
      onClick={() => terminalRef.current?.focus()}
      onFocus={() => terminalRef.current?.focus()}
    />
  );
};

export default XTermWrapper;
