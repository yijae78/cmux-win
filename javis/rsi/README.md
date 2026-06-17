# Javis RSI (재귀적 자기개선) 아카이브

> 마스터 Fleet이 수행한 모든 RSI 라운드의 산출물을 영구 보존한다.
> 신교수님이 "알려줘"라고 요청하면 이 폴더에서 조회하여 보고한다.

## 아카이브 구조

```
javis/rsi/
├── README.md              ← 이 파일 (인덱스)
├── vibe-design/           ← 바이브디자인 RSI (2026-06-17~)
│   ├── DESIGN_DRAFT.md    ← YAML+Markdown 듀얼 포맷 디자인 시스템 초안 (22KB)
│   ├── round1_worker1.md          ← R1 Worker1 심층 연구 (14KB)
│   ├── round1_worker2_review.md   ← R1 Worker2(AGY) 리뷰 (10KB)
│   ├── round1_worker3_review.md   ← R1 Worker3(Codex) 리뷰 (11KB)
│   ├── round1_worker1_rebuttal.md ← R1 Worker1 반박 (24KB)
│   ├── round1_final.md            ← R1 최종 보고서 (25KB) ★
│   ├── round2_worker2_research.md ← R2 Worker2 사전 연구 (8KB)
│   ├── round2_worker3_research.md ← R2 Worker3 사전 연구 (17KB)
│   ├── round2_worker1_synthesis.md ← R2 Worker1 종합 (27KB)
│   ├── round2_worker2_review.md   ← R2 Worker2 리뷰 (10KB)
│   ├── round2_worker3_review.md   ← R2 Worker3 리뷰 (18KB)
│   ├── round2_final.md            ← R2 최종 보고서 (10KB) ★
│   ├── worker2_prep.md            ← Worker2 사전 조사 (7KB)
│   └── worker3_prep.md            ← Worker3 사전 조사 (6KB)
└── (향후 RSI 주제별 폴더 추가)
```

## 완료된 RSI

| 주제 | 시작일 | 라운드 | 총 산출물 | 핵심 결과 |
|------|--------|--------|-----------|-----------|
| **바이브디자인** | 2026-06-17 | Round 1~2 | 14파일/209KB | DESIGN.md 초안 생성, 점수 52→68/100 |

## 핵심 발견 요약

### 바이브디자인 RSI
- 신교수님 디자인 시스템 = **인간용 A급** (토큰 92점, 컴포넌트 88점)
- **에이전틱 준비도 D급** → Round 2에서 C+급으로 개선
- 핵심 해결: DESIGN.md 분리 (YAML 기계용 + Markdown 인간용)
- 스킬 생성: `~/.claude/skills/vibe-design/SKILL.md`
- 다음 목표: Round 3~로 85점+ 달성
