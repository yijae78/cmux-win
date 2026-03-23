/**
 * Process-level PID status check.
 *
 * Uses `process.kill(pid, 0)` (signal 0 = no signal, just check existence).
 * Works on both Windows and POSIX Node.js runtimes.
 *
 * @returns 'alive' | 'dead' | 'no_permission'
 */
export function checkPidStatus(pid: number): 'alive' | 'dead' | 'no_permission' {
  try {
    process.kill(pid, 0);
    return 'alive';
  } catch (err: unknown) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === 'ESRCH') return 'dead';
    if (code === 'EPERM') return 'no_permission'; // F17: process exists, insufficient permissions
    return 'dead'; // any other error treated as dead
  }
}
