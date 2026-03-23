import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { migrateState, loadPersistedState } from '../../../../src/main/sot/migrations/index';
import { createDefaultState } from '../../../../src/main/sot/create-default-state';
import {
  SCHEMA_VERSION,
  SESSION_BACKUP_SUFFIX,
} from '../../../../src/shared/constants';
import type { PersistedState } from '../../../../src/shared/types';

describe('migrateState', () => {
  let tmpDir: string;
  let filePath: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cmux-migrate-test-'));
    filePath = path.join(tmpDir, 'state.json');
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('returns state as-is when version matches SCHEMA_VERSION', () => {
    const persisted: PersistedState = {
      version: SCHEMA_VERSION,
      state: createDefaultState(),
    };
    const result = migrateState(persisted);
    expect(result.version).toBe(SCHEMA_VERSION);
    expect(result.state).toEqual(persisted.state);
  });

  it('creates backup before migration when filePath provided', () => {
    const persisted: PersistedState = {
      version: 0, // old version that won't find a migration
      state: createDefaultState(),
    };
    // Write the "old" file
    fs.writeFileSync(filePath, JSON.stringify(persisted), 'utf-8');

    migrateState(persisted, filePath);

    const backupPath = filePath + SESSION_BACKUP_SUFFIX;
    expect(fs.existsSync(backupPath)).toBe(true);
  });
});

describe('loadPersistedState', () => {
  let tmpDir: string;
  let filePath: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cmux-load-test-'));
    filePath = path.join(tmpDir, 'state.json');
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it('loads valid persisted state from file', () => {
    const data: PersistedState = {
      version: SCHEMA_VERSION,
      state: createDefaultState(),
    };
    fs.writeFileSync(filePath, JSON.stringify(data), 'utf-8');

    const result = loadPersistedState(filePath);
    expect(result).not.toBeNull();
    expect(result!.version).toBe(SCHEMA_VERSION);
  });

  it('returns null for corrupted main file with no backup', () => {
    fs.writeFileSync(filePath, '{{not json', 'utf-8');

    const result = loadPersistedState(filePath);
    expect(result).toBeNull();
  });

  it('falls back to backup when main file is corrupted', () => {
    // Corrupted main
    fs.writeFileSync(filePath, '{{not json', 'utf-8');

    // Valid backup
    const backupPath = filePath + SESSION_BACKUP_SUFFIX;
    const data: PersistedState = {
      version: SCHEMA_VERSION,
      state: createDefaultState(),
    };
    fs.writeFileSync(backupPath, JSON.stringify(data), 'utf-8');

    const result = loadPersistedState(filePath);
    expect(result).not.toBeNull();
    expect(result!.version).toBe(SCHEMA_VERSION);
  });

  it('returns null when both main and backup are missing', () => {
    const result = loadPersistedState(
      path.join(tmpDir, 'nonexistent.json'),
    );
    expect(result).toBeNull();
  });

  it('returns null when main is missing and backup is corrupted', () => {
    const backupPath = filePath + SESSION_BACKUP_SUFFIX;
    fs.writeFileSync(backupPath, 'corrupted', 'utf-8');

    const result = loadPersistedState(filePath);
    expect(result).toBeNull();
  });
});
