import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import net from 'node:net';
import { JsonRpcRouter } from '../../../src/main/socket/router';
import { SocketApiServer } from '../../../src/main/socket/server';
import { AppStateStore } from '../../../src/main/sot/store';
import { registerSystemHandlers } from '../../../src/main/socket/handlers/system';
import { registerWindowHandlers } from '../../../src/main/socket/handlers/window';
import { registerWorkspaceHandlers } from '../../../src/main/socket/handlers/workspace';
import { registerPanelHandlers } from '../../../src/main/socket/handlers/panel';
import { registerSurfaceHandlers } from '../../../src/main/socket/handlers/surface';
import { registerAgentHandlers } from '../../../src/main/socket/handlers/agent';
import { registerNotificationHandlers } from '../../../src/main/socket/handlers/notification';
import { registerSettingsHandlers } from '../../../src/main/socket/handlers/settings';

/**
 * Send a JSON-RPC 2.0 request over TCP and return the parsed response.
 */
function sendRpc(
  port: number,
  method: string,
  params?: unknown,
  id: number | string = 1,
): Promise<{ jsonrpc: string; id: unknown; result?: unknown; error?: { code: number; message: string } }> {
  return new Promise((resolve, reject) => {
    const client = net.createConnection({ port, host: '127.0.0.1' }, () => {
      const request = JSON.stringify({ jsonrpc: '2.0', method, params, id });
      client.write(request + '\n');
    });

    let buffer = '';
    client.on('data', (data) => {
      buffer += data.toString();
      const newlineIdx = buffer.indexOf('\n');
      if (newlineIdx !== -1) {
        const line = buffer.substring(0, newlineIdx).trim();
        client.destroy();
        try {
          resolve(JSON.parse(line));
        } catch (err) {
          reject(new Error(`Failed to parse response: ${line}`));
        }
      }
    });

    client.on('error', reject);

    // Timeout after 5 seconds
    const timeout = setTimeout(() => {
      client.destroy();
      reject(new Error('Timeout waiting for response'));
    }, 5000);

    client.on('close', () => {
      clearTimeout(timeout);
    });
  });
}

describe('SocketApiServer integration', () => {
  let store: AppStateStore;
  let router: JsonRpcRouter;
  let server: SocketApiServer;
  let port: number;

  beforeAll(async () => {
    store = new AppStateStore();
    router = new JsonRpcRouter();

    // Register all handlers
    registerSystemHandlers(router, store);
    registerWindowHandlers(router, store);
    registerWorkspaceHandlers(router, store);
    registerPanelHandlers(router, store);
    registerSurfaceHandlers(router, store);
    registerAgentHandlers(router, store);
    registerNotificationHandlers(router, store);
    registerSettingsHandlers(router, store);

    // Start on port 0 to let OS assign a free port
    port = await server_start();
  });

  async function server_start(): Promise<number> {
    // R2: use allow-all auth mode in tests (no handshake needed)
    server = new SocketApiServer(router, 'allow-all');
    return server.start(0);
  }

  afterAll(async () => {
    await server.stop();
  });

  // BUG-3: verify port > 0 returned
  it('returns actual bound port > 0 (BUG-3)', () => {
    expect(port).toBeGreaterThan(0);
    expect(server.getPort()).toBe(port);
  });

  it('system.ping returns pong', async () => {
    const resp = await sendRpc(port, 'system.ping');
    expect(resp.jsonrpc).toBe('2.0');
    expect(resp.result).toBeDefined();
    expect((resp.result as { pong: boolean }).pong).toBe(true);
  });

  it('workspace.create then workspace.list returns created workspace', async () => {
    // First create a window to attach workspace to
    const winResp = await sendRpc(port, 'window.create', {}, 10);
    expect(winResp.result).toBeDefined();
    const windowId = (winResp.result as { window: { id: string } }).window.id;

    // Create workspace
    const createResp = await sendRpc(port, 'workspace.create', {
      windowId,
      name: 'Test WS',
    }, 11);
    expect(createResp.result).toBeDefined();
    const wsName = (createResp.result as { workspace: { name: string } }).workspace.name;
    expect(wsName).toBe('Test WS');

    // List workspaces
    const listResp = await sendRpc(port, 'workspace.list', {}, 12);
    expect(listResp.result).toBeDefined();
    const workspaces = (listResp.result as { workspaces: { name: string }[] }).workspaces;
    expect(workspaces.some((ws) => ws.name === 'Test WS')).toBe(true);
  });

  it('notification.create then notification.list returns notification', async () => {
    const createResp = await sendRpc(port, 'notification.create', {
      title: 'Test Notification',
      body: 'Hello world',
    }, 20);
    expect(createResp.result).toBeDefined();

    const listResp = await sendRpc(port, 'notification.list', {}, 21);
    expect(listResp.result).toBeDefined();
    const notifications = (listResp.result as { notifications: { title: string }[] }).notifications;
    expect(notifications.some((n) => n.title === 'Test Notification')).toBe(true);
  });

  it('unknown method returns error -32601', async () => {
    const resp = await sendRpc(port, 'nonexistent.method', {}, 30);
    expect(resp.error).toBeDefined();
    expect(resp.error!.code).toBe(-32601);
    expect(resp.error!.message).toContain('Method not found');
  });

  it('system.identify returns app info', async () => {
    const resp = await sendRpc(port, 'system.identify', {}, 40);
    expect(resp.result).toBeDefined();
    const result = resp.result as { name: string; platform: string };
    expect(result.name).toBe('cmux-win');
    expect(result.platform).toBe('win32');
  });

  it('system.capabilities returns registered methods', async () => {
    const resp = await sendRpc(port, 'system.capabilities', {}, 50);
    expect(resp.result).toBeDefined();
    const methods = (resp.result as { methods: string[] }).methods;
    expect(methods).toContain('system.ping');
    expect(methods).toContain('workspace.list');
    expect(methods).toContain('notification.create');
    expect(methods).toContain('settings.get');
  });
});
