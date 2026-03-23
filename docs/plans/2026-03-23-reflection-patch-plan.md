# 성찰 패치 구현 계획 v1

> **작성일**: 2026-03-23
> **선행 완료**: Phase 1-2 구현 완료, Phase 3-6 부분 구현
> **설계안 정본**: `2026-03-21-phases-3-to-6-design.md` v3
> **이 문서의 위치**: Phase 3-6 설계안의 **보완 패치** (교체가 아님)

---

## 성찰 요약

2026-03-23 심층 리서치 결과, 기존 Phase 3-6 설계안에 다음 결함이 발견됨:

| # | 결함 | 심각도 | 출처 |
|---|------|--------|------|
| R1 | PTY spawn 시 TMUX/TMUX_PANE/AGENT_TEAMS 환경변수 미주입 | **CRITICAL** | 코드 검증 |
| R2 | Socket 인증(SocketAuth) 정의만 있고 미적용 — API 완전 오픈 | **CRITICAL** | 코드 검증 |
| R3 | Windows isTTY blocker — Claude Code가 tmux 모드를 무시 | **CRITICAL** | GitHub #26244 |
| R4 | XTermWrapper pendingCommand useEffect 의존성 누락 (1회만 실행) | **HIGH** | 코드 검증 |
| R5 | findRealClaude()가 PATH 미등록 설치 탐색 불가 | **HIGH** | 코드 검증 |
| R6 | capture-pane stub — 관찰용, 팀 통신과 무관 (심각도 하향) | **HIGH** | 리서치 |
| R7 | Agent Teams 실제 통신은 inbox JSON 파일 (tmux는 패널 관리만) | **설계 보정** | 리서치 |

---

## 핵심 발견: Claude Code Agent Teams 통신 구조

```
┌─ Layer 1: Inbox/Mailbox (실제 통신 채널) ─────────────────────┐
│  ~/.claude/teams/{team-name}/inboxes/{agent-name}.json       │
│  에이전트 간 SendMessage → 파일 쓰기 → 상대방 폴링 → 읽기     │
│  tmux와 무관하게 동작                                         │
└───────────────────────────────────────────────────────────────┘

┌─ Layer 2: tmux 명령 (패널 수명주기 관리) ─────────────────────┐
│  split-window   → 패널 생성                                   │
│  send-keys      → 초기 명령 전달 (에이전트 CLI 실행)           │
│  kill-pane      → 패널 삭제                                   │
│  list-panes     → 패널 목록 조회                               │
│  display-message → 패널 ID 조회                               │
│  capture-pane   → 터미널 출력 읽기 (관찰용, 통신 아님)         │
└───────────────────────────────────────────────────────────────┘
```

**결론**: capture-pane은 CRITICAL이 아닌 HIGH. 에이전트 팀은 inbox 파일이 핵심.

---

## Task R1: TMUX 환경변수 주입 [CRITICAL]

**Files:**
- Modify: `src/main/terminal/pty-manager.ts` (buildPtyEnv)

### 구현

buildPtyEnv()에 3개 환경변수 추가:

```typescript
// buildPtyEnv() 내부:

// Agent Teams 활성화: Claude Code가 tmux 모드를 인식하도록 설정
env.TMUX = `cmux-win://127.0.0.1:${process.env.CMUX_SOCKET_PORT || '19840'},${process.pid},0`;
env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = '1';

// TMUX_PANE: workspace 내 surface 인덱스로 동적 할당
// surfaceId의 해시 하위 4자리를 인덱스로 사용 (간단하고 충돌 가능성 낮음)
const paneIndex = parseInt(surfaceId.replace(/[^0-9a-f]/gi, '').slice(-4), 16) % 1000;
env.TMUX_PANE = `%${paneIndex}`;
```

### TMUX_PANE 동적 할당 전략

설계안 §4.6의 3가지 방안 중 **실용적 방안** 채택:
- UUID 해시 기반: 충돌 가능성 있으나, Claude Code는 `display-message -p '#{pane_id}'`로 확인하므로 충분
- 정확한 인덱스 필요 시 store에서 workspace별 surface 순서 카운터 관리 (후속 개선)

### 테스트

```typescript
describe('buildPtyEnv TMUX variables', () => {
  it('sets TMUX with socket port and PID', () => {
    const env = buildPtyEnv('surf-1', 'ws-1');
    expect(env.TMUX).toMatch(/^cmux-win:\/\/127\.0\.0\.1:\d+,\d+,0$/);
  });

  it('sets CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1', () => {
    const env = buildPtyEnv('surf-1', 'ws-1');
    expect(env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS).toBe('1');
  });

  it('sets TMUX_PANE with unique index per surfaceId', () => {
    const env1 = buildPtyEnv('surf-aaa', 'ws-1');
    const env2 = buildPtyEnv('surf-bbb', 'ws-1');
    expect(env1.TMUX_PANE).toMatch(/^%\d+$/);
    expect(env2.TMUX_PANE).toMatch(/^%\d+$/);
    expect(env1.TMUX_PANE).not.toBe(env2.TMUX_PANE);
  });
});
```

### 커밋
```
git commit -m "feat(R1): inject TMUX/TMUX_PANE/AGENT_TEAMS env vars in PTY spawn"
```

---

## Task R2: Socket 인증 적용 [CRITICAL]

**Files:**
- Modify: `src/main/socket/server.ts`
- Modify: `src/main/socket/auth.ts`
- Modify: `src/main/index.ts`

### 현재 상태

`SocketAuth` 클래스가 `auth.ts`에 정의되어 있으나, `server.ts`와 `router.ts`에서 **인스턴스화/적용되지 않음**. 모든 Socket 클라이언트가 인증 없이 전체 API 접근 가능.

### 구현

```typescript
// server.ts — createSocketServer() 내부:

import { SocketAuth } from './auth';

// 기본 모드: cmux-only (토큰 기반, 내부 프로세스만 허용)
const auth = new SocketAuth('cmux-only');

// 연결 시 첫 메시지에서 토큰 검증
server.on('connection', (socket) => {
  let authenticated = false;

  socket.on('data', (data) => {
    const msg = JSON.parse(data.toString());

    // 첫 메시지가 auth.handshake가 아니면 거부
    if (!authenticated) {
      if (msg.method === 'auth.handshake' && auth.verify(msg.params?.token)) {
        authenticated = true;
        socket.write(JSON.stringify({ jsonrpc: '2.0', id: msg.id, result: { ok: true } }));
      } else {
        socket.write(JSON.stringify({
          jsonrpc: '2.0', id: msg.id,
          error: { code: -32600, message: 'Authentication required' }
        }));
        socket.destroy();
      }
      return;
    }

    // 인증 후 정상 라우팅
    router.handle(msg, socket);
  });
});
```

```typescript
// auth.ts 보완:

export class SocketAuth {
  private token: string;
  private mode: 'off' | 'cmux-only' | 'automation' | 'password' | 'allow-all';

  constructor(mode: string) {
    this.mode = mode as any;
    // cmux-only: 앱 시작 시 랜덤 토큰 생성, process.env.CMUX_SOCKET_TOKEN에 저장
    this.token = crypto.randomUUID();
    process.env.CMUX_SOCKET_TOKEN = this.token;
  }

  verify(token: string | undefined): boolean {
    if (this.mode === 'off' || this.mode === 'allow-all') return true;
    return token === this.token;
  }
}
```

```typescript
// CLI/shim 측 (claude-wrapper.js, tmux-shim.js, cmux-win.ts):
// process.env.CMUX_SOCKET_TOKEN을 상속받아 연결 시 auth.handshake에 포함
```

### 테스트

```typescript
describe('SocketAuth', () => {
  it('rejects unauthenticated connections in cmux-only mode', () => { ... });
  it('accepts valid token in cmux-only mode', () => { ... });
  it('allows all in off mode', () => { ... });
});
```

### 커밋
```
git commit -m "fix(R2): enforce SocketAuth on socket server — close unauthenticated API"
```

---

## Task R3: Windows isTTY 우회 [CRITICAL]

**Files:**
- Modify: `resources/bin/claude-wrapper.js`

### 문제

Claude Code issue [#26244]: Windows에서 `process.stdout.isTTY`가 Bun SFE 바이너리에서 항상 `undefined` → `isInProcessEnabled()` = `true` → tmux split-pane 모드 강제 무시.

### 우회 방안

claude-wrapper.js에서 `--settings` JSON에 `teammateMode: "tmux"`를 명시적으로 주입:

```javascript
// claude-wrapper.js — hooks JSON 생성 시:
const settings = {
  hooks: { ... }, // 기존 6개 hook
  teammateMode: 'tmux', // R3: Windows isTTY 우회 — tmux 모드 강제
};

const child = spawnChild(realClaude, [
  '--session-id', sessionId,
  '--settings', JSON.stringify(settings),
  ...args,
], { stdio: 'inherit', env });
```

### 대안 (Claude Code 측 수정 대기)

Claude Code가 `TMUX` 환경변수 존재 시 isTTY 체크를 건너뛰도록 수정되면 이 우회는 불필요. 하지만 현재는 필수.

### 테스트

```typescript
describe('claude-wrapper hook JSON', () => {
  it('includes teammateMode: tmux in settings', () => {
    const hooks = buildHookJson(cliPath);
    expect(hooks.teammateMode).toBe('tmux');
  });
});
```

### 커밋
```
git commit -m "fix(R3): force teammateMode:tmux in claude-wrapper — bypass Windows isTTY blocker"
```

---

## Task R4: pendingCommand useEffect 의존성 수정 [HIGH]

**Files:**
- Modify: `src/renderer/components/terminal/XTermWrapper.tsx`

### 문제

`useEffect`가 `[surfaceId]`에만 의존하여 pendingCommand를 PTY spawn 시 1회만 실행. 이후 `surface.update_meta`로 pendingCommand가 갱신되어도 무시됨.

### 구현

pendingCommand 실행을 별도 useEffect로 분리:

```typescript
// 기존 main useEffect에서 pendingCommand 실행 코드 제거

// 별도 useEffect: pendingCommand 변경 감지 → 실행 → 소비
useEffect(() => {
  if (!pendingCommand || !terminalRef.current) return;

  // PTY가 준비된 후에만 실행
  window.ptyBridge?.write(surfaceId, pendingCommand);

  // 소비: pendingCommand를 null로 설정
  void dispatch({
    type: 'surface.update_meta',
    payload: { surfaceId, pendingCommand: null },
  });
}, [pendingCommand, surfaceId, dispatch]);
```

### 테스트

기존 agent-spawn.test.ts에 케이스 추가:
```typescript
it('executes pendingCommand when surface.update_meta changes it', () => { ... });
```

### 커밋
```
git commit -m "fix(R4): separate pendingCommand useEffect — react to update_meta changes"
```

---

## Task R5: findRealClaude() 탐색 경로 보강 [HIGH]

**Files:**
- Modify: `resources/bin/claude-wrapper-lib.js`

### 문제

`where claude`만으로는 PATH에 등록되지 않은 설치 (npm global in AppData, scoop, winget 등)를 찾지 못함.

### 구현

```javascript
function findRealClaude(myDir, execSyncFn) {
  const candidates = [];

  // 1. where claude (기존)
  try {
    const result = execSyncFn('where claude 2>nul', { encoding: 'utf8' });
    candidates.push(...result.trim().split(/\r?\n/).map(s => s.trim()).filter(Boolean));
  } catch { /* where failed */ }

  // 2. npm global (AppData\Roaming\npm)
  const npmGlobal = path.join(
    process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'),
    'npm', 'claude.cmd'
  );
  if (fs.existsSync(npmGlobal)) candidates.push(npmGlobal);

  // 3. scoop
  const scoop = path.join(os.homedir(), 'scoop', 'shims', 'claude.cmd');
  if (fs.existsSync(scoop)) candidates.push(scoop);

  // 4. %LOCALAPPDATA%\Programs (winget 등)
  const localPrograms = path.join(
    process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'),
    'Programs', 'claude', 'claude.exe'
  );
  if (fs.existsSync(localPrograms)) candidates.push(localPrograms);

  // 자기 자신 제외
  const myDirNorm = myDir.toLowerCase().replace(/\\/g, '/');
  for (const p of candidates) {
    const dir = path.dirname(p).toLowerCase().replace(/\\/g, '/');
    if (dir !== myDirNorm) return p;
  }
  return null;
}
```

### 테스트

기존 claude-wrapper.test.ts에 케이스 추가:
```typescript
it('finds claude in npm global path when not in PATH', () => { ... });
it('finds claude in scoop shims', () => { ... });
```

### 커밋
```
git commit -m "fix(R5): findRealClaude() — search npm global, scoop, winget paths"
```

---

## Task R6: capture-pane → surface.read 구현 [HIGH]

**Files:**
- Modify: `src/main/socket/handlers/surface.ts` — `surface.read` RPC 추가
- Modify: `src/preload/index.ts` — scrollback 읽기 IPC
- Modify: `resources/bin/tmux-shim.js` — capture-pane stub → surface.read 호출

### 구현

```typescript
// surface.ts — surface.read RPC:
router.register('surface.read', async (params) => {
  const p = params as { surfaceId: string; lines?: number };
  if (!p?.surfaceId) throw new Error('surfaceId is required');

  // scrollbackStore에서 캐시된 내용 반환 (Task S3에서 구현된 scrollback persistence)
  const content = scrollbackStore.get(p.surfaceId) ?? '';

  // lines 제한
  if (p.lines && p.lines > 0) {
    const allLines = content.split('\n');
    return { content: allLines.slice(-p.lines).join('\n') };
  }
  return { content };
});
```

```javascript
// tmux-shim.js — capture-pane 수정:
case 'capture-pane': {
  const target = getTarget();
  let surfaceId = process.env.CMUX_SURFACE_ID;
  if (target) {
    // target 해석 (기존 send-keys와 동일)
    if (target.startsWith('%')) {
      const panels = await rpcCall('panel.list', {});
      const panel = Array.isArray(panels) ? panels[parseInt(target.slice(1))] : null;
      if (panel) surfaceId = panel.activeSurfaceId;
    } else {
      surfaceId = target;
    }
  }
  const result = await rpcCall('surface.read', { surfaceId });
  console.log(result?.content ?? '');
  break;
}
```

### 테스트

```typescript
describe('surface.read', () => {
  it('returns scrollback content for existing surface', () => { ... });
  it('returns empty string for unknown surface', () => { ... });
  it('respects lines limit', () => { ... });
});
```

### 커밋
```
git commit -m "feat(R6): surface.read RPC + capture-pane implementation"
```

---

## 실행 순서

```
R1 (TMUX env vars)  ─┐
R2 (Socket auth)     ├→ 동시 가능, 의존 관계 없음
R3 (isTTY bypass)   ─┘

R4 (pendingCommand)  ─→ R1 완료 후 (agent.spawn이 TMUX env를 사용)
R5 (findRealClaude)  ─→ 독립

R6 (capture-pane)    ─→ R1 완료 후 (팀 활성화 후 의미 있음)
```

**추천 순서**: R1 → R3 → R2 → R4 → R5 → R6

---

## 기존 설계안과의 관계

| 기존 설계안 항목 | 이 패치의 영향 |
|----------------|--------------|
| Phase 4 §4.1 Task 16 (환경변수 주입) | R1이 **TMUX 3종 추가** 보완 |
| Phase 4 §4.2 Task 17 (claude-wrapper) | R3이 **teammateMode 추가** 보완, R5가 **경로 탐색 보강** |
| Phase 4 §4.6 Task 21 (tmux shim) | R6이 **capture-pane stub → 실구현** 교체 |
| Phase 4 §4.7 Task 22 (agent.spawn) | R4가 **pendingCommand 버그 수정** |
| Phase 3-6 Socket 보안 | R2가 **미적용 인증 활성화** |
| Phase 5 §5.4 Task 31 (scrollback) | R6이 scrollbackStore 활용 (이미 구현됨) |

---

## 완료 체크리스트

```
[ ] R1: buildPtyEnv에 TMUX, TMUX_PANE, AGENT_TEAMS 추가
[ ] R2: SocketAuth 인스턴스화 + server.ts 연결 핸들러에 인증 적용
[ ] R2: CLI/shim에 CMUX_SOCKET_TOKEN 전달
[ ] R3: claude-wrapper.js settings에 teammateMode:"tmux" 추가
[ ] R4: XTermWrapper pendingCommand를 별도 useEffect로 분리
[ ] R5: findRealClaude()에 npm global, scoop, winget 경로 추가
[ ] R6: surface.read RPC 등록 (scrollbackStore 활용)
[ ] R6: tmux-shim.js capture-pane → surface.read 호출
[ ] 전체 테스트 ALL PASS
```
