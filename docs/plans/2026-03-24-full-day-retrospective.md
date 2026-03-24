# 2026-03-24 전일 성찰 보고서 + 설계안 반영

> **작성일**: 2026-03-24
> **범위**: 텔레그램 연동, 파일 탐색기, 패널 DnD, AI CLI 협업, 터미널 간 통신
> **핵심 성과**: Claude CLI가 cmux-win 앱 안에서 tmux shim으로 터미널을 제어하고, 3개 AI가 코딩 협업에 성공

---

## 1. 심층 성찰: 발견된 근본 문제와 해결

### 1.1 한글 OneDrive 경로 문제 [CRITICAL]

**증상**: `where tmux`가 PATH에 있는 `resources/bin/tmux.cmd`를 못 찾음
**근본 원인**: Windows PATH 해석기가 한글 Unicode normalization(NFC/NFD)이 다른 경로를 동일하게 인식하지 못함
**해결**: shim 파일들을 ASCII-only 경로(`~/.cmux-win/bin/`)에 복사
**교훈**: Windows에서 한글/일본어/중국어 경로는 절대 PATH에 넣지 말 것

```
❌ C:\Users\신이재\OneDrive - the presbyerian church of korea\바탕 화면\cmux-win\resources\bin
✅ C:\Users\신이재\.cmux-win\bin
```

### 1.2 Claude Code Bash tool은 bash를 사용 [CRITICAL]

**증상**: Claude CLI에서 `tmux split-window`가 실패 — "error connecting to /tmp/tmux-*/default"
**근본 원인**: Claude Code의 Bash tool은 **PowerShell이 아닌 bash/sh**를 사용. `tmux.cmd`(Windows CMD 스크립트)가 아닌 `tmux`(Unix 바이너리)를 실행. `~/bin/tmux.exe`(실제 tmux)가 우리 shim보다 먼저 발견됨.
**해결**:
1. bash-compatible Node.js shim (`#!/usr/bin/env node`) 생성
2. `~/bin/tmux`에 설치 (Claude Code가 여기서 먼저 찾음)
3. `~/bin/tmux-shim.js`도 함께 복사

```javascript
// ~/bin/tmux (bash-compatible shim)
#!/usr/bin/env node
const path = require("path");
require(path.join(__dirname, "tmux-shim.js"));
```

### 1.3 teammateMode:'tmux'가 소켓 직접 연결을 강제 [CRITICAL]

**증상**: Claude Code가 `/tmp/tmux-*/default` 또는 `~/.cmux-win/tmux/default`에 Unix socket 연결 시도 → Windows에 없어 실패
**근본 원인**: `--settings`의 `teammateMode: 'tmux'`가 Claude Code를 "tmux 소켓에 직접 연결" 모드로 전환. Bash tool로 tmux 명령을 실행하는 것이 아니라, 내부적으로 소켓에 연결.
**해결**: `teammateMode` 제거. `TMUX` 환경변수도 제거. Claude Code는 CLAUDE.md의 지시에 따라 Bash tool로 tmux 명령을 실행.

```
제거:
- teammateMode: 'tmux' (claude-wrapper-lib.js)
- TMUX env var (claude-wrapper.js)

유지:
- CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 (env-utils.ts)
- TMUX_PANE=%N (claude-wrapper.js)
- tmux.cmd shim in PATH
- ~/.claude/CLAUDE.md 지시문
```

### 1.4 Gemini/Codex TUI가 send_text를 무시 [HIGH]

**증상**: `surface.send_text`로 보낸 텍스트가 Gemini/Codex 입력창에 반영 안 됨
**근본 원인**: ink(React for Terminal) 기반 TUI가 raw input mode를 사용. PTY write가 TUI 입력 필드에 반영 안 됨.
**해결**:
- Gemini: `gemini -p "prompt" -y` (headless + yolo 자동 승인)
- Codex: `codex --full-auto "prompt"` (샌드박스 + 자동 승인)
- Claude: interactive 모드 유지 (send_text 작동)

### 1.5 Auto-Approver가 stale buffer로 반복 Enter 전송 [HIGH]

**증상**: PTY 버퍼에 이전 승인 텍스트가 남아있어 매 데이터 수신마다 Enter를 계속 전송
**해결**: 버퍼 전체가 아닌 **새 incoming data만** 체크. 3초 쿨다운. 500ms 딜레이 후 Enter 전송.

### 1.6 filterSources가 사용자 타이핑을 삼킴 [HIGH]

**증상**: 터미널에 글자를 쳐도 안 보임
**근본 원인**: `filterSources`가 줄바꿈 없는 데이터를 버퍼에 쌓고 빈 문자열 반환. 사용자 타이핑 에코는 줄바꿈 없이 한 글자씩 옴 → 전부 삼킴.
**해결**: 줄바꿈 없는 데이터는 즉시 통과 (`return data`).

---

## 2. 현재 아키텍처 (성찰 반영)

### 2.1 터미널 간 통신 아키텍처

```
┌─ cmux-win 앱 (Electron Main Process) ─────────────────────┐
│                                                            │
│  Socket API Server (TCP :19840)                            │
│    ├── panel.split → 패널 생성                              │
│    ├── surface.send_text → PTY에 텍스트 전송                │
│    ├── surface.read → PTY 버퍼 읽기                         │
│    └── panel.list → 패널 목록                               │
│                                                            │
│  PTY Manager                                               │
│    ├── Auto-Approver (onData 콜백에 내장)                   │
│    ├── Live Buffer (100KB per surface)                      │
│    └── Source Filter (줄바꿈 있는 데이터만 필터)             │
│                                                            │
│  Shim Files (~/.cmux-win/bin/ + ~/bin/)                    │
│    ├── tmux → #!/usr/bin/env node + tmux-shim.js           │
│    ├── tmux.cmd → @echo off + node tmux-shim.js            │
│    ├── tmux-shim.js → Socket API RPC 호출                   │
│    ├── claude.cmd → node claude-wrapper.js                   │
│    └── claude-wrapper.js → Hook JSON + 환경변수 주입         │
└────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
    │ Claude  │         │ Gemini  │         │ Codex   │
    │ CLI     │         │ CLI     │         │ CLI     │
    │ (inter- │         │ (-p -y) │         │ (--full │
    │ active) │         │         │         │  -auto) │
    └─────────┘         └─────────┘         └─────────┘
    ↕ send_text          단방향 실행          단방향 실행
    ↕ capture-pane       결과: 파일 생성      결과: 파일 생성
```

### 2.2 Claude CLI → tmux shim → Socket API 흐름

```
Claude CLI (Bash tool)
  ↓ "tmux split-window -h"
~/bin/tmux (Node.js shim)
  ↓ require("./tmux-shim.js")
tmux-shim.js
  ↓ CMUX_SOCKET_PORT, CMUX_SOCKET_TOKEN 환경변수
Socket API (TCP :19840)
  ↓ auth.handshake + panel.split RPC
cmux-win Main Process
  ↓ store.dispatch({ type: 'panel.split' })
Renderer (React)
  ↓ 새 패널 + 새 XTermWrapper
사용자 화면에 새 터미널 표시
```

### 2.3 CLI별 실행/제어 방식

| CLI | 시작 | 작업 지시 | 자동 승인 | 상태 감지 |
|-----|------|----------|----------|----------|
| Claude | `claude` (interactive) | `send_text + \r` | Auto-Approver (PTY) | "Musing", "❯" |
| Gemini | `gemini -p "task" -y` | 인자로 1회 실행 | `-y` yolo mode | 셸 프롬프트 복귀 |
| Codex | `codex --full-auto "task"` | 인자로 1회 실행 | `--full-auto` | 셸 프롬프트 복귀 |

---

## 3. 구현 완료 항목 (커밋 이력)

### 커밋 1: c0d4dcf — Telegram, Explorer, DnD, UI
- TelegramBotService (grammY, safeStorage)
- FileExplorer (트리뷰, 프로젝트 탭)
- EdgeDropZone (4방향 드롭)
- 균등 분할 (⊞/⊟)
- AI 서비스 바로가기 (🧠💎🤖)

### 커밋 2: 6f0d5bf — Auto-Approver, CLI modes, Title detection
- Auto-Approver (PTY onData 내장)
- Gemini `-p -y`, Codex `--full-auto`
- 터미널 타이틀 자동 감지 (OSC 0/2 + 키워드)
- Socket auth mode 설정 반영

### 커밋 3: fc44df3 — Copy/Paste, Sidebar, CLAUDE.md, filterSources
- Ctrl+Shift+C/V 복사/붙여넣기
- 사이드바 버튼 가시성 개선
- 글로벌 CLAUDE.md (~/.claude/)
- filterSources 타이핑 삼킴 수정
- .md 파일 클릭 → 마크다운 뷰어
- 패널 접기/펼치기

### 커밋 4: 036a1bc — tmux shim for Claude CLI [핵심 돌파]
- bash-compatible tmux shim (#!/usr/bin/env node)
- ~/bin/tmux + ~/bin/tmux-shim.js 설치
- teammateMode 제거 (소켓 직접 연결 방지)
- TMUX 환경변수 제거
- CLI 경로 ASCII-safe path로 복사

---

## 4. 미해결 항목 + 다음 단계

### 4.1 워크스페이스 전환 버그
- 새 워크스페이스 열면 기존 워크스페이스 클릭 불가
- 원인 미조사, 다음 세션에서 수정

### 4.2 Claude CLI에서 2번째 split이 불안정
- 첫 번째 `tmux split-window` 성공
- 두 번째가 가끔 실패 (Claude가 병렬 실행하거나 재시도 안 함)
- CLAUDE.md에 "한 번에 하나씩" 지시 강화 필요

### 4.3 electron-vite build 멈춤
- `electron-vite build`가 main 42 modules 후 exit 127
- esbuild 직접 사용으로 우회 중
- 근본 원인 미조사

### 4.4 Codex 상태 감지 부정확
- "Working", "Thinking" 외 다양한 출력 패턴
- UNKNOWN으로 자주 표시
- 더 많은 패턴 수집 필요

### 4.5 브라우저 반응형
- claude.ai는 데스크톱 반응형 CSS 없음 → 모바일 UA 적용
- gemini/chatgpt는 자체 반응형 잘 됨
- Anthropic이 claude.ai를 수정하지 않는 한 해결 불가

---

## 5. 핵심 교훈 (설계 원칙으로 승격)

### D26: Windows에서 한글 경로는 PATH에 넣지 말 것
OneDrive 한글 경로는 Windows PATH, `where` 명령, CMD `%~dp0` 등에서 Unicode normalization 문제를 일으킨다. 항상 ASCII-safe 경로(`~/.cmux-win/bin/`)에 실행 파일을 배치할 것.

### D27: Claude Code의 Bash tool은 Unix bash를 사용
Windows에서도 Claude Code는 Git Bash/WSL의 `/bin/bash`를 사용한다. `.cmd` 스크립트가 아닌 `#!/usr/bin/env node` shebang의 Unix-style 스크립트를 만들어야 한다.

### D28: teammateMode와 TMUX 환경변수는 소켓 직접 연결을 유발
Claude Code는 `teammateMode: 'tmux'`이나 `TMUX` 환경변수가 있으면 tmux Unix socket에 직접 연결을 시도한다. Windows에는 Unix socket이 없으므로 항상 실패. 이 설정들을 제거하고 CLAUDE.md로 Bash tool 사용을 유도해야 한다.

### D29: Gemini/Codex는 인자 방식으로만 제어 가능
ink TUI 기반 CLI(Gemini, Codex)는 `pty.write()`로 보낸 텍스트를 입력 필드에 반영하지 않는다. `gemini -p "prompt" -y`와 `codex --full-auto "prompt"` 형태로만 작업을 지시할 수 있다.

### D30: Auto-Approver는 새 데이터만 체크해야 한다
PTY 출력 버퍼에서 승인 패턴을 찾을 때, 전체 버퍼가 아닌 새로 들어온 데이터만 검사해야 한다. 그렇지 않으면 이전 승인 텍스트가 남아서 반복 Enter를 보낸다.

---

## 6. 검증된 협업 워크플로우

### 6.1 최소 검증 완료

```
1. 앱 시작 → 터미널 1개 자동 생성
2. Claude CLI 실행 (`claude`)
3. Claude가 Bash로 `tmux split-window -h` → 패널 2개
4. 소켓 API로 3번째 패널 생성
5. Gemini (`gemini -p "task" -y`) + Codex (`codex --full-auto "task"`) 실행
6. 3개 AI 동시 파일 생성
7. Claude가 capture-pane으로 다른 터미널 감시
8. 최종 결과물 docx 생성

산출물: server.js, test.js, README.md, package.json, collab-report.docx
```

### 6.2 성능 측정

| 항목 | 결과 |
|------|------|
| 패널 생성 (소켓 API) | < 300ms |
| 패널 생성 (Claude Bash) | 10~30초 (Claude 사고 시간 포함) |
| send_text 전달 | < 100ms |
| surface.read | < 50ms |
| Auto-Approver 응답 | 1.5~3초 (쿨다운) |
| Gemini 파일 생성 | 30~60초 |
| Codex 파일 생성 | 30~120초 |
| Claude 파일 생성 | 20~60초 |
