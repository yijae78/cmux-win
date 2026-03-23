import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { ClaudeHookSessionStore } from '../../../src/cli/claude-hook-session-store';

describe('ClaudeHookSessionStore', () => {
  let tmpDir: string;
  let store: ClaudeHookSessionStore;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cmux-test-'));
    store = new ClaudeHookSessionStore(path.join(tmpDir, 'sessions.json'));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('upsert and lookup', () => {
    store.upsert({
      sessionId: 's1',
      workspaceId: 'w1',
      surfaceId: 'sf1',
      startedAt: Date.now(),
      updatedAt: Date.now(),
    });
    const record = store.lookup('s1');
    expect(record).not.toBeNull();
    expect(record!.workspaceId).toBe('w1');
  });

  it('consume reads and deletes', () => {
    store.upsert({
      sessionId: 's1',
      workspaceId: 'w1',
      surfaceId: 'sf1',
      startedAt: Date.now(),
      updatedAt: Date.now(),
    });
    const record = store.consume('s1');
    expect(record).not.toBeNull();
    expect(store.lookup('s1')).toBeNull();
  });

  it('findByContext fallback', () => {
    store.upsert({
      sessionId: 's1',
      workspaceId: 'w1',
      surfaceId: 'sf1',
      startedAt: Date.now(),
      updatedAt: Date.now(),
    });
    const record = store.findByContext('sf1', 'w1');
    expect(record).not.toBeNull();
    expect(record!.sessionId).toBe('s1');
  });

  it('7-day auto expiry', () => {
    const oldTime = Date.now() - 8 * 24 * 60 * 60 * 1000; // 8 days ago
    store.upsert({
      sessionId: 's-old',
      workspaceId: 'w1',
      surfaceId: 'sf1',
      startedAt: oldTime,
      updatedAt: oldTime,
    });
    expect(store.lookup('s-old')).toBeNull();
  });

  it('returns empty on missing file', () => {
    const emptyStore = new ClaudeHookSessionStore(path.join(tmpDir, 'nonexistent.json'));
    expect(emptyStore.lookup('anything')).toBeNull();
  });

  it('recovers from corrupted file', () => {
    fs.writeFileSync(path.join(tmpDir, 'sessions.json'), 'not json{{{');
    expect(store.lookup('anything')).toBeNull();
  });

  it('lookup returns null for empty sessionId', () => {
    expect(store.lookup('')).toBeNull();
  });

  it('consume returns null for empty sessionId', () => {
    expect(store.consume('')).toBeNull();
  });
});
