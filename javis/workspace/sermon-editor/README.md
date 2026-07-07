# My-Sermon-Editor

설교 원고 작성 자동화 프로젝트. 성경 본문을 입력하면 Claude가 설교 DNA에 맞춰 기본틀 → 원고 → 이미지 → DOCX → PPT까지 자동 생성한다.

## 워크플로우

```
본문 + 날짜 입력
  ↓
[1] 폴더 생성 (sermons/YYYYMMDD-제목/)
  ↓
[2] 기본틀 작성 (기본틀.md)
  ↓
[3] 전체 원고 작성 (원고.md)
  ↓
[4] 이미지 생성 (하이브리드 ⭐)
    ├─ 장면 이미지       → Pollinations.ai (Claude가 프롬프트 세밀 작성)
    ├─ 텍스트/인포그래픽 → md_to_pptx.py (자동 렌더)
    └─ 유명인 실제 사진  → 웹 검색 다운로드
  ↓
[5] DOCX 변환 (output/)
  ↓
[6] PPT 생성 (output/)
  ↓
[7] 완료
```

## 프로젝트 구조

```
My-Sermon-Editor/
├── README.md
├── CLAUDE.md                 ← Claude 설계 문서
├── scripts/                  ← Python 스크립트
│   ├── md_to_pptx.py         ← MD → PPT 자동 생성
│   ├── md_to_docx.py         ← MD → DOCX 변환
│   ├── image_selector.py     ← 브라우저 이미지 선택기 (Streamlit :8503)
│   ├── auto_regen.py         ← NLM 자동 재생성 워처
│   ├── image_editor.py       ← 이미지 편집 (크롭/보정)
│   ├── md_preview.py         ← 원고 미리보기 HTML 생성
│   └── extract_slides.py     ← PPTX에서 이미지 추출
├── templates/                ← 새 설교 시작 시 참조 템플릿
│   ├── 기본틀-template.md
│   ├── 원고-template.md
│   └── ppt-template-wide.pptx
├── sermons/                  ← 모든 설교 작업 폴더
│   └── YYYYMMDD-제목/
│       ├── 기본틀.md
│       ├── 원고.md
│       ├── images/           ← NLM 슬라이드 이미지
│       └── output/           ��� 최종 산출물 (DOCX/PPTX)
├── myppt/                    ← 참조 PPT 원본 (2022~2026)
├── references/               ← 스타일 가이드, 참고 자료
└── .claude/skills/           ← Claude 스킬
    ├── sermon-writer/        ← 설교 작성
    ├── ppt-maker/            ← PPT 생성/수정
    └── image-selector/       ← 이미지 선택 워크플로우
```

## 사용법

### 새 설교 시작

Claude Code에서:

```
"시작하자" 또는 직접 본문/날짜 입력
```

### 주요 명령

| 명령 | 동작 |
|------|------|
| 시작하자 | 새 설교 워크플로우 ���작 |
| PPT 만들어 | 원고 기반 PPT 생성 |
| PPT 수정 | 기존 PPT 수정 |
| 미리보기 | ���고 HTML 미리보기 (localhost:8502) |

## 주요 도구

| 도구 | 용도 |
|------|------|
| **`Pollinations.ai`** ⭐ | **장면 이미지 생성** (무료, API 키 불필요, 16:9 1920×1080) |
| `python-pptx` | PPTX 파일 생성 + 텍스트/인포그래픽 슬라이드 자동 렌더 |
| `python-docx` | DOCX 파일 생성 |
| `Streamlit` | 이미지 선택 브라우저 UI (선택적) |
| `nlm` CLI | [레거시] 노트북LM 슬라이드 (정보 시각화 설교 전용) |

### Pollinations.ai 사용법

```bash
# 단일 이미지 생성 예시
curl -o image.jpg \
  "https://image.pollinations.ai/prompt/$(python -c 'import urllib.parse;print(urllib.parse.quote("your prompt here"))')?width=1920&height=1080&model=sana&nologo=true&seed=101"
```

- **레이트 리밋**: 익명 15초/요청 (배치 시 `time.sleep(16)` 필수)
- **스크립트 템플릿**: `sermons/<설교폴더>/_gen_pollinations.py`
- **API 레퍼런스**: `바탕 화면/pollinations/APIDOCS.md`

## 설교 DNA

- 3단 본론 구조 (진단 → 복음 → 적용)
- 원어(헬라어/히브리어) 분석 필수
- Q&A 대화체 + (pause) 표기
- 하나님의 1인칭 선언으로 결론
- 함께 고백/선포문 포함
