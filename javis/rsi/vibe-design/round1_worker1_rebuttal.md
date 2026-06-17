# RSI Vibe-Design — Round 1 Worker1 반박·수용 보고서 (Vindication)

> **Author**: Worker1(Claude)
> **Date**: 2026-06-17
> **Target**: Worker2(AGY) 심층 리뷰 (`round1_worker2_review.md`)
> **RSI Stage**: Step 3 심화 — 객관적 평가 (반박·수용 라운드)

---

## 판정 요약

| # | Worker2 지적 | 판정 | 근거 요약 |
|---|-------------|------|-----------|
| 1-1 | Intent Mapping 심각도 LOW는 오류 | **ACCEPT** | 바이브디자인 패러다임에서 의도 매핑은 디자인 토큰보다 상위 제어층 |
| 1-2 | AI-Native UI 패턴 전략적 구체성 결여 | **PARTIAL ACCEPT** | 타당하나, Round 1은 탐색 단계 — 구체화는 Round 2 범위 |
| 1-D | Vibe vs 예측 가능성 충돌 | **ACCEPT** | UX Safe Zone 개념 수용 |
| 2-1 | YAML vs JSON 포맷 모순 | **REBUT** | 모순 아님 — 글로벌(YAML) vs 컴포넌트(JSON) 보완 관계 |
| 2-2 | 6파일 구조 과잉 | **PARTIAL ACCEPT** | TDP 원문 인용이지 처방이 아님, 3파일 슬림 모델 실용적 |
| 2-D | 글로벌 vs 분할 메타데이터 | **ACCEPT** | 이원화 전략 합의 |
| 3-1 | 동적 UI 접근성 검증 부재 | **ACCEPT** | 정적 선언만으로 불충분, 런타임 가드 필요 |
| 3-2 | CSS 성능 저하 방지책 누락 | **ACCEPT** | 디자인 Linter 훅 필요성 인정 |
| 3-D | 검증 타이밍 (빌드 vs 런타임) | **ACCEPT with NUANCE** | 양층 모두 필요 |
| 4-1 | 브랜드 DNA 주입 장치 결여 | **PARTIAL ACCEPT** | DNA는 CLAUDE.md에 존재, DESIGN.md 변환 브릿지 미제안 |
| 4-D | Mood 묘사 vs Constraint 제어 | **ACCEPT** | 이중 인코딩(산문+수치) 원칙 수용 |

**최종 점수: ACCEPT 7건 / PARTIAL ACCEPT 3건 / REBUT 1건**

---

## 상세 반박·수용

### 1-1. Intent Mapping 심각도 LOW → HIGH 격상

**판정: ACCEPT**

Worker2의 지적이 정당하다. 내 원래 평가는 Intent Mapping을 "컴포넌트 수준 이슈"로 국한시켰으나, 바이브디자인 패러다임에서는 사용자 의도가 **디자인 시스템의 상위 제어층(Upper Control Layer)**으로 기능한다.

**논리 경로**:
1. 바이브디자인 = AI가 자연어에서 UI를 생성
2. 자연어의 핵심 = 사용자 의도(Intent)
3. 의도 매핑 없이 토큰만 있으면 = "정확한 색상의 잘못된 화면"
4. 따라서 Intent Mapping은 토큰/컴포넌트보다 **선행** 계층

**수정 사항**: Gap 분석 G7 심각도 LOW → **HIGH** 격상. DESIGN.md 설계 시 `## Core UX Constraints` 섹션을 `## Colors`보다 앞에 배치.

**UX Safe Zone 수용**: AI 변형 가능 영역과 절대 고정 UX 불변 요소를 분리하는 설계 원칙 채택.

```
UX Safe Zone (절대 고정)        Vibe Zone (AI 변형 허용)
─────────────────────────      ─────────────────────────
- 내비게이션 구조               - 카드 내부 레이아웃 변형
- 핵심 CTA 버튼 위치            - 색상 강조 변주 (토큰 범위 내)
- 폼 제출 흐름 순서             - 일러스트/아이콘 선택
- 에러 표시 위치                - 마이크로인터랙션 변주
- 접근성 키보드 흐름            - 컨텐츠 카드 순서 (개인화)
```

---

### 1-2. AI-Native UI 패턴 전략적 구체성 결여

**판정: PARTIAL ACCEPT**

Worker2의 지적 자체는 타당하다. 그러나 맥락을 보아야 한다:

**수용하는 부분**: "맥락적 인라인 제어"와 "에이전트 사고 가시화"를 개념 나열에 그쳤다. 실제 사용자 저니 내에서의 인지 부하 분석과 적용 가이드라인이 빠졌다.

**반론 (partial)**: Round 1의 목적은 RSI Step 1-2(검색·탐색 + 패턴 추출)이다. 구체적 적용 가이드라인은 Step 5(Skill 제작) 단계 — 즉 Round 2~3의 범위다. 탐색 단계에서 모든 패턴을 즉시 구체화하면 오히려 성급한 최적화(Premature Optimization) 위험이 있다.

**합의안**: Round 2에서 AI-Native UI 패턴별 "인지 부하 영향 분석표"를 작성하여 구체화한다.

---

### 2-1. YAML vs JSON 포맷 모순

**판정: REBUT (반박)**

Worker2는 보고서가 "YAML이 AI 파싱에 더 신뢰성 있다고 주장하면서 동시에 JSON이 80% 토큰 절감한다고 강조하는 모순"을 지적했다. **이것은 모순이 아니다.**

**반박 근거**:

두 포맷은 **서로 다른 계층에서 서로 다른 문제를 해결**한다:

| 계층 | 포맷 | 용도 | 소비자 |
|------|------|------|--------|
| **글로벌** (DESIGN.md) | YAML 프론트매터 + Markdown 산문 | 브랜드 정체성, 공통 토큰, 디자인 철학, WHY | 마스터 에이전트, 인간 디자이너 |
| **컴포넌트** (meta.json) | JSON | 개별 컴포넌트 계약 (props, variants, anti-patterns) | 실행 에이전트, MCP 서버 |

Google DESIGN.md가 Markdown을 선택한 이유 = "LLM이 Markdown을 더 신뢰성 있게 파싱" → 이것은 **글로벌 수준의 산문형 가이드라인**에 대한 설명이다.

Indeed 벤치마크의 JSON 80% 절감 = **컴포넌트 수준의 구조화된 쿼리**에 대한 결과이다.

즉, 내 보고서는 글로벌은 YAML+Markdown, 컴포넌트는 JSON이라는 **이원 구조를 암묵적으로 제안**하고 있었다. Worker2의 "이중 포맷 전략" 권고(2번 조언)는 사실상 **내 보고서가 이미 내포한 결론과 동일**하다.

다만 수용하는 점: 이 이원 구조를 **명시적으로** 선언하지 않아 혼동을 유발한 것은 서술의 미비다. Round 2에서 명확히 도식화한다.

---

### 2-2. 6파일 구조 과잉

**판정: PARTIAL ACCEPT**

**수용하는 부분**: Javis 프로젝트 규모에서 컴포넌트당 6파일은 실용적이지 않다. Worker2의 3파일 슬림 모델이 더 적합하다.

**반론 (partial)**: 내 보고서는 TDP의 6파일 구조를 **"TDP 권장"**으로 인용(cite)한 것이지, Javis에 그대로 적용하라는 **처방(prescription)**이 아니었다. 개선 제안 D2에서 "컴포넌트 meta.json 스키마 설계"를 중기 과제로 분류한 것이 이를 증명한다 — 즉, 파일 구조는 아직 확정 전이었다.

**합의안**: Worker2의 3파일 슬림 모델 채택:
```
component/
├── component.tsx           # 구현 + CSS-in-JS/Tailwind
├── component.meta.json     # 메타데이터 (purpose, variants, antiPatterns, tokens, a11y)
└── component.test.tsx      # 사용법 강제 테스트
```

Stories는 Storybook 자동 발견에 의존, 토큰은 글로벌 DESIGN.md에서 관리.

---

### 3-1. 동적 UI 접근성 검증 부재

**판정: ACCEPT**

Worker2의 지적이 정당하다. meta.json의 정적 체크리스트(`accessibility: { keyboard: true }`)는 **설계 시점(Design-Time)** 계약이다. 바이브디자인에서 AI가 런타임에 동적 생성하는 UI는 이 정적 계약만으로 접근성을 보장할 수 없다.

**수용 내용**:
1. **런타임 접근성 래퍼(A11y Wrapper)**: 동적 생성 UI의 상위에 ARIA live region, 포커스 트랩, 키보드 내비게이션을 강제 주입하는 래퍼 컴포넌트
2. **접근성 검증 2중 방어**:
   - Layer 1: meta.json 정적 선언 (설계 시점)
   - Layer 2: 런타임 a11y 래퍼 + axe-core 자동 검사 (실행 시점)

---

### 3-2. CSS 성능 저하 방지책 누락

**판정: ACCEPT**

AI 에이전트가 임의 값(arbitrary values)을 하드코딩하면 CSS 비대화가 불가피하다. 디자인 Linter 훅의 필요성을 인정한다.

**수용 내용**:
- Tailwind arbitrary value 탐지 린터 (예: `bg-[#1a2b3c]`, `w-[99px]` 금지)
- 허용 목록: DESIGN.md YAML에 선언된 토큰 값만 사용 가능
- 위반 시 빌드 실패 또는 에이전트에 경고 반환

---

### 3-D. 검증 타이밍 (빌드 vs 런타임)

**판정: ACCEPT with NUANCE**

Worker2는 "어느 쪽이 나은가"를 논쟁점으로 제시했으나, 정답은 **양층 모두**다:

| 타이밍 | 검증 대상 | 도구 |
|--------|----------|------|
| **에이전트 생성 직후** | 토큰 준수, 안티패턴 위반, arbitrary value | 디자인 Linter (즉시 피드백) |
| **커밋/빌드 시** | 접근성 (axe-core), 번들 크기, unused CSS | CI 파이프라인 게이트 |
| **런타임** | ARIA live, 포커스 트랩, 동적 콘텐츠 접근성 | 래퍼 컴포넌트 + 모니터링 |

---

### 4-1. 브랜드 DNA 주입 장치 결여

**판정: PARTIAL ACCEPT**

**수용하는 부분**: DESIGN.md에 "Brand DNA & Mood Guidelines" 섹션이 필요하다는 점은 타당하다. 현행 CLAUDE.md의 디자인 DNA를 DESIGN.md 포맷으로 변환하는 브릿지가 내 보고서에 없었다.

**반론 (partial)**: Worker2는 "브랜드 DNA 주입 장치가 빠져 있다"고 했으나, 실제로 **현행 CLAUDE.md 디자인 시스템 자체가 바로 그 브랜드 DNA의 결정체**다:
- 다크 퍼스트 (#0a~#0f 배경)
- 글래스모피즘 4계층
- 135deg 그라디언트
- 시네마틱 역광 + 황금빛 하이라이트 (NLM 이미지)
- Pretendard + Inter 페어링

이 DNA는 이미 **존재한다**. 문제는 존재하지 않는 것이 아니라, AI 에이전트가 소비할 수 있는 **포맷으로 변환되지 않은 것**이다.

**합의안**: Round 2에서 DESIGN.md `## Brand DNA & Mood Guidelines` 섹션을 설계할 때, 현행 CLAUDE.md DNA를 다음 이중 인코딩으로 변환:

```yaml
# YAML (기계용 — 수치 제약)
brand_mood:
  background_lightness_range: [0, 12]      # HSL L값 0~12% 강제
  accent_hue_range: [35, 50]               # 골드 톤 강제
  gradient_angle: 135                       # 각도 고정
  glass_blur_min: 16                        # 최소 blur
  prohibited_moods: ["flat", "pastel", "corporate-blue", "neon-rainbow"]
```

```markdown
## Brand DNA (판단용 — 산문 묘사)
Always apply cinematic backlight and golden highlight on dark charcoal background.
Glass morphism with depth layers is the primary design language.
Avoid flat, pastel, corporate blue-toned, or neon rainbow color schemes.
When in doubt, darker and more dramatic is preferred over brighter and lighter.
```

---

### 4-D. Mood 묘사 vs Constraint 제어

**판정: ACCEPT**

Worker2가 제시한 "추상적 Mood vs 정밀 Constraint" 이분법은 유효한 논쟁이나, 답은 **이중 인코딩**이다:

- **YAML 토큰** = 수학적 제약 (명도 범위, 각도, blur 최소값) → 에이전트가 기계적으로 준수
- **Markdown 산문** = 미학적 방향 (시네마틱, 역광, 극적) → 에이전트가 모호한 판단 시 참조

Google DESIGN.md 사양이 정확히 이 구조다: "WHAT(토큰) = 기계용, WHY(산문) = 판단용."

---

## 수정된 Gap 분석 (Round 1 보고서 정정)

| Gap | 원래 심각도 | 수정 심각도 | 변경 사유 |
|-----|-----------|-----------|-----------|
| G1. DESIGN.md 미분리 | HIGH | HIGH | 유지 |
| G2. 컴포넌트 메타데이터 부재 | HIGH | HIGH | 유지 |
| G3. 안티패턴 미선언 | HIGH | HIGH | 유지 |
| G4. 토큰 네이밍 혼재 | MEDIUM | MEDIUM | 유지 |
| G5. 거버넌스 파이프라인 부재 | MEDIUM | MEDIUM | 유지 |
| G6. 에이전트 소비 최적화 부재 | MEDIUM | MEDIUM | 유지 |
| G7. Intent Mapping 부재 | **LOW** | **HIGH** | Worker2 지적 수용 — 의도 매핑은 상위 제어층 |
| **G8. 런타임 접근성 가드 부재** | (신규) | **HIGH** | Worker2 지적 수용 — 정적 선언만으로 불충분 |
| **G9. CSS 성능 가드레일 부재** | (신규) | **MEDIUM** | Worker2 지적 수용 — arbitrary value 방지 |
| **G10. 브랜드 DNA 포맷 변환 미비** | (신규) | **HIGH** | 기존 DNA 존재하나 에이전트 소비 포맷 미변환 |

## 수정된 종합 평점

| 평가 기준 | 원래 점수 | 수정 점수 | 변경 사유 |
|-----------|----------|----------|-----------|
| 토큰 포괄성 | 92 | 92 | 유지 |
| 기계 판독성 | 45 | 45 | 유지 |
| 컴포넌트 계약 | 30 | 30 | 유지 |
| 안티패턴 커버리지 | 5 | 5 | 유지 |
| 거버넌스 자동화 | 15 | 15 | 유지 |
| 의도 매핑 | 10 | 10 | 점수 유지 (Gap 심각도만 격상) |
| **런타임 접근성** | (미평가) | 20 | 신규 축 추가 |
| **브랜드 DNA 에이전트 소비성** | (미평가) | 35 | DNA 존재하나 포맷 미변환 |
| **가중 평균** | **42/100** | **38/100** | 평가 축 확대로 하락 — 더 정확한 현실 반영 |

> **해석**: 평가 축을 8개로 확대하면 현행 시스템의 실제 에이전틱 준비도는 원래 평가보다 **더 낮다(38점)**. 이는 Worker2의 리뷰가 유효한 맹점을 찔렀음을 의미한다.

---

## Worker3(Codex) 반박·수용

### W3 판정 요약

| # | Worker3 지적 | 판정 | 근거 요약 |
|---|-------------|------|-----------|
| W3-C1 | DESIGN.md 사양 주장 검증 불충분 | **PARTIAL ACCEPT** | 1차 출처 URL 보완 필요, 그러나 "미검증"은 과잉 |
| W3-C2 | 현행 시스템 평가가 사실상 오류 (CLAUDE.md 184줄) | **REBUT** | Worker3가 프로젝트 CLAUDE.md와 글로벌 CLAUDE.md를 혼동 |
| W3-H1 | DESIGN.md가 토큰 SOT로 부적합 | **PARTIAL ACCEPT** | 드리프트 우려 타당, 그러나 현 단계에서 토큰 파이프라인은 과잉 |
| W3-H2 | meta.json 의무화 과잉 명세 | **PARTIAL ACCEPT** | "3~5개 핵심 프리미티브부터" 조언은 타당 |
| W3-H3 | 보안 모델 불완전 | **ACCEPT** | 에이전트 파이프라인 위협 모델 누락 인정 |
| W3-M1 | 성능 리스크 미개발 | **PARTIAL ACCEPT** | 성능 예산 필요, 그러나 cmux-win 특화 우려는 범위 밖 |
| W3-M2 | 토큰 네이밍 마이그레이션 경로 없음 | **ACCEPT** | 인벤토리 → 별칭 → 배치 전환 → 린트 필요 |
| W3-M3 | 접근성 주장에 구체적 시행 부재 | **ACCEPT** | Worker2 리뷰 수용과 일맥상통 |
| W3-M4 | 외부 벤치마크가 구현 근거 불충분 | **ACCEPT** | 로컬 검증 필수 — 가설로만 취급 |
| W3-L1 | MAPE-K 시기상조 | **ACCEPT** | Round 1 원안도 D3(Round 4+)로 분류 |
| W3-E | 누락된 엣지 케이스 10건 | **PARTIAL ACCEPT** | 범용 엣지 케이스 6건 수용, cmux-win 특화 4건은 범위 밖 |

**최종 점수: ACCEPT 5건 / PARTIAL ACCEPT 5건 / REBUT 1건**

---

### W3-C1. DESIGN.md 사양 주장 검증 불충분

**판정: PARTIAL ACCEPT**

**수용하는 부분**: 내 보고서가 1차 출처(GitHub 공식 리포지토리) URL을 명시하지 않고 2차 블로그/뉴스 링크만 인용한 것은 학술적 엄밀성이 부족하다. Worker3의 "1차 출처 없이는 미검증 관찰(unverified observation)"이라는 기준은 정당하다.

**반론 (partial)**: 그러나 "미검증"이라는 판정은 과잉이다. 사실 관계를 정리하면:
- Google Labs가 `google-labs-code/design.md`를 GitHub에 공개한 것은 복수의 독립 매체가 교차 확인 (Pasquale Pillitteri, Medium/Bootcamp, Sebastien Dubois, MindStudio, NewsDefused 등)
- Apache-2.0 라이선스, 알파 상태, YAML 프론트매터 구조는 모든 출처에서 일관되게 보고
- "업계 표준이 형성 중"이라는 표현은 "표준이 확립되었다"가 아니라 진행형

**수정 사항**: 향후 보고서에서 1차 출처 URL(`github.com/google-labs-code/design.md`)을 명시. "업계 표준"은 "업계 표준 후보(candidate)"로 수정.

---

### W3-C2. 현행 시스템 평가가 사실상 오류

**판정: REBUT (반박)**

Worker3의 핵심 주장: "실제 root CLAUDE.md는 184줄이며 디자인 토큰 섹션이 없다. Worker1의 A/A+ 점수를 제거하고 실제 파일에서 재평가하라."

**이것은 Worker3의 범위 오인(Scope Misidentification)이다.**

**실측 증거**:
```
프로젝트 CLAUDE.md:  /c/dev/cmux-win/CLAUDE.md          → 184줄 (cmux-win 아키텍처)
글로벌 CLAUDE.md:    ~/.claude/CLAUDE.md                 → 1,307줄 (215줄부터 "신교수님 통합 디자인 시스템")
```

내 보고서가 평가한 대상은 **글로벌 `~/.claude/CLAUDE.md`의 디자인 시스템 섹션** (215~1100줄, 약 900줄의 디자인 토큰·컴포넌트·애니메이션·접근성·레이아웃 정의)이다. 이 시스템은 마스터님이 **모든 프로젝트에 적용하는 통합 디자인 시스템**이다.

Worker3는 `/c/dev/cmux-win/CLAUDE.md` (프로젝트 레벨)만 조사하고, 글로벌 CLAUDE.md의 존재를 인지하지 못했다. 따라서:
- "디자인 토큰이 없다"는 주장 → **사실 오류**
- "A/A+ 점수를 제거하라"는 요구 → **근거 없음**
- "실제 스타일은 prototype.html과 App.tsx에 분산"이라는 주장 → cmux-win 프로젝트의 구현 현황이지, 평가 대상인 글로벌 디자인 시스템과 무관

**결론**: 내 평가 대상과 점수는 유효하다. Worker3는 RSI의 범위(글로벌 디자인 시스템 개선)를 cmux-win 프로젝트로 축소 해석했다.

---

### W3-H1. DESIGN.md가 토큰 SOT(Single Source of Truth)로 부적합

**판정: PARTIAL ACCEPT**

**수용하는 부분**: Worker3의 아키텍처 우려는 원칙적으로 타당하다. YAML 프론트매터에 토큰 값을 매립하면:
- 스키마 강제 없음 (JSON Schema 대비)
- 순환 참조 탐지 불가
- CSS 변수와의 드리프트 가능성

`design/tokens/*.json → 생성된 CSS → DESIGN.md는 참조만` 아키텍처가 이론적으로는 더 견고하다.

**반론 (partial)**: 그러나 현재 상황은 **글로벌 디자인 시스템의 에이전틱 준비도 향상**이 목표이다. 현 단계에서 완전한 토큰 파이프라인(JSON → CSS 생성 → DESIGN.md 참조)을 구축하는 것은 **과잉 엔지니어링**이다. 이유:
1. 글로벌 CLAUDE.md는 AI 에이전트가 직접 읽는 지침서 — JSON 파이프라인이 아니라 **에이전트가 판단에 사용하는 산문+토큰** 형태가 최적
2. 현재 토큰 수가 50~80개 수준 — 순환 참조·드리프트 리스크가 낮음
3. Brad Frost: "Plant Seeds, Not Trees" — 인프라 과잉 투자보다 점진적 개선

**합의안**: Phase 1은 DESIGN.md에 YAML 토큰 매립으로 시작. 토큰이 100개를 초과하거나 다중 프로젝트 동기화가 필요해지면 Phase 2에서 JSON 파이프라인으로 전환.

---

### W3-H2. meta.json 의무화 과잉 명세

**판정: PARTIAL ACCEPT**

Worker3의 "3~5개 핵심 프리미티브부터 시작하고 에이전트 유용성을 증명한 후 확장"은 **Brad Frost의 "Plant Seeds" 원칙과 일치**하며 타당하다.

**수정 사항**: 
- Phase 1: button, input, card, modal, toast — 5개만 meta.json 작성
- 에이전트 생성 품질 측정 (meta.json 있을 때 vs 없을 때)
- 측정 결과가 유의미하면 확장, 아니면 접근법 재검토

---

### W3-H3. 보안 모델 불완전

**판정: ACCEPT**

Worker3의 지적이 정당하다. 에이전틱 디자인 파이프라인의 보안 위협을 전혀 다루지 않았다.

**수용하는 보안 게이트**:
1. 디자인 콘텐츠에서 셸 명령 보간(interpolation) 금지
2. 인자 배열(argument-array) 실행만 허용
3. MCP 도구 화이트리스트
4. 디자인 에이전트에 시크릿 접근 금지
5. 생성된 코드의 의존성 리뷰
6. 자동 수정에 대한 감사 로그
7. 머지 전 인간 리뷰 필수 (GitHub Primer 정책과 합치)

---

### W3-M1. 성능 리스크 미개발

**판정: PARTIAL ACCEPT**

**수용하는 부분**: 성능 예산(Performance Budget)을 명시하지 않은 것은 미비하다. 디자인 토큰 도입 시 CSS 번들 크기, 테마 재계산 비용, backdrop-filter 남용을 모니터링해야 한다.

**반론 (partial)**: Worker3가 제기한 "Electron 시작 시간, xterm 타이핑 지연, 패널 리사이즈 지연"은 **cmux-win 프로젝트 특화 성능 우려**이다. 이 RSI의 범위는 글로벌 디자인 시스템이므로, 프로젝트별 성능 벤치마크는 각 프로젝트 적용 시점에서 수행할 사항이다.

**합의안**: DESIGN.md에 `## Performance Constraints` 섹션 추가 — backdrop-filter 최대 8개/화면, 애니메이션 기본 GPU 가속, CSS 변수 50개 이하 권장 등 범용 성능 가이드라인 포함.

---

### W3-M2. 토큰 네이밍 마이그레이션 경로 없음

**판정: ACCEPT**

Worker3의 지적이 정당하다. 시맨틱 토큰으로의 전환에는 구체적 마이그레이션 경로가 필요하다.

**수용하는 마이그레이션 단계**:
```
Phase 1: 인벤토리 — 현행 CSS 변수 전수 조사 (--bg-*, --text-*, --accent-* 등)
Phase 2: 별칭 생성 — 새 시맨틱 이름 → 기존 이름 매핑 (둘 다 유효)
Phase 3: 배치 전환 — 프로젝트별로 새 이름 적용, 시각 스크린샷 비교
Phase 4: 린트 강제 — 구 이름 사용 시 경고/에러
Phase 5: 별칭 제거 — 모든 프로젝트 전환 완료 후
```

---

### W3-M3/M4. 접근성·벤치마크 구체성 부족

**판정: ACCEPT (양건 모두)**

접근성은 Worker2 리뷰 수용과 일맥상통. Indeed 벤치마크는 **가설(hypothesis)**로만 취급하고 로컬 검증 필수.

---

### W3-L1. MAPE-K 시기상조

**판정: ACCEPT**

내 원안도 D3(Round 4+)로 분류했으므로 합의됨.

---

### W3-E. 누락된 엣지 케이스

**판정: PARTIAL ACCEPT**

| 엣지 케이스 | 판정 | 근거 |
|-------------|------|------|
| 다크/라이트 모드 + 고대비 모드 | **ACCEPT** | 글로벌 디자인 시스템에 해당 |
| Windows DPI 스케일링 + ClearType | **ACCEPT** | 범용 — 다중 플랫폼 대응 |
| i18n/한글 텍스트 레이아웃 | **ACCEPT** | 현행 시스템에 keep-all 있으나 확장 필요 |
| reduced-motion + 키보드 전용 | **ACCEPT** | 현행 시스템에 기반 있으나 강화 필요 |
| CSS 변수 폴백 전략 | **ACCEPT** | 마이그레이션 시 필수 |
| 생성 코드 실패 모드 | **ACCEPT** | 스키마 버전 불일치 등 |
| xterm 테마 통합 | 범위 밖 | cmux-win 프로젝트 특화 |
| themes.json 매핑 | 범위 밖 | cmux-win 프로젝트 특화 |
| Electron/브라우저 모드 토큰 분리 | 범위 밖 | cmux-win 프로젝트 특화 |
| Storybook/MCP 공급망 리뷰 | 범위 밖 | 현 단계 의존성 미추가 |

---

## Round 2 입력 사항 (Worker2 + Worker3 반영 통합)

### 최우선 과제

| 순번 | 과제 | 출처 |
|------|------|------|
| 1 | DESIGN.md 분리 + YAML 프론트매터 | Round 1 원안 |
| 2 | `## Core UX Constraints` (UX Safe Zone) 선행 배치 | Worker2 리뷰 1-1 수용 |
| 3 | `## Brand DNA & Mood Guidelines` 이중 인코딩 | Worker2 리뷰 4-1 수용 |
| 4 | 안티패턴 선언 (모든 컴포넌트) | Round 1 원안 |
| 5 | 3파일 슬림 컴포넌트 모델 채택 | Worker2 리뷰 2-2 수용 |
| 6 | 이원 포맷 전략 명시적 도식화 | Round 1 내포 → 명시화 |
| 7 | 런타임 접근성 래퍼 설계 | Worker2 리뷰 3-1 수용 |
| 8 | 디자인 Linter 훅 (arbitrary value 금지) | Worker2 리뷰 3-2 수용 |
| 9 | AI-Native UI 패턴 인지 부하 분석표 | Worker2 리뷰 1-2 수용 |
| 10 | 에이전트 보안 게이트 7항목 명문화 | Worker3 리뷰 H3 수용 |
| 11 | 성능 제약 섹션 (backdrop-filter 상한 등) | Worker3 리뷰 M1 수용 |
| 12 | 토큰 네이밍 마이그레이션 5단계 경로 | Worker3 리뷰 M2 수용 |
| 13 | 핵심 프리미티브 5개만 먼저 meta.json | Worker3 리뷰 H2 수용 |
| 14 | 1차 출처 URL 보완 + "표준 후보" 표현 수정 | Worker3 리뷰 C1 수용 |
| 15 | 엣지 케이스 6건 반영 (다크/라이트, DPI, i18n, 폴백 등) | Worker3 리뷰 E 수용 |

---

## 종합 결론

### Worker2(AGY) 리뷰: ACCEPT 7 / PARTIAL ACCEPT 3 / REBUT 1
### Worker3(Codex) 리뷰: ACCEPT 5 / PARTIAL ACCEPT 5 / REBUT 1

**총 22개 지적 중 REBUT 2건** (9%):
1. Worker2 2-1: YAML vs JSON "포맷 모순" → 보완 관계이지 모순 아님
2. Worker3 C2: "현행 시스템 평가 사실 오류" → 프로젝트 CLAUDE.md와 글로벌 CLAUDE.md 혼동

양 리뷰어의 피드백이 보고서의 실질적 품질을 높였다. 특히:
- Worker2: UX 계층(Intent, Safe Zone, Brand DNA) 보강
- Worker3: 엔지니어링 엄밀성(보안, 성능, 마이그레이션, 1차 출처) 보강

이 정직한 기준선 위에서 Round 1 최종 보고서를 작성한다.
