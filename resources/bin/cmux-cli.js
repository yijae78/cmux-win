#!/usr/bin/env node
'use strict';

/**
 * cmux-cli.js — Universal CLI tool for cmux-win socket API.
 * Any AI agent or script can use this to control the app.
 *
 * Usage:
 *   cmux ping
 *   cmux tree
 *   cmux identify [--surface <id>]
 *   cmux health <surfaceId>
 *   cmux panels
 *   cmux surfaces
 *   cmux send <surfaceId> <text>
 *   cmux split <panelId> [--direction horizontal|vertical] [--type terminal|browser] [--url <url>]
 *   cmux workspaces
 *   cmux rpc <method> [json-params]
 */

const net = require('net');

const port = parseInt(process.env.CMUX_SOCKET_PORT || '19840', 10);
const token = process.env.CMUX_SOCKET_TOKEN;

function rpcCall(method, params) {
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

async function main() {
  const args = process.argv.slice(2);
  const cmd = args[0];

  if (!cmd) {
    console.log('Usage: cmux <command> [args]');
    console.log('Commands: ping, tree, identify, health, panels, surfaces, send, split, workspaces, rpc');
    process.exit(0);
  }

  try {
    switch (cmd) {
      case 'ping': {
        const r = await rpcCall('system.ping', {});
        console.log(JSON.stringify(r, null, 2));
        break;
      }
      case 'tree': {
        const r = await rpcCall('system.tree', {});
        console.log(JSON.stringify(r, null, 2));
        break;
      }
      case 'identify': {
        const surfaceId = args.indexOf('--surface') !== -1 ? args[args.indexOf('--surface') + 1] : undefined;
        const r = await rpcCall('system.identify', surfaceId ? { surfaceId } : {});
        console.log(JSON.stringify(r, null, 2));
        break;
      }
      case 'health': {
        if (!args[1]) { console.error('Usage: cmux health <surfaceId>'); process.exit(1); }
        const r = await rpcCall('surface.health', { surfaceId: args[1] });
        console.log(JSON.stringify(r, null, 2));
        break;
      }
      case 'panels': {
        const r = await rpcCall('panel.list', {});
        console.log(JSON.stringify(r, null, 2));
        break;
      }
      case 'surfaces': {
        const r = await rpcCall('surface.list', {});
        console.log(JSON.stringify(r, null, 2));
        break;
      }
      case 'workspaces': {
        const r = await rpcCall('workspace.list', {});
        console.log(JSON.stringify(r, null, 2));
        break;
      }
      case 'send': {
        if (!args[1] || !args[2]) { console.error('Usage: cmux send <surfaceId> <text>'); process.exit(1); }
        const r = await rpcCall('surface.send_text', { surfaceId: args[1], text: args.slice(2).join(' ') });
        console.log(JSON.stringify(r));
        break;
      }
      case 'split': {
        if (!args[1]) { console.error('Usage: cmux split <panelId> [--direction h|v] [--type terminal|browser] [--url <url>]'); process.exit(1); }
        const params = { panelId: args[1], direction: 'horizontal', newPanelType: 'terminal' };
        const dirIdx = args.indexOf('--direction');
        if (dirIdx !== -1) params.direction = args[dirIdx + 1] === 'v' ? 'vertical' : 'horizontal';
        const typeIdx = args.indexOf('--type');
        if (typeIdx !== -1) params.newPanelType = args[typeIdx + 1];
        const urlIdx = args.indexOf('--url');
        if (urlIdx !== -1) params.url = args[urlIdx + 1];
        const r = await rpcCall('panel.split', params);
        console.log(JSON.stringify(r, null, 2));
        break;
      }
      case 'rpc': {
        if (!args[1]) { console.error('Usage: cmux rpc <method> [json-params]'); process.exit(1); }
        const params = args[2] ? JSON.parse(args[2]) : {};
        const r = await rpcCall(args[1], params);
        console.log(JSON.stringify(r, null, 2));
        break;
      }
      default:
        console.error(`Unknown command: ${cmd}`);
        process.exit(1);
    }
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
}

if (require.main === module) main();
module.exports = { rpcCall };
