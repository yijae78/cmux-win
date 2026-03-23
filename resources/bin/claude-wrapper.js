#!/usr/bin/env node
'use strict';

const { spawn: spawnChild } = require('child_process');
const crypto = require('crypto');
const path = require('path');
const { buildHookJson, shouldBypass, findRealClaude, socketAlive } = require('./claude-wrapper-lib');

const args = process.argv.slice(2);

function passthrough() {
  const real = findRealClaude(
    __dirname,
    require('child_process').execSync,
  );
  // S2: Claude 미설치 시 무한 루프 방지
  if (!real) {
    process.stderr.write(
      'cmux-win: Claude Code not found.\n' +
      'Install: npm install -g @anthropic-ai/claude-code\n' +
      'Or download from: https://claude.ai/download\n'
    );
    process.exit(127);
    return;
  }
  const child = spawnChild(real, args, { stdio: 'inherit' });
  child.on('exit', (code) => process.exit(code ?? 0));
  child.on('error', (err) => {
    process.stderr.write(`cmux-win: failed to start claude: ${err.message}\n`);
    process.exit(127);
  });
}

(async () => {
  // 1. cmux 외부면 통과
  if (!process.env.CMUX_SURFACE_ID) return passthrough();

  // 2. Hook 비활성화면 통과
  if (process.env.CMUX_CLAUDE_HOOKS_DISABLED === '1') return passthrough();

  // 3. bypass 서브명령
  if (shouldBypass(args)) return passthrough();

  // 4. Socket ping
  const port = parseInt(process.env.CMUX_SOCKET_PORT || '19840', 10);
  const alive = await socketAlive(port);
  if (!alive) return passthrough();

  // 5. UUID 생성
  const sessionId = crypto.randomUUID();

  // 6. CLI 경로
  const cliPath = process.env.CMUX_CLI_PATH
    || path.join(__dirname, '../../out/cli/cmux-win.js');

  // 7. Hook JSON
  const hooks = buildHookJson(cliPath);

  // 8. 실제 claude 찾기
  const realClaude = findRealClaude(
    __dirname,
    require('child_process').execSync,
  );
  if (!realClaude) return passthrough();

  // 9. 실행 — inject TMUX vars HERE (not in PTY env, to avoid interfering with normal shell)
  const socketPort = process.env.CMUX_SOCKET_PORT || '19840';
  const paneIndex = process.env.CMUX_PANE_INDEX || '0';
  const env = {
    ...process.env,
    CMUX_CLAUDE_PID: String(process.pid),
    TMUX: `cmux-win://127.0.0.1:${socketPort},${process.pid},0`,
    TMUX_PANE: `%${paneIndex}`,
  };
  delete env.CLAUDECODE;

  const child = spawnChild(realClaude, [
    '--session-id', sessionId,
    '--settings', JSON.stringify(hooks),
    ...args,
  ], { stdio: 'inherit', env });

  // F13: error 시 exit 리스너 제거 후 passthrough
  const onExit = (code) => process.exit(code ?? 0);
  child.on('exit', onExit);
  child.on('error', () => {
    child.removeListener('exit', onExit);
    passthrough();
  });

})().catch(() => passthrough());
