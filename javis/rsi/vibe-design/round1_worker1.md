# RSI Vibe-Design — Round 1 Worker1 심층 연구 보고서

> **Worker**: Worker1(Claude)
> **Date**: 2026-06-17
> **RSI Stage**: Step 1(검색·탐색) + Step 2(패턴·철학 추출) + Step 3(객관적 평가)
> **Status**: COMPLETE

---

## Executive Summary

2026년 바이브디자인(Vibe Design)은 단순 "자연어로 UI 생성"을 넘어 **에이전틱 디자인 시스템(Agentic Design System)** 패러다임으로 진화했다. 핵심 전환: 디자인 시스템이 인간용 참조 문서에서 **AI 에이전트가 프로그래머블하게 소비하는 계약(Contract)**으로 변모. Google이 2026-04 DESIGN.md 사양을 오픈소스화하면서 업계 표준이 형성 중이다.

---

## Part A: RSI Step 1 — 검색·탐색 결과

### A1. 핵심 전문가 및 출처

| 전문가/조직 | 기여 | 출처 |
|-------------|------|------|
| **Andrej Karpathy** | "Vibe Coding" 개념 대중화 (2025) | 원조 트윗·강연 |
| **Anna Arteeva** (Payoneer) | "Design Systems for the Vibe-Coding Era" — 3계층 아키텍처, shadcn+Tailwind 전략 | [Design Systems Collective](https://www.designsystemscollective.com/design-systems-for-the-vibe-coding-era-42282e1affef) |
| **Diana Wolosin** (Indeed) | JSON 메타데이터 벤치마크 — MD 대비 80% 토큰 절감, 정확도 상승 | [Into Design Systems 2026](https://www.intodesignsystems.com/agentic-design-systems) |
| **Jan Six** (GitHub) | 시맨틱 토큰 네이밍 (`danger.background` > `red-500`) | 동 컨퍼런스 |
| **Brad Frost** | "Plant Seeds, Not Trees" — 점진적 에이전틱 도입 전략 | 동 컨퍼런스 |
| **Google Labs** | DESIGN.md 오픈소스 사양 (Apache-2.0, 2026-04-21) | [Google Stitch](https://pasqualepillitteri.it/en/news/1251/google-stitch-design-md-open-source-spec-2026) |
| **Chris Carini** | AI Component Metadata 스킬 (`npx claude-skill ai-component-metadata`) | [TDP Blog](https://designproject.io/blog/agentic-design-system/) |
| **Spotify Encore** | 레이어드 컴포넌트 아키텍처 (Foundation/Style/Behavior 분리) | AI Design Systems Conference 2026 |
| **GitHub Primer** | 에이전트 안전 출력 정책 (이슈만 생성, 자동 머지 금지) | 동 컨퍼런스 |

### A2. Google DESIGN.md 사양 (2026-04 오픈소스)

**파일 구조**:
```
---
# YAML 프론트매터 (기계 판독용 디자인 토큰)
colors:
  primary: "#1a3a52"
  background: "#f7f3ec"
typography:
  headline:
    fontFamily: "Inter"
    fontSize: 48
    fontWeight: 700
spacing:
  scale: [4, 8, 16, 24, 32]
---

## Overview
(브랜드 정체성, 디자인 철학 — 인간+AI 공용 산문)

## Colors
## Typography
## Layout
## Elevation & Depth
## Shapes
## Components
## Do's and Don'ts
```

**핵심 설계 결정**:
- Markdown 선택 이유: LLM이 JSON/YAML보다 Markdown을 더 신뢰성 있게 파싱
- YAML 프론트매터 = "WHAT" (기계용) / Markdown 산문 = "WHY" (판단용)
- 접근성: WCAG AA/AAA 색상 대비 검증 의무화
- 현재 알파 — 애니메이션, 다크모드 토큰, 반응형 브레이크포인트 미해결

### A3. 에이전틱 디자인 시스템 아키텍처

**3파일 표준 (AGENTS.md + SKILL.md + DESIGN.md)**:
- `AGENTS.md`: 프로젝트 컨텍스트 + 에이전트 행동 규칙
- `SKILL.md`: 이식 가능한 에이전트 능력
- `DESIGN.md`: 시각적 정체성 + 디자인 토큰

**컴포넌트 메타데이터 6파일 구조** (TDP 권장):
```
button/
├── button.tsx              # 구현
├── button.meta.json        # AI 소비용 메타데이터
├── button.tokens.css       # 토큰 정의
├── button.stories.tsx      # Storybook 시각 참조
├── button.test.tsx         # 사용법 강제 테스트
└── index.ts                # 익스포트
```

**meta.json 필수 필드**:
```json
{
  "category": "atom",
  "purpose": "Interactive trigger for a single decisive action",
  "variants": ["primary", "secondary", "minimal", "destructive"],
  "commonPatterns": ["dialog confirm/cancel", "form submit"],
  "antiPatterns": [
    "two primary buttons side by side",
    "buttons used for navigation",
    "destructive variant without confirm step"
  ],
  "tokens": {
    "background": "color.action.primary",
    "text": "color.text.on-primary",
    "spacing": "spacing.button"
  },
  "accessibility": { "keyboard": true, "screenReader": true, "focusRing": true }
}
```

### A4. Indeed 벤치마크 (Diana Wolosin)

| 지표 | Markdown | JSON |
|------|----------|------|
| 토큰 소비 | ~30,000/쿼리 | ~6,000/쿼리 (80% 절감) |
| 정확도 | 82% + 환각 발생 | 높은 정확도, 환각 감소 |
| 연간 비용 | $1,500 | $300 |
| 컴포넌트 수 | 77개 (MDX 파싱) | 77개 (JSON 변환) |

**핵심**: JSON은 계약(Contract)이다. 명시적 키, 명시적 값, 명시적 경계.

### A5. 디자인 드리프트 방지 거버넌스

**MAPE-K 자기치유 루프** (IBM 2003 모델 기반):
```
Observe(Figma API/CI hooks/사용량 분석)
  → Detect(드리프트 스코어링 엔진)
  → Suggest(자동 생성 PR)
  → Fix(승인 후 적용)
  → Learn(패턴 학습)
```

**신뢰 수준 프레임워크**:
| Level | 권한 | 예시 |
|-------|------|------|
| Intern | 제안만 | "이 색상은 토큰에 없습니다" |
| Junior | 기계적 수정 | auto-fixable lint 이슈 |
| Senior | 제한적 자율 | 컴포넌트 조합 |
| 절대 불가 | 완전 자율 금지 | 인간 판단 게이트 필수 |

**GitHub Primer 정책**: 에이전트는 이슈만 생성 가능, 자동 머지 절대 금지.

### A6. Intent-First Design 방법론

**핵심 전환**: "이 버튼을 어디에 놓을까" → "사용자가 이 시점에서 달성하려는 의도가 무엇인가"

**Experience Architecture** (2026 #1 기술 스킬):
- Intent Mapping: 사용자 목표 → 시스템 상태 흐름
- 맥락적 인라인 제어: 챗 UI를 넘어, 작업 화면 내에서 AI 상호작용
- 투명성 필수: AI가 주도권을 가지면 "무엇을 왜 하는지" 명확히 설명

---

## Part B: RSI Step 2 — 패턴·철학 추출

### B1. 5대 핵심 패턴

#### Pattern 1: "계약으로서의 디자인 시스템" (Design System as Contract)

**현상**: 디자인 시스템이 인간용 참조에서 AI 에이전트용 프로그래머블 계약으로 전환.
**구현**: meta.json + DESIGN.md YAML 프론트매터 = 기계 판독 가능한 계약.
**효과**: "될 것이다" → "확인했다"로 전환. 에이전트가 추측 대신 계약을 따름.

#### Pattern 2: "시맨틱 의도 토큰" (Semantic Intent Tokens)

**현상**: 토큰 네이밍이 구현(`red-500`)에서 의도(`danger.background`)로 전환.
**원칙**: 변수가 역할(role)을 설명해야 한다 — emphasis/default/subtle > primary/secondary/tertiary.
**Figma 연동**: 모든 토큰에 1줄 설명 필수 ("Hover state on items with subtle emphasis").

#### Pattern 3: "안티패턴 선언이 가장 강력한 지침" (Anti-Patterns as Primary Instructions)

**발견**: AI 에이전트에게 "하지 마라"가 "해라"보다 더 효과적.
**구현**: 모든 컴포넌트 meta.json에 `antiPatterns` 배열 필수.
**이유**: 에이전트는 학습 데이터에서 패턴 매칭하므로, 금지 규칙 없이는 훈련 데이터의 흔한 실수를 반복.

#### Pattern 4: "기반 상시 + 컴포넌트 온디맨드" (Always-On Foundation + On-Demand Components)

**문제**: MCP는 요청한 것만 반환 — "카드 만들어"하면 카드+버튼만 오고 spacing/typography/color 무시.
**해결**: 기반(spacing, color, typography) = AGENTS.md에서 상시 주입 / 컴포넌트 = MCP로 온디맨드 조회.
**핵심**: 기반 없는 컴포넌트 생성 = 건물 없는 가구 배치.

#### Pattern 5: "점진적 인프라 구축" (Plant Seeds, Not Trees)

**Brad Frost**: 거대한 시스템 한번에 구축 X → 네이밍 → 토큰 → 설명 → JSON → 에이전트 순서로 점진적.
**실증**: 1번째 컴포넌트 = 1일, 5번째 = 1시간, 20번째 = 10분.
**핵심**: 5~6개 컴포넌트 완성 후 스킬/하네스로 자동화.

### B2. 3대 철학

#### Philosophy 1: "실행에서 큐레이션으로" (Execution → Curation)

생성 비용이 0에 수렴하면서 디자이너의 핵심 경쟁력이 "만드는 능력"에서 **"구별하는 안목(Taste)"**으로 이동. 마스터님의 디자인 DNA가 바로 이 Taste의 결정체.

#### Philosophy 2: "문서 = 실행 코드" (Documentation as Executable Code)

Anna Arteeva: "AI will follow documentation blindly." — 문서의 오류가 곧 산출물의 오류. 문서를 코드처럼 버전 관리·리뷰·테스트해야 함. `guidelines.md`가 실행 가능한 규칙이 되어야 함.

#### Philosophy 3: "인간 판단 게이트 불변" (Human Judgment Gate Invariant)

전 산업 합의: 완전 자율 AI 디자인은 위험. 에이전트 신뢰 수준(Intern→Senior)에 관계없이 최종 인간 검토 게이트 필수. GitHub Primer: "에이전트는 이슈만 생성, 자동 머지 금지."

---

## Part C: RSI Step 3 — 현행 디자인시스템 대비 객관적 평가

### C1. 현행 시스템 (CLAUDE.md 디자인 섹션) 강점

| 항목 | 평가 | 근거 |
|------|------|------|
| 디자인 토큰 포괄성 | **A+** | spacing, radius, opacity, duration, border-width, shadow 5단계 — 업계 최고 수준 완비 |
| 색상 체계 | **A** | 시맨틱 4색 + RGB 분리값 + 브랜드 악센트 3축 + 전례력 컬러 — 매우 풍부 |
| 타이포그래피 | **A** | Pretendard+Inter 페어링 + 한글 최적화(keep-all) + clamp() 반응형 — 모범 |
| 컴포넌트 패턴 | **A** | 글래스모피즘 4계층, 버튼 3단계, 모달, 토스트 등 25+ 패턴 — 포괄적 |
| 애니메이션 | **A** | 실제 키프레임 12종 + spring 이징 + reduced-motion 대응 — 실전형 |
| 접근성 | **B+** | WCAG AA, 포커스, 터치 타겟, reduced-motion — 기반 있음 |
| PWA/아이콘 | **A-** | 체계적 아이콘 생성 + manifest + 메타태그 — 잘 정비됨 |

### C2. 현행 시스템 Gap 분석 (세계 최고 대비)

| Gap | 현행 | 세계 최고 (2026) | 심각도 |
|-----|------|-----------------|--------|
| **G1. DESIGN.md 미분리** | 디자인 토큰이 CLAUDE.md 안에 산문으로 매립 | Google DESIGN.md: YAML 프론트매터 (기계용) + Markdown 산문 (판단용) 분리 | **HIGH** |
| **G2. 컴포넌트 메타데이터 부재** | CSS 패턴만 존재, meta.json 없음 | 컴포넌트별 purpose/variants/antiPatterns/tokens/accessibility JSON 메타데이터 | **HIGH** |
| **G3. 안티패턴 미선언** | 금지 규칙 없음 | 모든 컴포넌트에 `antiPatterns` 배열 필수 — "가장 강력한 지침" | **HIGH** |
| **G4. 토큰 네이밍 혼재** | `--bg-primary`, `--text-secondary` (위치 기반) | `emphasis.default`, `danger.background` (의도 기반) | **MEDIUM** |
| **G5. 거버넌스 파이프라인 부재** | 체크리스트만 존재 (수동) | MAPE-K 자기치유 루프 + 신뢰 수준 프레임워크 + 자동 드리프트 감지 | **MEDIUM** |
| **G6. 에이전트 소비 최적화 부재** | 인간 독해용 CSS 코드 블록 | JSON 계약 (80% 토큰 절감, 환각 감소) | **MEDIUM** |
| **G7. Intent Mapping 부재** | 컴포넌트 "어떻게 생겼나"만 기술 | "사용자가 이 시점에서 무엇을 달성하려는가" 의도 매핑 | **LOW** |

### C3. 종합 평점

| 평가 기준 | 현행 점수 | 세계 최고 기준 | Gap |
|-----------|----------|---------------|-----|
| 토큰 포괄성 | 92/100 | 95/100 | -3 |
| 기계 판독성 | 45/100 | 90/100 | **-45** |
| 컴포넌트 계약 | 30/100 | 85/100 | **-55** |
| 안티패턴 커버리지 | 5/100 | 80/100 | **-75** |
| 거버넌스 자동화 | 15/100 | 75/100 | **-60** |
| 의도 매핑 | 10/100 | 70/100 | **-60** |
| **가중 평균** | **42/100** | **83/100** | **-41** |

> **해석**: 현행 시스템은 디자인 토큰의 **인간 독해용 품질**은 세계 최고 수준이나, **AI 에이전트 소비용 구조**에서 세계 최고 대비 41점 차이. 핵심 병목: 기계 판독성 + 컴포넌트 계약 + 안티패턴.

---

## Part D: RSI Step 4 — 개선 제안 (Round 2 입력)

### D1. 즉시 실행 가능 (Quick Wins)

1. **DESIGN.md 분리**: CLAUDE.md에서 디자인 섹션을 `DESIGN.md`로 분리, YAML 프론트매터 추가
2. **안티패턴 선언**: 기존 25+ 컴포넌트 패턴에 각각 `antiPatterns` 추가
3. **Do's and Don'ts 섹션**: DESIGN.md 말미에 명시적 Do/Don't 목록

### D2. 중기 과제 (Round 2~3)

4. **컴포넌트 meta.json 스키마 설계**: purpose/variants/antiPatterns/tokens/accessibility
5. **토큰 네이밍 시맨틱 전환**: 위치 기반 → 의도 기반 매핑 테이블
6. **기반 상시 주입 규칙**: AGENTS.md에 spacing/color/typography 상시 참조 규칙

### D3. 장기 과제 (Round 4+)

7. **MAPE-K 거버넌스 루프**: 드리프트 감지 → 자동 PR → 승인 → 학습
8. **meta.json 자동 생성 스킬**: 5~6개 완성 후 스킬화 (1일→1시간→10분 곡선)
9. **Intent Mapping 레이어**: 컴포넌트별 사용자 의도 매핑

---

## Sources

- [Anna Arteeva — Design Systems for the Vibe-Coding Era](https://www.designsystemscollective.com/design-systems-for-the-vibe-coding-era-42282e1affef)
- [Into Design Systems — Agentic Design Systems Complete Guide](https://www.intodesignsystems.com/agentic-design-systems)
- [TDP — Agentic Design System Component Library](https://designproject.io/blog/agentic-design-system/)
- [Google Stitch DESIGN.md Open Source](https://pasqualepillitteri.it/en/news/1251/google-stitch-design-md-open-source-spec-2026)
- [DESIGN.md Specification — Sebastien Dubois](https://www.dsebastien.net/design-md-specification/)
- [AGENTS.md + SKILL.md + DESIGN.md 3계층](https://dev.to/aws-builders/agentsmd-skillmd-designmd-how-ai-instructions-split-into-three-layers-d0g)
- [Intent-Driven Design — UX Collective](https://uxdesign.cc/the-next-era-of-design-is-intent-driven-f789ee521482)
- [Softr — Vibe Coding Best Practices 2026](https://www.softr.io/blog/vibe-coding-best-practices)
- [Muzli — Vibe Design 2026](https://muz.li/blog/vibe-design-in-2026-what-ai-generated-ui-means-for-your-work/)
- [NxCode — Vibe Designing Complete Guide 2026](https://www.nxcode.io/resources/news/vibe-designing-complete-guide-2026)
