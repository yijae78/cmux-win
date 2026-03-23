import type { AppStateStore } from '../sot/store';
import { PTY_RESTART_MAX_RETRIES } from '../../shared/constants';

export interface SurfaceRecoveryInfo {
  cwd: string;
  shell: string;
}

/**
 * GAP-E: RecoveryManager handles pty crash recovery with retry limits.
 */
export class RecoveryManager {
  private store: AppStateStore;
  private retryCounts = new Map<string, number>();

  constructor(store: AppStateStore) {
    this.store = store;
  }

  /**
   * Handle a pty crash for a surface.
   * Returns 'restart' if under retry limit, 'give-up' otherwise.
   */
  handlePtyCrash(surfaceId: string): 'restart' | 'give-up' {
    const count = this.retryCounts.get(surfaceId) ?? 0;
    const next = count + 1;
    this.retryCounts.set(surfaceId, next);

    if (next > PTY_RESTART_MAX_RETRIES) {
      return 'give-up';
    }
    return 'restart';
  }

  /**
   * Get recovery info for a surface from the current state.
   * Returns null if the surface or its terminal info doesn't exist.
   */
  getSurfaceRecoveryInfo(surfaceId: string): SurfaceRecoveryInfo | null {
    const state = this.store.getState();
    const surface = state.surfaces.find((s) => s.id === surfaceId);
    if (!surface?.terminal) return null;
    return {
      cwd: surface.terminal.cwd,
      shell: surface.terminal.shell,
    };
  }

  /**
   * Reset the retry counter for a surface (e.g., after successful restart).
   */
  resetRetryCount(surfaceId: string): void {
    this.retryCounts.delete(surfaceId);
  }

  /**
   * Get the current retry count for a surface.
   */
  getRetryCount(surfaceId: string): number {
    return this.retryCounts.get(surfaceId) ?? 0;
  }
}
