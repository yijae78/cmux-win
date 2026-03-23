import { describe, it, expect, beforeEach } from 'vitest';
import { JsonRpcRouter } from '../../../src/main/socket/router';
import { AppStateStore } from '../../../src/main/sot/store';
import { registerBrowserHandlers } from '../../../src/main/socket/handlers/browser';

describe('browser automation handlers', () => {
  let router: JsonRpcRouter;

  beforeEach(() => {
    router = new JsonRpcRouter();
    const store = new AppStateStore();
    registerBrowserHandlers(router, store);
  });

  it('browser.eval requires surfaceId and code', async () => {
    const res1 = await router.handle(
      JSON.stringify({ jsonrpc: '2.0', method: 'browser.eval', params: {}, id: 1 }),
    );
    expect(JSON.parse(res1).error).toBeDefined();
    const res2 = await router.handle(
      JSON.stringify({
        jsonrpc: '2.0',
        method: 'browser.eval',
        params: { surfaceId: 's1' },
        id: 2,
      }),
    );
    expect(JSON.parse(res2).error).toBeDefined();
    const res3 = await router.handle(
      JSON.stringify({
        jsonrpc: '2.0',
        method: 'browser.eval',
        params: { surfaceId: 's1', code: 'x' },
        id: 3,
      }),
    );
    expect(JSON.parse(res3).result.ok).toBe(true);
  });

  it('browser.snapshot requires surfaceId', async () => {
    const res = await router.handle(
      JSON.stringify({ jsonrpc: '2.0', method: 'browser.snapshot', params: {}, id: 1 }),
    );
    expect(JSON.parse(res).error).toBeDefined();
  });

  it('browser.click requires surfaceId and ref', async () => {
    const res = await router.handle(
      JSON.stringify({
        jsonrpc: '2.0',
        method: 'browser.click',
        params: { surfaceId: 's1' },
        id: 1,
      }),
    );
    expect(JSON.parse(res).error).toBeDefined();
  });

  it('browser.type requires surfaceId and text', async () => {
    const res = await router.handle(
      JSON.stringify({
        jsonrpc: '2.0',
        method: 'browser.type',
        params: { surfaceId: 's1' },
        id: 1,
      }),
    );
    expect(JSON.parse(res).error).toBeDefined();
  });

  it('browser.fill requires surfaceId and ref', async () => {
    const res = await router.handle(
      JSON.stringify({
        jsonrpc: '2.0',
        method: 'browser.fill',
        params: { surfaceId: 's1' },
        id: 1,
      }),
    );
    expect(JSON.parse(res).error).toBeDefined();
  });

  it('browser.press requires surfaceId and key', async () => {
    const res = await router.handle(
      JSON.stringify({
        jsonrpc: '2.0',
        method: 'browser.press',
        params: { surfaceId: 's1' },
        id: 1,
      }),
    );
    expect(JSON.parse(res).error).toBeDefined();
  });

  it('browser.wait requires surfaceId', async () => {
    const res = await router.handle(
      JSON.stringify({ jsonrpc: '2.0', method: 'browser.wait', params: {}, id: 1 }),
    );
    expect(JSON.parse(res).error).toBeDefined();
  });

  it('browser.screenshot requires surfaceId', async () => {
    const res = await router.handle(
      JSON.stringify({ jsonrpc: '2.0', method: 'browser.screenshot', params: {}, id: 1 }),
    );
    expect(JSON.parse(res).error).toBeDefined();
  });
});
