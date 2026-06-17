---
# ═══════════════════════════════════════════════════════
# 신교수님 통합 디자인 시스템 — DESIGN.md
# AI 에이전트 + 인간 디자이너 공용 정책 계약
# ═══════════════════════════════════════════════════════
#
# 이 YAML은 에이전트 정책 토큰(Agent Policy Tokens)이다.
# 빌드 시스템의 SOT(Single Source of Truth)가 아니다.
# 프로젝트별 빌드 SOT는 해당 프로젝트의 design/tokens/*.json에 둔다.
# 프로젝트 토큰이 이 YAML과 충돌 시, 프로젝트 토큰이 우선한다.
#
version: "1.0.0"
schemaVersion: 1

# ─── Brand Mood Guardrails ───
brand:
  background_lightness_max: 12        # unit: HSL L% — 배경 명도 상한
  accent_hue_range: [35, 50]          # unit: HSL H° — 황금빛 톤 범위
  gradient_angle: 135                 # unit: deg
  glass_blur_min: 16                  # unit: px
  prohibited_moods:
    - flat
    - pastel
    - corporate-blue-monotone
    - neon-rainbow
    - candy-colored
    - generic-shadcn-default

# ─── Primitive Palette ───
# Layer 1: 원시 색상. 직접 사용 금지 — semantic 계층을 통해서만 소비.
primitive:
  charcoal:
    900: "#0a0a0a"
    850: "#0a0e1a"
    800: "#0c111b"
    750: "#0f172a"
    700: "#111827"
    650: "#16161d"
  slate:
    200: "#f1f5f9"
    400: "#94a3b8"
    500: "#64748b"
  green:
    500: "#22c55e"
    400: "#34d399"
  blue:
    500: "#3b82f6"
    400: "#60a5fa"
    600: "#448aff"
  amber:
    500: "#f59e0b"
    400: "#fbbf24"
  red:
    500: "#ef4444"
    400: "#f87171"
  cyan:
    500: "#00A8FF"
    400: "#00d4ff"
    300: "#38bdf8"
  purple:
    500: "#7c6ef0"
    400: "#8b5cf6"
    300: "#a78bfa"
  gold:
    500: "#FFB800"

# ─── Semantic Tokens ───
# Layer 2: 의미적 역할. 에이전트와 컴포넌트가 소비하는 대상.
semantic:
  surface:
    void: "#0a0a0a"                   # 최심부 배경 (보이드)
    base: "#0c111b"                   # 메인 배경
    raised: "#111827"                 # 떠있는 표면
    glass_1: "rgba(255,255,255,0.04)" # 글래스 카드 Lv1
    glass_2: "rgba(255,255,255,0.06)" # 호버 상태
    glass_3: "rgba(255,255,255,0.09)" # 활성 상태
  text:
    emphasis: "#f1f5f9"               # 강조 (최고 대비)
    default: "#94a3b8"                # 기본
    subtle: "#64748b"                 # 보조
    disabled: "rgba(255,255,255,0.25)"
  status:
    success: "#22c55e"                # 완료/성공
    info: "#3b82f6"                   # 활성/정보
    warning: "#f59e0b"                # 경고/대기
    danger: "#ef4444"                 # 에러/위험
  status_rgb:                         # rgba() 사용 시 (생성 권장, 수동 작성 대안)
    success: "34, 197, 94"
    info: "59, 130, 246"
    warning: "245, 158, 11"
    danger: "239, 68, 68"
    cyan: "0, 168, 255"
  interactive:
    primary: "(프로젝트별 악센트 축 선택)"
    hover: "rgba(255,255,255,0.07)"
    active: "rgba(255,255,255,0.10)"
  border:
    default: "rgba(255,255,255,0.08)"
    emphasis: "rgba(255,255,255,0.25)"

# ─── Accent Axes (프로젝트 성격별 선택) ───
accent_axes:
  A_blue_cyan: ["#00A8FF", "#00d4ff", "#38bdf8"]     # 기술/데이터/모니터링
  B_purple_violet: ["#7c6ef0", "#8b5cf6", "#a78bfa"]  # 창작/브랜드/교육
  C_dual_premium: { cyan: "#00D4FF", gold: "#FFB800" } # 프리미엄/내러티브

# ─── Typography ───
typography:
  families:
    ui: "Pretendard Variable, Inter, -apple-system, Noto Sans KR, sans-serif"
    serif: "Noto Serif KR, serif"
    code: "JetBrains Mono, D2Coding, monospace"
  scale:                              # unit: CSS values (clamp/px)
    hero:    { size: "clamp(22px,3vw,36px)", weight: 800, line_height: 1.1 }
    title:   { size: "clamp(20px,4vw,28px)", weight: 800, line_height: 1.2 }
    section: { size: "15px",                 weight: 600, line_height: 1.3 }
    label:   { size: "11px",                 weight: 600, line_height: 1.4, letter_spacing: "0.1em", transform: "uppercase" }
    body:    { size: "14px",                 weight: 400, line_height: 1.6 }

# ─── Spacing ───
spacing:
  unit: px
  base: 4
  scale: [4, 8, 12, 16, 20, 24, 32, 40, 48, 64]

# ─── Border Radius ───
radius:
  unit: px
  sm: 6        # 뱃지, 태그, 툴팁
  md: 10       # 버튼, 입력폼
  lg: 12       # 글래스 카드
  xl: 20       # 모달, 대형 패널
  full: 9999   # 원형 뱃지, 아바타

# ─── Opacity Scale ───
opacity:
  subtle: 0.04     # 글래스 카드 배경
  light: 0.06      # 호버 배경
  border: 0.08     # 기본 보더
  medium: 0.10     # 디바이더
  strong: 0.15     # 뱃지 배경
  heavy: 0.25      # 강조 보더

# ─── Shadows ───
shadows:
  sm:   "0 1px 3px rgba(0,0,0,0.3)"
  md:   "0 4px 16px rgba(0,0,0,0.3)"
  lg:   "0 8px 32px rgba(0,0,0,0.4)"
  xl:   "0 24px 64px rgba(0,0,0,0.5)"
  glow: "0 0 24px rgba(var(--accent-rgb),0.2)"

# ─── Animation ───
animation:
  easing:
    spring:   "cubic-bezier(0.22, 1, 0.36, 1)"
    standard: "cubic-bezier(0.4, 0, 0.2, 1)"
  duration:
    unit: s
    fast: 0.15      # 툴팁, 색상 변화
    normal: 0.25     # 호버, 포커스
    slow: 0.4        # 모달 진입, 페이지 전환

# ─── Borders ───
borders:
  unit: px
  thin: 1        # 카드 보더, 디바이더
  medium: 2      # 포커스 outline
  thick: 3       # 탭 active, 토스트 좌측
  heavy: 4       # 스텝카드 좌측 컬러바

# ─── Z-Index ───
z_index:
  sidebar: 10
  dropdown: 30
  toast: 90
  modal_backdrop: 100
  modal_content: 101
  loading: 200

# ─── Breakpoints ───
breakpoints:
  unit: px
  mobile: 800
  tablet: 1200

# ─── Performance Budget (범용 가이드) ───
# 프로젝트별 정밀 예산은 각 프로젝트의 DESIGN.md override에서 측정·정의한다.
performance:
  max_backdrop_filter_per_screen: 8
  animation_properties_allowed: ["transform", "opacity"]
  image_loading: "lazy"
  image_aspect_ratio: "required"
---

## Overview

신교수님 통합 디자인 시스템. **다크 퍼스트 + 글래스모피즘 + 시네마틱 역광**의 프리미엄 UI를 모든 프로젝트에 일관되게 적용한다.

**운용 원칙:**
- 기본값 = 이 문서의 스타일 → 질문 없이 바로 적용
- 대안 = 제안만 → 신교수님 승인 후에만 적용
- 강제 변경 금지 → 묵시적 적용 절대 금지

**파일 역할:** 이 DESIGN.md는 에이전트 정책(Policy) 문서다. 빌드 SOT가 아니다. 프로젝트별 빌드 토큰은 해당 프로젝트의 `design/tokens/` 디렉토리에 둔다. 충돌 시 프로젝트 토큰이 우선한다.

**토큰 참조:** 모든 토큰 값은 위 YAML 프론트매터에 정의되어 있다. 이하 산문에서 토큰 값을 중복 기재하지 않는다. 색상·간격·크기 등은 YAML의 해당 키를 참조하라.

---

## Core UX Constraints

이 섹션은 모든 디자인 결정에 **선행**하는 절대 제약이다. AI 에이전트가 UI를 생성할 때, 컴포넌트 스타일보다 이 제약을 먼저 확인하라.

### UX Safe Zone (절대 고정 — AI 변형 금지)

| 요소 | 제약 | 위반 결과 |
|------|------|----------|
| 내비게이션 구조 | 사이드바/탭 위치·계층·순서 고정 | 멘탈 모델 붕괴 |
| 핵심 CTA 위치 | 폼 제출, 저장 버튼의 위치/크기 불변 | 작업 완료 방해 |
| 폼 제출 흐름 | 입력 → 검증 → 확인 → 제출 순서 불변 | 데이터 손실 위험 |
| 에러 표시 위치 | 폼 필드 직하, 토스트 우하단 | 에러 인식 실패 |
| 키보드 흐름 | Tab 순서, Escape 닫기, Enter 제출 | 접근성 위반 |
| 파괴적 행동 | 모달 확인 필수, 인라인 삭제 금지 | 비가역 손실 |

### Vibe Zone (AI 변형 허용 — YAML 토큰 범위 내)

- 카드 내부 레이아웃 변형
- 색상 강조 변주 (semantic 토큰 범위 내)
- 마이크로인터랙션 변주 (animation.duration 범위 내)
- 장식적 요소 (글로우, 그라디언트 변주 — gradient_angle 135deg 고정)
- 컨텐츠 카드 순서 (개인화 목적)

### Intent Mapping (사용자 의도 → 패턴)

| 사용자 의도 | 권장 패턴 | 금지 패턴 |
|------------|----------|----------|
| 단일 결정적 행동 | Primary 버튼 1개 | Primary 2개 병렬 |
| 정보 탐색 | 검색바 + 필터 + 카드 그리드 | 무한 스크롤 단독 |
| 데이터 입력 | 스텝 위자드 (3~5단계) | 한 페이지 20+ 필드 |
| 상태 확인 | KPI 카드 + 프로그레스 | 텍스트만의 상태 설명 |
| 위험 행동 확인 | 모달 + Destructive 버튼 + 확인 | 인라인 삭제 |
| 설정 변경 | 토글/체크 + 즉시 저장 피드백 | 저장 버튼 없는 폼 |
| 목록 탐색 | 테이블 (sticky 헤더) + 정렬/필터 | 카드만 나열 (50+건) |

---

## Brand DNA & Mood Guidelines

### 조형적 연출 메타포 (Aesthetic Rendering Metaphors)

마치 어두운 고딕 성당 안에 유일하게 흘러드는 황금빛 햇살처럼 — 화면은 90% 이상의 깊고 성스러운 어둠(`surface.void`)을 유지하고, 사용자가 응시할 단 하나의 핵심 액션 요소(`interactive.primary`)만이 신비롭고 깊이 있는 역광 글로우(`shadows.glow`)를 뿜어낸다.

글래스모피즘 카드는 이 어둠 속에 떠 있는 반투명한 창(窓)이다. 빛은 카드의 가장자리를 스치며 미세한 보더(`border.default`)로 존재를 암시하고, 호버 시 카드가 살짝 떠오르며(`translateY(-2px)`) 더 깊은 그림자(`shadows.lg`)를 드리운다.

숫자와 KPI는 이 장면의 주인공이다 — 크고 굵게(`typography.scale.hero`), 장식보다 데이터가 말하게 하라. 워크플로우는 스텝 카드와 도트 커넥터로 시각화하되, 과잉 장식 없이 상태색(`status.*`)으로만 구분한다.

모든 그라디언트는 135도. 느린 글로우는 2~3초 주기. 서두르지 않는 우아함.

### 금지 무드 (Anti-Visual Mood)

- **NEVER**: 플랫 디자인 — 깊이감 없는 평면적 UI
- **NEVER**: 파스텔 톤 — 가볍고 몽환적인 색조
- **NEVER**: 기업형 블루 단색 — 차갑고 획일적인 톤
- **NEVER**: 네온 레인보우 — 과시적이고 산만한 그라디언트
- **NEVER**: generic shadcn/ui 기본 테마 무수정 — 브랜드 정체성 부재
- **NEVER**: 밝은 배경 기본 — 다크가 기본, 라이트는 명시적 요청 시에만

### 악센트 축 선택 (프로젝트 성격별)

위 YAML `accent_axes` 참조. 프로젝트 시작 시 A/B/C 중 하나를 선택하여 `interactive.primary`에 바인딩한다.

---

## Colors

모든 색상 값은 위 YAML의 `primitive`, `semantic`, `accent_axes`에 정의되어 있다.

**계층 규칙:**
1. 컴포넌트는 `semantic.*` 토큰만 소비한다. `primitive.*`를 직접 참조하지 않는다.
2. RGB 분리값(`status_rgb.*`)은 `rgba()` 함수에서 사용한다.
3. 프로젝트별 악센트는 `accent_axes`에서 선택하여 `interactive.primary`에 바인딩한다.
4. 새 색상 추가 시 `primitive`에 등록 → `semantic`에 매핑 → CSS alias 생성 순서를 따른다.

**교회 프로젝트 전용 — 전례력 컬러:**

| 절기 | 색상 | 사용 |
|------|------|------|
| 대림절(Advent) | #7c3aed (바이올렛) | 악센트 오버라이드 |
| 성탄절(Christmas) | #fbbf24 (골드) | 악센트 오버라이드 |
| 사순절(Lent) | #7c2d12 (갈색) | 악센트 오버라이드 |
| 부활절(Easter) | #ffffff (화이트) | 텍스트 강조 |
| 성령강림(Pentecost) | #dc2626 (레드) | 악센트 오버라이드 |
| 연중시기(Ordinary) | #16a34a (그린) | 악센트 오버라이드 |

**그라디언트 공식:**
- 브랜드: `linear-gradient(135deg, [악센트-어두운], [악센트-밝은])`
- 프로그레스: `linear-gradient(90deg, [cyan], [gold 또는 green])`
- Hero 배경: `linear-gradient(135deg, rgba([악센트],0.06), rgba([보조],0.04))`

**그림자:** YAML `shadows.*` 참조. 5단계 (sm→md→lg→xl→glow).

---

## Typography

폰트 패밀리와 스케일은 YAML `typography.*` 참조.

**폰트 로딩:** Pretendard는 자가 호스팅 또는 CDN(`cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/...`) 중 프로젝트 보안/오프라인 요구에 따라 선택한다. Electron/오프라인 앱은 자가 호스팅 필수.

**한글 최적화:**
```css
:lang(ko) {
    word-break: keep-all;
    overflow-wrap: break-word;
    font-feature-settings: "cv02", "cv03", "cv04", "cv11";
    -webkit-font-smoothing: antialiased;
    line-height: 1.7;
}
```

**텍스트 오버플로우:** 한 줄 truncate(`text-overflow: ellipsis`) 또는 다중 줄 clamp(`-webkit-line-clamp: N`).

---

## Components

### 글래스모피즘 카드 (핵심 컴포넌트)

4개 변형: default, accent, nested, interactive. 위 YAML의 `semantic.surface.glass_*`, `shadows.*`, `radius.lg` 토큰을 소비한다.

**핵심 규칙:**
- `backdrop-filter: blur(16px) saturate(1.3)` — 기본
- hover: `translateY(-2px)` + `shadows.lg`
- nested 변형: `backdrop-filter: none` + 불투명 배경 (성능)
- **antiPatterns**: 밝은 배경 사용 금지, 2단 중첩 금지, 한 화면 8개 초과 금지

### 버튼 3단계

Primary (그라디언트 + 글로우), Secondary (반투명 악센트), Ghost (투명 + 보더).

**antiPatterns**: Primary 2개 나란히 금지, 내비게이션용 금지, Destructive는 확인 모달 필수.

### 입력 폼

배경 `surface.glass_1`, 보더 `border.default`, 포커스 시 악센트 보더 + 글로우.

**antiPatterns**: 라벨 없는 입력 금지, validation 상태 없이 제출 금지, 한 페이지 20+ 필드 금지.

### 모달

배경 `rgba(0,0,0,0.6)` + `blur(6px)`, 콘텐츠 `surface.raised` + `radius.xl`.

**antiPatterns**: Escape 비활성 금지, 포커스 트랩 없는 모달 금지, 파괴적 행동 확인 없는 닫기 금지.

### 토스트

우하단 고정, 상태색 좌측 보더(`borders.thick`), 자동 소멸.

**antiPatterns**: 영구 표시 금지 (auto-dismiss 필수), ARIA role="alert" 없는 토스트 금지.

> 상세 CSS 코드 예시는 `~/.claude/CLAUDE.md` 디자인 섹션 참조 (미러링 기간 동안 유지).

---

## Animation

이징과 듀레이션은 YAML `animation.*` 참조.

**핵심 키프레임:** pulse-glow(2.5s), fadeUp(slow), slideUp(slow, 모달), shimmer(1.8s, 스켈레톤), spin(0.6s, 스피너).

**규칙:**
- 애니메이션 속성은 `transform`과 `opacity`만 사용 (GPU 가속)
- `layout` 변경 애니메이션 금지 (60fps 불가)
- `@media (prefers-reduced-motion: reduce)` 전역 대응 필수

---

## Accessibility

### WCAG 2.2 구체 기준

| 기준 | SC | 요구 |
|------|----|------|
| 색상 대비 | 1.4.3 AA | 본문 4.5:1, 대형(18px+) 3:1 |
| 포커스 가시성 | 2.4.7 AA | focus-visible + outline + 글로우 |
| 포커스 가림 방지 | 2.4.12 AA | 포커스된 요소가 다른 요소에 가려지지 않음 |
| 터치 타겟 | 2.5.8 AA | 최소 24x24, 권장 44x44px |
| 드래그 대안 | 2.5.7 AA | 드래그에 클릭 대안 필수 |
| 키보드 접근 | 2.1.1 A | 모든 기능 키보드 도달 가능 |
| reduced-motion | 2.3.3 AAA | `prefers-reduced-motion` 전역 대응 |

### 접근성 검증 파이프라인 (evidence packet)

AI 생성 UI를 수용하기 전 5계층 검증:

1. **정적 린트**: accessible name, aria-hidden 내 focusable 금지, img alt 필수
2. **DOM 스캔**: axe-core 규칙, 대비 측정, 랜드마크 존재
3. **행위 테스트**: Tab 순서, focus-visible, 모달 포커스 트랩, Escape/Enter
4. **시각 검증**: 포커스 링 가림 없음, 타겟 사이즈, 줌 200% reflow
5. **인간 체크포인트**: 레이블 의미 적절성, 파괴적 행동 인체공학

---

## Layout

**반응형 브레이크포인트:** YAML `breakpoints.*` 참조.

- 모바일(<800px): 1열, 사이드바 숨김, 하단 네비게이션
- 태블릿(800~1200px): 2열, 사이드바 축소 가능
- 데스크톱(>1200px): 3~4열, 사이드바 고정

**스크롤바:** 6px 너비, 반투명 thumb, 투명 track.

**z-index:** YAML `z_index.*` 참조.

---

## Performance Constraints

YAML `performance.*` 참조.

**범용 가이드 (모든 프로젝트):**
- backdrop-filter: 한 화면 최대 8개. 초과 시 nested 변형(불투명) 사용
- 애니메이션: transform/opacity만 사용
- 이미지: lazy loading + aspect-ratio 필수
- 인라인 CSS: 토큰 시스템만 허용, 하드코딩 금지
- Tailwind: arbitrary value(`bg-[#hex]`, `w-[Npx]`) 금지 — 토큰만 허용

**프로젝트별 정밀 예산:** 각 프로젝트의 DESIGN.md override 또는 `design/budgets.json`에서 측정·정의한다. 예: Electron → 렌더러 시작 시간, 패널 리사이즈 지연 측정.

---

## Security Gates

### 에이전트 신뢰 수준

| 수준 | 허용 범위 |
|------|----------|
| **Allow** | 토큰 제안, 컴포넌트 초안, 메타데이터 제안, 스크린샷, 테스트 작성 |
| **Require Approval** | 스키마 변경, 의존성 추가, 글로벌 CSS 변경, 생성 파일 수정 |
| **Block** | 셸 보간, 자동 머지, 시크릿 접근, 런타임 원격 에셋, 프롬프트 기반 패키지 설치 |

### 위협 완화

| 위협 | 완화 |
|------|------|
| MCP 명령 주입 | 공식/화이트리스트 도구만, 셸 보간 금지, 최소 권한 |
| 토큰 생성기 변조 | lockfile 리뷰, 결정론적 스냅샷, 최소 의존성 |
| 시각적 정상 + 접근 불가 | evidence packet 5계층 검증 + 인간 리뷰 |
| CSS 비대화 | raw-color 린트, CSS 바이트 예산, 중복 선언 스캔 |
| 스키마 드리프트 | 프로젝트 토큰 = canonical, DESIGN.md = 정책 참조 |

---

## Do's and Don'ts

### Do's (반드시)

- 다크 배경 (`surface.void` ~ `surface.base`) 기본 적용
- 글래스모피즘 카드에 hover 효과 (translateY + shadow 확대)
- KPI 수치는 `typography.scale.hero`로 크고 굵게
- 모든 인터랙티브 요소에 focus-visible 인디케이터
- 한글 텍스트에 `word-break: keep-all`
- 그라디언트 각도 135deg 통일
- `@media (prefers-reduced-motion: reduce)` 전역 대응
- 최소 44x44px 터치 타겟
- WCAG 2.2 SC 1.4.3 대비 4.5:1 유지
- AI 생성 UI에 evidence packet (5계층 검증) 첨부
- 파괴적 행동에 모달 확인 필수
- 프로젝트별 성능 예산 측정 후 적용
- 컴포넌트는 `semantic.*` 토큰만 소비 (`primitive.*` 직접 참조 금지)

### Don'ts (절대 금지)

- Primary 버튼 2개 나란히 배치
- 확인 없이 Destructive 행동 실행
- 내비게이션에 버튼 사용 (Link/Anchor 사용)
- 한 폼에 20개 이상 필드 나열
- backdrop-filter 한 화면 8개 초과
- 인라인 CSS 하드코딩 (토큰만 허용)
- Tailwind arbitrary value (토큰 외 값 금지)
- 밝은 배경 기본 적용 (명시적 요청 시에만)
- generic shadcn/ui 기본 테마 무수정 사용
- 에이전트 자동 머지 (PR 초안만 허용)
- 에이전트에 시크릿/자격증명 접근 허용
- 스크린샷만으로 접근성 판정 (행위 검증 필수)
- `primitive.*` 팔레트를 컴포넌트에서 직접 소비

---

## Checklist

### 필수 (매번 확인)

- [ ] 다크 테마 (surface.void ~ surface.base 배경)
- [ ] 글래스모피즘 카드 (blur + 반투명 + 보더 + 4변형 + 성능 폴백)
- [ ] YAML 토큰 적용 (spacing, radius, opacity, duration, borders)
- [ ] 시맨틱 4색 (status.*) + RGB 분리값
- [ ] 그림자 5단계 (shadows.*)
- [ ] Pretendard + Inter 페어링, 한글 keep-all
- [ ] clamp() 반응형 타이포 + line-height
- [ ] 135deg 그라디언트 각도
- [ ] 2~3초 느린 글로우 + spring 이징
- [ ] hover, focus-visible, active, disabled 상태
- [ ] 포커스 인디케이터 (focus-visible + 글로우)
- [ ] 반응형 (<800 / 800~1200 / >1200)
- [ ] reduced-motion 대응
- [ ] WCAG 2.2 대비 4.5:1
- [ ] 안티패턴(Don'ts) 위반 없음

### 조건부 (해당 시)

- [ ] 입력 폼 + validation 상태 (에러/성공)
- [ ] 모달 (포커스 트랩 + Escape)
- [ ] 토스트 (auto-dismiss + ARIA role)
- [ ] 데이터 테이블 (sticky 헤더 + 호버)
- [ ] 차트/시각화 (투명 배경 + 악센트 팔레트)
- [ ] PWA 메타태그 + manifest
- [ ] 앱 아이콘 (512px, 다크 그라디언트)
- [ ] evidence packet (AI 생성 UI인 경우)

---

## Token Migration Guide

### 역방향 호환 별칭 레이어

기존 프로젝트에서 구 변수명을 유지하면서 새 시맨틱 토큰으로 전환하려면, 프로젝트 글로벌 CSS에 다음을 1회 선언한다:

```css
/* ═══ Retrofit Compatibility Layer ═══ */
:root {
    --bg-void: var(--surface-void);
    --bg-primary: var(--surface-base);
    --bg-raised: var(--surface-raised);
    --surface-1: var(--glass-1);
    --surface-2: var(--glass-2);
    --surface-3: var(--glass-3);
    --text-primary: var(--text-emphasis);
    --text-secondary: var(--text-default);
    --text-muted: var(--text-subtle);
    --green: var(--status-success);
    --red: var(--status-danger);
    --amber: var(--status-warning);
    --blue: var(--status-info);
}
/* 마이그레이션 완료 후 이 블록 삭제 */
```

컴포넌트 코드 수정 없이 하위 호환 100% 보장. 마이그레이션 완료 후 이 파일만 제거.

### 마이그레이션 단계

1. **이 DESIGN.md 배포** — 미러링 방식 (CLAUDE.md 유지)
2. **새 프로젝트**: 시맨틱 변수만 사용
3. **기존 프로젝트**: 역방향 별칭 레이어 추가
4. **점진 전환**: 프로젝트별 구 변수 사용처를 배치 교체
5. **별칭 제거**: 전환 완료 후 (급하지 않음)

### 프로젝트 호환 선언

프로젝트가 이 디자인 시스템을 채택할 때, 프로젝트 DESIGN.md 또는 `design/config.json`에 다음을 선언한다:

```json
{ "tokenSchemaVersion": 1, "aliasLayer": "retrofit" }
```

- `tokenSchemaVersion: 1`: 이 DESIGN.md v1.0.0의 시맨틱 토큰을 지원
- `aliasLayer: "retrofit"`: 구 변수명 호환 레이어 활성 상태
- 별칭 레이어 제거 후: `"aliasLayer": "none"`으로 변경
