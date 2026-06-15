/**
 * TCP Socket API server for cmux.
 *
 * Handles newline-delimited JSON-RPC 2.0 over TCP.
 * BUG-3 FIX: listen() returns the ACTUAL bound port from server.address().
 */

import net from 'node:net';
import { JsonRpcRouter } from './router';
import { SocketAuth, type AuthMode } from './auth';
import { MAX_SOCKET_PORT_RETRIES } from '../../shared/constants';

export class SocketApiServer {
  private server: net.Server | null = null;
  private router: JsonRpcRouter;
  private auth: SocketAuth;
  private boundPort = 0;

  constructor(router: JsonRpcRouter, authMode: AuthMode = 'cmux-only') {
    this.router = router;
    this.auth = new SocketAuth(authMode);
    // R2: expose token via process.env so child processes (CLI/shims) inherit it
    process.env.CMUX_SOCKET_TOKEN = this.auth.getToken();
  }

  /** Get the auth token for child process injection. */
  getAuthToken(): string {
    return this.auth.getToken();
  }

  /**
   * Start the server, trying ports starting from `startPort`.
   * Returns the actual port bound (BUG-3 fix).
   */
  async start(startPort: number): Promise<number> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < MAX_SOCKET_PORT_RETRIES; attempt++) {
      try {
        const port = await this.listen(startPort + attempt);
        return port;
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
      }
    }

    throw lastError ?? new Error('Failed to start socket server');
  }

  /**
   * Attempt to listen on a specific port.
   * BUG-3 FIX: Returns the ACTUAL bound port from server.address().
   */
  private listen(port: number): Promise<number> {
    return new Promise((resolve, reject) => {
      const server = net.createServer((socket) => {
        this.handleConnection(socket);
      });

      server.on('error', (err) => {
        reject(err);
      });

      server.listen(port, '127.0.0.1', () => {
        const addr = server.address() as net.AddressInfo;
        this.server = server;
        this.boundPort = addr.port;
        resolve(addr.port);
      });
    });
  }

  /**
   * Handle an individual TCP connection.
   * Protocol: newline-delimited JSON-RPC 2.0.
   * R2: First message must authenticate (unless auth mode is allow-all).
   */
  private handleConnection(socket: net.Socket): void {
    // #2: TCP keepalive — 30초마다 probe, 죽은 연결 빠르게 감지
    socket.setKeepAlive(true, 30_000);

    let buffer = '';
    let authenticated = false;
    const socketRef = socket; // stable ref for WeakSet

    socket.on('data', (data) => {
      buffer += data.toString();

      // C3: Prevent OOM from oversized buffer (max 10 MB)
      if (buffer.length > 10 * 1024 * 1024) {
        console.error('[socket] Buffer exceeded 10 MB limit — disconnecting client');
        socket.destroy();
        return;
      }

      // Process all complete lines (newline-delimited)
      let newlineIdx = buffer.indexOf('\n');
      while (newlineIdx !== -1) {
        const line = buffer.substring(0, newlineIdx).trim();
        buffer = buffer.substring(newlineIdx + 1);

        if (line.length > 0) {
          // R2: authenticate on first message
          if (!authenticated) {
            const authResult = this.auth.authenticate(socketRef, line);
            if (authResult.allowed) {
              authenticated = true;
              // If the first message was a pure auth handshake, ack and continue
              try {
                const parsed = JSON.parse(line);
                if (parsed.method === 'auth.handshake') {
                  if (!socket.destroyed) {
                    socket.write(
                      JSON.stringify({
                        jsonrpc: '2.0',
                        id: parsed.id ?? null,
                        result: { ok: true },
                      }) + '\n',
                    );
                  }
                  newlineIdx = buffer.indexOf('\n');
                  continue;
                }
              } catch {
                /* not JSON or not handshake — proceed as normal RPC */
              }
              // Auth passed and it's a normal RPC — fall through to router
            } else {
              // Auth failed — reject and disconnect
              try {
                const parsed = JSON.parse(line);
                if (!socket.destroyed) {
                  socket.write(
                    JSON.stringify({
                      jsonrpc: '2.0',
                      id: parsed.id ?? null,
                      error: {
                        code: -32600,
                        message: authResult.reason || 'Authentication required',
                      },
                    }) + '\n',
                  );
                }
              } catch {
                /* ignore parse errors */
              }
              socket.destroy();
              return;
            }
          }

          // R2: check method-level authorization
          let methodAllowed = true;
          try {
            const parsed = JSON.parse(line);
            if (parsed.method && !this.auth.isMethodAllowed(parsed.method)) {
              methodAllowed = false;
              if (!socket.destroyed) {
                socket.write(
                  JSON.stringify({
                    jsonrpc: '2.0',
                    id: parsed.id ?? null,
                    error: { code: -32600, message: `Method not allowed: ${parsed.method}` },
                  }) + '\n',
                );
              }
            }
          } catch {
            // C4: JSON parse failure must block — never pass unparseable data to router
            methodAllowed = false;
            if (!socket.destroyed) {
              socket.write(
                JSON.stringify({
                  jsonrpc: '2.0',
                  id: null,
                  error: { code: -32700, message: 'Parse error' },
                }) + '\n',
              );
            }
          }

          if (methodAllowed) {
            this.router
              .handle(line)
              .then((response) => {
                if (!socket.destroyed) {
                  socket.write(response + '\n');
                }
              })
              .catch(() => {
                // Router.handle already catches errors internally;
                // this is a safety net.
              });
          }
        }

        newlineIdx = buffer.indexOf('\n');
      }
    });

    socket.on('error', () => {
      // Client disconnect errors are expected; silently ignore.
    });
  }

  /**
   * Get the actual bound port.
   */
  getPort(): number {
    return this.boundPort;
  }

  /**
   * Stop the server.
   */
  async stop(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.server) {
        resolve();
        return;
      }

      this.server.close((err) => {
        this.server = null;
        this.boundPort = 0;
        if (err) {
          reject(err);
        } else {
          resolve();
        }
      });
    });
  }
}
