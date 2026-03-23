import { describe, it, expect, vi } from 'vitest';
import { JsonRpcRouter } from '../../../src/main/socket/router';

function makeRequest(method: string, params?: unknown, id: number | string = 1): string {
  return JSON.stringify({ jsonrpc: '2.0', method, params, id });
}

describe('JsonRpcRouter', () => {
  it('routes valid request to handler', async () => {
    const router = new JsonRpcRouter();
    router.register('echo', (params) => params);

    const raw = makeRequest('echo', { msg: 'hello' });
    const resp = JSON.parse(await router.handle(raw));

    expect(resp.jsonrpc).toBe('2.0');
    expect(resp.id).toBe(1);
    expect(resp.result).toEqual({ msg: 'hello' });
    expect(resp.error).toBeUndefined();
  });

  it('returns error for unknown method (-32601)', async () => {
    const router = new JsonRpcRouter();

    const raw = makeRequest('nonexistent');
    const resp = JSON.parse(await router.handle(raw));

    expect(resp.error).toBeDefined();
    expect(resp.error.code).toBe(-32601);
    expect(resp.error.message).toContain('Method not found');
  });

  it('returns error for invalid JSON (-32700)', async () => {
    const router = new JsonRpcRouter();

    const resp = JSON.parse(await router.handle('{invalid json!!!'));

    expect(resp.error).toBeDefined();
    expect(resp.error.code).toBe(-32700);
    expect(resp.error.message).toBe('Parse error');
    expect(resp.id).toBeNull();
  });

  it('returns error for missing method (-32600)', async () => {
    const router = new JsonRpcRouter();

    // Valid JSON but missing method field
    const raw = JSON.stringify({ jsonrpc: '2.0', id: 1 });
    const resp = JSON.parse(await router.handle(raw));

    expect(resp.error).toBeDefined();
    expect(resp.error.code).toBe(-32600);
    expect(resp.error.message).toBe('Invalid Request');
  });

  it('returns error for wrong jsonrpc version (-32600)', async () => {
    const router = new JsonRpcRouter();

    const raw = JSON.stringify({ jsonrpc: '1.0', method: 'test', id: 1 });
    const resp = JSON.parse(await router.handle(raw));

    expect(resp.error).toBeDefined();
    expect(resp.error.code).toBe(-32600);
  });

  it('passes params to handler', async () => {
    const router = new JsonRpcRouter();
    const handler = vi.fn((params) => ({ received: params }));
    router.register('test', handler);

    const params = { key: 'value', num: 42 };
    await router.handle(makeRequest('test', params));

    expect(handler).toHaveBeenCalledWith(params);
  });

  it('handles handler errors gracefully (-32603)', async () => {
    const router = new JsonRpcRouter();
    router.register('fail', () => {
      throw new Error('kaboom');
    });

    const resp = JSON.parse(await router.handle(makeRequest('fail')));

    expect(resp.error).toBeDefined();
    expect(resp.error.code).toBe(-32603);
    expect(resp.error.message).toContain('Internal error');
    expect(resp.error.message).toContain('kaboom');
  });

  it('handles async handler errors gracefully (-32603)', async () => {
    const router = new JsonRpcRouter();
    router.register('async-fail', async () => {
      throw new Error('async kaboom');
    });

    const resp = JSON.parse(await router.handle(makeRequest('async-fail')));

    expect(resp.error).toBeDefined();
    expect(resp.error.code).toBe(-32603);
    expect(resp.error.message).toContain('async kaboom');
  });

  it('preserves request id in response', async () => {
    const router = new JsonRpcRouter();
    router.register('ping', () => 'pong');

    const resp = JSON.parse(await router.handle(makeRequest('ping', undefined, 42)));
    expect(resp.id).toBe(42);

    const resp2 = JSON.parse(await router.handle(makeRequest('ping', undefined, 'abc')));
    expect(resp2.id).toBe('abc');
  });

  it('getMethods returns registered methods', () => {
    const router = new JsonRpcRouter();
    router.register('a', () => null);
    router.register('b', () => null);

    expect(router.getMethods().sort()).toEqual(['a', 'b']);
  });
});
