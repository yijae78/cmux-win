#!/usr/bin/env node
'use strict';

/**
 * master — Relay messages to the Master panel in cmux-win.
 *
 * Usage:
 *   master "보고 내용"              # Send message to master
 *   master --read                   # Read master's screen
 *   echo "long report" | master     # Pipe content to master
 *
 * Finds the Master panel automatically via surface.list (label === "Master").
 * Falls back to paneIndex 0 if no label found.
 */

const net = require('net');
const fs = require('fs');
const path = require('path');

const port = parseInt(process.env.CMUX_SOCKET_PORT || '19840', 10);

function getToken() {
  if (process.env.CMUX_SOCKET_TOKEN) return process.env.CMUX_SOCKET_TOKEN;
  const tokenPaths = [
    path.join(process.env.APPDATA || '', 'Electron', 'socket-token'),
    path.join(process.env.APPDATA || '', 'cmux-win', 'socket-token'),
  ];
  for (const p of tokenPaths) {
    try {
      return fs.readFileSync(p, 'utf8').split('\n')[0].trim();
    } catch { /* try next */ }
  }
  return null;
}

function rpcCall(method, params) {
  const token = getToken();
  return new Promise((resolve, reject) => {
    const socket = new net.Socket();
    socket.setTimeout(5000);
    const request = JSON.stringify({ jsonrpc: '2.0', method, params: params || {}, id: 1 }) + '\n';

    let data = '';
    let resolved = false;
    let authenticated = !token;

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
      data = lines.pop() || '';
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const parsed = JSON.parse(line);
          if (parsed.id === 0 && !authenticated) {
            if (parsed.error) { resolved = true; socket.destroy(); reject(new Error('Auth failed')); return; }
            authenticated = true;
            socket.write(request);
            continue;
          }
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
    socket.on('end', () => { if (!resolved) resolve(null); });
    socket.on('error', (err) => { if (!resolved) reject(err); });
    socket.on('timeout', () => { socket.destroy(); if (!resolved) reject(new Error('timeout')); });
  });
}

async function findMasterSurface() {
  const result = await rpcCall('surface.list', {});
  if (!result?.surfaces) throw new Error('No surfaces found');

  // 1) label === 'Master'
  const byLabel = result.surfaces.find(s => s.label === 'Master');
  if (byLabel) return byLabel.id;

  // 2) fallback: first terminal surface (paneIndex 0)
  const panels = await rpcCall('panel.list', {});
  if (panels?.panels) {
    const firstPanel = panels.panels.find(p => p.paneIndex === 0);
    if (firstPanel?.activeSurfaceId) return firstPanel.activeSurfaceId;
  }

  // 3) last fallback: first terminal surface
  const terminal = result.surfaces.find(s => s.surfaceType === 'terminal');
  if (terminal) return terminal.id;

  throw new Error('Master panel not found');
}

async function main() {
  const args = process.argv.slice(2);

  // --read: read master's screen
  if (args[0] === '--read') {
    const masterSid = await findMasterSurface();
    const lines = args[1] ? parseInt(args[1]) : 30;
    const result = await rpcCall('surface.read', { surfaceId: masterSid, lines });
    console.log(result?.content || '(empty)');
    return;
  }

  // Get message from args or stdin
  let message;
  if (args.length > 0) {
    message = args.join(' ');
  } else {
    // Read from stdin (pipe)
    const chunks = [];
    process.stdin.setEncoding('utf8');
    for await (const chunk of process.stdin) {
      chunks.push(chunk);
    }
    message = chunks.join('').trim();
  }

  if (!message) {
    console.error('Usage: master "message to send to master"');
    console.error('       master --read [lines]');
    console.error('       echo "content" | master');
    process.exit(1);
  }

  const masterSid = await findMasterSurface();

  // Send message with newline (Enter)
  await rpcCall('surface.send_text', {
    surfaceId: masterSid,
    text: message + '\r',
  });

  console.log(`✓ Sent to Master (${masterSid.slice(0, 8)}...)`);
}

main().catch(err => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});
