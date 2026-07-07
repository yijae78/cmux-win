# 코드 보안 및 아키텍처 리뷰 보고서

신교수님, 요청하신 [monitor.py](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/monitor.py) 및 [launch_monitor.py](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/launch_monitor.py) 두 파일에 대한 보안 취약점, 에러 핸들링 품질, 설계 패턴 적합성 리뷰 결과입니다.

---

## 1. monitor.py 상세 리뷰

### 🔍 보안 취약점 (Security Vulnerability)

1. **HTML/JS 인젝션 및 XSS 위험 (`unsafe_allow_html=True`)**
   - Streamlit의 `st.markdown` 메서드에서 `unsafe_allow_html=True` 옵션을 다수 사용하고 있습니다. 
   - 특히 [_load](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/monitor.py#L216)에서 로드하는 외부 JSON 파일(`master-status.json` 및 `dashboard-data-{date}.json`)의 값(예: `title_ko`, `title`, `date` 등)이 HTML 문자열 내에 포매팅되어 직접 렌더링됩니다.
   - 외부 파일에 악의적인 스크립트(예: `<script>` 태그 또는 이벤트 핸들러)가 포함되어 있다면 웹 브라우저 콘텍스트 내에서 XSS(Cross-Site Scripting) 공격이 실행될 위험이 있습니다.
   
2. **부모 프레임 도메인 접근 제약 및 샌드박스 우회 우려 (`ZOOM` 스크립트)**
   - [ZOOM](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/monitor.py#L126-L131) 변수의 JavaScript 코드 내에서 `window.parent.document` 객체에 직접 접근하여 스크롤 줌 속성을 조작합니다.
   - Streamlit은 기본적으로 컴포넌트들을 격리된 `iframe` 환경에서 실행시키며, 부모 도큐먼트에 대한 직접 제어는 브라우저 보안 정책(Same-Origin Policy 등)에 의해 차단되거나 오동작을 유발할 수 있어 지양해야 하는 패턴입니다.

3. **명시적 바인딩 주소 부재에 따른 네트워크 노출 위험**
   - 대시보드 구동 시 바인딩 호스트를 지정하지 않으면, 외부 네트워크에 포트가 개방되어 승인되지 않은 사용자가 대시보드 데이터에 접근할 우려가 있습니다.

---

### 🛠️ 에러 핸들링 품질 (Error Handling Quality)

1. **포괄적 예외 묵살 (Broad Exception Swallowing)**
   - JSON 파싱 도우미 함수인 [_j](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/monitor.py#L158-L162)에서 `except Exception:` 블록을 통해 모든 에러를 가두고 단순히 `None`만을 리턴합니다.
   - 디렉터리 내의 파일 파싱 중 에러가 나거나 JSON 스키마 손상 시, 원인(FileNotFound, PermissionError, JSONDecodeError 등)을 추적하기 어려워 디버깅 생산성을 떨어뜨립니다.
   - 날짜 포매팅 및 캐스팅 블록(`try-except-pass` 구문)에서도 구체적인 로깅 없이 에러를 방치하는 구조적 결함이 관찰됩니다.

2. **UI 스레드 내 차단형 대기 (Blocking Sleep in Main Thread)**
   - 스캔 데이터가 유효하지 않을 때 아래와 같이 스레드를 정지시킵니다.
     ```python
     if not s.has_data:
         time.sleep(30)
         st.rerun()
     ```
   - Streamlit의 메인 루프를 `time.sleep(30)`으로 직접 잡아두는 설계는 웹 요청 처리 성능에 악영향을 주며, 애플리케이션 반응성을 저해시킵니다.

---

### 📐 설계 패턴 적합성 (Design Pattern Suitability)

1. **Streamlit 상태 관리 아키텍처 미준수**
   - Streamlit은 세션 상태 관리를 위해 내장 객체 `st.session_state` 및 캐싱 메커니즘(`st.cache_data`, `st.cache_resource`)을 제공합니다.
   - 그러나 본 코드는 [State](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/monitor.py#L134) 데이타클래스를 선언한 뒤 매 렌더링 루프마다 디스크 디렉터리를 물리적으로 재탐색하는 구조입니다.
   - 불필요한 디스크 I/O가 매 새로고침 시마다 대량으로 유발되어 성능 병목을 발생시킬 수 있습니다.

2. **강한 파일 시스템 종속성과 도메인 레이어 결합**
   - 데이터 수집기(`_load`)가 고정된 상대 경로(`PROJECT / "env-scanning"`)에 강력하게 결합되어 있어, 다양한 실행 환경에서 유연하게 대응하기 어렵습니다. 
   - 데이터 액세스 로직과 UI 프리젠테이션 로직이 한 파일 내에 밀접하게 혼재해 있습니다.

---

## 2. launch_monitor.py 상세 리뷰

### 🔍 보안 취약점 (Security Vulnerability)

1. **하드코딩된 서버 바인딩 정보 및 포트**
   - `PORT = 8504`가 고정(Hardcoded)되어 있어 다른 서비스와의 포트 충돌 위험이 있고, 외부 호스트 바인딩 제어가 불가능합니다.
   - 로컬 환경 전용 실행을 보장하기 위해 `--server.address 127.0.0.1` 인수 추가를 명시하는 것이 보안상 안전합니다.

---

### 🛠️ 에러 핸들링 품질 (Error Handling Quality)

1. **경쟁 상태 유발 (Race Condition in Initialization)**
   - [main](file:///C:/dev/cmux-win/javis/tests/workspace/env-scan/launch_monitor.py#L16) 함수에서 프로세스 구동 후 단순 `time.sleep(3)` 대기하고 브라우저를 엽니다.
   - 시스템 사양에 따라 Streamlit 구동이 3초보다 지연될 경우 사용자는 브라우저에서 연결 거부(Connection Refused) 에러 페이지를 마주하게 됩니다.
   - 루프 내에서 소켓 포트 개방 여부(Socket Connection Polling)를 지능적으로 판별한 후 브라우저를 기동하도록 개선해야 합니다.

2. **예외 처리 부재로 인한 좀비 프로세스 방치 위험**
   - `proc.wait()` 도중 `KeyboardInterrupt`만을 특별 처단하고 있지만, 다른 비정상적인 종료 흐름이나 프로그램 이탈 시 `finally` 구문에서 서브프로세스를 확실하게 해제해주는 클린업 로직이 결여되어 있습니다. 이는 백그라운드 내 Streamlit 인스턴스의 좀비 프로세스화를 초래할 수 있습니다.

---

### 📐 설계 패턴 적합성 (Design Pattern Suitability)

1. **유연하지 못한 CLI 설계 (Hardcoded Params)**
   - Streamlit의 실행 옵션(테마, 포트 등)이 단순 Python 문자열 리스트 인자로 고정되어 있습니다. 
   - Argument Parser (`argparse`) 또는 환경 변수를 반영할 수 있는 구조로 리팩토링할 시 설정 유연성이 확보될 수 있습니다.

---

## 💡 종합 권장 개선 사항 (Action Items)

- **보안 강화**: 외부 파일 수집을 시각화할 때 XSS 위험이 없도록 HTML 이스케이프 유틸리티를 적용하거나 Markdown 렌더링에 필요한 필드만 엄격히 화이트리스트 가공을 거쳐야 합니다.
- **에러 핸들링**: 무분별한 `try-except-pass`와 `except Exception:`을 대체하여, 최소한의 에러 로깅(`logging.exception`)을 추가하고 예상 가능한 예외 타입(예: `FileNotFoundError`, `JSONDecodeError`)을 구분하여 세분화해야 합니다.
- **설계 품질**: Streamlit의 `st.cache_data` 장치를 적용하여 파일 로드 횟수를 제한하고 디스크 I/O 오버헤드를 경감시킬 것을 권장합니다.
