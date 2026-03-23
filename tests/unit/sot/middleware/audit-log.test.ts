import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { AppStateStore } from '../../../../src/main/sot/store';
import { AuditLogMiddleware } from '../../../../src/main/sot/middleware/audit-log';

describe('AuditLogMiddleware', () => {
  let store: AppStateStore;
  let tmpDir: string;
  let logPath: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cmux-audit-test-'));
    logPath = path.join(tmpDir, 'audit.log');
    store = new AppStateStore();
    store.use(new AuditLogMiddleware(logPath));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('writes audit entry with timestamp and action type on dispatch', () => {
    store.dispatch({ type: 'window.create', payload: {} });

    expect(fs.existsSync(logPath)).toBe(true);
    const content = fs.readFileSync(logPath, 'utf-8').trim();
    const lines = content.split('\n');
    expect(lines).toHaveLength(1);

    const entry = JSON.parse(lines[0]);
    expect(entry.type).toBe('window.create');
    expect(entry.timestamp).toBeDefined();
    // Verify ISO format
    expect(new Date(entry.timestamp).toISOString()).toBe(entry.timestamp);
    expect(entry.payload).toBeDefined();
  });

  it('appends multiple entries for multiple dispatches', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;
    store.dispatch({
      type: 'workspace.create',
      payload: { windowId: winId, name: 'Test' },
    });

    const content = fs.readFileSync(logPath, 'utf-8').trim();
    const lines = content.split('\n');
    expect(lines).toHaveLength(2);

    const entry1 = JSON.parse(lines[0]);
    const entry2 = JSON.parse(lines[1]);
    expect(entry1.type).toBe('window.create');
    expect(entry2.type).toBe('workspace.create');
  });

  it('includes payload in the audit entry', () => {
    store.dispatch({ type: 'window.create', payload: {} });
    const winId = store.getState().windows[0].id;
    store.dispatch({
      type: 'workspace.create',
      payload: { windowId: winId, name: 'Audited WS' },
    });

    const content = fs.readFileSync(logPath, 'utf-8').trim();
    const lines = content.split('\n');
    const entry = JSON.parse(lines[1]);
    expect(entry.payload.name).toBe('Audited WS');
  });

  it('creates parent directory if it does not exist', () => {
    const nestedPath = path.join(tmpDir, 'nested', 'dir', 'audit.log');
    const store2 = new AppStateStore();
    store2.use(new AuditLogMiddleware(nestedPath));

    store2.dispatch({ type: 'window.create', payload: {} });
    expect(fs.existsSync(nestedPath)).toBe(true);
  });
});
