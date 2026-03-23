'use strict';

const path = require('path');
const fs = require('fs');
const os = require('os');

const BYPASS_SUBCOMMANDS = ['mcp', 'config', 'api-key', 'rc', 'remote-control'];

/**
 * Hook JSON 생성
 * @param {string} cliPath - cmux-win CLI 경로
 * @returns {object} hooks 설정 객체
 */
function buildHookJson(cliPath) {
  const makeCmd = (sub) => `node "${cliPath}" claude-hook ${sub}`;
  return {
    // R3: force tmux teammate mode — bypass Windows isTTY blocker (#26244)
    teammateMode: 'tmux',
    hooks: {
      SessionStart: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('session-start'), timeout: 10 }] }],
      Stop: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('stop'), timeout: 10 }] }],
      SessionEnd: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('session-end'), timeout: 1 }] }],
      Notification: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('notification'), timeout: 10 }] }],
      UserPromptSubmit: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('prompt-submit'), timeout: 10 }] }],
      PreToolUse: [{ matcher: '', hooks: [
        { type: 'command', command: makeCmd('pre-tool-use'), timeout: 5, async: true }] }],
    },
  };
}

/**
 * bypass할 서브명령인지 확인
 * @param {string[]} args - CLI 인자
 * @returns {boolean}
 */
function shouldBypass(args) {
  return args.length > 0 && BYPASS_SUBCOMMANDS.includes(args[0]);
}

/**
 * 실제 claude 바이너리 찾기 (자기 자신 제외)
 * @param {string} myDir - 현재 wrapper가 있는 디렉토리 (lowercase, forward slashes)
 * @param {function} execSyncFn - child_process.execSync 함수 (테스트용 DI)
 * @returns {string|null}
 */
/**
 * B2: 실제 claude 바이너리 찾기.
 * 자기 자신 제외: 경로 문자열 비교 대신 claude-wrapper.js 마커 파일 존재로 식별.
 * OneDrive 한글 경로의 Unicode NFC/NFD 불일치를 완전히 회피.
 */
function findRealClaude(myDir, execSyncFn) {
  const candidates = [];

  // 1. where claude (PATH 검색)
  try {
    const result = execSyncFn('where claude 2>nul', { encoding: 'utf8' })
      .trim().split(/\r?\n/);
    candidates.push(...result.map(s => s.trim()).filter(Boolean));
  } catch { /* where failed */ }

  // 2. 직접 경로 탐색 (where 실패 또는 PATH 미등록 대비)
  const homedir = os.homedir();
  const appData = process.env.APPDATA || path.join(homedir, 'AppData', 'Roaming');
  const localAppData = process.env.LOCALAPPDATA || path.join(homedir, 'AppData', 'Local');

  const directPaths = [
    path.join(homedir, '.local', 'bin', 'claude.exe'),
    path.join(appData, 'npm', 'claude.cmd'),
    path.join(homedir, 'scoop', 'shims', 'claude.cmd'),
    path.join(localAppData, 'Programs', 'claude', 'claude.exe'),
  ];
  for (const p of directPaths) {
    if (fs.existsSync(p) && !candidates.includes(p)) candidates.push(p);
  }

  // 3. 자기 자신 제외 — claude-wrapper.js 마커 파일로 래퍼 디렉토리 식별
  for (const p of candidates) {
    if (!p) continue;
    const dir = path.dirname(p);
    const wrapperMarker = path.join(dir, 'claude-wrapper.js');
    if (fs.existsSync(wrapperMarker)) continue; // 래퍼 디렉토리 → 건너뜀
    return p;
  }
  return null;
}

/**
 * cmux-win이 실행 중인지 socket ping으로 확인
 * @param {number} port
 * @returns {Promise<boolean>}
 */
function socketAlive(port) {
  const net = require('net');
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(750);
    socket.connect(port, '127.0.0.1', () => { socket.destroy(); resolve(true); });
    socket.on('error', () => { socket.destroy(); resolve(false); });
    socket.on('timeout', () => { socket.destroy(); resolve(false); });
  });
}

module.exports = { buildHookJson, shouldBypass, findRealClaude, socketAlive, BYPASS_SUBCOMMANDS };
