import { describe, it, expect } from 'vitest';
import { IPC_CHANNELS } from '../../../src/shared/ipc-channels';

describe('IPC_CHANNELS', () => {
  it('defines all required channels', () => {
    expect(IPC_CHANNELS.DISPATCH).toBeDefined();
    expect(IPC_CHANNELS.QUERY_STATE).toBeDefined();
    expect(IPC_CHANNELS.GET_INITIAL_STATE).toBeDefined();
    expect(IPC_CHANNELS.STATE_UPDATE).toBeDefined();
    expect(IPC_CHANNELS.WINDOW_ID).toBeDefined();
    expect(IPC_CHANNELS.PTY_WRITE).toBeDefined();
    expect(IPC_CHANNELS.PTY_METADATA).toBeDefined();
  });

  it('all channel values are non-empty strings', () => {
    for (const [key, value] of Object.entries(IPC_CHANNELS)) {
      expect(typeof value).toBe('string');
      expect(value.length).toBeGreaterThan(0);
    }
  });

  it('all channel values are unique', () => {
    const values = Object.values(IPC_CHANNELS);
    const unique = new Set(values);
    expect(unique.size).toBe(values.length);
  });

  it('WINDOW_ID channel exists (BUG-8)', () => {
    expect(IPC_CHANNELS.WINDOW_ID).toBe('cmux:window-id');
  });

  it('channel values follow naming convention', () => {
    for (const value of Object.values(IPC_CHANNELS)) {
      expect(value).toMatch(/^(cmux|pty):/);
    }
  });
});
