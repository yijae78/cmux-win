import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { AppStateStore } from '../../../../src/main/sot/store';
import { PersistenceMiddleware } from '../../../../src/main/sot/middleware/persistence';
import { SCHEMA_VERSION, SESSION_BACKUP_SUFFIX } from '../../../../src/shared/constants';

describe('PersistenceMiddleware', () => {
  let store: AppStateStore;
  let tmpDir: string;
  let filePath: string;
  let mw: PersistenceMiddleware;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cmux-persist-test-'));
    filePath = path.join(tmpDir, 'state.json');
    store = new AppStateStore();
    // Use 50ms debounce for tests
    mw = new PersistenceMiddleware(filePath, 50);
    store.use(mw);
  });

  afterEach(() => {
    mw.dispose();
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('saves state to file after debounce', async () => {
    store.dispatch({ type: 'window.create', payload: {} });

    // Wait for debounce
    await new Promise((r) => setTimeout(r, 100));

    expect(fs.existsSync(filePath)).toBe(true);
    const content = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    expect(content.version).toBe(SCHEMA_VERSION);
    expect(content.state.windows).toHaveLength(1);
  });

  it('debounce coalesces multiple dispatches', async () => {
    const writeSpy = vi.spyOn(fs, 'writeFileSync');

    store.dispatch({ type: 'window.create', payload: {} });
    store.dispatch({ type: 'window.create', payload: {} });
    store.dispatch({ type: 'window.create', payload: {} });

    // Wait for debounce
    await new Promise((r) => setTimeout(r, 100));

    // Should have written only once (coalesced)
    const persistWrites = writeSpy.mock.calls.filter(
      (call) => call[0] === filePath,
    );
    expect(persistWrites).toHaveLength(1);

    const content = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    expect(content.state.windows).toHaveLength(3);

    writeSpy.mockRestore();
  });

  it('creates backup on second save', async () => {
    store.dispatch({ type: 'window.create', payload: {} });
    await new Promise((r) => setTimeout(r, 100));

    // First save done, now dispatch again
    store.dispatch({ type: 'window.create', payload: {} });
    await new Promise((r) => setTimeout(r, 100));

    const backupPath = filePath + SESSION_BACKUP_SUFFIX;
    expect(fs.existsSync(backupPath)).toBe(true);

    // Backup should have the first save (1 window)
    const backup = JSON.parse(fs.readFileSync(backupPath, 'utf-8'));
    expect(backup.state.windows).toHaveLength(1);

    // Main file should have 2 windows
    const main = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    expect(main.state.windows).toHaveLength(2);
  });

  it('dispose flushes immediately', () => {
    store.dispatch({ type: 'window.create', payload: {} });

    // Don't wait for debounce, just dispose
    mw.dispose();

    expect(fs.existsSync(filePath)).toBe(true);
    const content = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    expect(content.version).toBe(SCHEMA_VERSION);
  });

  it('loadState returns persisted data from file', () => {
    const data = {
      version: SCHEMA_VERSION,
      state: store.getState(),
    };
    fs.writeFileSync(filePath, JSON.stringify(data), 'utf-8');

    const loaded = PersistenceMiddleware.loadState(filePath);
    expect(loaded).not.toBeNull();
    expect(loaded!.version).toBe(SCHEMA_VERSION);
  });

  it('loadState returns null for missing file', () => {
    const loaded = PersistenceMiddleware.loadState(
      path.join(tmpDir, 'nonexistent.json'),
    );
    expect(loaded).toBeNull();
  });

  it('loadState returns null for corrupted file', () => {
    fs.writeFileSync(filePath, '{{invalid json', 'utf-8');
    const loaded = PersistenceMiddleware.loadState(filePath);
    expect(loaded).toBeNull();
  });
});
