# 모니터링 시스템 패턴 비교 분석 보고서

신교수님, 요청하신 두 가지 모니터링 프로젝트의 소스 코드를 면밀히 분석한 비교 보고서입니다.

분석 대상 프로젝트:
* **프로젝트 1 (Office Monitor)**: [detection_engine.py](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/detection_engine.py) 및 [monitor_engine.py](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/monitor_engine.py)
* **프로젝트 2 (Env Scan)**: [monitor.py](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/monitor.py)

---

## 1. 모니터링 패턴 공통점 및 차이점

### 🔄 공통점
* **주기적 상태 갱신**: 두 프로젝트 모두 실시간 상태 변화를 추적하기 위해 주기적인 인터벌 기법(200ms 단위 실시간 감지 vs 5초/30초 단위의 화면 새로고침)을 채택하고 있습니다.
* **상태 시각화 보장**: 추적된 상태를 사용자 엔드포인트(PyQt6 GUI 프레임워크 vs Streamlit 브라우저 대시보드)에 가시적으로 출력하여 모니터링 정보의 인지도를 확보합니다.

### ⚖️ 차이점
* **기기 결합도 (Edge vs Virtual)**:
  - **Office Monitor**는 물리 장치(카메라)에 직접 결합되어 프레임 단위의 대용량 비디오 스트림을 캡처하고 분석하는 **능동형 에지 디바이스 모니터링**입니다.
  - **Env Scan**은 이미 생성되어 파일 시스템에 저장된 텍스트 로그 및 JSON 상태 정보 요약본을 파싱하는 **수동형 파일 기반 대시보드 모니터링**입니다.
* **동작 패러다임**:
  - **Office Monitor**는 실시간 프레임 분석에 따른 쓰기 연산(방문자 DB 기록 및 이미지 생성)이 빈번한 **상태 변경/수집 시스템**입니다.
  - **Env Scan**은 시스템 변경 내역 없이 파일의 수집 결과를 시각화하기만 하는 **읽기 전용 상태 관측 시스템**입니다.

---

## 2. 이벤트 감지 방식 (Event Detection Mechanism)

### 📸 프로젝트 1: Office Monitor
* **AI 융합 실시간 감지**: YOLO11n(인물 바운딩박스 검출) ➡️ ByteTrack(추적 ID 및 동선 영속성 부여) ➡️ InsightFace(얼굴 매칭 및 신원 조회)의 3단계 딥러닝 체인을 결합하여 감지합니다.
* **지능적 임계 필터링**:
  - 임베딩 매칭의 신뢰도를 보장하기 위해 얼굴 신뢰 점수(confidence), 양 눈 사이 간격(최소 15px), 코와 눈의 위치 관계를 이용한 정면성 검증([_is_frontal_enough](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/detection_engine.py#L295))을 통해 불량 캡처를 일차 차단합니다.
  - 등록 대기 중인 얼굴의 선명도는 라플라시안 분산(최소 25.0)을 통과해야 이벤트가 기재됩니다.
* **최고 화질 캡처 윈도우(Best Frame)**:
  - 감지 즉시 데이터를 기록하지 않고, 3초의 임시 수집 버퍼를 두어 얼굴 품질 점수([_compute_quality_score](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/detection_engine.py#L624))가 가장 높은 단 1장의 프레임만 선별 저장함으로써 오감지 및 중복 로그를 방지합니다.

### 🔬 프로젝트 2: Env Scan
* **규칙 기반 상태 해석**:
  - 마스터 상태 파일의 메타데이터 필드(`workflow_results`, `status`)를 정기 폴링하여 `live` (수집 중), `idle` (대기), `completed` (성공) 상태를 논리적으로 추출합니다.
* **휴리스틱 로그 스캔**:
  - 터미널 텍스트 로그의 마지막 8줄을 역순으로 읽어 "traceback", "exception" 등의 키워드가 잡히면 `error`로 분류하고, "working", "processing" 등이 매칭되면 `live`로 판별하는 정적 텍스트 매칭 패턴을 사용합니다.

---

## 3. 데이터 수집 패턴 (Data Ingestion Pattern)

* **Office Monitor (Push/Streaming)**:
  - OpenCV 비디오 캡처 스레드([CameraThread](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/monitor_engine.py#L13))를 통해 카메라 실시간 비디오 입력을 Push 방식으로 지속 수용합니다.
  - 파이썬의 GIL(Global Interpreter Lock) 병목을 회피하기 위해, 핵심 추론 로직을 PySide 메인 루프와 완전히 격리된 별도의 서브프로세스([_inference_loop](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/detection_engine.py#L32))로 구동하고 `multiprocessing.Queue`로 프레임을 전송받는 고성능 비동기 파이프라인 패턴을 사용합니다.
* **Env Scan (Pull/Polling)**:
  - 주기적인 새로고침에 의해 디스크 내에 덤프된 JSON 데이터를 동기적으로 호출하여 메모리에 가져오는([_load](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/monitor.py#L216)) 전형적인 간접 Polling/Pull 방식을 구현하고 있습니다.

---

## 4. 우수 사례(Best Practice) 식별

### 🌟 Office Monitor 우수 사례
1. **GIL 병목 완벽 격리 (Multiprocessing App)**:
   - 프레임 캡처, GUI 이벤트 루프, YOLO/InsightFace의 신경망 추론 연산을 각각 별도 스레드 및 서브프로세스로 분할하고 `Queue`를 통해 최소화된 직렬화 데이터(바이트 및 딕셔너리)만 공유함으로써 프레임 드랍 없는 안정적 동작을 보장합니다.
2. **지수 백오프 및 기기 정합성 복원**:
   - 카메라 물리 연결 해제 시 지수 백오프(Exponential Backoff, 최대 30초)로 재연결을 시도하여 시스템 크래시를 방지하고, 화면 비율을 체크하여 가상 카메라 드라이버 주입을 차단하는 보안 기법이 우수합니다.
3. **지능적 임베딩 증강 (Augmentation)**:
   - 식별 성공 시, 정면 구도와 임베딩 유사성(최대 유사도 0.85 미만)을 종합 판정하여 기등록자의 임베딩을 DB에 추가 데이터로 자동 보강([_try_augment_embedding](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/detection_engine.py#L569))하여 시간이 지날수록 인식률을 스스로 개선해 나가는 기법이 적용되어 있습니다.

### 🌟 Env Scan 우수 사례
1. **가변 쿨다운 리프레시**:
   - 시스템 동작 모드(`live` 상태 시 5초, `idle` 대기 상태 시 30초)에 따라 폴링 주기를 탄력적으로 제어하여 불필요한 디스크 I/O와 렌더링 비용을 합리적으로 제어합니다.
2. **경량 키워드 분석기**:
   - 무거운 구문 파싱 라이브러리 없이 순수 역방향 문자열 슬라이싱을 사용해 터미널 핵심 상태를 정확하게 해석해내는 휴리스틱 기법이 자원이 제한된 환경에서 훌륭한 실용성을 보여줍니다.
