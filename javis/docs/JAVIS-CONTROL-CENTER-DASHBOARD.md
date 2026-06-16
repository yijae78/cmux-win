# Javis Control Center Dashboard 명세서

> Javis Fleet 실시간 모니터링 대시보드. cmux-win 브라우저 패널에서 구동.

## 개요

| 항목 | 내용 |
|------|------|
| **파일** | `/c/dev/cmux-win/javis/dashboard.py` |
| **프레임워크** | Streamlit + components.html (단일 iframe) |
| **포트** | 8500 (Streamlit) + 8501 (데이터 서버) |
| **새로고침** | JS fetch 5초 간격 (깜박임 없음) |
| **디자인** | 신교수님 통합 디자인 시스템 적용 |
| **실행** | `streamlit run dashboard.py --server.headless true --server.port 8500` |

## 아키텍처

```
┌─────────────────────────────────────────────┐
│  cmux-win 브라우저 패널 (%5)                │
│  ┌───────────────────────────────────────┐  │
│  │  Streamlit (port 8500)                │  │
│  │  └─ components.html() 단일 iframe     │  │
│  │     └─ JS fetch → localhost:8501      │  │
│  │        (5초마다 body HTML 교체)        │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  데이터 서버 (port 8501, 별도 스레드)  │  │
│  │  └─ 매 요청마다:                      │  │
│  │     ├─ Socket API → surface 목록/내용  │  │
│  │     ├─ JSONL 파싱 → 토큰 사용량       │  │
│  │     ├─ Anthropic API → rate limit     │  │
│  │     └─ psutil → CPU/MEM              │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

## 데이터 소스

| 데이터 | 소스 | 갱신 주기 |
|--------|------|----------|
| 플릿 상태 | cmux-win Socket API (`surface.list` + `surface.read`) | 5초 |
| 토큰 사용량 | `~/.claude/projects/` JSONL 파싱 | 5초 |
| Rate Limit | Anthropic API 헤더 (haiku 1토큰 호출) | 60초 캐시 |
| CPU/메모리 | psutil | 5초 |
| 가동시간 | 대시보드 시작 시각 기준 JS 카운팅 | 1초 (클라이언트) |

## 레이아웃 구성

### 1. 헤더

```
[빨간 펄스 점] JARVIS Control Center   [LIVE/IDLE 뱃지]   2026.06.16 | 16:42:35
```
- 빨간 펄스 점: 0.8초 주기 깜박임
- LIVE/IDLE 뱃지: 작업 중 에이전트 유무에 따라 전환
- 실시간 시계: JS 1초마다 갱신

### 2. 상단 원형 지표 (2개 나란히)

```
┌──────────┐  ┌──────────┐
│  레이더   │  │  가동시간  │
│   40%    │  │ 01:23:45 │
│ 2/5 활성  │  │  가동시간  │
└──────────┘  └──────────┘
```
- **레이더**: 활성 에이전트 비율, 스윕 애니메이션 + 리플 (활성 시)
- **가동시간**: HH:MM:SS 실시간 카운팅 (JS), 분 기준 원호 진행

### 3. KPI 카드 (2열)

```
┌─────────────┐ ┌─────────────┐
│    12%      │ │     3%      │
│ 리셋 21:30  │ │ 리셋 06/23  │
│ 세션 (5h)   │ │ 주간 (7d)   │
└─────────────┘ └─────────────┘
```
- 색상: 60% 이상 앰버, 80% 이상 레드, 그 외 그린
- 리셋 시각 표시

### 4. 플릿 현황 (세로 스택)

```
┌ [M] Master ────────────── ● 대기 ┐
├ [C] CSO ───────────────── ● 작업중┤
├ [A] Worker1 ───────────── ● 대기 ┤
├ [G] Worker2 ───────────── ● 대기 ┤
└ [X] Worker3 ───────────── ● 대기 ┘
```
- 각 에이전트별 고유 색상 (Master=블루, CSO=퍼플, Worker1=그린, Worker2=오렌지, Worker3=시안)
- 상태: 작업중(그린 깜박), 대기(그레이), 오류(레드 깜박), 오프라인(다크)
- 좌측 3px 컬러바

### 5. 토큰 사용량

```
세션 ████████░░░░░░ 12%     리셋 21:30
주간 ██░░░░░░░░░░░░  3%     리셋 06/23

┌─────────┬─────────┬─────────┐
│ 최근1시간 │ 오늘소비  │ 세션 수  │
│  2.3만   │  15.7만  │   4     │
│ 입력1.8만 │ 입력12만  │ 메시지23│
└─────────┴─────────┴─────────┘

12h [스파크라인 차트]
    05   08   11   14
```

### 6. 시스템

```
CPU ████████░░░░░░ 45%
MEM ██████░░░░░░░░ 12.3/32G
```

### 7. 푸터

```
자비스 플릿 v2 · 5초 새로고침 · 2026-06-16 16:42:35
```

## 에이전트 설정

| Key | 아이콘 | 색상 | AI | 역할 |
|-----|--------|------|-----|------|
| Master | M | #3b82f6 (블루) | Claude | 총지휘 |
| CSO | C | #8b5cf6 (퍼플) | Claude | 시스템 운영 |
| Worker1(AGY) | A | #00e676 (그린) | Claude | 작업 수행 |
| Worker2(AGY) | G | #ffa726 (오렌지) | AGY | 리뷰 |
| Worker3(Codex) | X | #00d4ff (시안) | Codex | 검수 |

## 상태 감지 로직

### idle (대기)
```python
키워드: "waiting", "idle", "> ", "ps c:\\", "bypass permissions",
        "대기합니다", "분석 완료", "작업 완료", "각성 완료",
        "? for shortcuts", "worked for"
```

### live (작업중)
```python
키워드: "working", "running", "processing", "generating", "thinking",
        "reading file", "writing file", "editing", "creating",
        "분석 중", "작업 중", "모니터링", "zigzagging", "shenaniganing"
```

### error (오류)
```python
키워드: "traceback", "exception", "crash", "fatal error", "panic"
제외: "mcp server failed", "settings issue" (노이즈)
```

### offline
```
content가 비어있으면 offline
```

## 디자인 토큰 (적용된 값)

```
배경:      #0a0a0a (void)
카드:      rgba(255,255,255,0.05) + blur(16px)
보더:      rgba(255,255,255,0.10)
악센트:    #00A8FF → #00d4ff (블루-시안)
텍스트:    #e2e8f0 (primary), #94a3b8 (secondary), #64748b (muted)
시맨틱:    #22c55e(성공) #3b82f6(활성) #f59e0b(경고) #ef4444(에러)
폰트:      Pretendard Variable + JetBrains Mono
```

## 애니메이션

| 이름 | 대상 | 주기 |
|------|------|------|
| red-pulse | 헤더 라이브 점 | 0.8s |
| blink | 상태 점 (live/error) | 1.4s |
| radar-spin | 레이더 스윕 라인 | 4s |
| rp-out | 레이더 리플 | 4s (3개 stagger) |
| wave-rot | 레이더 외곽 장식 | 4s |
| shimmer | 스켈레톤 로딩 | 1.8s |
| barFlow | AI 처리중 바 | 2s |

## 실행 방법

```bash
# 단독 실행
streamlit run /c/dev/cmux-win/javis/dashboard.py --server.headless true --server.port 8500

# fleet 부트스트랩 시 자동 실행
# bootstrap_fleet.sh가 대시보드를 가장 먼저 시작하고,
# 마지막에 cmux-win 브라우저 패널(%5)로 연결
```

## 알려진 이슈 및 개선 필요사항

1. **균등분할**: `panel.resize` API가 불안정. 패널 열기/닫기 후 균등분할 버튼 수동 클릭 필요
2. **AGY 파일 접근**: AGY CLI의 TUI 권한 프롬프트가 send-keys로 제어 안 됨. workspace 디렉토리에서 시작해야 함
3. **Codex 한글**: Codex CLI가 한글 프롬프트 처리 불안정. 영어로 지시 권장
4. **가동시간**: JS 클라이언트에서 1초마다 카운팅. 대시보드 재시작 시 리셋됨

## 파일 구조

```
/c/dev/cmux-win/javis/
├── dashboard.py              # 대시보드 메인
├── docs/
│   └── JAVIS-CONTROL-CENTER-DASHBOARD.md   # 이 문서
├── directives/
│   ├── CSO_DIRECTIVE.md      # CSO 절대지침
│   └── WORKER_DIRECTIVE.md   # 워커 절대지침
├── scripts/
│   └── bootstrap_fleet.sh    # fleet 부트스트랩
├── fleet_mapping.env         # pane 매핑
├── logs/                     # 로그
└── workspace/                # 작업 공간 (원본 프로젝트 복사본)
    └── output/               # 산출물 저장
```
