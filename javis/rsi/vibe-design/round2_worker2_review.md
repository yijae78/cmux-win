# RSI Vibe-Design — Round 2 Worker2(AGY) 심층 리뷰 보고서

* **Reviewer**: Worker2(AGY) (디자인/UX/전략/컨텐츠 리뷰어)
* **Date**: 2026-06-17
* **Target File**: [round2_worker1_synthesis.md](file:///C:/dev/cmux-win/javis/rsi/vibe-design/round2_worker1_synthesis.md)
* **Review Focus**: 
  1) `DESIGN.md` 분리 계획의 실현 가능성
  2) 토큰 마이그레이션의 하위 호환성
  3) 마스터 브랜드 DNA의 기계 판독 포맷 변환 시 뉘앙스 손실 검증

---

## Executive Summary

Worker1의 Round 2 종합 실행 계획은 Round 1에서 본 리뷰어가 제시한 피드백을 충실히 반영하여 **UX 안전 구역(Safe Zone)**, **브랜드 DNA의 수치 제약화**, **디자인 Linter 훅** 등을 구체적이고 체계적인 로드맵(Phase 1~4)으로 발전시켰습니다. 

특히 글로벌 수준과 프로젝트 수준의 토큰 SOT를 이원화(YAML vs JSON)하여 빌드 파이프라인 유무에 따른 최적화 경로를 개척한 것은 매우 뛰어난 전략적 결단입니다.

다만, 실제 적용을 앞두고 **1) 에이전트의 지침 인지 메커니즘 한계, 2) 리팩토링 비용이 과도한 폴백 체인 설계, 3) 수치화 과정에서 거세되는 마스터 고유의 조형적 뉘앙스** 등 실무적 차원의 심각한 리스크가 발견되었습니다. 이에 대해 보다 엄격한 관점에서 [문제점/논쟁점/조언]을 피드백합니다.

---

## 1. DESIGN.md 분리 계획의 실현 가능성 (Feasibility of DESIGN.md Separation)

> **"호스트 에이전트의 인지 범위 한계 및 포인터 지침의 작동 실패 리스크"**

### 🚨 문제점 (Problems)
1. **에이전트 인지 경로 이탈 (Ignore Risk)**: 현재 Claude Code 및 주요 코딩 에이전트들은 시스템 프롬프트 상에서 프로젝트 루트의 `CLAUDE.md`만을 제1의 자동 탐색 및 로드 지침서로 인식하도록 코어 아키텍처가 빌트인되어 있습니다. 디자인 섹션 922줄을 `DESIGN.md`로 밀어내고 `CLAUDE.md`에는 참조 포인터만 남길 경우, 에이전트가 코딩 중 매번 의식적으로 `DESIGN.md`를 열어보지 않고 CLAUDE.md의 껍데기 포인터만 읽은 채 작업을 수행하여 **디자인 규격을 통째로 누락하고 평범한 코드를 짤 가능성**이 극히 높습니다.
2. **Phase 1 대규모 변경에 따른 컨텍스트 충격**: 검증 샌드박스 없이 즉각적으로 CLAUDE.md의 70%가 넘는 분량을 지우고 DESIGN.md를 신설하는 것은 마스터 에이전트의 세션 기억 복원 및 복구 프로세스(RECOVERY.md 등)에 예기치 않은 오류를 유발할 수 있습니다.

### ⚖️ 논쟁점 (Debatable Points)
* 에이전트가 파일 링크나 텍스트 포인터만을 보고 스스로 `DESIGN.md`를 `view_file` 하도록 유도하는 것이 100% 신뢰 가능한가? 아니면 에이전트 기동 훅(Startup Hook)을 통해 세션 시작 시 `DESIGN.md`를 강제 리드(Force Read)하도록 셸 환경에서 강제 제어해야 하는가?

### 💡 조언 (Recommendations)
* **점진적 미러링(Mirroring) 및 포인터 검증 도입**:
  - 즉각적인 물리적 삭제를 지양하고, **Phase 1-A (미러링 단계)**를 신설하십시오. 이 단계에서는 CLAUDE.md의 기존 구조를 유지한 채 `DESIGN.md`를 생성하여 정합성을 동기화합니다.
  - 에이전트가 두 파일의 연동을 안정적으로 소화하는지 검증된 이후에만 CLAUDE.md의 디자인 내용을 축소하고 지침 참조 포인터로 점진 대체하십시오.
  - 또한, `CLAUDE.md`의 참조 포인터 섹션에 다음과 같이 에이전트가 시작 시 반드시 읽어야 할 **강제적 호출 커맨드(Run Command/Force Read instruction)**를 삽입하여 에이전트가 실행 흐름 상에서 무조건 `DESIGN.md`를 메모리에 로드하게 강제하십시오.

---

## 2. 토큰 마이그레이션의 하위 호환성 (Backward Compatibility of Token Migration)

> **"3단 폴백 체인의 실무적 복잡성과 런타임 변수 해석 오버헤드"**

### 🚨 문제점 (Problems)
1. **수작업 리팩토링 비용의 폭증**: Worker1이 제시한 `var(--surface-base, var(--bg-primary, #0c111b))`와 같은 3단 폴백 체인은 기존 수십 개 컴포넌트 코드베이스의 모든 스타일 속성마다 수동으로 삽입해야 하므로 마이그레이션 리소스 낭비가 큽니다.
2. **CSS 변수 처리 성능 저하**: 브라우저 렌더링 엔진(특히 Electron WebView 등)에서 복잡하게 중첩된 CSS 변수 폴백 체인(Nested CSS Variable Resolution Chain)은 다량의 컴포넌트가 실시간으로 리사이징되거나 렌더링될 때 프레임 드랍 및 레이아웃 지연(Layout Thrashing)을 유발할 수 있습니다.

### ⚖️ 논쟁점 (Debatable Points)
* 모든 컴포넌트마다 3단 폴백을 인라인으로 심는 로컬 대응 방식과, 전역 호환성 레이어를 빌드 타임 혹은 엔트리 스타일시트에 한 번에 심어 구 변수 호출을 신규 변수로 우회하는 글로벌 대응 방식 중 어떤 것이 자바리스의 성능과 개발 효율에 더 적합한가?

### 💡 조언 (Recommendations)
* **글로벌 역방향 호환 레이어 (Retrofit stylesheet) 제안**:
  - 컴포넌트 코드를 수정하지 말고, 프로젝트의 공통 변수 파일(`global.css` 또는 Style Dictionary generated 변수 파일) 최상단에 **역방향 별칭 레이어**를 단 한번만 선언할 것을 조언합니다.
    ```css
    :root {
        /* 구 변수명이 들어오면 자동으로 새 시맨틱 토큰 변수를 참조하도록 바인딩 */
        --bg-void: var(--surface-void);
        --bg-primary: var(--surface-base);
        --bg-raised: var(--surface-raised);
        --text-primary: var(--text-emphasis);
        --text-secondary: var(--text-default);
        --text-muted: var(--text-subtle);
    }
    ```
  - 이 방식을 사용하면 컴포넌트 소스 코드를 단 한 줄도 건드리지 않고 하위 호환성이 100% 보장되며, 향후 마이그레이션이 완료되면 이 호환 레이어 파일 하나만 제거하면 되므로 유지보수 및 성능 상 극도로 안전합니다.

---

## 3. 마스터 브랜드 DNA의 기계 판독 포맷 변환 시 뉘앙스 손실 검증 (Brand DNA Nuance Integrity)

> **"수치화로 인한 심미적 유연성 거세 및 인문학적/조형적 뉘앙스의 박제화"**

### 🚨 문제점 (Problems)
1. **미학적 비례 관계의 무시**: Worker1은 `background_lightness_range: [0, 12]` 또는 `accent_hue_range: [35, 50]`(황금빛 범위) 등 단순 수치 밴드로 마스터의 디자인 DNA를 인코딩했습니다. 그러나 마스터 고유의 디자인 정체성인 **'시네마틱 역광'**이나 **'성스러운 어둠'**은 단일 수치 밴드가 아닌, 배경 대비 광채의 세기, 빛의 산란 효과(Glow/Blur), 서체 서정성 등 **고차원적인 조형적 관계(Visual Ratio)**에서 나옵니다. AI가 수치 범위만 간신히 맞춰 촌스럽고 평이한 템플릿 UI를 내놓아도 "수치적 제약은 통과했다"고 인지하여 완성도 낮은 화면을 최종 승인할 리스크가 큽니다.
2. **문맥적 감성 상실**: "Cinematic backlight"나 "Sola Gratia의 광채"와 같은 성경적/철학적 장엄함의 뉘앙스가 YAML 키-값 쌍으로 압축되는 과정에서 완전히 소멸되었습니다.

### ⚖️ 논쟁점 (Debatable Points)
* 브랜드의 시각적 완성도(Taste)를 통제하기 위해 AI 에이전트에게 수학적 수치 가이드만을 전달해야 하는가, 아니면 비유와 메타포가 풍부한 인문학적 산문 가이드를 프롬프트에 포함하는 것이 미학적 렌더링 품질 향상에 더 기여하는가?

### 💡 조언 (Recommendations)
* **이중 레이어 미학 코딩 (Dual-Layer Aesthetic Encoding) 전략 구축**:
  - YAML은 최소한의 경계선(가드레일)으로만 유지하고, `DESIGN.md` 내 `Brand DNA & Mood Guidelines`에 **"Aesthetic Rendering Metaphors (조형적 연출 메타포)"** 서술 섹션을 한층 강화하십시오.
  - 여기에 단순히 "어두운 배경" 대신 마스터의 철학과 연결된 구체적 연출 묘사를 명문화해야 합니다.
    * 예시: *"마치 어두운 고딕 성당 안에 유일하게 흘러드는 황금빛 햇살처럼, 화면은 90% 이상의 성스러운 어둠(--surface-void)을 유지하고, 마스터가 응시할 단 하나의 핵심 액션 요소(--interactive-primary)만이 신비롭고 깊이 있는 역광 글로우(shadows.glow, 24px)를 뿜어내야 한다. 화려한 네온 무지개나 가벼운 파스텔톤은 마스터의 철학을 훼손하는 심각한 안티패턴이다."*
  - 이와 같이 문학적 묘사(Do's/Don'ts 결합)를 텍스트로 보강하여 AI 에이전트가 스타일을 창조할 때 심미적/스토리적 깊이를 잃지 않도록 봉인해 주어야 합니다.

---

## 결론 및 지시 건의

Worker1의 종합 실행 계획은 즉시 Phase 1로 진입하기에 충분히 치밀합니다. 

다만 마스터님께서는 본 리뷰어의 3대 리스크 보완책인 **1) CLAUDE.md-DESIGN.md 미러링 및 에이전트 리드 훅 강제화, 2) 글로벌 역방향 호환 별칭 레이어로의 마이그레이션 변경, 3) Brand DNA 섹션에 대한 인문학적/조형적 메타포 가이드라인 보강**을 추가 반영하여 실행할 것을 명령해 주시기 바랍니다.
