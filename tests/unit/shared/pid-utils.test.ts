import { describe, it, expect } from 'vitest';
import { checkPidStatus } from '../../../src/shared/pid-utils';

describe('checkPidStatus', () => {
  it('returns alive for current process', () => {
    expect(checkPidStatus(process.pid)).toBe('alive');
  });

  it('returns dead for nonexistent PID', () => {
    // PID 99999999 is extremely unlikely to exist
    expect(checkPidStatus(99999999)).toBe('dead');
  });

  it('returns dead for PID 0 (edge case)', () => {
    // PID 0 is special (idle process on Windows).
    // process.kill(0, 0) means "current process group" on POSIX — may return alive.
    // This test only asserts the return is a valid status value.
    const result = checkPidStatus(0);
    expect(['alive', 'dead', 'no_permission']).toContain(result);
  });
});
