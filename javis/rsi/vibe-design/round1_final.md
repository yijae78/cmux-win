# RSI Vibe-Design — Round 1 최종 개선 보고서

> **Author**: Worker1(Claude)
> **Date**: 2026-06-17
> **RSI Stage**: Step 4 — 영속 저장 (모든 리뷰·반박 종합)
> **Input**: round1_worker1.md → round1_worker2_review.md + round1_worker3_review.md → round1_worker1_rebuttal.md → **이 문서**
> **Status**: FINAL

---

## 1. 이 문서의 목적

신교수님의 글로벌 디자인 시스템(`~/.claude/CLAUDE.md`, 215~1100줄)을 2026 바이브디자인 세계 최고 수준으로 끌어올리기 위한 **구체적 통합 제안서**. Worker2(AGY)의 UX/전략 피드백과 Worker3(Codex)의 엔지니어링 엄밀성 피드백을 모두 반영한 합의안이다.

---

## 2. 현행 시스템 최종 평가

### 2-1. 평가 대상 확인 (Worker3 범위 오인 교정)

| 항목 | 경로 | 내용 |
|------|------|------|
| **글로벌 CLAUDE.md** (평가 대상) | `~/.claude/CLAUDE.md` | 1,307줄. 215줄부터 "신교수님 통합 디자인 시스템" — 토큰, 컴포넌트, 애니메이션, 접근성, 레이아웃 약 900줄 |
| 프로젝트 CLAUDE.md (평가 대상 아님) | `/c/dev/cmux-win/CLAUDE.md` | 184줄. cmux-win 아키텍처 문서 |

> Worker3는 프로젝트 CLAUDE.md(184줄)만 조사하여 "디자인 토큰이 없다"고 판정했으나, 이는 범위 오인. 글로벌 CLAUDE.md에 완전한 디자인 시스템이 존재한다.

### 2-2. 최종 Gap 분석 (Worker2 + Worker3 반영)

| # | Gap | 심각도 | 출처 |
|---|-----|--------|------|
| G1 | DESIGN.md 미분리 — 디자인 토큰이 CLAUDE.md 산문에 매립 | **CRITICAL** | Round 1 |
| G2 | 컴포넌트 메타데이터 부재 — meta.json 없음 | **HIGH** | Round 1 |
| G3 | 안티패턴 미선언 — "하지 마라"가 없음 | **HIGH** | Round 1 |
| G7 | Intent Mapping 부재 — UX 의도 매핑 없음 | **HIGH** | W2 리뷰로 LOW→HIGH 격상 |
| G8 | 런타임 접근성 가드 부재 — 정적 선언만 존재 | **HIGH** | W2 리뷰 신규 |
| G10 | 브랜드 DNA 에이전트 소비 포맷 미변환 | **HIGH** | W2 리뷰 신규 |
| G11 | 에이전트 보안 모델 부재 | **HIGH** | W3 리뷰 신규 |
| G4 | 토큰 네이밍 혼재 — 위치 기반과 의도 기반 혼재 | **MEDIUM** | Round 1 |
| G5 | 거버넌스 파이프라인 부재 | **MEDIUM** | Round 1 |
| G6 | 에이전트 소비 최적화 부재 (JSON 계약 없음) | **MEDIUM** | Round 1 |
| G9 | CSS 성능 가드레일 부재 | **MEDIUM** | W2 리뷰 신규 |
| G12 | 토큰 마이그레이션 경로 없음 | **MEDIUM** | W3 리뷰 신규 |
| G13 | 엣지 케이스 미처리 (다크/라이트, DPI, i18n, 폴백) | **MEDIUM** | W3 리뷰 신규 |

### 2-3. 최종 종합 평점

| 평가 축 | 점수 | 비고 |
|---------|------|------|
| 토큰 포괄성 | 92/100 | 세계 최고 수준 — spacing, radius, opacity, duration, shadow 5단계 완비 |
| 컴포넌트 패턴 | 88/100 | 글래스모피즘 4계층, 버튼 3단계, 모달, 토스트 등 25+ 패턴 |
| 타이포그래피 | 90/100 | Pretendard+Inter, 한글 keep-all, clamp() 반응형 |
| 애니메이션 | 85/100 | 키프레임 12종 + spring 이징 + reduced-motion |
| 기계 판독성 | 40/100 | 인간 독해용 CSS 코드 블록 — YAML/JSON 계약 부재 |
| 컴포넌트 계약 | 25/100 | meta.json 없음, 안티패턴 없음 |
| UX 의도 매핑 | 10/100 | Intent Mapping 전무 |
| 보안 모델 | 5/100 | 에이전트 보안 게이트 전무 |
| 브랜드 DNA 소비성 | 35/100 | DNA 풍부하나 에이전트 소비 포맷 미변환 |
| **가중 평균** | **52/100** | 인간 독해 품질 A급 / 에이전틱 준비도 D급 |

> **핵심 진단**: "세계 최고의 인간용 디자인 시스템"이나 "AI 에이전트에겐 읽을 수 없는 소설책"

---

## 3. 개선 아키텍처: 신교수님 디자인 시스템 + 바이브디자인 통합

### 3-1. 목표 아키텍처 개요

```
현행                              목표
────────────────────              ────────────────────────────────
~/.claude/CLAUDE.md               ~/.claude/CLAUDE.md (축소: 참조 포인터만)
  └─ 900줄 디자인 산문                │
                                      ├─ ~/.claude/DESIGN.md (신규)
                                      │    ├─ YAML 프론트매터 (기계용 토큰)
                                      │    ├─ ## Core UX Constraints
                                      │    ├─ ## Brand DNA & Mood Guidelines
                                      │    ├─ ## Colors
                                      │    ├─ ## Typography
                                      │    ├─ ## Layout
                                      │    ├─ ## Components
                                      │    ├─ ## Animation
                                      │    ├─ ## Accessibility
                                      │    ├─ ## Performance Constraints
                                      │    ├─ ## Security Gates
                                      │    └─ ## Do's and Don'ts (안티패턴)
                                      │
                                      └─ ~/.claude/components/ (선택적, Phase 2)
                                           ├─ button.meta.json
                                           ├─ card.meta.json
                                           ├─ modal.meta.json
                                           ├─ toast.meta.json
                                           └─ input.meta.json
```

### 3-2. CLAUDE.md 변경 사항

현행 CLAUDE.md에서 디자인 섹션(215~1100줄)을 **DESIGN.md로 분리**하고, 원래 위치에는 참조 포인터만 남긴다:

```markdown
# 신교수님 통합 디자인 시스템

> **모든 디자인 지침은 `~/.claude/DESIGN.md`에 정의되어 있다.**
> UI/UX 작업 시 반드시 DESIGN.md를 읽고 따르라.
```

### 3-3. DESIGN.md 상세 설계

#### 3-3-1. YAML 프론트매터 (기계용 토큰)

```yaml
---
# 신교수님 통합 디자인 시스템 — 기계 판독용 토큰
version: "1.0.0"
status: "production"

brand_mood:
  background_lightness_range: [0, 12]
  accent_hue_range: [35, 50]
  gradient_angle: 135
  glass_blur_min: 16
  prohibited_moods: ["flat", "pastel", "corporate-blue", "neon-rainbow"]

colors:
  bg_void: "#0a0a0a"
  bg_primary: "#0c111b"
  bg_raised: "#111827"
  surface_1: "rgba(255,255,255,0.04)"
  surface_2: "rgba(255,255,255,0.06)"
  surface_3: "rgba(255,255,255,0.09)"
  text_primary: "#f1f5f9"
  text_secondary: "#94a3b8"
  text_muted: "#64748b"
  semantic_success: "#22c55e"
  semantic_active: "#3b82f6"
  semantic_warning: "#f59e0b"
  semantic_error: "#ef4444"
  accent_blue_cyan: ["#00A8FF", "#00d4ff", "#38bdf8"]
  accent_purple: ["#7c6ef0", "#8b5cf6", "#a78bfa"]
  accent_dual: { cyan: "#00D4FF", gold: "#FFB800" }

typography:
  ui_font: "Pretendard Variable, Inter, -apple-system, Noto Sans KR, sans-serif"
  serif_font: "Noto Serif KR, serif"
  code_font: "JetBrains Mono, D2Coding, monospace"
  hero_size: "clamp(22px, 3vw, 36px)"
  title_size: "clamp(20px, 4vw, 28px)"
  body_size: "13px-15px"
  label_size: "10px-12px"

spacing:
  base: 4
  scale: [4, 8, 12, 16, 20, 24, 32, 40, 48, 64]

radius:
  sm: 6
  md: 10
  lg: 12
  xl: 20
  full: 9999

shadows:
  sm: "0 1px 3px rgba(0,0,0,0.3)"
  md: "0 4px 16px rgba(0,0,0,0.3)"
  lg: "0 8px 32px rgba(0,0,0,0.4)"
  xl: "0 24px 64px rgba(0,0,0,0.5)"
  glow: "0 0 24px rgba(var(--accent-rgb), 0.2)"

animation:
  ease_spring: "cubic-bezier(0.22, 1, 0.36, 1)"
  ease_standard: "cubic-bezier(0.4, 0, 0.2, 1)"
  duration_fast: "0.15s"
  duration_normal: "0.25s"
  duration_slow: "0.4s"

performance:
  max_backdrop_filter_per_screen: 8
  max_css_variables: 80
  animation_gpu_accelerated: true

breakpoints:
  mobile: 800
  tablet: 1200
---
```

#### 3-3-2. 신규 섹션: Core UX Constraints (최선두 배치)

```markdown
## Core UX Constraints

이 섹션은 모든 디자인 결정에 선행하는 절대 제약이다.
AI 에이전트가 UI를 생성할 때, 컴포넌트 스타일보다 이 제약을 먼저 확인하라.

### UX Safe Zone (절대 고정 — AI 변형 금지)

- **내비게이션 구조**: 사이드바/탭 위치, 계층, 순서 고정
- **핵심 CTA 위치**: 폼 제출 버튼, 저장 버튼의 위치/크기 고정
- **폼 제출 흐름**: 입력 → 검증 → 확인 → 제출 순서 불변
- **에러 표시 위치**: 폼 필드 직하, 토스트 우하단 고정
- **키보드 내비게이션 흐름**: Tab 순서, Escape 동작, Enter 제출 고정

### Vibe Zone (AI 변형 허용 — 토큰 범위 내)

- 카드 내부 레이아웃 변형
- 색상 강조 변주 (시맨틱 4색 + 브랜드 악센트 범위 내)
- 마이크로인터랙션 변주 (duration 범위 내)
- 컨텐츠 카드 순서 (개인화 목적)
- 장식적 요소 (글로우, 그라디언트 변주)

### Intent Mapping (사용자 의도 → 컴포넌트 매핑)

모든 UI 생성은 "어떤 컴포넌트를 놓을까"가 아니라 "사용자가 이 시점에서
무엇을 달성하려 하는가"에서 출발한다:

| 사용자 의도 | 권장 패턴 | 금지 패턴 |
|------------|----------|----------|
| 단일 결정적 행동 | Primary 버튼 1개 | Primary 버튼 2개 병렬 |
| 정보 탐색 | 검색바 + 필터 + 카드 그리드 | 무한 스크롤 단독 |
| 데이터 입력 | 스텝 위자드 (3~5단계) | 한 페이지에 20+ 필드 |
| 상태 확인 | KPI 카드 + 프로그레스 바 | 텍스트만의 상태 설명 |
| 위험 행동 확인 | 모달 + Destructive 버튼 + 확인 | 인라인 삭제 (확인 없음) |
```

#### 3-3-3. 신규 섹션: Brand DNA & Mood Guidelines

```markdown
## Brand DNA & Mood Guidelines

### 시각적 정체성 (산문 — AI 판단용)

Always apply cinematic backlight and golden highlight on dark charcoal background.
Glass morphism with depth layers is the primary design language.
Numbers and KPIs are the hero — decoration is restrained.
Workflow visualization uses step cards + dot connectors + progress bars.
All gradients at 135 degrees. Slow glows at 2-3 second cycles.

When in doubt: darker and more dramatic is preferred over brighter and lighter.

### 금지 무드 (Anti-Visual Mood)

- NEVER: flat design, pastel tones, corporate blue monotone
- NEVER: neon rainbow gradients, candy-colored UI
- NEVER: generic shadcn/ui default theme without customization
- NEVER: white/light backgrounds unless explicitly requested
- NEVER: stock photo aesthetics, clip-art style illustrations

### 브랜드 악센트 선택 규칙

| 프로젝트 성격 | 악센트 축 | 예시 |
|--------------|----------|------|
| 기술/데이터/모니터링 | 블루-시안 | cmux-win, 대시보드 |
| 창작/브랜드/교육 | 퍼플-바이올렛 | 설교 에디터, 교재 |
| 프리미엄/내러티브 | 시안+골드 듀얼 | 특별 프레젠테이션 |
```

#### 3-3-4. 신규 섹션: Security Gates

```markdown
## Security Gates (에이전트 보안 제약)

AI 에이전트가 디자인 시스템을 소비하여 코드를 생성할 때 적용되는 보안 규칙:

1. **셸 보간 금지**: 디자인 콘텐츠(토큰 값, 컴포넌트 이름)를 셸 명령에 보간하지 않는다
2. **인자 배열 실행**: 명령 실행 시 문자열 연결이 아닌 인자 배열 방식만 사용
3. **MCP 도구 화이트리스트**: 디자인 에이전트는 승인된 MCP 도구만 사용
4. **시크릿 접근 금지**: 디자인 에이전트에 API 키, 토큰, 자격 증명 접근 불가
5. **의존성 리뷰**: 생성된 코드에 새 npm/pip 패키지 추가 시 인간 승인 필수
6. **감사 로그**: 자동 수정(auto-fix)은 모두 로그에 기록
7. **머지 전 인간 리뷰**: 에이전트는 이슈/PR 초안만 생성, 자동 머지 절대 금지
```

#### 3-3-5. 신규 섹션: Performance Constraints

```markdown
## Performance Constraints

- **backdrop-filter**: 한 화면에 최대 8개. 초과 시 중첩 카드는 불투명 배경 사용
- **CSS 변수**: 프로젝트당 80개 이하 권장. 초과 시 토큰 감사 수행
- **애니메이션**: transform/opacity만 사용 (GPU 가속). layout 변경 애니메이션 금지
- **이미지**: lazy loading 필수. aspect-ratio 명시. WebP/AVIF 우선
- **번들**: 사용하지 않는 키프레임/컴포넌트 CSS는 트리셰이킹
- **arbitrary value 금지**: Tailwind 사용 시 `bg-[#hex]`, `w-[Npx]` 등 하드코딩 금지
  — 반드시 디자인 토큰으로 정의된 값만 사용
```

#### 3-3-6. 신규 섹션: Do's and Don'ts (안티패턴)

```markdown
## Do's and Don'ts

### Do's (반드시)
- DO: 다크 배경 (#0a~#0f) 기본 적용
- DO: 글래스모피즘 카드에 hover 효과 (translateY + shadow 확대)
- DO: KPI 수치는 clamp()로 크고 굵게
- DO: 모든 인터랙티브 요소에 focus-visible 인디케이터
- DO: 한글 텍스트에 word-break: keep-all
- DO: 그라디언트 각도 135deg 통일
- DO: reduced-motion 미디어쿼리 대응
- DO: 최소 44x44px 터치 타겟
- DO: WCAG AA 4.5:1 대비 유지

### Don'ts (절대 금지)
- DON'T: Primary 버튼 2개를 나란히 배치
- DON'T: 확인 없이 Destructive 액션 실행
- DON'T: 내비게이션용으로 버튼 사용 (Link 사용)
- DON'T: 한 폼에 20개 이상 필드 나열
- DON'T: backdrop-filter 8개 초과 (성능)
- DON'T: 인라인 CSS 하드코딩 (토큰 시스템 사용)
- DON'T: Tailwind arbitrary value 사용 (토큰만 허용)
- DON'T: 밝은 배경 기본 적용 (요청 시에만)
- DON'T: generic shadcn/ui 기본 테마 무수정 사용
- DON'T: 에이전트 자동 머지 (PR 초안만 허용)
- DON'T: 디자인 에이전트에 시크릿 접근 허용
```

---

## 4. 컴포넌트 메타데이터 통합 (Phase 2)

### 4-1. 대상: 핵심 프리미티브 5개만 우선 (Worker3 권고 수용)

| 컴포넌트 | 우선순위 | 이유 |
|----------|---------|------|
| button | P0 | 모든 UI의 기본 인터랙션 |
| card (glass-card) | P0 | 신교수님 디자인 DNA의 핵심 |
| input (form) | P1 | 데이터 입력 흐름의 기초 |
| modal | P1 | 위험 행동 확인의 핵심 |
| toast | P2 | 피드백 표시 |

### 4-2. meta.json 예시: glass-card

```json
{
  "name": "glass-card",
  "category": "molecule",
  "purpose": "Translucent container with depth layers. The primary visual building block of the design system. Always used with dark backgrounds.",

  "variants": {
    "default": "Standard glass card with blur + subtle border",
    "accent": "Top border colored with accent — for highlighted sections",
    "nested": "Inner card with darker background, no backdrop-filter — for performance",
    "interactive": "Clickable card with hover lift + glow shadow",
    "image": "Card with zero-padding image header + body content"
  },

  "tokens": {
    "background": "surface_1",
    "border": "rgba(255,255,255,0.08)",
    "radius": "radius.lg",
    "padding": "spacing.4",
    "blur": "16px",
    "hover_background": "surface_2",
    "hover_transform": "translateY(-2px)",
    "hover_shadow": "shadows.lg"
  },

  "antiPatterns": [
    "Never use glass-card on light/white backgrounds — blur becomes invisible",
    "Never nest more than 1 level of glass cards — performance and readability",
    "Never use backdrop-filter on nested cards — use opaque fallback (nested variant)",
    "Never exceed 8 glass-cards with backdrop-filter on one screen",
    "Never apply accent variant to more than 2 cards per view — dilutes emphasis",
    "Never use image variant without aspect-ratio on the image"
  ],

  "accessibility": {
    "keyboard": true,
    "focusRing": "interactive variant only",
    "role": "interactive variant: role=button or role=link",
    "reducedMotion": "disable hover transform, keep shadow change"
  },

  "relationships": {
    "parents": ["main content area", "sidebar", "modal body", "grid layout"],
    "children": ["kpi-value", "step-card", "badge", "progress-bar", "data-table"],
    "incompatible": ["never inside another glass-card with backdrop-filter"]
  }
}
```

### 4-3. 3파일 슬림 모델 (Worker2 합의)

```
~/.claude/components/
├── glass-card.meta.json      # 메타데이터 (위 예시)
├── button.meta.json
├── input.meta.json
├── modal.meta.json
└── toast.meta.json
```

> 구현(.tsx)과 테스트(.test.tsx)는 각 프로젝트에 종속. 글로벌 디자인 시스템에는 meta.json(계약서)만 보관.

---

## 5. 토큰 네이밍 마이그레이션 경로 (Worker3 수용)

### 5-1. 현행 → 시맨틱 매핑 (부분 예시)

| 현행 이름 | 시맨틱 이름 | 역할 |
|----------|-----------|------|
| `--bg-primary` | `--surface.base` | 메인 배경 |
| `--bg-raised` | `--surface.raised` | 떠있는 표면 |
| `--text-primary` | `--text.emphasis` | 강조 텍스트 |
| `--text-secondary` | `--text.default` | 기본 텍스트 |
| `--text-muted` | `--text.subtle` | 보조 텍스트 |
| `--accent` | `--interactive.primary` | 주요 인터랙션 색상 |
| `--green` | `--status.success` | 성공/완료 |
| `--red` | `--status.danger` | 에러/위험 |
| `--amber` | `--status.warning` | 경고/대기 |
| `--blue` | `--status.info` | 정보/활성 |

### 5-2. 마이그레이션 5단계

```
Phase 1: 인벤토리 — 글로벌 CLAUDE.md의 모든 CSS 변수명 추출 (약 60~80개)
Phase 2: 별칭 생성 — 새 시맨틱 이름을 구 이름에 매핑 (둘 다 유효)
           --surface-base: var(--bg-primary);  /* alias */
Phase 3: 배치 전환 — 새 프로젝트는 시맨틱 이름 사용, 기존은 별칭으로 호환
Phase 4: 린트 규칙 — 구 이름 사용 시 warning, 새 이름 권장
Phase 5: 별칭 제거 — 모든 프로젝트 전환 완료 후 (급하지 않음)
```

> Worker3 권고: "별칭과 폐기 정책 없이 이름 변경하면 UI가 깨지거나 토큰 중복 발생" — 이 경로로 방지.

---

## 6. 엣지 케이스 반영 (Worker3 수용 6건)

| 엣지 케이스 | DESIGN.md 반영 위치 | 구체적 대응 |
|-------------|-------------------|------------|
| 다크/라이트 + 고대비 모드 | `## Colors` | `[data-theme="light"]` 토큰 세트 + `prefers-contrast: high` 미디어쿼리 |
| Windows DPI 스케일링 | `## Layout` | `clamp()` + viewport 단위 + 시스템 폰트 폴백 |
| i18n/한글 레이아웃 | `## Typography` | `word-break: keep-all` + `lang="ko"` 폰트 스택 + 줄바꿈 테스트 |
| reduced-motion | `## Animation` | `@media (prefers-reduced-motion: reduce)` 전역 적용 (현행 유지+강화) |
| CSS 변수 폴백 | `## Colors` 프론트매터 | `var(--new-name, var(--old-name, #fallback))` 3단 폴백 체인 |
| 생성 코드 실패 모드 | `## Security Gates` | 스키마 버전 체크, 존재하지 않는 토큰 참조 시 빌드 에러 |

---

## 7. 이원 포맷 전략 확정 (Worker2 + Worker3 합의)

```
┌─────────────────────────────────────────────────────────┐
│                    AI 에이전트                            │
│                        │                                │
│         ┌──────────────┼──────────────┐                 │
│         ▼              ▼              ▼                 │
│   DESIGN.md      meta.json ×5    CLAUDE.md             │
│   (글로벌 계약)   (컴포넌트 계약)  (행동 지침)           │
│                                                         │
│   YAML 토큰       JSON 메타        참조 포인터           │
│   + Markdown 산문  (props,          "DESIGN.md를         │
│   (WHY 판단용)    variants,         읽어라"              │
│                   antiPatterns)                          │
│                                                         │
│   상시 주입        온디맨드 조회     상시 주입             │
│   (기반: 색상,     (특정 컴포넌트    (비-디자인 지침)     │
│   타이포, 간격)    작업 시에만)                           │
└─────────────────────────────────────────────────────────┘
```

- **DESIGN.md**: 글로벌 기반(Foundation) — 항상 에이전트 컨텍스트에 포함
- **meta.json**: 컴포넌트별 계약 — 해당 컴포넌트 작업 시에만 로드 (토큰 절약)
- **CLAUDE.md**: 디자인 외 지침 — 참조 포인터로 DESIGN.md 연결

> 이것은 Worker2의 "이원화" 제안 + Worker3의 "토큰 SOT 분리" 우려를 동시에 해결한다.

---

## 8. 실행 로드맵

### Phase 1: 즉시 실행 (Round 2)

| # | 작업 | 산출물 | 난이도 |
|---|------|--------|--------|
| 1 | CLAUDE.md 디자인 섹션 → DESIGN.md 분리 | `~/.claude/DESIGN.md` | 중 |
| 2 | YAML 프론트매터 작성 (토큰 60~80개) | DESIGN.md 상단 | 중 |
| 3 | Core UX Constraints 섹션 작성 | DESIGN.md `## Core UX Constraints` | 하 |
| 4 | Brand DNA 섹션 작성 (이중 인코딩) | DESIGN.md `## Brand DNA` | 하 |
| 5 | Do's and Don'ts 섹션 작성 | DESIGN.md 말미 | 하 |
| 6 | Security Gates 섹션 작성 | DESIGN.md `## Security Gates` | 하 |
| 7 | Performance Constraints 섹션 작성 | DESIGN.md `## Performance Constraints` | 하 |
| 8 | CLAUDE.md에 참조 포인터 삽입 | CLAUDE.md 수정 (900줄→10줄) | 하 |

### Phase 2: 단기 (Round 3~4)

| # | 작업 | 산출물 |
|---|------|--------|
| 9 | glass-card meta.json 작성 (1번째 프리미티브) | `~/.claude/components/glass-card.meta.json` |
| 10 | button meta.json 작성 | `~/.claude/components/button.meta.json` |
| 11 | input, modal, toast meta.json | 3개 파일 |
| 12 | 에이전트 생성 품질 A/B 측정 | meta.json 유무 비교 보고서 |
| 13 | 토큰 인벤토리 + 별칭 매핑표 | `design-token-inventory.md` |

### Phase 3: 중기 (Round 5+)

| # | 작업 | 산출물 |
|---|------|--------|
| 14 | 시맨틱 토큰 별칭 도입 (Phase 2 전환) | CSS 변수 별칭 레이어 |
| 15 | 디자인 Linter 훅 개발 | arbitrary value 금지 린트 |
| 16 | meta.json 확장 (10→20 컴포넌트) | 추가 meta.json 파일들 |
| 17 | 런타임 접근성 래퍼 설계 | A11y wrapper 컴포넌트 |

### Phase 4: 장기 (안정화 후)

| # | 작업 | 전제 조건 |
|---|------|----------|
| 18 | MAPE-K 거버넌스 루프 | 토큰 안정화 + 시각 회귀 테스트 |
| 19 | meta.json 자동 생성 스킬 | 20+ 컴포넌트 경험 축적 |
| 20 | JSON 토큰 파이프라인 (DESIGN.md → JSON SOT) | 토큰 100개 초과 시 |

---

## 9. RSI 5단계 정리

| RSI 단계 | 상태 | 산출물 |
|----------|------|--------|
| Step 1: 검색·탐색 | COMPLETE | 전문가 10명, 출처 10+, 패턴 5개, 철학 3개 |
| Step 2: 패턴·철학 추출 | COMPLETE | 5대 패턴 + 3대 철학 |
| Step 3: 객관적 평가 | COMPLETE | Gap 분석 13건 + Worker2·W3 반박·수용 |
| Step 4: 영속 저장 | **이 문서** | round1_final.md |
| Step 5: Skill/Harness 제작 | **Round 2 범위** | DESIGN.md 실제 작성 → 바이브디자인 스킬 |

---

## 10. Sources

- [Anna Arteeva — Design Systems for the Vibe-Coding Era](https://www.designsystemscollective.com/design-systems-for-the-vibe-coding-era-42282e1affef)
- [Into Design Systems — Agentic Design Systems Complete Guide](https://www.intodesignsystems.com/agentic-design-systems)
- [TDP — Agentic Design System Component Library](https://designproject.io/blog/agentic-design-system/)
- [Google Stitch DESIGN.md Open Source](https://pasqualepillitteri.it/en/news/1251/google-stitch-design-md-open-source-spec-2026)
- [DESIGN.md Specification — Sebastien Dubois](https://www.dsebastien.net/design-md-specification/)
- [AGENTS.md + SKILL.md + DESIGN.md 3계층](https://dev.to/aws-builders/agentsmd-skillmd-designmd-how-ai-instructions-split-into-three-layers-d0g)
- [Intent-Driven Design — UX Collective](https://uxdesign.cc/the-next-era-of-design-is-intent-driven-f789ee521482)
- [Softr — Vibe Coding Best Practices 2026](https://www.softr.io/blog/vibe-coding-best-practices)
- [Muzli — Vibe Design 2026](https://muz.li/blog/vibe-design-in-2026-what-ai-generated-ui-means-for-your-work/)
- [LogRocket — Align AI Designs with Design System](https://blog.logrocket.com/ux-design/align-ai-designs-with-design-system/)
