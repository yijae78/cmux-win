import { describe, it, expect } from 'vitest';
import { getShellIntegrationArgs } from '../../../src/shared/shell-integration-utils';

describe('getShellIntegrationArgs', () => {
  const dir = '/app/shell-integration';

  it('powershell: returns -NoExit -Command dot-source', () => {
    const result = getShellIntegrationArgs('powershell', dir);
    expect(result.args).toHaveLength(3);
    expect(result.args[0]).toBe('-NoExit');
    expect(result.args[2]).toContain('powershell.ps1');
  });

  it('pwsh: treated as powershell', () => {
    const result = getShellIntegrationArgs('pwsh', dir);
    expect(result.args[0]).toBe('-NoExit');
  });

  it('bash: returns --rcfile and sets env', () => {
    const result = getShellIntegrationArgs('bash', dir);
    expect(result.args).toEqual(['--rcfile', expect.stringContaining('bash.sh')]);
    expect(result.env.CMUX_SHELL_INTEGRATION).toBe('1');
  });

  it('wsl: uses WSL-specific integration script', () => {
    const result = getShellIntegrationArgs('wsl', dir);
    expect(result.args).toEqual(['--rcfile', expect.stringContaining('cmux-wsl-integration.sh')]);
    expect(result.env.CMUX_SHELL_INTEGRATION).toBe('1');
  });

  it('git-bash: treated as bash', () => {
    const result = getShellIntegrationArgs('git-bash', dir);
    expect(result.args[0]).toBe('--rcfile');
  });

  it('cmd: returns /k with CMD integration script', () => {
    const result = getShellIntegrationArgs('cmd', dir);
    expect(result.args).toEqual(['/k', expect.stringContaining('cmux-cmd-integration.cmd')]);
    expect(result.env.CMUX_SHELL_INTEGRATION).toBe('1');
  });

  it('unknown shell: returns empty', () => {
    const result = getShellIntegrationArgs('fish', dir);
    expect(result.args).toEqual([]);
  });
});
