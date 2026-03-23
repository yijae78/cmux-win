#!/usr/bin/env node
'use strict';

const net = require('net');
const path = require('path');

// Key conversion for send-keys
function convertTmuxKeys(keyArgs) {
  return keyArgs.map(arg => {
    if (arg === 'Enter') return '\n';
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

  const port = parseInt(process.env.CMUX_SOCKET_PORT || '19840', 10);
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

  // Simple RPC call (copied pattern from cmux-win CLI socket-client)
  function rpcCall(method, params) {
    return new Promise((resolve, reject) => {
      const socket = new net.Socket();
      socket.setTimeout(5000);
      const token = process.env.CMUX_SOCKET_TOKEN;
      const request = JSON.stringify({
        jsonrpc: '2.0',
        method,
        params: params || {},
        id: 1,
      }) + '\n';

      let data = '';
      socket.connect(port, '127.0.0.1', () => {
        // R2: send auth handshake before request
        if (token) {
          socket.write(JSON.stringify({ jsonrpc: '2.0', method: 'auth.handshake', params: { token }, id: 0 }) + '\n');
        }
        socket.write(request);
      });
      socket.on('data', (chunk) => { data += chunk.toString(); });
      socket.on('end', () => {
        try {
          const parsed = JSON.parse(data.trim());
          if (parsed.error) reject(new Error(parsed.error.message));
          else resolve(parsed.result);
        } catch (e) { reject(e); }
      });
      socket.on('error', (err) => reject(err));
      socket.on('timeout', () => { socket.destroy(); reject(new Error('timeout')); });
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
          const surfaces = await rpcCall('surface.list', {});
          const surface = Array.isArray(surfaces) ? surfaces.find(s => s.id === surfaceId) : null;
          const panelId = surface?.panelId;
          if (!panelId) {
            process.stderr.write('Could not determine active panel\n');
            process.exit(1);
          }
          await rpcCall('panel.split', { panelId, direction, newPanelType: 'terminal' });
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
          if (target.startsWith('%')) {
            const index = parseInt(target.slice(1));
            const panels = await rpcCall('panel.list', {});
            const panel = Array.isArray(panels) ? panels[index] : null;
            if (panel) await rpcCall('panel.focus', { panelId: panel.id });
            else { process.stderr.write(`Pane ${target} not found\n`); process.exit(1); }
          } else {
            await rpcCall('panel.focus', { panelId: target });
          }
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
          let surfaceId = process.env.CMUX_SURFACE_ID;
          if (target) {
            // target을 surface로 해석
            if (target.startsWith('%')) {
              const panels = await rpcCall('panel.list', {});
              const panel = Array.isArray(panels) ? panels[parseInt(target.slice(1))] : null;
              if (panel) surfaceId = panel.activeSurfaceId;
            } else {
              surfaceId = target;
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
          const panels = await rpcCall('panel.list', {});
          if (Array.isArray(panels)) {
            panels.forEach((p, i) => {
              console.log(`%${i}: ${p.panelType} (${p.id})`);
            });
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
          if (target.startsWith('%')) {
            const panels = await rpcCall('panel.list', {});
            const panel = Array.isArray(panels) ? panels[parseInt(target.slice(1))] : null;
            if (panel) await rpcCall('panel.close', { panelId: panel.id });
          } else {
            await rpcCall('panel.close', { panelId: target });
          }
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
          let capSurfaceId = process.env.CMUX_SURFACE_ID;
          if (capTarget) {
            if (capTarget.startsWith('%')) {
              const panels = await rpcCall('panel.list', {});
              const panel = Array.isArray(panels) ? panels[parseInt(capTarget.slice(1))] : null;
              if (panel) capSurfaceId = panel.activeSurfaceId;
            } else {
              capSurfaceId = capTarget;
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
          const pIdx = args.indexOf('-p');
          if (pIdx !== -1 && args[pIdx + 1]) {
            let fmt = args[pIdx + 1];
            fmt = fmt.replace('#{session_id}', process.env.CMUX_WORKSPACE_ID || '');
            fmt = fmt.replace('#{window_id}', process.env.CMUX_WORKSPACE_ID || '');
            fmt = fmt.replace('#{pane_id}', process.env.CMUX_SURFACE_ID || '');
            console.log(fmt);
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
