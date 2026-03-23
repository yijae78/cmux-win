import { describe, it, expect } from 'vitest';
import { parseSshTarget, buildSshCommand } from '../../../src/main/remote/ssh-session';

describe('parseSshTarget', () => {
  it('parses user@host', () => {
    expect(parseSshTarget('john@example.com')).toEqual({
      user: 'john',
      host: 'example.com',
      port: undefined,
    });
  });
  it('parses host only', () => {
    expect(parseSshTarget('example.com')).toEqual({
      user: undefined,
      host: 'example.com',
      port: undefined,
    });
  });
  it('parses user@host:port', () => {
    expect(parseSshTarget('john@example.com:2222')).toEqual({
      user: 'john',
      host: 'example.com',
      port: 2222,
    });
  });
  it('parses host:port without user', () => {
    expect(parseSshTarget('example.com:22')).toEqual({
      user: undefined,
      host: 'example.com',
      port: 22,
    });
  });
  it('throws on empty string', () => {
    expect(() => parseSshTarget('')).toThrow('Invalid SSH target');
  });
});

describe('buildSshCommand', () => {
  it('basic host', () => {
    expect(buildSshCommand({ host: 'example.com' })).toEqual({
      shell: 'ssh',
      args: ['example.com'],
    });
  });
  it('with user', () => {
    const result = buildSshCommand({ user: 'john', host: 'example.com' });
    expect(result.args).toContain('-l');
    expect(result.args).toContain('john');
  });
  it('with port', () => {
    const result = buildSshCommand({ host: 'example.com', port: 2222 });
    expect(result.args).toContain('-p');
    expect(result.args).toContain('2222');
  });
});
