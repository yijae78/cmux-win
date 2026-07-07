# OfficeMonitor

사무실 출입자를 실시간으로 감지하고 인식하는 데스크톱 모니터링 시스템입니다.
카메라 영상에서 사람을 추적하고, 등록된 방문자를 자동으로 식별하며, 방문 기록을 관리합니다.

## 주요 기능

- **실시간 얼굴 인식** - InsightFace(buffalo_l) 기반 얼굴 임베딩 매칭
- **사람 추적** - YOLO11n + ByteTrack으로 전신 감지 및 추적 (뒷모습도 추적 유지)
- **방문자 관리** - 등록/삭제/복구, 최대 10개 다각도 임베딩 자동 수집
- **방문 기록** - 타임라인 UI, 일별/시간대별 통계, KPI 대시보드
- **영상 녹화** - 수동 녹화, 30분 세그먼트 자동 분할
- **스냅샷 캡처** - 전체 화면 또는 영역 선택 캡처
- **미등록자 자동 캡처** - 3초간 최고 품질 프레임 선별 후 저장
- **시스템 트레이** - 최소화 시 트레이로 이동, 백그라운드 동작

## 화면 표시

| 상태 | 박스 색상 | 설명 |
|------|----------|------|
| 등록자 (얼굴 보임) | 녹색 실선 + 이름 | 얼굴 매칭 성공 |
| 등록자 (뒷모습) | 녹색 점선 + 이름 | 이전 매칭 track 유지 |
| 미등록자 (얼굴 보임) | 붉은색 실선 | 얼굴 감지되었으나 미등록 |
| 미등록자 (뒷모습) | 붉은색 점선 | 사람 감지, 얼굴 미검출 |

## 기술 스택

- **Python 3.10+**
- **PyQt6** - 데스크톱 UI
- **InsightFace** - 얼굴 검출 및 임베딩 추출
- **Ultralytics YOLO11n** - 사람 전신 감지
- **ByteTrack** - 다중 객체 추적
- **OpenCV** - 카메라 캡처, 이미지 처리
- **SQLite (WAL 모드)** - 방문자/방문기록 저장

## 프로젝트 구조

```
OfficeMonitor/
├── main.py                 # 앱 진입점
├── config.yaml             # 카메라/감지/녹화/저장 설정
├── paths.py                # 경로 설정 (config.yaml 기반)
├── database.py             # SQLite DB (visitors, visit_logs, pending_faces 등)
├── detection_engine.py     # 얼굴 인식 + YOLO 추적 스레드
├── monitor_engine.py       # 카메라 캡처 스레드
├── recording_engine.py     # 영상 녹화 스레드
├── assets/                 # 앱 아이콘 (ICO + PNG 16~512px)
├── tools/
│   └── generate_icon.py    # 앱 아이콘 생성 스크립트
└── ui/
    ├── main_window.py      # 메인 윈도우 (전체 통합)
    ├── camera_widget.py    # 카메라 뷰어 (줌, 영역 캡처, 감지 오버레이)
    ├── visitor_manager.py  # 방문자 등록/관리 UI
    ├── visitor_timeline.py # 방문 타임라인
    ├── stats_view.py       # 통계 뷰
    ├── settings_dialog.py  # 설정 다이얼로그
    ├── new_face_dialog.py  # 미등록 얼굴 등록 팝업
    ├── header_bar.py       # 상단 헤더
    ├── kpi_card.py         # KPI 카드 위젯
    ├── toast_widget.py     # 토스트 알림
    ├── glass_card.py       # 글래스모피즘 카드
    ├── design_tokens.py    # 디자인 토큰 (색상, 폰트 등)
    ├── styles.py           # 글로벌 스타일시트
    └── flow_layout.py      # 플로우 레이아웃
```

## 데이터 저장 구조

소스 코드와 데이터는 완전히 분리되어 있습니다. 모든 런타임 데이터는 `config.yaml`의 `storage.data_dir` 경로에 저장됩니다 (기본값: `C:\OfficeMonitor`).

```
C:\OfficeMonitor/                # 런타임 데이터 (git 추적 안 됨)
├── data/
│   ├── monitor.db              # SQLite 데이터베이스
│   ├── thumbnails/             # 방문 썸네일 이미지
│   └── pending_faces/          # 미등록 얼굴 캡처 이미지
├── snapshots/                  # 스냅샷 이미지
├── recordings/                 # 녹화 영상
├── app.log                     # 앱 로그 (5MB x 3 로테이션)
└── crash.log                   # 크래시 로그
```

## 빠른 시작

```bash
git clone https://github.com/yijae78/Office-Monitor.git
cd Office-Monitor
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

최초 실행 시 InsightFace 모델(`buffalo_l`)이 자동 다운로드됩니다.

> 상세 설치 가이드, 사용법, 문제 해결은 **[사용 매뉴얼 (MANUAL.md)](MANUAL.md)**을 참고하세요.

## 설정 (config.yaml)

```yaml
camera:
  id: 0                          # 카메라 장치 ID
  resolution: [1280, 720]        # 해상도
  fallback_ids: [2, 3]           # 메인 카메라 실패 시 대체 ID

detection:
  model: "buffalo_l"             # InsightFace 모델
  interval_ms: 200               # 감지 주기 (ms)
  similarity_threshold: 0.65     # 얼굴 매칭 임계값 (0~1)
  cooldown_seconds: 300          # 같은 사람 재기록 쿨다운 (초)
  auto_augment_embeddings: true  # 다각도 임베딩 자동 수집

recording:
  codec: "XVID"                  # 녹화 코덱
  fps: 15                        # 녹화 FPS
  segment_minutes: 30            # 세그먼트 길이

storage:
  data_dir: "C:\\OfficeMonitor"  # 데이터 저장 경로
  retention_days: 3              # 데이터 보존 기간
```

## 단축키

| 단축키 | 기능 |
|--------|------|
| `Ctrl+Shift+C` | 영역 캡처 |
| `Ctrl+R` | 녹화 시작/중지 |
| `Ctrl+P` | 녹화 일시정지 |
| `Ctrl+마우스휠` | 카메라 줌 |
| `ESC` | 영역 선택 취소 |

## DB 스키마

| 테이블 | 용도 |
|--------|------|
| `visitors` | 등록된 방문자 (이름, 썸네일, 상태) |
| `face_embeddings` | 얼굴 벡터 (방문자당 최대 10개, 품질 점수 포함) |
| `visit_logs` | 방문 기록 (시간, 등록 여부, 썸네일) |
| `pending_faces` | 미등록 얼굴 캡처 (등록 대기) |
| `snapshots` | 스냅샷 파일 기록 |
| `recordings` | 녹화 파일 기록 |

## 감지 파이프라인

```
카메라 프레임
    ↓
YOLO11n → 사람 바운딩박스 (모든 각도)
    ↓
ByteTrack → track_id 부여/유지
    ↓
InsightFace → 얼굴 검출 시 임베딩 매칭 → track_id에 이름 바인딩
    ↓
얼굴 미검출 → track_id의 기존 이름 유지 (뒷모습도 OK)
    ↓
결과 emit → UI 오버레이 + 방문 로그 + 미등록자 자동 캡처
```

## 라이선스

Private repository. All rights reserved.
