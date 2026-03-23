import fs from 'node:fs';
import path from 'node:path';
import type { Middleware } from '../store';
import type { Action } from '../../../shared/actions';
import type { AppState } from '../../../shared/types';

export class AuditLogMiddleware implements Middleware {
  private filePath: string;

  constructor(filePath: string) {
    this.filePath = filePath;
  }

  post(
    action: Action,
    _prevState: Readonly<AppState>,
    _nextState: Readonly<AppState>,
  ): void {
    try {
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      const entry = {
        timestamp: new Date().toISOString(),
        type: action.type,
        payload: action.payload,
      };

      fs.appendFileSync(
        this.filePath,
        JSON.stringify(entry) + '\n',
        'utf-8',
      );
    } catch (err) {
      console.error('[AuditLogMiddleware] Failed to write audit log:', err);
    }
  }
}
