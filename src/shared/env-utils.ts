export function buildPtyEnv(
  surfaceId: string,
  workspaceId: string | undefined,
  baseEnv: Record<string, string>,
): Record<string, string> {
  const env = { ...baseEnv };
  env.CMUX_SURFACE_ID = surfaceId;
  if (workspaceId) env.CMUX_WORKSPACE_ID = workspaceId;
  const binDir = env.CMUX_BIN_DIR || '';
  if (binDir) {
    const sep = process.platform === 'win32' ? ';' : ':';
    env.PATH = binDir + sep + (env.PATH || '');
  }

  // R1: Agent Teams env vars — set CMUX-specific vars here.
  // TMUX/TMUX_PANE/AGENT_TEAMS are injected by claude-wrapper.js only when
  // Claude Code is actually invoked, to avoid interfering with normal shell
  // commands (e.g. real tmux, git, etc. that check $TMUX).
  const socketPort = env.CMUX_SOCKET_PORT || '19840';
  env.CMUX_SOCKET_ADDR = `tcp://127.0.0.1:${socketPort}`;
  env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1';
  // TMUX_PANE index for this surface (used by claude-wrapper to set TMUX_PANE)
  const paneIndex = parseInt(surfaceId.replace(/[^0-9a-f]/gi, '').slice(-4) || '0', 16) % 1000;
  env.CMUX_PANE_INDEX = `${paneIndex}`;

  return env;
}
