# Phase 5: 셸 통합 + 원격 — 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** PowerShell/CMD/WSL/Git Bash 셸 통합(CWD, Git 정보), OSC 133 프롬프트 감지, SSH 기본 원격, 세션 스크롤백 저장/복원을 구현한다.

**Architecture:** 셸 통합 스크립트가 OSC 시퀀스를 터미널에 주입하고, XTermWrapper가 커스텀 핸들러로 파싱하여 surface.update_meta Action으로 Store를 업데이트한다.

**Tech Stack:** PowerShell, Bash, xterm.js parser API, node-pty, ssh2 (폴백)

**선행 조건:** Phase 1-2, Phase 4 완료 (237 tests)
**설계안 정본:** `2026-03-21-phases-3-to-6-design.md` v3

---

## 의존성 그래프

```
Task 28 (셸 통합 스크립트)
  └─→ Task 29 (OSC 133 감지)

Task 30 (SSH 기본) ← 독립
Task 31 (스크롤백 저장/복원) ← 독립

실행 순서: 28 → 29, 그리고 30, 31 병렬
```

---

## Task 28: 셸 프롬프트 통합

**Files:**
- Create: `resources/shell-integration/powershell.ps1`
- Create: `resources/shell-integration/bash.sh`
- Create: `src/shared/shell-integration-utils.ts`
- Modify: `src/preload/index.ts` — 셸 통합 env 추가
- Test: `tests/unit/shared/shell-integration-utils.test.ts`

### Step 1: powershell.ps1

```powershell
# cmux-win PowerShell integration
# Injects OSC 133 prompt markers + CWD + Git info

function cmux_prompt_start {
  $e = [char]0x1b
  # OSC 133;A — prompt start
  Write-Host -NoNewline "${e}]133;A${e}\"
  # OSC 7 — CWD
  $cwdUri = "file://localhost/" + ($PWD.Path -replace '\\','/' -replace ' ','%20')
  Write-Host -NoNewline "${e}]7;${cwdUri}${e}\"
  # Git info
  $branch = git branch --show-current 2>$null
  if ($branch) {
    $dirty = ''
    if (git status --porcelain 2>$null) { $dirty = '*' }
    Write-Host -NoNewline "${e}]133;P;k=git_branch;v=${branch}${dirty}${e}\"
  }
}

function cmux_prompt_end {
  $e = [char]0x1b
  Write-Host -NoNewline "${e}]133;B${e}\"
}

# Override prompt function
$_cmux_original_prompt = $function:prompt
function prompt {
  cmux_prompt_start
  $result = & $_cmux_original_prompt
  cmux_prompt_end
  return $result
}
```

### Step 2: bash.sh

```bash
#!/bin/bash
# cmux-win Bash integration (WSL / Git Bash)

cmux_precmd() {
  local e=$'\e'
  # OSC 133;A — prompt start
  printf '%s]133;A%s\\' "$e" "$e"
  # OSC 7 — CWD
  printf '%s]7;file://localhost%s%s\\' "$e" "$PWD" "$e"
  # Git info
  local branch
  branch=$(git branch --show-current 2>/dev/null)
  if [ -n "$branch" ]; then
    local dirty=""
    if [ -n "$(git status --porcelain 2>/dev/null | head -1)" ]; then
      dirty="*"
    fi
    printf '%s]133;P;k=git_branch;v=%s%s%s\\' "$e" "$branch" "$dirty" "$e"
  fi
}

# Inject into PROMPT_COMMAND
if [[ ! "$PROMPT_COMMAND" == *"cmux_precmd"* ]]; then
  PROMPT_COMMAND="cmux_precmd;${PROMPT_COMMAND:-}"
fi
```

### Step 3: shell-integration-utils.ts (로딩 메커니즘)

```typescript
// src/shared/shell-integration-utils.ts
import path from 'node:path';

export function getShellIntegrationArgs(
  shell: string,
  integrationDir: string,
): { args: string[]; env: Record<string, string> } {
  const env: Record<string, string> = {};

  if (shell === 'powershell' || shell.includes('pwsh')) {
    const psScript = path.join(integrationDir, 'powershell.ps1');
    return {
      args: ['-NoExit', '-Command', `. '${psScript}'`],
      env,
    };
  }

  if (shell === 'bash' || shell === 'wsl' || shell === 'git-bash' || shell.includes('bash')) {
    env.CMUX_SHELL_INTEGRATION = '1';
    env.CMUX_SHELL_INTEGRATION_DIR = integrationDir;
    const bashScript = path.join(integrationDir, 'bash.sh');
    return {
      args: ['--rcfile', bashScript],
      env,
    };
  }

  // CMD / other: no integration
  return { args: [], env };
}
```

### Step 4: preload spawn 수정

셸 통합 스크립트를 자동 로드하도록 spawn에서 env와 args를 추가.

### Step 5: 테스트

```typescript
describe('getShellIntegrationArgs', () => {
  it('powershell: returns -NoExit -Command dot-source');
  it('bash: returns --rcfile and sets CMUX_SHELL_INTEGRATION');
  it('cmd: returns empty args and env');
  it('wsl: treated as bash');
  it('git-bash: treated as bash');
});
```

### Step 6: 커밋

---

## Task 29: OSC 133 프롬프트 감지

**Files:**
- Modify: `src/shared/types.ts` — SurfaceState.terminal 확장
- Modify: `src/shared/actions.ts` — SurfaceUpdateMetaAction 추가
- Modify: `src/main/sot/store.ts` — surface.update_meta applyAction
- Modify: `src/renderer/components/terminal/XTermWrapper.tsx` — OSC 핸들러 등록
- Test: `tests/unit/shared/osc-parser.test.ts`

### Step 1: types.ts 확장

```typescript
export interface SurfaceState {
  // 기존 필드...
  terminal?: {
    pid: number;
    cwd: string;
    shell: string;
    gitBranch?: string;
    gitDirty?: boolean;
    exitCode?: number;
  };
}
```

### Step 2: SurfaceUpdateMetaAction 추가

```typescript
export const SurfaceUpdateMetaAction = z.object({
  type: z.literal('surface.update_meta'),
  payload: z.object({
    surfaceId: z.string(),
    title: z.string().optional(),
    pendingCommand: z.string().nullable().optional(),
    browser: z.object({
      url: z.string().optional(),
      isLoading: z.boolean().optional(),
    }).optional(),
    terminal: z.object({
      cwd: z.string().optional(),
      gitBranch: z.string().optional(),
      gitDirty: z.boolean().optional(),
      exitCode: z.number().optional(),
    }).optional(),
  }),
});
```

ActionSchema union에 추가.

### Step 3: store.ts applyAction

```typescript
case 'surface.update_meta': {
  const surface = draft.surfaces.find(s => s.id === action.payload.surfaceId);
  if (!surface) break;
  if (action.payload.title !== undefined) surface.title = action.payload.title;
  if (action.payload.pendingCommand !== undefined) {
    surface.pendingCommand = action.payload.pendingCommand ?? undefined;
  }
  if (action.payload.terminal) {
    surface.terminal = { ...surface.terminal, ...action.payload.terminal } as any;
  }
  if (action.payload.browser) {
    surface.browser = { ...surface.browser, ...action.payload.browser } as any;
  }
  break;
}
```

### Step 4: XTermWrapper OSC 핸들러

```typescript
// initPty 완료 후, F24:
terminal.parser.registerOscHandler(133, (data) => {
  if (data.startsWith('P;')) {
    // k=git_branch;v=main* 파싱
    const params: Record<string, string> = {};
    data.slice(2).split(';').forEach(kv => {
      const [k, v] = kv.split('=');
      if (k && v) params[k] = v;
    });
    if (params.k === 'git_branch') {
      const dirty = params.v?.endsWith('*') || false;
      const branch = dirty ? params.v.slice(0, -1) : params.v;
      dispatch?.({ type: 'surface.update_meta', payload: {
        surfaceId, terminal: { gitBranch: branch, gitDirty: dirty },
      }});
    }
  }
  return true;
});

terminal.parser.registerOscHandler(7, (data) => {
  try {
    const url = new URL(data);
    const cwd = decodeURIComponent(url.pathname);
    dispatch?.({ type: 'surface.update_meta', payload: {
      surfaceId, terminal: { cwd },
    }});
  } catch {}
  return true;
});
```

XTermWrapperProps에 `dispatch` 추가 필요 → PanelContainer에서 전달.

### Step 5: OSC 파싱 로직 테스트

```typescript
// 파싱 로직을 pure 함수로 추출하여 테스트
describe('parseOsc133', () => {
  it('parses git_branch without dirty');
  it('parses git_branch with dirty marker');
  it('ignores unknown keys');
});
describe('parseOsc7', () => {
  it('extracts CWD from file URL');
  it('handles URL-encoded spaces');
  it('returns null for invalid URL');
});
```

### Step 6: 커밋

---

## Task 30: SSH 기본

**Files:**
- Create: `src/main/remote/ssh-session.ts`
- Modify: `src/cli/cmux-win.ts` — ssh 서브명령 추가
- Test: `tests/unit/remote/ssh-session.test.ts`

### 구현

```typescript
// src/main/remote/ssh-session.ts
// 1. ssh.exe 존재 확인: where ssh
// 2. 있으면: node-pty + ssh.exe (네이티브)
// 3. 없으면: 에러 메시지 ("SSH client not available. Install OpenSSH.")
// 4. 연결 끊김 감지: PTY exit → 재시도 (backoff)
// ssh2 폴백은 Phase 6으로 연기 (복잡도 과다)

export function createSshPtyArgs(host: string, port?: number, user?: string): {
  shell: string;
  args: string[];
} {
  const sshArgs = [];
  if (port) sshArgs.push('-p', String(port));
  if (user) sshArgs.push('-l', user);
  sshArgs.push(host);
  return { shell: 'ssh', args: sshArgs };
}

export function parseSshTarget(target: string): { user?: string; host: string; port?: number } {
  // user@host:port 또는 host 또는 user@host
  const match = target.match(/^(?:([^@]+)@)?([^:]+)(?::(\d+))?$/);
  if (!match) throw new Error(`Invalid SSH target: ${target}`);
  return { user: match[1], host: match[2], port: match[3] ? parseInt(match[3]) : undefined };
}
```

### CLI ssh 명령

```typescript
case 'ssh': {
  const target = positional[0];
  if (!target) { console.error('Usage: cmux-win ssh user@host[:port]'); process.exit(1); }
  // workspace 생성 + ssh 실행은 Socket API 경유
  // 간단 구현: workspace.create + surface에 ssh 명령 send
  break;
}
```

### 테스트

```typescript
describe('parseSshTarget', () => {
  it('parses user@host');
  it('parses host only');
  it('parses user@host:port');
  it('throws on invalid target');
});
```

### 커밋

---

## Task 31: 세션 스크롤백 저장/복원

**Files:**
- Create: `src/shared/scrollback-utils.ts`
- Modify: `src/main/sot/middleware/persistence.ts` — scrollback 저장
- Modify: `src/renderer/components/terminal/XTermWrapper.tsx` — scrollback 복원
- Test: `tests/unit/shared/scrollback-utils.test.ts`

### 구현

```typescript
// src/shared/scrollback-utils.ts
const MAX_SCROLLBACK_LINES = 10000;
const MAX_SCROLLBACK_BYTES = 1_000_000; // 1MB

export function extractScrollback(buffer: any, rows: number): string {
  // xterm.js buffer에서 텍스트 추출
  const lines: string[] = [];
  const totalRows = buffer.length;
  const startRow = Math.max(0, totalRows - MAX_SCROLLBACK_LINES);
  for (let i = startRow; i < totalRows; i++) {
    const line = buffer.getLine(i);
    if (line) lines.push(line.translateToString(true));
  }
  let result = lines.join('\n');
  if (result.length > MAX_SCROLLBACK_BYTES) {
    result = result.slice(-MAX_SCROLLBACK_BYTES);
  }
  return result;
}
```

### 저장 (persistence middleware)

앱 종료 시 각 terminal surface의 scrollback을 JSON에 포함.

### 복원 (XTermWrapper)

mount 시 scrollback 데이터가 있으면 `terminal.write(scrollback)`.

### 테스트

```typescript
describe('scrollback-utils', () => {
  it('limits to MAX_SCROLLBACK_LINES');
  it('limits to MAX_SCROLLBACK_BYTES');
  it('handles empty buffer');
});
```

---

## Phase 5 완료 체크리스트

```
[ ] PowerShell 통합: OSC 133 + CWD + Git
[ ] Bash 통합 (WSL/Git Bash): PROMPT_COMMAND injection
[ ] OSC 133 파싱: XTermWrapper 커스텀 핸들러
[ ] surface.update_meta Action 동작
[ ] CWD/gitBranch 사이드바 표시 가능
[ ] SSH: cmux-win ssh user@host 기본 동작
[ ] 스크롤백 저장: 앱 종료 시 buffer 덤프
[ ] 스크롤백 복원: 앱 시작 시 write
[ ] 전체 테스트 ALL PASS
```
