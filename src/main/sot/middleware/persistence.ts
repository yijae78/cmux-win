import fs from 'node:fs';
import path from 'node:path';
import type { Middleware } from '../store';
import type { Action } from '../../../shared/actions';
import type { AppState, PersistedState } from '../../../shared/types';
import { SCHEMA_VERSION, SESSION_BACKUP_SUFFIX } from '../../../shared/constants';

export class PersistenceMiddleware implements Middleware {
  private filePath: string;
  private debounceMs: number;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private pendingState: AppState | null = null;
  private hasSavedBefore = false;

  constructor(filePath: string, debounceMs: number = 500) {
    this.filePath = filePath;
    this.debounceMs = debounceMs;
  }

  post(
    _action: Action,
    _prevState: Readonly<AppState>,
    nextState: Readonly<AppState>,
  ): void {
    this.pendingState = nextState as AppState;
    if (this.timer) {
      clearTimeout(this.timer);
    }
    this.timer = setTimeout(() => {
      this.flush();
    }, this.debounceMs);
  }

  dispose(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.flush();
  }

  private flush(): void {
    if (!this.pendingState) return;
    const state = this.pendingState;
    this.pendingState = null;
    this.timer = null;

    try {
      // If we've saved before, create a backup of the current file
      if (this.hasSavedBefore && fs.existsSync(this.filePath)) {
        const backupPath = this.filePath + SESSION_BACKUP_SUFFIX;
        fs.copyFileSync(this.filePath, backupPath);
      }

      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      const persisted: PersistedState = {
        version: SCHEMA_VERSION,
        state,
      };
      fs.writeFileSync(this.filePath, JSON.stringify(persisted), 'utf-8');
      this.hasSavedBefore = true;
    } catch (err) {
      console.error('[PersistenceMiddleware] Failed to save state:', err);
    }
  }

  static loadState(filePath: string): PersistedState | null {
    try {
      if (!fs.existsSync(filePath)) return null;
      const raw = fs.readFileSync(filePath, 'utf-8');
      const parsed: unknown = JSON.parse(raw);
      // Basic validation
      if (
        typeof parsed === 'object' &&
        parsed !== null &&
        'version' in parsed &&
        'state' in parsed
      ) {
        return parsed as PersistedState;
      }
      return null;
    } catch {
      return null;
    }
  }
}
