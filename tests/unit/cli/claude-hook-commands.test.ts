import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { ClaudeHookSessionStore } from '../../../src/cli/claude-hook-session-store';

describe('claude-hook commands integration', () => {
  let tmpDir: string;
  let store: ClaudeHookSessionStore;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cmux-hook-test-'));
    store = new ClaudeHookSessionStore(path.join(tmpDir, 'sessions.json'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('session-start stores session record', () => {
    store.upsert({
      sessionId: 'test-session',
      workspaceId: 'ws-1',
      surfaceId: 'sf-1',
      cwd: '/test',
      pid: 12345,
      startedAt: Date.now(),
      updatedAt: Date.now(),
    });
    const record = store.lookup('test-session');
    expect(record).not.toBeNull();
    expect(record!.workspaceId).toBe('ws-1');
    expect(record!.pid).toBe(12345);
  });

  it('stop consumes session record', () => {
    store.upsert({
      sessionId: 'test-session',
      workspaceId: 'ws-1',
      surfaceId: 'sf-1',
      startedAt: Date.now(),
      updatedAt: Date.now(),
    });
    const record = store.consume('test-session');
    expect(record).not.toBeNull();
    expect(record!.sessionId).toBe('test-session');
    expect(store.lookup('test-session')).toBeNull();
  });

  it('pre-tool-use saves AskUserQuestion lastBody', () => {
    store.upsert({
      sessionId: 'test-session',
      workspaceId: 'ws-1',
      surfaceId: 'sf-1',
      startedAt: Date.now(),
      updatedAt: Date.now(),
    });
    const record = store.lookup('test-session')!;
    record.lastBody = 'What should I do next?';
    record.updatedAt = Date.now();
    store.upsert(record);
    const updated = store.lookup('test-session');
    expect(updated!.lastBody).toBe('What should I do next?');
  });

  it('notification consumes lastBody', () => {
    store.upsert({
      sessionId: 'test-session',
      workspaceId: 'ws-1',
      surfaceId: 'sf-1',
      lastBody: 'saved question',
      startedAt: Date.now(),
      updatedAt: Date.now(),
    });
    const record = store.lookup('test-session')!;
    const body = record.lastBody;
    expect(body).toBe('saved question');
    record.lastBody = undefined;
    store.upsert(record);
    expect(store.lookup('test-session')!.lastBody).toBeUndefined();
  });

  it('session-end removes session', () => {
    store.upsert({
      sessionId: 'test-session',
      workspaceId: 'ws-1',
      surfaceId: 'sf-1',
      startedAt: Date.now(),
      updatedAt: Date.now(),
    });
    store.consume('test-session');
    expect(store.lookup('test-session')).toBeNull();
  });

  it('findByContext works as fallback when sessionId is missing', () => {
    store.upsert({
      sessionId: 'test-session',
      workspaceId: 'ws-1',
      surfaceId: 'sf-1',
      startedAt: Date.now(),
      updatedAt: Date.now(),
    });
    const record = store.findByContext('sf-1', 'ws-1');
    expect(record).not.toBeNull();
    expect(record!.sessionId).toBe('test-session');
  });
});
