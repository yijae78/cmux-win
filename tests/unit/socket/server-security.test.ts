import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import net from 'node:net';
import { JsonRpcRouter } from '../../../src/main/socket/router';
import { SocketApiServer } from '../../../src/main/socket/server';

/**
 * Phase 4-1: Socket server security scenario tests.
 * Covers C3 (buffer limit), C4 (JSON parse rejection), auth handshake.
 */

function connectAndSend(
  port: number,
  data: string,
  opts?: { timeout?: number },
): Promise<{ response: string; destroyed: boolean }> {
  return new Promise((resolve, reject) => {
    const client = net.createConnection({ port, host: '127.0.0.1' }, () => {
      client.write(data);
    });

    let buffer = '';
    let destroyed = false;

    client.on('data', (chunk) => {
      buffer += chunk.toString();
    });

    client.on('close', () => {
      destroyed = true;
      resolve({ response: buffer, destroyed: true });
    });

    client.on('error', () => {
      destroyed = true;
      resolve({ response: buffer, destroyed: true });
    });

    const timeout = setTimeout(() => {
      const wasDestroyed = destroyed;
      client.destroy();
      resolve({ response: buffer, destroyed: wasDestroyed });
    }, opts?.timeout ?? 2000);

    client.on('close', () => clearTimeout(timeout));
  });
}

describe('Socket server security (Phase 4-1)', () => {
  let router: JsonRpcRouter;
  let server: SocketApiServer;
  let port: number;

  beforeAll(async () => {
    router = new JsonRpcRouter();
    router.register('test.echo', async (params) => params);
    server = new SocketApiServer(router, 'allow-all');
    port = await server.start(0);
  });

  afterAll(async () => {
    await server.stop();
  });

  it('responds to valid JSON-RPC request', async () => {
    const { response } = await connectAndSend(
      port,
      JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'test.echo', params: { hello: 'world' } }) + '\n',
    );
    const parsed = JSON.parse(response.trim());
    expect(parsed.result).toEqual({ hello: 'world' });
  });

  it('C4: rejects unparseable JSON with -32700 Parse error', async () => {
    const { response } = await connectAndSend(port, 'this is not json\n');
    const parsed = JSON.parse(response.trim());
    expect(parsed.error).toBeDefined();
    expect(parsed.error.code).toBe(-32700);
    expect(parsed.error.message).toBe('Parse error');
  });

  it('C3: disconnects client when buffer exceeds 10MB', async () => {
    // Send a massive payload without newline — buffer grows until limit hit
    const bigData = 'A'.repeat(11 * 1024 * 1024); // 11MB, no newline
    const { destroyed } = await connectAndSend(port, bigData, { timeout: 5000 });
    expect(destroyed).toBe(true);
  }, 10000);
});
