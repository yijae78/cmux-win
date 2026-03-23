import fs from 'node:fs';
import type { AppState, PersistedState } from '../../../shared/types';
import { SCHEMA_VERSION, SESSION_BACKUP_SUFFIX } from '../../../shared/constants';

/**
 * A migration function transforms state from version N to version N+1.
 */
export interface Migration {
  fromVersion: number;
  toVersion: number;
  migrate: (state: AppState) => AppState;
}

// Register migrations here in order
const migrations: Migration[] = [
  // Example: { fromVersion: 1, toVersion: 2, migrate: (state) => { ... return state; } }
];

/**
 * GAP-F: Apply migration chain from persisted version to current SCHEMA_VERSION.
 * Creates a backup before migrating if filePath is provided.
 */
export function migrateState(
  persisted: PersistedState,
  filePath?: string,
): PersistedState {
  let { version, state } = persisted;

  if (version === SCHEMA_VERSION) {
    return persisted;
  }

  // Create backup before migration if file path provided
  if (filePath && fs.existsSync(filePath)) {
    const backupPath = filePath + SESSION_BACKUP_SUFFIX;
    try {
      fs.copyFileSync(filePath, backupPath);
    } catch (err) {
      console.error('[migrateState] Failed to create backup:', err);
    }
  }

  // Apply migrations in sequence
  while (version < SCHEMA_VERSION) {
    const migration = migrations.find((m) => m.fromVersion === version);
    if (!migration) {
      console.warn(
        `[migrateState] No migration found from version ${version} to ${version + 1}`,
      );
      break;
    }
    state = migration.migrate(state);
    version = migration.toVersion;
  }

  return { version, state };
}

/**
 * GAP-F: Load persisted state from file, with backup fallback.
 * Try main file first, then backup, return null on total failure.
 */
export function loadPersistedState(filePath: string): PersistedState | null {
  // Try main file
  const mainResult = tryLoadFile(filePath);
  if (mainResult) return mainResult;

  // Try backup
  const backupPath = filePath + SESSION_BACKUP_SUFFIX;
  const backupResult = tryLoadFile(backupPath);
  if (backupResult) return backupResult;

  return null;
}

function tryLoadFile(filePath: string): PersistedState | null {
  try {
    if (!fs.existsSync(filePath)) return null;
    const raw = fs.readFileSync(filePath, 'utf-8');
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      'version' in parsed &&
      'state' in parsed &&
      typeof (parsed as PersistedState).version === 'number'
    ) {
      return parsed as PersistedState;
    }
    return null;
  } catch {
    return null;
  }
}
