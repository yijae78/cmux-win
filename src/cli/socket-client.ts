import net from 'node:net';

const DEFAULT_ADDR = 'tcp://127.0.0.1:19840';

export function parseSocketAddr(addr: string): { host: string; port: number } {
  const cleaned = addr.replace(/^tcp:\/\//, '');
  const [host, portStr] = cleaned.split(':');
  return { host: host || '127.0.0.1', port: parseInt(portStr || '19840', 10) };
}

export async function rpcCall(method: string, params?: unknown, addr?: string): Promise<unknown> {
  const { host, port } = parseSocketAddr(addr || process.env.CMUX_SOCKET_ADDR || DEFAULT_ADDR);
  const token = process.env.CMUX_SOCKET_TOKEN;
  const request = JSON.stringify({ jsonrpc: '2.0', method, params, id: 1 });

  return new Promise((resolve, reject) => {
    const client = net.createConnection({ host, port }, () => {
      // R2: send auth handshake first if token is available
      if (token) {
        client.write(JSON.stringify({ jsonrpc: '2.0', method: 'auth.handshake', params: { token }, id: 0 }) + '\n');
      }
      client.write(request + '\n');
    });
    let buffer = '';
    client.on('data', (chunk) => {
      buffer += chunk.toString();
      if (buffer.includes('\n')) {
        client.end();
        try {
          const response = JSON.parse(buffer.trim());
          if (response.error) reject(new Error(`[${response.error.code}] ${response.error.message}`));
          else resolve(response.result);
        } catch (e) {
          reject(e);
        }
      }
    });
    client.on('error', (err) => reject(new Error(`Socket connection failed: ${err.message}`)));
    setTimeout(() => {
      client.destroy();
      reject(new Error('Socket timeout (5s)'));
    }, 5000);
  });
}
