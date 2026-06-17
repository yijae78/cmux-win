# RSI Vibe-Design — Round 1 Worker2(AGY) 심층 리뷰 보고서

* **Reviewer**: Worker2(AGY) (디자인/UX/전략/컨텐츠 리뷰어)
* **Date**: 2026-06-17
* **Target File**: [round1_worker1.md](file:///C:/dev/cmux-win/javis/rsi/vibe-design/round1_worker1.md)
* **Review Framework**: [worker2_prep.md](file:///C:/dev/cmux-win/javis/rsi/vibe-design/worker2_prep.md) 기반 4대 핵심 축 평가 및 [문제점/논쟁점/조언] 도출

---

## Executive Summary

Worker1의 Round 1 보고서는 2026년 최신 기술 동향(`DESIGN.md` 오픈소스 사양, 에이전틱 디자인 시스템의 3파일 구조 등)을 심도 있게 탐색하고, 현행 CLAUDE.md의 기계 판독성 및 컴포넌트 계약 부재를 날카롭게 짚어낸 훌륭한 연구 산출물입니다.

그러나 본 리뷰어(Worker2) 관점에서 본 보고서는 **디자인의 기계적·엔지니어링적 구조화에 매몰되어, 실제 사용자가 경험하는 UX(Intent-First) 및 브랜드 고유의 가치(Taste)를 기술적으로 통제·보호하는 방어 장치 설계가 현저히 부족**합니다. 

이러한 공백을 메우기 위해 UX/전략, 시스템 정합성, 접근성/성능, 브랜드 차별화의 4대 축을 기준으로 피드백을 제시합니다.

---

## 1. UX/전략 관점 (UX & Strategic Perspective)

> **"의도 중심 디자인(Intent-First)의 가치 과소평가와 구체적 상호작용 시나리오 부재"**

### 🚨 문제점 (Problems)
1. **의도 매핑(Intent Mapping) 중요도 오류**: Gap 분석(C2)에서 'G7. Intent Mapping 부재'의 심각도를 **"LOW"**로 분류했습니다. 이는 의도 중심 디자인(Intent-First Design) 철학을 단순 기술 보조 수준으로 오인한 중대한 설계적 왜곡입니다. 사용자의 의도 매핑이 디자인 시스템보다 선행 및 상위 제어로 작동하지 않으면, AI는 화려한 껍데기뿐인 UI를 난무하게 됩니다.
2. **AI-Native UI 패턴에 대한 전략적 구체성 결여**: '맥락적 인라인 제어'와 '에이전트 사고 가시화'를 언급만 했을 뿐, 이러한 컴포넌트들이 실제 사용자 저니(User Journey)에서 어떻게 인지 부하를 줄이고 예측 가능성을 높이는지에 대한 UX적 평가와 구체적인 적용 가이드라인이 누락되어 있습니다.

### ⚖️ 논쟁점 (Debatable Points)
* **즉흥적 'Vibe' vs UX의 '예측 가능성(Predictability)'**: AI 에이전트와 대화하며 동적으로 UI가 변조되는 'Vibe Design'은 사용자의 멘탈 모델(Mental Model)을 교란할 위험이 큽니다. 매 접속마다 UI 요소의 위치나 인터랙션 방식이 미세하게 달라질 때 발생하는 인지적 혼란을 어떻게 제어할 것인가?

### 💡 조언 (Recommendations)
* **의도 매핑 심각도 격상**: G7(의도 매핑 부재)의 심각도를 **"HIGH"**로 즉각 수정하고, `DESIGN.md` 설계 시 컴포넌트 레이아웃 규칙에 앞서 **"Core UX Constraints (사용자 인지 부하 방지를 위한 절대적 인터페이스 제약 조건)"**을 우선 선언할 것을 조언합니다.
* AI의 무분별한 UI 변형을 방지하기 위해, 변경 가능한 범위와 절대 고정되어야 하는 UX 불변 요소(예: 내비게이션 구조, 핵심 액션 버튼 위치 등)를 분리하는 **'UX 안전 구역(UX Safe Zone)'** 설계를 기획안에 추가하십시오.

---

## 2. 시스템 정합성 (System Consistency & Integrity)

> **"포맷 간 모순점 및 소규모 프로젝트에서의 컴포넌트 6파일 구조의 오버헤드"**

### 🚨 문제점 (Problems)
1. **데이터 포맷의 모순**: Google의 `DESIGN.md` 사양(YAML 프론트매터 + Markdown 산문)이 AI 파싱에 더 신뢰성 있다고 주장하는 동시에, Indeed의 벤치마크를 인용하며 JSON 메타데이터가 토큰을 80% 절감하고 정확도를 높인다고 강조하고 있습니다. 결과적으로 자바리스(Javis) 프로젝트에서 메인 '계약(Contract)' 문서로 어떤 포맷을 우선순위로 삼아야 하는지 명확한 가이드가 모호합니다.
2. **소규모 프로젝트에서의 파일 폭증(Thrashing)**: 컴포넌트당 6파일 구조(TDP 권장)는 대규모 엔터프라이즈 환경에는 적합할지 모르나, 신속한 프로토타이핑과 Vibe Coding의 애자일함이 핵심인 자바리스 환경에서는 파일 수가 기하급수적으로 늘어나는 관리 오버헤드를 초래합니다.

### ⚖️ 논쟁점 (Debatable Points)
* **글로벌 단일 DESIGN.md vs 컴포넌트별 meta.json 분할**: AI 에이전트가 작업을 수행할 때, 전체 컨텍스트를 파악하는 글로벌 `DESIGN.md`를 읽는 것이 유리한가, 아니면 해당 컴포넌트 디렉토리 내의 독립된 `meta.json`을 소비하는 것이 유리한가? (토큰 비용 및 컨텍스트 정밀도 대립)

### 💡 조언 (Recommendations)
* **하이브리드 메타 데이터 모델 제안**: 6파일 구조를 지양하고, 컴포넌트 구현 시 파일 개수를 최대 3개로 압축하는 **'슬림 에이전틱 컴포넌트 패키지'** 구성을 제안합니다.
  - `button.tsx` (구현 + 내장 CSS)
  - `button.meta.json` (안티패턴 및 토큰 의도 선언 통합)
  - `button.test.tsx` (검증용 테스트)
* **이중 포맷 전략의 정립**: `DESIGN.md`는 마스터 에이전트의 거시적 가이드라인과 공통 토큰(YAML)을 제공하는 글로벌 계약서로 삼고, 개별 컴포넌트 단위의 미시적 제어와 안티패턴 방어는 `meta.json` 계약서로 이원화하여 AI의 토큰 소비 효율을 극대화하십시오.

---

## 3. 접근성/성능 방어책 (Accessibility & Performance Defense)

> **"동적 UI 접근성 검증 기법의 부재 및 토큰 드리프트로 인한 스타일 시트 비대화 대책 미비"**

### 🚨 문제점 (Problems)
1. **동적/스트리밍 UI 접근성(a11y) 검증 방안 부재**: 보고서는 `meta.json` 내의 정적 체크 리스트(`accessibility: { keyboard: true }`) 선언에만 의존하고 있습니다. 그러나 런타임에 동적으로 변경되거나 스트리밍되는 AI 생성 UI의 접근성(ARIA 라이브 영역, 포커스 트랩 등)을 어떻게 실시간 검증할 것인지에 대한 해결책이 없습니다.
2. **토큰 드리프트로 인한 CSS 성능 저하 방지책 누락**: AI 에이전트가 자유롭게 스타일을 재정의하도록 방치할 경우, 인라인 CSS의 과도한 중복과 무분별한 유틸리티 클래스 남발로 인해 빌드된 스타일 시트 용량이 급증하는 성능 저하 문제를 예방할 수 없습니다.

### ⚖️ 논쟁점 (Debatable Points)
* **접근성/성능 검증의 타이밍**: 디자인 정합성 및 성능/접근성 검증을 깃훅(Git Hooks)을 통한 빌드/커밋 타임에 수행할 것인가, 아니면 AI 에이전트가 코드를 쓰거나 UI를 생성하는 즉시 샌드박스 런타임 환경에서 인터셉트하여 필터링할 것인가?

### 💡 조언 (Recommendations)
* **런타임 접근성 가드레일 & 컴포넌트 래퍼 도입**: 동적 생성 UI의 접근성 훼손을 차단하기 위해, AI가 렌더링하는 모든 동적 요소 상위에 접근성 표준 규격을 강제 주입하는 상위 래퍼(Wrapper) 컴포넌트를 설계에 추가할 것을 조언합니다.
* **임의 스타일링 금지 가드레일 (Linter Hook)**: Tailwind CSS 등을 사용할 때 AI 에이전트가 임의의 값(Arbitrary values, 예: `bg-[#1a2b3c]`, `w-[99px]`)을 코드에 하드코딩하지 못하도록 탐지하고 에러를 뱉는 **디자인 Linter 훅**을 개발 가이드라인에 명문화하십시오.

---

## 4. 브랜드 차별화 전략 (Brand Differentiation Strategy)

> **"AI의 범용 스타일 회귀 경향 방어 및 브랜드 고유 비주얼 DNA 주입 가이드 결여"**

### 🚨 문제점 (Problems)
1. **AI의 평준화된 범용 디자인(Generic Design)에 대한 방어 부족**: 생성형 AI는 학습 데이터의 영향으로 기본 제공되는 흔한 템플릿(예: standard shadcn/ui 테마)으로 수렴하는 강한 경향이 있습니다. 보고서에는 브랜드만의 독창적 정체성(예: 어거스틴 설교 프로젝트의 다크 배경 + 황금빛 하이라이트 + 클래식 타이포)을 유지하도록 통제할 구체적인 '시각적 레퍼런스 및 감성 주입 장치'가 빠져 있습니다.

### ⚖️ 논쟁점 (Debatable Points)
* **추상적 'Mood' 묘사 vs 정밀 'Constraint' 제어**: AI 에이전트에게 브랜드의 예술적 감성(Brand Vibe)을 주입하기 위해 문학적 묘사(예: "Cinematic backlight with dynamic shadows")를 프롬프트로 주는 것이 나은가, 아니면 수학적 토큰 비율과 색상 명도 범위를 엄격하게 고정하는 것이 나은가?

### 💡 조언 (Recommendations)
* **DESIGN.md 내 "Brand DNA & Mood Guidelines" 섹션 신설**:
  - AI 에이전트가 단순 컴포넌트 조립을 넘어 브랜드 특유의 미학적 결과물을 낼 수 있도록, 브랜드의 **핵심 비주얼 브리프(Visual Brief)** 문장을 표준 프롬프트 형태로 포함하십시오.
  - 예: *"Always apply cinematic backlight and golden highlight on dark charcoal background. Avoid flat, pastel, or corporate blue-toned color schemes."*와 같이 시각적 금지 무드(Anti-visual mood)를 명확히 하여 AI의 평이한 디자인 출력을 방어하십시오.

---

## 결론 및 차기 라운드 제안

Worker1이 제안한 `DESIGN.md` 도입과 `meta.json`을 통한 기계 판독성 강화는 지극히 올바른 방향입니다. 

다만, 차기 Round 2에서는 본 리뷰어가 지적한 **UX 일관성 수호(UX Safe Zone), 파일 폭증을 방지하는 컴포넌트 메타 설계(3파일 하이브리드 모델), 실시간 접근성/성능 훅(Linter Hook), 그리고 브랜드 DNA(Cinematic mood 등) 주입 방안**을 구체적으로 가시화하여 통합 제안서에 반영할 것을 강력히 권고합니다.
