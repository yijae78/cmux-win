import { describe, it, expect } from 'vitest';
import { buildPtyEnv } from '../../../src/shared/env-utils';

describe('buildPtyEnv', () => {
  it('sets CMUX_SURFACE_ID', () => {
    const env = buildPtyEnv('surf-1', undefined, {});
    expect(env.CMUX_SURFACE_ID).toBe('surf-1');
  });

  it('sets CMUX_WORKSPACE_ID when provided', () => {
    const env = buildPtyEnv('surf-1', 'ws-1', {});
    expect(env.CMUX_WORKSPACE_ID).toBe('ws-1');
  });

  it('omits CMUX_WORKSPACE_ID when undefined', () => {
    const env = buildPtyEnv('surf-1', undefined, {});
    expect(env.CMUX_WORKSPACE_ID).toBeUndefined();
  });

  it('inherits CMUX_SOCKET_PORT from baseEnv', () => {
    const env = buildPtyEnv('surf-1', undefined, { CMUX_SOCKET_PORT: '19841' });
    expect(env.CMUX_SOCKET_PORT).toBe('19841');
  });

  it('prepends CMUX_BIN_DIR to PATH', () => {
    const env = buildPtyEnv('surf-1', undefined, {
      CMUX_BIN_DIR: 'C:\\app\\bin',
      PATH: 'C:\\usr\\bin',
    });
    expect(env.PATH).toMatch(/^C:\\app\\bin/);
  });

  it('does not modify PATH without CMUX_BIN_DIR', () => {
    const env = buildPtyEnv('surf-1', undefined, { PATH: '/usr/bin' });
    expect(env.PATH).toBe('/usr/bin');
  });

  it('preserves other baseEnv entries', () => {
    const env = buildPtyEnv('surf-1', undefined, { HOME: '/home/user', SHELL: '/bin/bash' });
    expect(env.HOME).toBe('/home/user');
    expect(env.SHELL).toBe('/bin/bash');
  });
});
