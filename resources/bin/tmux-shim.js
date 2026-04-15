#!/usr/bin/env node
'use strict';

const net = require('net');
const path = require('path');
const fs = require('fs');
const os = require('os');

// Key conversion for send-keys
// FIX: Enter must be \r (carriage return), NOT \n (line feed).
// \n causes PowerShell to enter >> multiline mode instead of executing.
function convertTmuxKeys(keyArgs) {
  return keyArgs.map(arg => {
    if (arg === 'Enter') return '\r';
    if (arg === 'Space') return ' ';
    if (arg === 'Tab') return '\t';
    if (arg === 'Escape') return '\x1b';
    if (/^C-(.)$/.test(arg)) return String.fromCharCode(arg.charCodeAt(2) - 96);
    return arg;
  }).join('');
}

// Export for testing
if (typeof module !== 'undefined') {
  module.exports = { convertTmuxKeys };
}

// Only run main logic when executed directly (not when required as a module)
if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command) {
    process.stderr.write('Usage: tmux <command> [options]\n');
    process.exit(1);
  }

  // F1: Auto-detect cmux-win connection (token + port) from env or file.
  // Enables tmux-shim to work from ANY terminal (Dispatch, Cursor, standalone).
  function resolveConnection() {
    // 1. Environment variables (cmux-win 내부 PTY — 최우선)
    if (process.env.CMUX_SOCKET_TOKEN && process.env.CMUX_SOCKET_PORT) {
      return {
        token: process.env.CMUX_SOCKET_TOKEN,
        port: parseInt(process.env.CMUX_SOCKET_PORT, 10),
      };
    }

    // 2. Token file fallback (외부 터미널, Dispatch 등)
    const appData = process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming');
    const candidates = [
      path.join(appData, 'Electron', 'socket-token'),   // dev 모드
      path.join(appData, 'cmux-win', 'socket-token'),    // 패키지 모드
    ];
    for (const tokenPath of candidates) {
      try {
        const content = fs.readFileSync(tokenPath, 'utf8');
        const lines = content.split('\n');
        const token = (lines[0] || '').trim();
        const port = lines[1] ? parseInt(lines[1].trim(), 10) : 19840;
        if (token && token.length > 10) {
          return { token, port };
        }
      } catch { /* file not found, try next */ }
    }

    // 3. Env token only (port default)
    const envToken = process.env.CMUX_SOCKET_TOKEN || null;
    return { token: envToken, port: parseInt(process.env.CMUX_SOCKET_PORT || '19840', 10) };
  }

  const conn = resolveConnection();
  const port = conn.port;
  const addr = `tcp://127.0.0.1:${port}`;

  // Parse -t flag
  function getTarget() {
    const tIdx = args.indexOf('-t');
    if (tIdx !== -1 && args[tIdx + 1]) return args[tIdx + 1];
    return null;
  }

  // Parse -s or -n flag for name
  function getName() {
    for (const flag of ['-s', '-n']) {
      const idx = args.indexOf(flag);
      if (idx !== -1 && args[idx + 1]) return args[idx + 1];
    }
    return null;
  }

  // GAP-4: resolve %N pane reference to panel object using stable paneIndex
  async function resolvePane(paneRef) {
    const result = await rpcCall('panel.list', {});
    const panels = result?.panels || (Array.isArray(result) ? result : []);
    if (paneRef.startsWith('%')) {
      const idx = parseInt(paneRef.slice(1));
      return panels.find(p => p.paneIndex === idx) || null;
    }
    // Direct panel ID
    return panels.find(p => p.id === paneRef) || null;
  }

  // F6-FIX: RPC call with proper auth sequencing — wait for auth response
  // before sending the actual request, so auth failures are reported cleanly.
  function rpcCall(method, params) {
    return new Promise((resolve, reject) => {
      const socket = new net.Socket();
      socket.setTimeout(5000);
      const token = conn.token;
      const request = JSON.stringify({
        jsonrpc: '2.0',
        method,
        params: params || {},
        id: 1,
      }) + '\n';

      let data = '';
      let resolved = false;
      let authenticated = !token; // skip auth wait if no token

      socket.connect(port, '127.0.0.1', () => {
        if (token) {
          socket.write(JSON.stringify({ jsonrpc: '2.0', method: 'auth.handshake', params: { token }, id: 0 }) + '\n');
        } else {
          socket.write(request);
        }
      });
      socket.on('data', (chunk) => {
        data += chunk.toString();
        if (resolved) return;
        const lines = data.split('\n');
        // Keep last (possibly partial) line in buffer
        data = lines.pop() || '';
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const parsed = JSON.parse(line);
            // Auth response (id=0): send actual request after successful auth
            if (parsed.id === 0 && !authenticated) {
              if (parsed.error) {
                resolved = true;
                socket.destroy();
                reject(new Error('Auth failed: ' + (parsed.error.message || 'unknown')));
                return;
              }
              authenticated = true;
              socket.write(request);
              continue;
            }
            // Actual RPC response (id=1)
            if (parsed.id === 1) {
              resolved = true;
              socket.destroy();
              if (parsed.error) { reject(new Error(parsed.error.message)); return; }
              resolve(parsed.result);
              return;
            }
          } catch { /* partial line */ }
        }
      });
      socket.on('end', () => {
        if (!resolved) resolve(null);
      });
      socket.on('error', (err) => { if (!resolved) reject(err); });
      socket.on('timeout', () => { socket.destroy(); if (!resolved) reject(new Error('timeout')); });
    });
  }

  async function main() {
    try {
      switch (command) {
        case 'new-session':
        case 'new-window': {
          const name = getName();
          const windowId = process.env.CMUX_WINDOW_ID || '';
          const params = { windowId };
          if (name) params.name = name;
          const result = await rpcCall('workspace.create', params);
          console.log(JSON.stringify(result));
          break;
        }

        case 'split-window': {
          const direction = args.includes('-h') ? 'horizontal' : 'vertical';
          // 현재 surface에서 panel 찾기
          const surfaceId = process.env.CMUX_SURFACE_ID;
          if (!surfaceId) {
            process.stderr.write('CMUX_SURFACE_ID not set\n');
            process.exit(1);
          }
          // surface → panel 매핑은 surface.list로 조회
          const surfResult = await rpcCall('surface.list', {});
          const surfList = surfResult?.surfaces || (Array.isArray(surfResult) ? surfResult : []);
          const surface = surfList.find(s => s.id === surfaceId);
          const panelId = surface?.panelId;
          if (!panelId) {
            process.stderr.write('Could not determine active panel\n');
            process.exit(1);
          }
          const splitResult = await rpcCall('panel.split', { panelId, direction, newPanelType: 'terminal' });

          // F11: Auto-equalize layout after split — all panels get equal size.
          // Without this, nested binary splits cause panels to shrink exponentially.
          try {
            const wsResult = await rpcCall('workspace.list', {});
            const wsList = wsResult?.workspaces || (Array.isArray(wsResult) ? wsResult : []);
            const ws = wsList.find(w => {
              // Find workspace containing the panel we just split
              const json = JSON.stringify(w.panelLayout || {});
              return json.includes(panelId);
            });
            if (ws) {
              const panelResult = await rpcCall('panel.list', {});
              const allPanels = panelResult?.panels || [];
              const wsPanels = allPanels.filter(p => p.workspaceId === ws.id);
              if (wsPanels.length >= 2) {
                const ids = wsPanels.map(p => p.id);
                // Build balanced equal-size layout tree
                function buildEqual(pids) {
                  if (pids.length <= 1) return { type: 'leaf', panelId: pids[0] || '' };
                  if (pids.length === 2) return { type: 'split', direction, ratio: 0.5, children: [{ type: 'leaf', panelId: pids[0] }, { type: 'leaf', panelId: pids[1] }] };
                  const mid = Math.ceil(pids.length / 2);
                  return { type: 'split', direction, ratio: mid / pids.length, children: [buildEqual(pids.slice(0, mid)), buildEqual(pids.slice(mid))] };
                }
                await rpcCall('workspace.set_layout', { workspaceId: ws.id, panelLayout: buildEqual(ids) });
              }
            }
          } catch { /* best effort — equalize is a convenience, not critical */ }

          // Extract shell command from remaining args (after flags like -h, -v, -t, -P, -F)
          // Real tmux: `tmux split-window -h "gemini --flag"` → last non-flag arg is command
          const swFlags = new Set(['-h', '-v', '-d', '-P', '-b', '-f', '-l']);
          const swFlagsWithValue = new Set(['-t', '-F', '-e', '-c', '-l']);
          let shellCmd = null;
          for (let i = 1; i < args.length; i++) {
            if (swFlags.has(args[i])) continue;
            if (swFlagsWithValue.has(args[i])) { i++; continue; } // skip flag + value
            shellCmd = args[i]; // first non-flag arg = shell command
          }

          // GAP-3: output pane_id so Claude Code knows where the new pane is
          const newPaneId = splitResult?.paneIndex !== undefined ? `%${splitResult.paneIndex}` : null;
          if (newPaneId) console.log(newPaneId);

          // If a shell command was provided, send it to the new pane after a brief delay.
          // F10-FIX: PowerShell 5.x doesn't support '&&'. If the command contains '&&',
          // split into separate commands with a delay between them.
          if (shellCmd && splitResult?.surfaceId) {
            const sid = splitResult.surfaceId;
            const parts = shellCmd.includes('&&')
              ? shellCmd.split(/\s*&&\s*/)
              : [shellCmd];
            let delay = 1000;
            for (const part of parts) {
              const d = delay;
              setTimeout(async () => {
                try {
                  await rpcCall('surface.send_text', {
                    surfaceId: sid,
                    text: part.trim() + '\r',
                  });
                } catch { /* best effort */ }
              }, d);
              delay += 2000; // 2s between commands for shell to process
            }
            await new Promise(resolve => setTimeout(resolve, delay + 500));
          }
          break;
        }

        case 'select-window': {
          const target = getTarget();
          if (!target) { process.stderr.write('Usage: tmux select-window -t <id>\n'); process.exit(1); }
          // 숫자면 인덱스로 해석
          if (/^\d+$/.test(target)) {
            const workspaces = await rpcCall('workspace.list', {});
            const ws = Array.isArray(workspaces) ? workspaces[parseInt(target)] : null;
            if (ws) await rpcCall('workspace.select', { workspaceId: ws.id });
            else { process.stderr.write(`Window ${target} not found\n`); process.exit(1); }
          } else {
            await rpcCall('workspace.select', { workspaceId: target });
          }
          break;
        }

        case 'select-pane': {
          const target = getTarget();
          if (!target) { process.stderr.write('Usage: tmux select-pane -t <id>\n'); process.exit(1); }
          const spPanel = await resolvePane(target);
          if (spPanel) await rpcCall('panel.focus', { panelId: spPanel.id });
          else { process.stderr.write(`Pane ${target} not found\n`); process.exit(1); }
          break;
        }

        case 'send-keys': {
          const target = getTarget();
          // 나머지 인자에서 -t와 그 값 제거
          const keyArgs = args.slice(1).filter((a, i, arr) => {
            if (a === '-t') return false;
            if (i > 0 && arr[i - 1] === '-t') return false;
            return true;
          });
          const text = convertTmuxKeys(keyArgs);
          let surfaceId = process.env.CMUX_SURFACE_ID || null;
          if (target) {
            const skPanel = await resolvePane(target);
            if (skPanel) surfaceId = skPanel.activeSurfaceId;
          }
          // F1: surface 자동 선택 (env 없을 때)
          if (!surfaceId && !target) {
            const autoResult = await rpcCall('panel.list', {});
            const autoPanels = autoResult?.panels || [];
            if (autoPanels.length === 1) {
              surfaceId = autoPanels[0].activeSurfaceId;
            } else if (autoPanels.length > 1) {
              process.stderr.write('Multiple panes found. Use -t %%N to specify target.\n');
              process.exit(1);
            }
          }
          if (surfaceId) {
            await rpcCall('surface.send_text', { surfaceId, text });
          }
          break;
        }

        case 'list-windows': {
          const workspaces = await rpcCall('workspace.list', {});
          if (Array.isArray(workspaces)) {
            workspaces.forEach((ws, i) => {
              console.log(`${i}: ${ws.name || 'unnamed'} (${ws.id})`);
            });
          }
          break;
        }

        case 'list-panes': {
          const lpResult = await rpcCall('panel.list', {});
          const lpPanels = lpResult?.panels || (Array.isArray(lpResult) ? lpResult : []);
          for (const p of lpPanels) {
            const idx = p.paneIndex ?? '?';
            console.log(`%${idx}: ${p.panelType} (${p.id}) [surface: ${p.activeSurfaceId}]`);
          }
          break;
        }

        case 'kill-window': {
          const target = getTarget();
          if (!target) { process.stderr.write('Usage: tmux kill-window -t <id>\n'); process.exit(1); }
          if (/^\d+$/.test(target)) {
            const workspaces = await rpcCall('workspace.list', {});
            const ws = Array.isArray(workspaces) ? workspaces[parseInt(target)] : null;
            if (ws) await rpcCall('workspace.close', { workspaceId: ws.id });
          } else {
            await rpcCall('workspace.close', { workspaceId: target });
          }
          break;
        }

        case 'kill-pane': {
          const target = getTarget();
          if (!target) { process.stderr.write('Usage: tmux kill-pane -t <id>\n'); process.exit(1); }
          const kpPanel = await resolvePane(target);
          if (kpPanel) await rpcCall('panel.close', { panelId: kpPanel.id });
          else { process.stderr.write(`Pane ${target} not found\n`); process.exit(1); }
          break;
        }

        case 'resize-pane': {
          const target = getTarget() || process.env.CMUX_SURFACE_ID;
          let direction = 'down';
          let amount = 5;
          if (args.includes('-D')) direction = 'down';
          else if (args.includes('-U')) direction = 'up';
          else if (args.includes('-L')) direction = 'left';
          else if (args.includes('-R')) direction = 'right';
          // Parse amount (number after direction flag)
          const dirIdx = args.findIndex(a => ['-D','-U','-L','-R'].includes(a));
          if (dirIdx !== -1 && args[dirIdx + 1] && /^\d+$/.test(args[dirIdx + 1])) {
            amount = parseInt(args[dirIdx + 1]);
          }
          await rpcCall('panel.resize', { panelId: target, direction, amount });
          break;
        }

        case 'capture-pane': {
          // R6: read terminal scrollback via surface.read RPC
          const capTarget = getTarget();
          let capSurfaceId = process.env.CMUX_SURFACE_ID || null;
          if (capTarget) {
            const cpPanel = await resolvePane(capTarget);
            if (cpPanel) capSurfaceId = cpPanel.activeSurfaceId;
          }
          // F1: surface 자동 선택 (env 없을 때)
          if (!capSurfaceId && !capTarget) {
            const capAutoResult = await rpcCall('panel.list', {});
            const capAutoPanels = capAutoResult?.panels || [];
            if (capAutoPanels.length === 1) {
              capSurfaceId = capAutoPanels[0].activeSurfaceId;
            } else if (capAutoPanels.length > 1) {
              process.stderr.write('Multiple panes found. Use -t %%N to specify target.\n');
              process.exit(1);
            }
          }
          try {
            const result = await rpcCall('surface.read', { surfaceId: capSurfaceId });
            console.log(result?.content ?? '');
          } catch {
            console.log('');
          }
          break;
        }

        case 'display-message': {
          // -p 플래그로 변수 출력
          const dmPrintIdx = args.indexOf('-p');
          if (dmPrintIdx !== -1 && args[dmPrintIdx + 1]) {
            let fmt = args[dmPrintIdx + 1];
            const dmTarget = getTarget();

            // GAP-5: -t 타겟 지원 — 다른 패널의 정보 조회
            let dmPaneId = process.env.CMUX_SURFACE_ID || '';
            let dmPaneIndex = process.env.CMUX_PANE_INDEX || '0';
            let dmWorkspaceId = process.env.CMUX_WORKSPACE_ID || '';

            if (dmTarget) {
              const dmPanel = await resolvePane(dmTarget);
              if (dmPanel) {
                dmPaneId = dmPanel.activeSurfaceId || dmPanel.id;
                dmPaneIndex = String(dmPanel.paneIndex ?? 0);
                dmWorkspaceId = dmPanel.workspaceId || dmWorkspaceId;
              }
            }

            fmt = fmt.replace('#{session_id}', dmWorkspaceId);
            fmt = fmt.replace('#{session_name}', dmWorkspaceId);
            fmt = fmt.replace('#{window_id}', dmWorkspaceId);
            fmt = fmt.replace('#{pane_id}', `%${dmPaneIndex}`);
            fmt = fmt.replace('#{pane_index}', dmPaneIndex);
            fmt = fmt.replace('#{pane_pid}', String(process.pid));
            console.log(fmt);
          }
          break;
        }

        case 'has-session': {
          // GAP-1: check if a workspace/session exists — exit 0 = yes, exit 1 = no
          const hsTarget = getTarget() || getName();
          const workspaces = await rpcCall('workspace.list', {});
          const wsList = workspaces?.workspaces || (Array.isArray(workspaces) ? workspaces : []);
          if (hsTarget) {
            const found = wsList.some(ws => ws.id === hsTarget || ws.name === hsTarget);
            process.exit(found ? 0 : 1);
          } else {
            // No target specified — just check any session exists
            process.exit(wsList.length > 0 ? 0 : 1);
          }
          break;
        }

        case 'last-pane':
        case 'swap-pane':
        case 'break-pane':
          process.stderr.write(`${command}: stub (Phase 5)\n`);
          break;

        default:
          process.stderr.write(`Unknown tmux command: ${command}\n`);
          process.exit(1);
      }
    } catch (err) {
      process.stderr.write(`tmux shim error: ${err.message}\n`);
      process.exit(1);
    }
  }

  main();
}
