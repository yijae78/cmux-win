/**
 * JSON-RPC 2.0 router for the cmux socket API.
 *
 * Error codes per JSON-RPC 2.0 spec:
 *  -32700: Parse error
 *  -32600: Invalid Request
 *  -32601: Method not found
 *  -32603: Internal error
 */

export type RpcHandler = (params: unknown) => unknown | Promise<unknown>;

interface JsonRpcRequest {
  jsonrpc: string;
  method: string;
  params?: unknown;
  id?: string | number | null;
}

interface JsonRpcResponse {
  jsonrpc: '2.0';
  id: string | number | null;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

export class JsonRpcRouter {
  private handlers = new Map<string, RpcHandler>();

  register(method: string, handler: RpcHandler): void {
    this.handlers.set(method, handler);
  }

  async handle(raw: string): Promise<string> {
    let request: JsonRpcRequest;

    // Parse
    try {
      request = JSON.parse(raw) as JsonRpcRequest;
    } catch {
      return JSON.stringify(this.errorResponse(null, -32700, 'Parse error'));
    }

    // Validate
    if (
      !request ||
      typeof request !== 'object' ||
      request.jsonrpc !== '2.0' ||
      typeof request.method !== 'string'
    ) {
      return JSON.stringify(
        this.errorResponse(request?.id ?? null, -32600, 'Invalid Request'),
      );
    }

    const id = request.id ?? null;

    // Route
    const handler = this.handlers.get(request.method);
    if (!handler) {
      return JSON.stringify(
        this.errorResponse(id, -32601, `Method not found: ${request.method}`),
      );
    }

    // Execute
    try {
      const result = await handler(request.params);
      return JSON.stringify(this.successResponse(id, result));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return JSON.stringify(this.errorResponse(id, -32603, `Internal error: ${message}`));
    }
  }

  getMethods(): string[] {
    return Array.from(this.handlers.keys());
  }

  private successResponse(id: string | number | null, result: unknown): JsonRpcResponse {
    return { jsonrpc: '2.0', id, result };
  }

  private errorResponse(
    id: string | number | null,
    code: number,
    message: string,
  ): JsonRpcResponse {
    return { jsonrpc: '2.0', id, error: { code, message } };
  }
}
