import { describe, it, expect } from 'vitest';
import { z } from 'zod';
import { IPC_CHANNELS } from '../../../src/shared/ipc-channels';
import { IpcContract } from '../../../src/shared/ipc-contract';
import {
  JsonRpcRequestSchema,
  JsonRpcResponseSchema,
  JSON_RPC_ERRORS,
} from '../../../src/shared/protocol';

// ===== IPC Contract Tests =====

describe('IpcContract', () => {
  it('has an entry for every IPC_CHANNELS value', () => {
    const channelValues = Object.values(IPC_CHANNELS);
    for (const channel of channelValues) {
      expect(IpcContract).toHaveProperty(channel);
    }
  });

  it('every contract entry has input and output Zod schemas', () => {
    for (const [, entry] of Object.entries(IpcContract)) {
      expect(entry).toHaveProperty('input');
      expect(entry).toHaveProperty('output');

      // Verify they are Zod schemas by checking for safeParse method
      expect(typeof (entry.input as z.ZodTypeAny).safeParse).toBe('function');
      expect(typeof (entry.output as z.ZodTypeAny).safeParse).toBe('function');
    }
  });

  it('DISPATCH contract validates a valid action', () => {
    const contract = IpcContract[IPC_CHANNELS.DISPATCH];
    const result = contract.input.safeParse({
      type: 'window.create',
      payload: { geometry: { x: 0, y: 0, width: 800, height: 600 } },
    });
    expect(result.success).toBe(true);
  });

  it('DISPATCH contract rejects an invalid action', () => {
    const contract = IpcContract[IPC_CHANNELS.DISPATCH];
    const result = contract.input.safeParse({ type: 'not.real', payload: {} });
    expect(result.success).toBe(false);
  });

  it('DISPATCH output validates success response', () => {
    const contract = IpcContract[IPC_CHANNELS.DISPATCH];
    expect(contract.output.safeParse({ ok: true }).success).toBe(true);
    expect(contract.output.safeParse({ ok: false, error: 'bad' }).success).toBe(true);
  });

  it('PTY_WRITE contract validates write data', () => {
    const contract = IpcContract[IPC_CHANNELS.PTY_WRITE];
    expect(contract.input.safeParse({ surfaceId: 'sf-1', data: 'hello' }).success).toBe(true);
  });

  it('SCROLLBACK_SAVE contract validates save data', () => {
    const contract = IpcContract[IPC_CHANNELS.SCROLLBACK_SAVE];
    expect(contract.input.safeParse({ surfaceId: 'sf-1', data: 'buffer content' }).success).toBe(
      true,
    );
  });

  it('SCROLLBACK_LOAD contract validates load request', () => {
    const contract = IpcContract[IPC_CHANNELS.SCROLLBACK_LOAD];
    expect(contract.input.safeParse({ surfaceId: 'sf-1' }).success).toBe(true);
  });

  it('SHORTCUT contract validates shortcut action string', () => {
    const contract = IpcContract[IPC_CHANNELS.SHORTCUT];
    expect(contract.input.safeParse({ action: 'workspace.new' }).success).toBe(true);
  });

  it('channel count matches — no channel left behind', () => {
    const channelCount = Object.keys(IPC_CHANNELS).length;
    const contractCount = Object.keys(IpcContract).length;
    expect(contractCount).toBe(channelCount);
  });
});

// ===== JSON-RPC Protocol Tests =====

describe('JsonRpcRequestSchema', () => {
  it('validates a correct request with all fields', () => {
    const result = JsonRpcRequestSchema.safeParse({
      jsonrpc: '2.0',
      method: 'state.get',
      params: { key: 'value' },
      id: 1,
    });
    expect(result.success).toBe(true);
  });

  it('validates a notification (no id)', () => {
    const result = JsonRpcRequestSchema.safeParse({
      jsonrpc: '2.0',
      method: 'event.notify',
    });
    expect(result.success).toBe(true);
  });

  it('validates request with string id', () => {
    const result = JsonRpcRequestSchema.safeParse({
      jsonrpc: '2.0',
      method: 'test.method',
      id: 'abc-123',
    });
    expect(result.success).toBe(true);
  });

  it('validates request with null id', () => {
    const result = JsonRpcRequestSchema.safeParse({
      jsonrpc: '2.0',
      method: 'test.method',
      id: null,
    });
    expect(result.success).toBe(true);
  });

  it('rejects request with wrong jsonrpc version', () => {
    const result = JsonRpcRequestSchema.safeParse({
      jsonrpc: '1.0',
      method: 'test',
      id: 1,
    });
    expect(result.success).toBe(false);
  });

  it('rejects request without method', () => {
    const result = JsonRpcRequestSchema.safeParse({
      jsonrpc: '2.0',
      id: 1,
    });
    expect(result.success).toBe(false);
  });

  it('rejects request with numeric method', () => {
    const result = JsonRpcRequestSchema.safeParse({
      jsonrpc: '2.0',
      method: 42,
      id: 1,
    });
    expect(result.success).toBe(false);
  });

  it('rejects completely invalid input', () => {
    expect(JsonRpcRequestSchema.safeParse('not an object').success).toBe(false);
    expect(JsonRpcRequestSchema.safeParse(null).success).toBe(false);
    expect(JsonRpcRequestSchema.safeParse(123).success).toBe(false);
  });
});

describe('JsonRpcResponseSchema', () => {
  it('validates a success response', () => {
    const result = JsonRpcResponseSchema.safeParse({
      jsonrpc: '2.0',
      id: 1,
      result: { windows: [] },
    });
    expect(result.success).toBe(true);
  });

  it('validates an error response', () => {
    const result = JsonRpcResponseSchema.safeParse({
      jsonrpc: '2.0',
      id: 1,
      error: { code: -32601, message: 'Method not found' },
    });
    expect(result.success).toBe(true);
  });

  it('validates an error response with data', () => {
    const result = JsonRpcResponseSchema.safeParse({
      jsonrpc: '2.0',
      id: null,
      error: { code: -32603, message: 'Internal error', data: { stack: '...' } },
    });
    expect(result.success).toBe(true);
  });

  it('validates response with string id', () => {
    const result = JsonRpcResponseSchema.safeParse({
      jsonrpc: '2.0',
      id: 'req-42',
      result: true,
    });
    expect(result.success).toBe(true);
  });

  it('rejects response without id', () => {
    const result = JsonRpcResponseSchema.safeParse({
      jsonrpc: '2.0',
      result: 'ok',
    });
    expect(result.success).toBe(false);
  });

  it('rejects response with wrong jsonrpc version', () => {
    const result = JsonRpcResponseSchema.safeParse({
      jsonrpc: '1.0',
      id: 1,
      result: 'ok',
    });
    expect(result.success).toBe(false);
  });
});

describe('JSON_RPC_ERRORS', () => {
  it('defines standard error codes', () => {
    expect(JSON_RPC_ERRORS.PARSE_ERROR).toBe(-32700);
    expect(JSON_RPC_ERRORS.INVALID_REQUEST).toBe(-32600);
    expect(JSON_RPC_ERRORS.METHOD_NOT_FOUND).toBe(-32601);
    expect(JSON_RPC_ERRORS.INVALID_PARAMS).toBe(-32602);
    expect(JSON_RPC_ERRORS.INTERNAL_ERROR).toBe(-32603);
  });
});
