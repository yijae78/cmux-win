import path from 'node:path';

export function getShellIntegrationArgs(
  shell: string,
  integrationDir: string,
): { args: string[]; env: Record<string, string> } {
  const env: Record<string, string> = {};
  const shellLower = shell.toLowerCase();

  if (shellLower === 'powershell' || shellLower.includes('pwsh')) {
    const psScript = path.join(integrationDir, 'powershell.ps1');
    return { args: ['-ExecutionPolicy', 'Bypass', '-NoExit', '-Command', `. '${psScript}'`], env };
  }

  if (shellLower === 'wsl') {
    const wslScript = path.join(integrationDir, 'wsl', 'cmux-wsl-integration.sh');
    env.CMUX_SHELL_INTEGRATION = '1';
    env.CMUX_SHELL_INTEGRATION_DIR = integrationDir;
    return { args: ['--rcfile', wslScript], env };
  }

  if (shellLower === 'bash' || shellLower === 'git-bash' || shellLower.includes('bash')) {
    const bashScript = path.join(integrationDir, 'bash.sh');
    env.CMUX_SHELL_INTEGRATION = '1';
    env.CMUX_SHELL_INTEGRATION_DIR = integrationDir;
    return { args: ['--rcfile', bashScript], env };
  }

  if (shellLower === 'cmd' || shellLower.includes('cmd.exe')) {
    const cmdScript = path.join(integrationDir, 'cmd', 'cmux-cmd-integration.cmd');
    env.CMUX_SHELL_INTEGRATION = '1';
    return { args: ['/k', cmdScript], env };
  }

  // Other: no integration
  return { args: [], env };
}
