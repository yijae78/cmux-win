# RSI Vibe-Design — Round 2 Worker1 종합 실행 계획

> **Author**: Worker1(Claude)
> **Date**: 2026-06-17
> **RSI Stage**: Round 2 — Gap 해결 실행 계획 + DESIGN.md 마이그레이션
> **Inputs**:
> - `round1_final.md` — Gap G1~G13 + 개선 아키텍처
> - `round2_worker2_research.md` — Stitch Agent, Figma MCP, shadcn/skills, Style Dictionary
> - `round2_worker3_research.md` — Contract stack, DTCG, evidence packet, 보안/성능 레지스터
> **Status**: COMPLETE

---

## 1. 종합 판단: Worker2·Worker3 연구의 합의점과 갈등점

### 1-1. 합의점 (양측 동의)

| # | 합의 사항 | W2 근거 | W3 근거 |
|---|----------|---------|---------|
| A1 | DESIGN.md는 필수, 역할은 "에이전트+인간 정책(Policy)" | Google Stitch 표준 | 토큰 SOT가 아닌 정책 문서 |
| A2 | 안티패턴 선언이 가장 효과적인 에이전트 지침 | shadcn/skills 환각 방지 | 메타데이터의 핵심 필드 |
| A3 | arbitrary value 린트 필수 | Style Dictionary 가드레일 | CSS 바이트 예산 + 린트 |
| A4 | 에이전트 보안 게이트 필수 | (암묵적 동의) | 명시적 위협 레지스터 6건 |
| A5 | 핵심 프리미티브부터 점진적 시작 | shadcn/skills 패턴 | 스파이크 후 확장 |
| A6 | 접근성은 자동+수동 다계층 검증 | (언급 없음) | WCAG 2.2 구체 기준 + evidence packet |

### 1-2. 갈등점과 Worker1 판정

| # | 갈등 | W2 입장 | W3 입장 | **Worker1 판정** |
|---|------|---------|---------|-----------------|
| D1 | 토큰 SOT 위치 | DESIGN.md YAML 프론트매터 | JSON 토큰 파일 → 생성된 CSS | **글로벌 = YAML, 프로젝트 = JSON** (아래 상세) |
| D2 | Figma MCP 즉시 도입 | 적극 권장 | Figma 소스 없으면 불필요 | **원칙 차용, 도구 보류** |
| D3 | Style Dictionary 도입 | 즉시 적용 권장 | 작으면 커스텀 생성기 | **Phase 3+ 검토** |
| D4 | 성능 벤치마크 범위 | 범용 | cmux-win 특화 (Electron) | **글로벌 범용 + 프로젝트별 특화** |

#### D1 판정 근거: 토큰 SOT의 이원 전략

**글로벌 디자인 시스템** (`~/.claude/DESIGN.md`):
- 빌드 파이프라인이 없다 — AI 에이전트가 직접 읽는 지침서
- YAML 프론트매터가 SOT로 적합 — 에이전트가 파싱하여 판단에 사용
- 토큰 수 60~80개 수준 — 순환 참조·드리프트 리스크 낮음
- Worker3의 "JSON → 생성된 CSS" 파이프라인은 과잉

**프로젝트 레벨** (예: cmux-win):
- 빌드 파이프라인이 존재 — Electron, Webpack/Vite
- Worker3의 `design/tokens/*.json → generated CSS` 아키텍처가 적합
- DESIGN.md는 프로젝트별 policy override로 기능

```
글로벌 레벨                         프로젝트 레벨
~/.claude/DESIGN.md                /project/DESIGN.md (override)
  YAML = 토큰 SOT                  참조만 (글로벌 토큰 상속)
  Markdown = 정책                    │
                                    /project/design/tokens/
                                      base.tokens.json (SOT)
                                      → generated/tokens.css
```

---

## 2. Gap G1~G13 해결 매핑

### 2-1. 해결 매핑표

| Gap | 심각도 | 해결 방법 | Round 2 연구 근거 | Phase |
|-----|--------|----------|-------------------|-------|
| **G1** DESIGN.md 미분리 | CRITICAL | CLAUDE.md 215~1137줄 → `~/.claude/DESIGN.md` 분리 | W2: Google Stitch 표준 / W3: 정책 문서 분리 | **1** |
| **G2** 컴포넌트 메타데이터 부재 | HIGH | 핵심 5개 프리미티브 meta.json 작성 | W2: shadcn/skills / W3: 스파이크 후 확장 | **2** |
| **G3** 안티패턴 미선언 | HIGH | DESIGN.md `## Do's and Don'ts` + meta.json `antiPatterns` | W2: 환각 소멸 효과 / W3: 가장 강력한 지침 | **1** |
| **G7** Intent Mapping 부재 | HIGH | DESIGN.md `## Core UX Constraints` — Safe Zone + Intent Map | W2: (Round 1 수용) / W3: 컴포넌트 API+사용 규칙 | **1** |
| **G8** 런타임 접근성 가드 부재 | HIGH | WCAG 2.2 구체 기준 + 다계층 검증 파이프라인 | W3: evidence packet + 5계층 테스트 스택 | **2** |
| **G10** 브랜드 DNA 미변환 | HIGH | DESIGN.md `## Brand DNA` — YAML 수치 + Markdown 산문 | W2: Stitch Agent mood steering | **1** |
| **G11** 보안 모델 부재 | HIGH | DESIGN.md `## Security Gates` + 위협 레지스터 | W3: 6건 위협 + 3단계 신뢰 수준 | **1** |
| **G4** 토큰 네이밍 혼재 | MEDIUM | 별칭 매핑표 + 5단계 마이그레이션 | W3: DTCG 개념 차용 ($deprecated, 참조) | **2** |
| **G5** 거버넌스 파이프라인 부재 | MEDIUM | 린트 훅 + evidence packet (MAPE-K는 Phase 4) | W2: Style Dictionary 가드레일 / W3: 로컬 벤치마크 | **2-3** |
| **G6** 에이전트 소비 최적화 부재 | MEDIUM | YAML 프론트매터 + 온디맨드 meta.json | W2: MCP 온디맨드 / W3: JSON 계약 | **1-2** |
| **G9** CSS 성능 가드레일 부재 | MEDIUM | DESIGN.md `## Performance Constraints` + 린트 | W3: 로컬 벤치마크 하네스 | **1** |
| **G12** 마이그레이션 경로 없음 | MEDIUM | 5단계 경로 + 별칭 레이어 + CSS 폴백 체인 | W3: $deprecated + 호환 별칭 | **2** |
| **G13** 엣지 케이스 미처리 | MEDIUM | 6건 반영 (다크/라이트, DPI, i18n, 폴백 등) | W3: high-contrast, DTCG $extensions | **1-2** |

---

## 3. Phase 1 실행 계획: CLAUDE.md → DESIGN.md 마이그레이션

### 3-1. 마이그레이션 개요

```
현행:  ~/.claude/CLAUDE.md (1,307줄)
         ├─ 비-디자인 섹션 (1~214줄, 1138~1307줄) — 유지
         └─ 디자인 섹션 (215~1137줄, 922줄) — 분리 대상

목표:  ~/.claude/CLAUDE.md (약 400줄) — 비-디자인 + 참조 포인터
       ~/.claude/DESIGN.md (약 1,000줄) — 디자인 시스템 전문 (신규 섹션 포함)
```

### 3-2. CLAUDE.md 수정: 디자인 섹션을 참조 포인터로 대체

**삭제 범위**: 215줄 (`# 신교수님 통합 디자인 시스템`) ~ 1137줄 (`## 체크리스트` 마지막)

**대체 내용** (약 15줄):

```markdown
# 신교수님 통합 디자인 시스템 (UI/UX Design Skill)

> **모든 디자인 지침은 `~/.claude/DESIGN.md`에 정의되어 있다.**
> UI/UX 작업 시 반드시 DESIGN.md를 읽고 따르라.
> 
> DESIGN.md 구조:
> - YAML 프론트매터: 기계 판독용 디자인 토큰 (색상, 타이포, 간격, 그림자 등)
> - Core UX Constraints: UX 안전 구역 + 사용자 의도 매핑
> - Brand DNA: 시각적 정체성 (수치 제약 + 산문 묘사)
> - Colors ~ Animation: 상세 디자인 사양
> - Accessibility: WCAG 2.2 기반 접근성 규칙
> - Performance Constraints: 성능 예산
> - Security Gates: 에이전트 보안 제약
> - Do's and Don'ts: 안티패턴 목록
> - 체크리스트: 필수/조건부 검증 항목
>
> 컴포넌트 메타데이터: `~/.claude/components/*.meta.json` (핵심 5개)
```

### 3-3. DESIGN.md 전체 구조

```markdown
---
# ═══════════════════════════════════════════════
# 신교수님 통합 디자인 시스템 — DESIGN.md
# AI 에이전트 + 인간 디자이너 공용 계약
# ═══════════════════════════════════════════════
version: "1.0.0"
schemaVersion: 1
status: production
generatedAt: "2026-06-17"

# ─── Brand Mood (기계용 수치 제약) ───
brand_mood:
  background_lightness_range: [0, 12]
  accent_hue_range: [35, 50]
  gradient_angle: 135
  glass_blur_min: 16
  prohibited_moods:
    - flat
    - pastel
    - corporate-blue
    - neon-rainbow
    - candy-colored

# ─── Colors ───
colors:
  bg:
    void: "#0a0a0a"
    primary: "#0c111b"
    raised: "#111827"
  surface:
    s1: "rgba(255,255,255,0.04)"
    s2: "rgba(255,255,255,0.06)"
    s3: "rgba(255,255,255,0.09)"
  text:
    emphasis: "#f1f5f9"
    default: "#94a3b8"
    subtle: "#64748b"
    disabled: "rgba(255,255,255,0.25)"
  semantic:
    success: "#22c55e"
    info: "#3b82f6"
    warning: "#f59e0b"
    danger: "#ef4444"
  semantic_rgb:
    success: "34, 197, 94"
    info: "59, 130, 246"
    warning: "245, 158, 11"
    danger: "239, 68, 68"
  accent:
    blue_cyan: ["#00A8FF", "#00d4ff", "#38bdf8"]
    purple_violet: ["#7c6ef0", "#8b5cf6", "#a78bfa"]
    dual: { cyan: "#00D4FF", gold: "#FFB800" }

# ─── Typography ───
typography:
  font_ui: "Pretendard Variable, Inter, -apple-system, Noto Sans KR, sans-serif"
  font_serif: "Noto Serif KR, serif"
  font_code: "JetBrains Mono, D2Coding, monospace"
  pretendard_cdn: "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css"
  scale:
    hero: { size: "clamp(22px,3vw,36px)", weight: "700-900", line_height: 1.1 }
    title: { size: "clamp(20px,4vw,28px)", weight: 800, line_height: 1.2 }
    section: { size: "14-16px", weight: "600-700", line_height: 1.3 }
    label: { size: "10-12px", weight: 600, letter_spacing: "0.1em", transform: uppercase }
    body: { size: "13-15px", weight: "400-500", line_height: 1.6 }

# ─── Spacing (4px base) ───
spacing:
  base: 4
  scale: [4, 8, 12, 16, 20, 24, 32, 40, 48, 64]

# ─── Border Radius ───
radius:
  sm: 6
  md: 10
  lg: 12
  xl: 20
  full: 9999

# ─── Opacity ───
opacity:
  subtle: 0.04
  light: 0.06
  border: 0.08
  medium: 0.10
  strong: 0.15
  heavy: 0.25

# ─── Shadows ───
shadows:
  sm: "0 1px 3px rgba(0,0,0,0.3)"
  md: "0 4px 16px rgba(0,0,0,0.3)"
  lg: "0 8px 32px rgba(0,0,0,0.4)"
  xl: "0 24px 64px rgba(0,0,0,0.5)"
  glow: "0 0 24px rgba(var(--accent-rgb),0.2)"

# ─── Animation ───
animation:
  ease_spring: "cubic-bezier(0.22, 1, 0.36, 1)"
  ease_standard: "cubic-bezier(0.4, 0, 0.2, 1)"
  duration:
    fast: "0.15s"
    normal: "0.25s"
    slow: "0.4s"

# ─── Borders ───
borders:
  thin: 1
  medium: 2
  thick: 3
  heavy: 4

# ─── Performance Budget ───
performance:
  max_backdrop_filter: 8
  max_css_variables: 80
  animation_gpu_only: true
  lazy_loading_images: true

# ─── Breakpoints ───
breakpoints:
  mobile: 800
  tablet: 1200

# ─── Z-Index Layers ───
z_index:
  sidebar: 10
  dropdown: 30
  toast: 90
  modal_backdrop: 100
  modal_content: 101
  loading: 200
---

## Overview

신교수님 통합 디자인 시스템. 다크 퍼스트, 글래스모피즘, 시네마틱 역광의 
프리미엄 UI를 모든 프로젝트에 일관되게 적용한다.

운용 원칙:
- **기본값 = 이 문서의 스타일** → 질문 없이 바로 적용
- **대안 = 제안만** → 신교수님 승인 후에만 적용
- **강제 변경 금지** → 묵시적 적용 절대 금지

## Core UX Constraints

(... Round 1 final의 3-3-2 내용 전문 삽입 ...)

## Brand DNA & Mood Guidelines

(... Round 1 final의 3-3-3 내용 전문 삽입 ...)

## Colors
(현행 CLAUDE.md ## 3. 색상 체계 전문 — 토큰 값은 YAML과 동기화)

## Typography
(현행 CLAUDE.md ## 4. 타이포그래피 전문)

## UI Icons
(현행 CLAUDE.md ## 5. UI 아이콘 시스템 전문)

## Components
(현행 CLAUDE.md ## 6~8 전문: 글래스모피즘 카드, 공통 상태, 컴포넌트 패턴)

## Animation
(현행 CLAUDE.md ## 9. 애니메이션 전문)

## Accessibility
(현행 CLAUDE.md ## 10 + WCAG 2.2 강화 — 아래 상세)

## Layout
(현행 CLAUDE.md ## 11. 레이아웃 전문)

## Data Visualization
(현행 CLAUDE.md ## 12. 차트/시각화 전문)

## App Icons
(현행 CLAUDE.md ## 13. 앱 아이콘 디자인 원칙 전문)

## PWA & Meta Tags
(현행 CLAUDE.md ## 14. PWA & 메타태그 전문)

## Theme Switching
(현행 CLAUDE.md ## 15. 테마 전환 + 고대비 모드 추가)

## CSS Injection
(현행 CLAUDE.md ## 16. CSS 주입 패턴 전문)

## Performance Constraints
(Round 1 final의 3-3-5 내용)

## Security Gates
(Round 1 final의 3-3-4 내용)

## Do's and Don'ts
(Round 1 final의 3-3-6 내용)

## Checklist
(현행 CLAUDE.md 체크리스트 전문 + 신규 항목 추가)
```

### 3-4. 토큰 네이밍 마이그레이션: 현행 → 시맨틱 전환 상세

YAML 프론트매터에서 이미 시맨틱 이름을 사용한다. Markdown 본문에서 현행 CSS 변수명을 참조할 때의 매핑:

```
현행 CSS 변수            → YAML 시맨틱 키         → 새 CSS 변수 (별칭)
────────────────────     ────────────────────     ────────────────────
--bg-void                colors.bg.void           --surface-void
--bg-primary             colors.bg.primary        --surface-base
--bg-raised              colors.bg.raised         --surface-raised
--surface-1              colors.surface.s1        (유지)
--text-primary           colors.text.emphasis     --text-emphasis
--text-secondary         colors.text.default      --text-default
--text-muted             colors.text.subtle       --text-subtle
--green                  colors.semantic.success  --status-success
--blue                   colors.semantic.info     --status-info
--amber                  colors.semantic.warning  --status-warning
--red                    colors.semantic.danger   --status-danger
--accent                 (프로젝트별 선택)         --interactive-primary
--accent-rgb             colors.semantic_rgb.*    --interactive-primary-rgb
```

**마이그레이션 5단계 (구체 실행)**:

```
Phase M1 (즉시): DESIGN.md YAML에 시맨틱 키 확정 — 이 문서가 SOT
Phase M2 (1주): Markdown 본문에서 "현행 이름 (= 시맨틱 이름)" 병기
                예: "--bg-primary (= surface.base)"
Phase M3 (프로젝트별): 새 프로젝트는 시맨틱 CSS 변수만 사용
                      기존 프로젝트는 별칭 추가:
                      --surface-base: var(--bg-primary);
Phase M4 (안정 후): 구 이름 사용 시 lint warning 발행
Phase M5 (전환 완료): 별칭 제거 (급하지 않음)
```

> **핵심**: Phase M1~M2는 DESIGN.md 작성과 동시에 완료. Phase M3~M5는 각 프로젝트 적용 시 점진적.

---

## 4. Phase 1 신규 섹션 상세 코드

### 4-1. Core UX Constraints (G7 해결)

```markdown
## Core UX Constraints

이 섹션은 모든 디자인 결정에 선행하는 절대 제약이다.
AI 에이전트가 UI를 생성할 때, 컴포넌트 스타일보다 이 제약을 먼저 확인하라.

### UX Safe Zone (절대 고정 — AI 변형 금지)

| 요소 | 제약 | 위반 시 |
|------|------|---------|
| 내비게이션 구조 | 사이드바/탭 위치·계층·순서 고정 | 사용자 멘탈 모델 붕괴 |
| 핵심 CTA 위치 | 폼 제출, 저장 버튼의 위치/크기 불변 | 작업 완료 방해 |
| 폼 제출 흐름 | 입력→검증→확인→제출 순서 불변 | 데이터 손실 위험 |
| 에러 표시 위치 | 폼 필드 직하, 토스트 우하단 | 에러 인식 실패 |
| 키보드 흐름 | Tab 순서, Escape 닫기, Enter 제출 | 접근성 위반 |
| 파괴적 행동 | 모달 확인 필수 (인라인 삭제 금지) | 비가역 손실 |

### Vibe Zone (AI 변형 허용 — 토큰 범위 내)

- 카드 내부 레이아웃 변형
- 색상 강조 변주 (시맨틱 4색 + 브랜드 악센트 범위 내)
- 마이크로인터랙션 변주 (duration 범위 내)
- 장식적 요소 (글로우, 그라디언트 변주)
- 컨텐츠 카드 순서 (개인화 목적)

### Intent Mapping

| 사용자 의도 | 권장 패턴 | 금지 패턴 |
|------------|----------|----------|
| 단일 결정적 행동 | Primary 버튼 1개 | Primary 2개 병렬 |
| 정보 탐색 | 검색바 + 필터 + 카드 그리드 | 무한 스크롤 단독 |
| 데이터 입력 | 스텝 위자드 (3~5단계) | 한 페이지 20+ 필드 |
| 상태 확인 | KPI 카드 + 프로그레스 | 텍스트만의 상태 |
| 위험 행동 | 모달 + Destructive + 확인 | 인라인 삭제 |
| 설정 변경 | 토글/체크 + 즉시 저장 피드백 | 저장 버튼 없는 폼 |
```

### 4-2. Accessibility 강화 (G8 해결)

```markdown
## Accessibility

### WCAG 2.2 구체 기준 (vague "AA" 금지)

| 기준 | WCAG SC | 요구 | 검증 방법 |
|------|---------|------|----------|
| 색상 대비 | 1.4.3 AA | 본문 4.5:1, 대형(18px+) 3:1 | axe-core 자동 + DevTools |
| 포커스 가시성 | 2.4.7 AA / 2.4.11 AAA | focus-visible + 글로우 | 키보드 탐색 스크린샷 |
| 포커스 가림 방지 | 2.4.12 AA (2.2 신규) | 포커스된 요소가 다른 요소에 가려지지 않음 | Playwright focus trace |
| 터치 타겟 | 2.5.8 AA (2.2 신규) | 최소 24x24px, 권장 44x44px | CSS 감사 |
| 드래그 대안 | 2.5.7 AA (2.2 신규) | 드래그 동작에 클릭 대안 제공 | 수동 검증 |
| 키보드 조작 | 2.1.1 A | 모든 기능 키보드 접근 | Tab/Enter/Escape 테스트 |
| reduced-motion | 2.3.3 AAA | `prefers-reduced-motion` 대응 | 미디어쿼리 존재 확인 |

### 다계층 접근성 검증 파이프라인 (W3 evidence packet 수용)

```
Layer 1 — 정적 린트 (에이전트 생성 직후)
  ├─ accessible name 존재 확인
  ├─ aria-hidden 내 focusable 금지
  ├─ 신규 raw color에 토큰 페어 체크
  └─ img에 alt 필수

Layer 2 — DOM 스캔 (렌더링 후)
  ├─ axe-core 규칙 실행
  ├─ 대비 비율 측정
  └─ 누락된 랜드마크 감지

Layer 3 — 행위 테스트 (Playwright)
  ├─ Tab 순서 추적
  ├─ focus-visible 스크린샷
  ├─ 모달 포커스 트랩 (Escape 동작)
  └─ 키보드 활성화 (Enter/Space)

Layer 4 — 시각 검증
  ├─ 포커스 링 가림 없음
  ├─ 타겟 사이즈 측정
  ├─ 줌 200% reflow
  └─ 고대비 모드 (선택적)

Layer 5 — 인간 체크포인트
  ├─ 레이블 의미적 적절성
  ├─ 파괴적 행동 키보드 인체공학
  └─ 스크린리더 흐름 검토
```

### 4-3. Security Gates (G11 해결)

```markdown
## Security Gates

### 에이전트 신뢰 수준 (W3 수용)

| 수준 | 허용 | 예시 |
|------|------|------|
| **Allow** | 토큰 제안, 컴포넌트 초안, 메타데이터 제안, 스크린샷, 테스트 작성 | 대부분의 UI 작업 |
| **Require Approval** | 스키마 변경, 의존성 추가, 글로벌 CSS 변경, 생성 파일 수정 | 마스터님 or 인간 승인 |
| **Block** | 셸 보간, 자동 머지, 시크릿 접근, 런타임 원격 에셋, 프롬프트 기반 패키지 설치 | 절대 금지 |

### 위협 레지스터 (W3 Round 2 연구)

| 위협 | 완화책 |
|------|--------|
| MCP 명령 주입 | 공식/화이트리스트 도구만, 셸 보간 금지, 최소 권한 |
| 토큰 생성기 변조 | lockfile 리뷰, 결정론적 스냅샷, 최소 의존성 |
| 시각적으로 정상이나 접근 불가 | evidence packet + 인간 리뷰 |
| CSS 비대화 | raw-color 린트, CSS 바이트 예산, 중복 선언 스캔 |
| 스키마 드리프트 | 토큰 = canonical, DESIGN.md는 참조 |
```

### 4-4. Performance Constraints (G9 해결)

```markdown
## Performance Constraints

### 범용 예산 (모든 프로젝트)

| 항목 | 상한 | 사유 |
|------|------|------|
| backdrop-filter 요소 | 8개/화면 | GPU 합성 비용 |
| CSS 변수 | 80개/프로젝트 | 파싱·재계산 비용 |
| 애니메이션 속성 | transform, opacity만 | layout 변경 = 60fps 불가 |
| 이미지 로딩 | lazy + aspect-ratio 필수 | LCP 보호 |
| 인라인 스타일 | 토큰 시스템만 허용 | 유지보수 + 캐싱 |
| Tailwind arbitrary | 금지 (`bg-[#hex]` 등) | 토큰 드리프트 방지 |

### 프로젝트별 예산 (각 프로젝트 DESIGN.md override에서 정의)

예: cmux-win은 Electron 렌더러 → xterm 타이핑 지연, 패널 리사이즈 지연 예산 추가.
예: 설교 에디터는 PPT 이미지 로딩 → LCP 예산 추가.
```

### 4-5. Do's and Don'ts (G3 해결)

```markdown
## Do's and Don'ts

### Do's
- DO: 다크 배경 (#0a~#0f) 기본
- DO: 글래스모피즘 카드 hover (translateY + shadow)
- DO: KPI 수치 clamp()로 크고 굵게
- DO: 모든 인터랙티브 요소에 focus-visible
- DO: 한글 word-break: keep-all
- DO: 그라디언트 135deg 통일
- DO: reduced-motion 대응
- DO: 최소 44x44px 터치 타겟
- DO: WCAG 2.2 SC 1.4.3 대비 4.5:1
- DO: 에이전트 생성 코드에 evidence packet 첨부
- DO: 파괴적 행동에 모달 확인

### Don'ts
- DON'T: Primary 버튼 2개 나란히
- DON'T: 확인 없이 Destructive 행동
- DON'T: 내비게이션에 버튼 (Link 사용)
- DON'T: 한 폼에 20+ 필드
- DON'T: backdrop-filter 8개 초과
- DON'T: 인라인 CSS 하드코딩
- DON'T: Tailwind arbitrary value
- DON'T: 밝은 배경 기본 (요청 시에만)
- DON'T: generic shadcn/ui 무수정
- DON'T: 에이전트 자동 머지
- DON'T: 에이전트에 시크릿 접근
- DON'T: 검증 없이 AI 생성 UI 수용 (evidence packet 필수)
- DON'T: 스크린샷만으로 접근성 판정 (행위 검증 필수)
```

---

## 5. Phase 2 실행 계획: 컴포넌트 메타데이터 + 접근성 + 거버넌스

### 5-1. 핵심 5개 meta.json (G2 해결)

| 컴포넌트 | 파일 | 핵심 antiPatterns |
|----------|------|-------------------|
| glass-card | `~/.claude/components/glass-card.meta.json` | 밝은 배경 사용, 2단 중첩, backdrop-filter 8개 초과 |
| button | `~/.claude/components/button.meta.json` | Primary 2개 병렬, 내비게이션용, 확인 없는 Destructive |
| input | `~/.claude/components/input.meta.json` | 라벨 없음, validation 상태 없음, 20+ 필드 |
| modal | `~/.claude/components/modal.meta.json` | Escape 비활성, 포커스 트랩 없음, 스크롤 잠금 없음 |
| toast | `~/.claude/components/toast.meta.json` | 영구 표시 (auto-dismiss 필수), 접근성 role 없음 |

### 5-2. 토큰 인벤토리 + 별칭 매핑 (G4, G12 해결)

```
실행 단계:
1. CLAUDE.md 디자인 섹션에서 모든 CSS 변수명 grep → inventory.md
2. YAML 프론트매터의 시맨틱 키와 1:1 매핑표 작성
3. 구 이름 → 새 이름 별칭 CSS 생성
4. 프로젝트별 적용 시 별칭 레이어 삽입
```

### 5-3. 린트 훅 설계 (G5, G9 해결)

```bash
#!/bin/bash
# design-lint.sh — AI 생성 코드 검증 훅
# 커밋 전 또는 에이전트 생성 직후 실행

# 1. arbitrary value 탐지
echo "=== Tailwind Arbitrary Value Check ==="
grep -rn 'bg-\[#' --include="*.tsx" --include="*.jsx" --include="*.css" src/ && \
  echo "ERROR: arbitrary background color detected" && exit 1

grep -rn 'w-\[.*px\]' --include="*.tsx" --include="*.jsx" src/ && \
  echo "ERROR: arbitrary width detected" && exit 1

# 2. raw hex color 탐지 (토큰 외)
echo "=== Raw Hex Color Check ==="
grep -rn '#[0-9a-fA-F]\{6\}' --include="*.tsx" --include="*.jsx" src/ | \
  grep -v 'var(--' | grep -v '// token:' | grep -v 'generated' && \
  echo "WARNING: raw hex color found — use design tokens" 

# 3. inline style 탐지
echo "=== Inline Style Check ==="
grep -rn 'style={{' --include="*.tsx" --include="*.jsx" src/ | \
  grep -v 'generated' && \
  echo "WARNING: inline style found — prefer CSS variables/Tailwind"

echo "=== Design Lint Complete ==="
```

---

## 6. Phase 2~3 엣지 케이스 반영 (G13 해결)

### 6-1. 다크/라이트 + 고대비 모드

DESIGN.md `## Theme Switching` 섹션에 추가:

```css
/* 고대비 모드 (WCAG 2.2 SC 1.4.11) */
@media (prefers-contrast: high) {
    :root {
        --surface-s1: rgba(255,255,255,0.08);  /* 대비 강화 */
        --border: rgba(255,255,255,0.20);       /* 보더 강화 */
        --text-emphasis: #ffffff;                /* 최대 대비 */
    }
}
```

### 6-2. CSS 변수 폴백 체인

마이그레이션 중 3단 폴백:

```css
.component {
    background: var(--surface-base, var(--bg-primary, #0c111b));
    /* 새 이름 → 구 이름 → 하드코딩 폴백 */
}
```

### 6-3. i18n/한글 레이아웃 강화

```css
:lang(ko) {
    word-break: keep-all;
    overflow-wrap: break-word;
    font-feature-settings: "cv02", "cv03", "cv04", "cv11";
    -webkit-font-smoothing: antialiased;
    line-height: 1.7; /* 한글은 영문보다 0.1 높게 */
}
```

---

## 7. 최종 실행 타임라인

```
Phase 1 (즉시 — Round 2 실행)
  ├─ [G1]  CLAUDE.md → DESIGN.md 분리 (922줄 이동 + 참조 포인터)
  ├─ [G1]  YAML 프론트매터 작성 (토큰 60~80개)
  ├─ [G3]  Do's and Don'ts 섹션 작성 (안티패턴 25+항목)
  ├─ [G7]  Core UX Constraints 섹션 (Safe Zone + Intent Map)
  ├─ [G10] Brand DNA 섹션 (이중 인코딩)
  ├─ [G11] Security Gates 섹션 (3단계 신뢰 + 6건 위협)
  ├─ [G9]  Performance Constraints 섹션
  └─ [G13] 엣지 케이스 반영 (고대비, i18n, 폴백)

Phase 2 (단기)
  ├─ [G2]  핵심 5개 meta.json 작성
  ├─ [G8]  접근성 5계층 검증 파이프라인 문서화
  ├─ [G4,12] 토큰 인벤토리 + 별칭 매핑표
  ├─ [G5]  디자인 린트 훅 (arbitrary value + raw hex)
  └─ [G6]  에이전트 소비 최적화 (상시 DESIGN.md + 온디맨드 meta.json)

Phase 3 (중기)
  ├─ 시맨틱 토큰 별칭 도입 (프로젝트별)
  ├─ Style Dictionary 검토 (토큰 100개 초과 시)
  ├─ meta.json 확장 (5→15 컴포넌트)
  └─ Playwright 접근성 스모크 테스트

Phase 4 (장기)
  ├─ MAPE-K 거버넌스 (토큰 안정화 후)
  ├─ meta.json 자동 생성 스킬
  └─ Figma MCP 연동 (Figma 소스 확보 시)
```

---

## 8. RSI Round 2 진행 상태

| RSI 단계 | Round 1 | Round 2 |
|----------|---------|---------|
| Step 1: 검색·탐색 | DONE | W2+W3 연구 완료 |
| Step 2: 패턴·철학 추출 | DONE | 이 문서에서 합의점/갈등점 해결 |
| Step 3: 객관적 평가 | DONE | G1~G13 해결 매핑 완료 |
| Step 4: 영속 저장 | DONE | **이 문서 = Round 2 영속 저장** |
| Step 5: Skill/Harness 제작 | 미실행 | **마스터님 승인 후 DESIGN.md 실제 작성** |

---

## 9. 마스터님 승인 요청

Phase 1 실행(CLAUDE.md → DESIGN.md 분리)은 **글로벌 CLAUDE.md의 922줄을 이동**하는 대규모 변경입니다.

**승인 필요 사항**:
1. CLAUDE.md 215~1137줄을 DESIGN.md로 분리해도 되는가?
2. YAML 프론트매터의 시맨틱 토큰 네이밍(위 매핑표)이 적절한가?
3. 신규 섹션 6개(Core UX, Brand DNA, Security, Performance, Do's/Don'ts, Accessibility 강화)를 추가해도 되는가?
4. `~/.claude/components/` 디렉토리에 meta.json 5개를 생성해도 되는가?

마스터님의 지시를 대기합니다.
