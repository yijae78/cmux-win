import { describe, it, expect, afterEach } from 'vitest';
import net from 'node:net';
import { parseSocketAddr, rpcCall } from '../../../src/cli/socket-client';

describe('parseSocketAddr', () => {
  it('parses tcp://127.0.0.1:19840', () => {
    const result = parseSocketAddr('tcp://127.0.0.1:19840');
    expect(result).toEqual({ host: '127.0.0.1', port: 19840 });
  });

  it('parses address without tcp:// prefix', () => {
    const result = parseSocketAddr('127.0.0.1:8080');
    expect(result).toEqual({ host: '127.0.0.1', port: 8080 });
  });

  it('parses tcp://localhost:3000', () => {
    const result = parseSocketAddr('tcp://localhost:3000');
    expect(result).toEqual({ host: 'localhost', port: 3000 });
  });

  it('uses defaults for empty string', () => {
    const result = parseSocketAddr('');
    expect(result).toEqual({ host: '127.0.0.1', port: 19840 });
  });
});

describe('rpcCall', () => {
  let server: net.Server | null = null;

  afterEach(async () => {
    if (server) {
      await new Promise<void>((resolve) => {
        server!.close(() => resolve());
      });
      server = null;
    }
  });

  function startMockServer(
    handler: (request: Record<string, unknown>) => Record<string, unknown>,
  ): Promise<number> {
    return new Promise((resolve) => {
      server = net.createServer((socket) => {
        let buffer = '';
        socket.on('data', (data) => {
          buffer += data.toString();
          if (buffer.includes('\n')) {
            const request = JSON.parse(buffer.trim());
            const response = handler(request);
            socket.write(JSON.stringify(response) + '\n');
          }
        });
      });
      server!.listen(0, '127.0.0.1', () => {
        const addr = server!.address() as net.AddressInfo;
        resolve(addr.port);
      });
    });
  }

  it('sends RPC request and receives successful result', async () => {
    const port = await startMockServer((request) => {
      return {
        jsonrpc: '2.0',
        id: request.id,
        result: { echo: request.method },
      };
    });

    const result = await rpcCall('test.method', undefined, `tcp://127.0.0.1:${port}`);
    expect(result).toEqual({ echo: 'test.method' });
  });

  it('sends params in RPC request', async () => {
    const port = await startMockServer((request) => {
      return {
        jsonrpc: '2.0',
        id: request.id,
        result: { received: request.params },
      };
    });

    const result = await rpcCall('test.params', { key: 'value' }, `tcp://127.0.0.1:${port}`);
    expect(result).toEqual({ received: { key: 'value' } });
  });

  it('rejects with error when server returns JSON-RPC error', async () => {
    const port = await startMockServer((request) => {
      return {
        jsonrpc: '2.0',
        id: request.id,
        error: { code: -32601, message: 'Method not found: bad.method' },
      };
    });

    await expect(rpcCall('bad.method', undefined, `tcp://127.0.0.1:${port}`)).rejects.toThrow(
      '[-32601] Method not found: bad.method',
    );
  });

  it('rejects when connection fails', async () => {
    // Use a port that nothing is listening on
    await expect(rpcCall('test', undefined, 'tcp://127.0.0.1:19999')).rejects.toThrow(
      'Socket connection failed',
    );
  });
});
