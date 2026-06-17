# 두 Python 모니터링 프로젝트 아키텍처 비교 분석 보고서

본 보고서는 신교수님의 요청에 따라 서로 다른 도메인과 목적을 가진 두 Python 모니터링 프로젝트의 소프트웨어 아키텍처를 분석하고 비교한 결과물입니다.

---

## 1. 비교 대상 프로젝트 개요

| 구분 | 프로젝트 1: 사무실 모니터링 (`office-monitor`) | 프로젝트 2: 환경 스캔 (`env-scan`) |
| :--- | :--- | :--- |
| **목적** | 실시간 영상 기반 객체/얼굴 감지 및 녹화 | 환경 변화 수집 정보 실시간 대시보드 브리핑 |
| **핵심 파일** | [main.py](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/main.py), [paths.py](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/paths.py), [database.py](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/database.py), [detection_engine.py](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/detection_engine.py), [monitor_engine.py](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/monitor_engine.py), [recording_engine.py](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/recording_engine.py) | [launch_monitor.py](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/launch_monitor.py), [monitor.py](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/monitor.py) |
| **기반 UI** | PyQt6 (데스크톱 네이티브 GUI) | Streamlit (반응형 웹 대시보드) |
| **핵심 기술** | YOLO11, InsightFace, OpenCV, SQLite3 | Streamlit Components (HTML/CSS), JSON 파싱 |

---

## 2. 관점별 비교 분석

### 2.1. 모듈 구조 (Module Structure)

#### [프로젝트 1: office-monitor] - 다층 계층형 및 멀티스레딩 구조
* **관심사 분리(Separation of Concerns)**: 비즈니스 로직, 데이터 접근(DAO), UI 영역이 매우 엄격하게 분리되어 있습니다.
* **비동기 스레드 구조**: GUI 스레드의 반응성을 유지하기 위해 무거운 IO 및 AI 연산을 전담 스레드로 이관했습니다.
  * **[CameraThread](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/monitor_engine.py#L13)**: 백그라운드 카메라 캡처.
  * **[RecordingThread](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/recording_engine.py#L16)**: 비디오 녹화 및 파일 세그먼트 생성.
  * **[DetectionThread](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/detection_engine.py#L96)**: 얼굴 매칭 및 캐싱.
* **프로세스 격리**: Python의 GIL(Global Interpreter Lock) 병목을 우회하기 위해 YOLO 및 InsightFace 추론 코드를 별도의 독립 프로세스(`_inference_loop`)로 격리하여 실행하고, `multiprocessing.Queue`를 통해 메인 프로세스와 통신합니다.

```mermaid
graph TD
    subgraph Main Process (PyQt6 UI)
        main[main.py] --> MainWindow
        MainWindow --> CameraThread
        MainWindow --> RecordingThread
        MainWindow --> DetectionThread
        DetectionThread <--> database[database.py]
    end
    subgraph Sub Process (Inference)
        DetectionThread <== multiprocessing.Queue ==> _inference_loop
        _inference_loop --> YOLO11
        _inference_loop --> InsightFace
    end
```

#### [프로젝트 2: env-scan] - 단일 평탄형 및 데이터 중심 구조
* **스크립트 중심 구성**: UI 컴포넌트, 커스텀 CSS 스타일 정의, 데이터 로드 및 집계 로직이 [monitor.py](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/monitor.py)라는 단일 파일에 통합되어 설계되었습니다.
* **실행 래퍼 분리**: [launch_monitor.py](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/launch_monitor.py)는 streamlit CLI 명령을 서브프로세스로 구동하고 브라우저를 띄워주는 원클릭 래퍼 역할에 한정됩니다.
* **데이터 단방향 흐름**: 주기적 폴링(`st.rerun()`)을 통해 디렉토리 내 특정 JSON 파일의 마스터 상태를 읽어 화면에 그대로 렌더링하는 전형적인 데이터 읽기 전용 대시보드 구조입니다.

---

### 2.2. 의존성 관리 (Dependency Management)

#### [프로젝트 1: office-monitor] - 복합적 및 로컬 환경 밀착형 의존
* **무거운 AI 종속성**: 실시간 영상 분석을 위해 `ultralytics`(YOLO), `insightface` 등을 갖추고 있어 시스템 리소스(CPU/GPU)와 밀접하게 연동됩니다.
* **운영체제(OS) 종속성**: Windows 네이티브에서 중복 실행을 막기 위한 `Named Mutex` 제어와 작업표시줄 아이콘 표시에 `ctypes` 및 `win32gui` 등의 Windows 전용 API를 직접 결합하여 사용합니다.
* **스레드 세이프 설계**: 다중 스레드가 단일 데이터베이스 파일에 읽기/쓰기를 진행하므로, SQLite의 WAL(Write-Ahead Logging) 모드를 활성화하고 Python 내 `threading.Lock`을 결합하여 동시성 레이스를 방지합니다.

#### [프로젝트 2: env-scan] - 가볍고 이식성 높은 의존성
* **웹 지향적 경량 패키지**: 실시간 UI를 손쉽게 구축할 수 있는 `streamlit` 패키지가 의존성의 핵심입니다. AI 연산이나 무거운 로컬 라이브러리가 프론트엔드 레벨에는 필요하지 않습니다.
* **비동기 간접 결합**: 수집 엔진(백엔드)과 시각화(프론트엔드)가 직접 스레드나 소켓으로 연결되지 않고 **JSON 파일 시스템**을 매개로 결합되어 있어, 상호 시스템 크래시가 전파되지 않습니다.

---

### 2.3. 설정 방식 (Configuration Management)

#### [프로젝트 1: office-monitor] - YAML 기반 단일 원천 경로 설정
* **설정의 명시적 분리**: 하드웨어 포트나 세부 모델 임계값을 코드에 작성하지 않고 `config.yaml` 템플릿 파일로 일괄 정의합니다.
* **단일 원천(Single Source of Truth)**: [paths.py](file:///C:/dev/cmux-win/javis/tests/workspace/office-monitor/paths.py) 모듈이 설정 파일의 `storage.data_dir`을 읽어 들여, DB 경로(`monitor.db`), 크래시 로그(`crash.log`), 캡처 이미지 폴더 등의 하위 경로를 일관성 있게 유추 및 생성합니다.

#### [프로젝트 2: env-scan] - 코드 내 내장 상수 및 파일 네이밍 컨벤션
* **하드코딩(Hard-coded) 상수**: 테마의 RGB/Hex 컬러 값, 수집 소스 배열(`WF_ORDER`), 다국어 변환 맵(`FSSF_KO`) 및 소스 데이터의 참조 경로가 코드([monitor.py](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/monitor.py)) 내부에 전역 변수 형태로 내장되어 있습니다.
* **컨벤션 의존**: 오늘 날짜를 기준으로 로그 파일 이름(`master-status-YYYY-MM-DD.json`, `dashboard-data-YYYY-MM-DD.json`)이 존재할 것이라 가정하고 경로를 순회 및 조립합니다.

---

### 2.4. 확장성 (Scalability)

#### [프로젝트 1: office-monitor]
* **성능 확장성**: GIL을 회피하기 위해 다중 스레드가 아닌 멀티프로세스를 사용하여 연산 부하가 큰 AI 파이프라인을 분리함으로써 CPU 자원을 최적으로 활용합니다.
* **기능 확장성**: `database.py` 내에 SQLite 테이블 자동 마이그레이션 구문(`ALTER TABLE`)을 구현하여 앱 버전 업데이트 시 스키마 변경 사항을 유연하게 배포 가능합니다.
* **한계**: 모든 모듈이 단일 컴퓨터 내부 리소스(물리 웹캠 및 로컬 디바이스 메모리)에 긴밀히 종속되어 분산 시스템으로 수평 확장(Scale-out)하려면 별도의 아키텍처 개편이 요구됩니다.

#### [프로젝트 2: env-scan]
* **시스템 아키텍처 확장성**: 데이터 수집 파이프라인(백엔드)과 모니터링 시각화(프론트엔드)가 독립적인 프로세스로 실행되므로, 수집 엔진의 구조 변화가 대시보드 화면 구동에 직접적인 장애를 야기하지 않습니다.
* **한계**: Streamlit 특성상 새로운 사용자가 브라우저로 접속할 때마다 전체 소스코드가 재실행되어 로컬 JSON 파일을 매번 파싱해야 합니다. 사용자 혹은 처리할 원천 데이터 파일 크기가 급증할 경우 대규모 IO 병목이 발생하여 동시성 성능이 급격히 저하됩니다.

---

### 2.5. 코드 재사용성 (Code Reusability)

#### [프로젝트 1: office-monitor]
* **모듈러 기반 설계**: `CameraThread`, `RecordingThread`, `database` 등의 엔진 클래스가 특정 프레임워크나 뷰에 비침투적으로 설계되어 있습니다. GUI를 배제하더라도 백그라운드 서비스나 CLI 모니터링 시스템 등 타 플랫폼에서 이 로직을 그대로 import 하여 재사용할 수 있습니다.

#### [프로젝트 2: env-scan]
* **강결합 구조**: HTML/CSS 스타일 속성과 UI 컴포넌트 렌더링, 데이터 파싱 흐름이 Streamlit 전용 함수 형태와 밀접하게 엮여(Tightly-coupled) 있습니다. 따라서 본 코드를 복사하지 않고 다른 성격의 프로젝트에서 독립된 컴포넌트로 호출하거나 라이브러리 형태로 활용하기는 불가능에 가깝습니다.

---

## 3. 아키텍처 종합 비교

| 아키텍처 관점 | 프로젝트 1: office-monitor | 프로젝트 2: env-scan |
| :--- | :--- | :--- |
| **모듈성 및 결합도** | 높음 (계층 분리, 객체지향, 낮은 결합도) | 낮음 (단일 모듈 내 UI-비즈니스 로직 강결합) |
| **동시성 모델** | Multi-process & Multi-thread (GIL 극복) | single-threaded Event Loop (웹 요청별 재실행) |
| **자원 공유 방식** | 스레드 메모리 공유 & SQLite (WAL / DB 락 제어) | 파일 시스템 공유 (비동기 JSON 파일 폴링) |
| **유지보수 용이성** | 단위 모듈별 테스트 및 디버깅 용이 | 파일 하나로 수정이 용이하나 코드 크기 증가 시 유지보수 복잡 |
| **플랫폼 독립성** | Windows 네이티브 기능 종속성 있음 | OS 독립적 (Streamlit 구동 가능한 모든 OS) |

---

## 4. 아키텍처 개선을 위한 제안

### [office-monitor 프로젝트 개선 제안]
1. **OS 독립성 확보**: `main.py`에 포함된 Named Mutex 및 Win32 API 윈도우 조작 코드를 크로스 플랫폼을 지원하는 패키지(예: `pywin32`를 조건부 임포트 처리하거나 Qt 네이티브의 `QSystemTrayIcon` 등 활용)로 래핑하여 Linux/macOS 환경에서도 이식이 가능하도록 추상화가 필요합니다.
2. **AI 서브프로세스 재사용성 강화**: `_inference_loop`를 범용적인 네트워크 API(예: FastAPI 기반 로컬 서버)나 gRPC 파이프라인으로 전환하면 모델 교체 및 클라이언트 다변화가 매우 쉬워집니다.

### [env-scan 프로젝트 개선 제안]
1. **데이터 계층 분리**: `monitor.py` 내의 JSON 파일 파싱 및 데이터 통계 연산 로직을 전담 모듈(예: `data_provider.py`)로 분리하여 비즈니스 로직과 UI 컴포넌트를 명확히 분리해야 합니다.
2. **데이터 캐싱 메커니즘 도입**: 파일 IO 성능 저하를 방지하기 위해 Streamlit의 내장 캐시 장치(`st.cache_data` 혹은 `st.cache_resource`)를 사용하여 수시로 반복되는 디스크 로드를 최소화하고 가상 메모리 상에서 최적의 속도로 동작하도록 수정해야 합니다.
