export function buildPtyEnv(
  surfaceId: string,
  workspaceId: string | undefined,
  baseEnv: Record<string, string>,
  paneIndex?: number,
): Record<string, string> {
  const env = { ...baseEnv };
  env.CMUX_SURFACE_ID = surfaceId;
  if (workspaceId) env.CMUX_WORKSPACE_ID = workspaceId;
  const binDir = env.CMUX_BIN_DIR || '';
  if (binDir) {
    const sep = process.platform === 'win32' ? ';' : ':';
    env.PATH = binDir + sep + (env.PATH || '');

    // On Windows, .EXE always beats .CMD in PATH resolution regardless of order.
    // Override PATHEXT so .CMD is checked before .EXE, ensuring our tmux.cmd
    // shim is found instead of a real tmux.exe that may exist in the user's PATH.
    if (process.platform === 'win32') {
      const pathext = env.PATHEXT || '.COM;.EXE;.BAT;.CMD';
      // Move .CMD before .EXE
      const parts = pathext.split(';').filter(Boolean);
      const cmdIdx = parts.findIndex(p => p.toUpperCase() === '.CMD');
      const exeIdx = parts.findIndex(p => p.toUpperCase() === '.EXE');
      if (cmdIdx > exeIdx && exeIdx >= 0) {
        parts.splice(cmdIdx, 1);
        parts.splice(exeIdx, 0, '.CMD');
      }
      env.PATHEXT = parts.join(';');
    }
  }

  // R1: Agent Teams env vars — set CMUX-specific vars here.
  // TMUX/TMUX_PANE/AGENT_TEAMS are injected by claude-wrapper.js only when
  // Claude Code is actually invoked, to avoid interfering with normal shell
  // commands (e.g. real tmux, git, etc. that check $TMUX).
  const socketPort = env.CMUX_SOCKET_PORT || '19840';
  env.CMUX_SOCKET_ADDR = `tcp://127.0.0.1:${socketPort}`;
  env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1';
  // F3-FIX: Use store's monotonic paneIndex (matches tmux shim resolvePane).
  // Previously derived from UUID hash, which created a mismatch with
  // store.nextPaneIndex() — causing send-keys to target wrong panels.
  env.CMUX_PANE_INDEX = `${paneIndex ?? 0}`;

  // BUG-C fix: explicitly propagate socket auth token so child processes
  // can authenticate to the socket server even if process.env is filtered.
  if (baseEnv.CMUX_SOCKET_TOKEN) {
    env.CMUX_SOCKET_TOKEN = baseEnv.CMUX_SOCKET_TOKEN;
  }

  return env;
}
