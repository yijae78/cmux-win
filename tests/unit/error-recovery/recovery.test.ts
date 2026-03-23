import { describe, it, expect, beforeEach } from 'vitest';
import { AppStateStore } from '../../../src/main/sot/store';
import { RecoveryManager } from '../../../src/main/error-recovery/recovery-manager';
import { PTY_RESTART_MAX_RETRIES } from '../../../src/shared/constants';
import type { AppState } from '../../../src/shared/types';

describe('RecoveryManager', () => {
  let store: AppStateStore;
  let recovery: RecoveryManager;

  beforeEach(() => {
    store = new AppStateStore();
    recovery = new RecoveryManager(store);
  });

  describe('handlePtyCrash', () => {
    it('returns restart for first crash', () => {
      const result = recovery.handlePtyCrash('surface-1');
      expect(result).toBe('restart');
    });

    it('returns restart up to PTY_RESTART_MAX_RETRIES times', () => {
      // PTY_RESTART_MAX_RETRIES is 3
      for (let i = 0; i < PTY_RESTART_MAX_RETRIES; i++) {
        const result = recovery.handlePtyCrash('surface-1');
        expect(result).toBe('restart');
      }
    });

    it('returns give-up after exceeding max retries', () => {
      // Exhaust retries (3 restarts)
      for (let i = 0; i < PTY_RESTART_MAX_RETRIES; i++) {
        recovery.handlePtyCrash('surface-1');
      }
      // 4th crash → give-up
      const result = recovery.handlePtyCrash('surface-1');
      expect(result).toBe('give-up');
    });

    it('tracks retries per surface independently', () => {
      // Exhaust retries for surface-1
      for (let i = 0; i < PTY_RESTART_MAX_RETRIES; i++) {
        recovery.handlePtyCrash('surface-1');
      }
      expect(recovery.handlePtyCrash('surface-1')).toBe('give-up');

      // surface-2 should still be restartable
      expect(recovery.handlePtyCrash('surface-2')).toBe('restart');
    });
  });

  describe('getSurfaceRecoveryInfo', () => {
    it('returns null when surface does not exist', () => {
      const info = recovery.getSurfaceRecoveryInfo('nonexistent');
      expect(info).toBeNull();
    });

    it('returns null when surface has no terminal info', () => {
      // Create a state with a surface that has no terminal property
      const stateWithSurface: AppState = {
        ...store.getState(),
        surfaces: [
          {
            id: 'surf-1',
            panelId: 'panel-1',
            surfaceType: 'terminal',
            title: 'Terminal',
            // no terminal property
          },
        ],
      };
      const storeWithSurface = new AppStateStore(stateWithSurface);
      const recoveryWithSurface = new RecoveryManager(storeWithSurface);

      const info = recoveryWithSurface.getSurfaceRecoveryInfo('surf-1');
      expect(info).toBeNull();
    });

    it('returns cwd and shell when surface has terminal info', () => {
      const stateWithTerminal: AppState = {
        ...store.getState(),
        surfaces: [
          {
            id: 'surf-1',
            panelId: 'panel-1',
            surfaceType: 'terminal',
            title: 'Terminal',
            terminal: {
              pid: 1234,
              cwd: 'C:\\Users\\test',
              shell: 'powershell',
            },
          },
        ],
      };
      const storeWithTerminal = new AppStateStore(stateWithTerminal);
      const recoveryWithTerminal = new RecoveryManager(storeWithTerminal);

      const info = recoveryWithTerminal.getSurfaceRecoveryInfo('surf-1');
      expect(info).not.toBeNull();
      expect(info!.cwd).toBe('C:\\Users\\test');
      expect(info!.shell).toBe('powershell');
    });
  });

  describe('resetRetryCount', () => {
    it('resets counter so surface can be restarted again', () => {
      for (let i = 0; i < PTY_RESTART_MAX_RETRIES; i++) {
        recovery.handlePtyCrash('surface-1');
      }
      expect(recovery.handlePtyCrash('surface-1')).toBe('give-up');

      recovery.resetRetryCount('surface-1');
      expect(recovery.handlePtyCrash('surface-1')).toBe('restart');
    });
  });

  describe('getRetryCount', () => {
    it('returns 0 for unknown surface', () => {
      expect(recovery.getRetryCount('unknown')).toBe(0);
    });

    it('returns current retry count', () => {
      recovery.handlePtyCrash('surface-1');
      recovery.handlePtyCrash('surface-1');
      expect(recovery.getRetryCount('surface-1')).toBe(2);
    });
  });
});
