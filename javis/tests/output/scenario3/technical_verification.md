# Python 모니터링 프로젝트 보안 및 성능 기술 검증 보고서

**검증일**: 2026-06-17  
**대상 프로젝트**: office-monitor (detection_engine.py, recording_engine.py), env-scan (monitor.py)  
**검증 관점**: OWASP 보안, 리소스 누수, 경쟁 조건, 에러 처리, 성능 병목

---

## 1. Office-Monitor: detection_engine.py

### 1.1 OWASP 보안 취약점

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **높음** | SQL 인젝션 경로 | L947 `database.execute("DELETE FROM face_embeddings WHERE id=?", (oldest_id,))` | `database.execute()`가 직접 SQL 문자열을 받는 공개 인터페이스. detection_engine 내부에서는 파라미터 바인딩을 사용하나, `register_face()`(L933)에서 `name.strip()`만 수행하고 별도 검증 없이 DB에 삽입. 외부 입력(UI)에서 이름에 제어 문자나 초장 문자열을 넣을 경우 DB 무결성 문제 가능. |
| **중간** | 경로 순회 (Path Traversal) | L831 `img_path = os.path.join(pending_dir, f"face_{ts}_{bbox[0]}.jpg")` | `bbox[0]`은 정수이므로 직접적 경로 순회는 불가하나, `PENDING_FACES_DIR`이 config.yaml에서 읽히는 사용자 지정 경로(`paths.py` L15)이므로, config 파일 조작 시 임의 디렉토리에 파일 쓰기 가능. |
| **중간** | 모델 파일 로드 | L43 `yolo = YOLO("yolo11n.pt")` | 모델 파일에 대한 무결성 검증(해시 체크) 없이 로드. pickle 역직렬화 공격 벡터가 존재. 신뢰하지 않는 환경에서 모델 파일 교체 시 원격 코드 실행 가능. |
| **낮음** | 정보 노출 | L200 `logger.info("추론 서브프로세스 시작 (PID: %s)", ...)` | PID 로깅 자체는 운영에 필요하나, 로그 파일 접근 제어가 없으면 프로세스 정보 노출. |

### 1.2 리소스 누수

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **높음** | multiprocessing.Queue 미정리 | L165-166 `self._frame_q = mp.Queue(maxsize=2)` | `stop()` 메서드(L970)에서 Queue에 poison pill을 넣고 프로세스 join/terminate는 하지만, **Queue 자체를 close()/join_thread() 하지 않음**. Windows에서 Queue 내부의 feeder 스레드가 좀비로 남을 수 있음. `mp.Queue`는 반드시 `close()` + `join_thread()` 호출 필요. |
| **중간** | 서브프로세스 좀비 가능성 | L978-981 | `join(timeout=5)` 후 `terminate()` 호출하나, terminate 후 재차 `join()`을 호출하지 않아 좀비 프로세스 잔류 가능. Windows에서는 `terminate()` 후에도 `join()`이 필요. |
| **중간** | 프레임 복사 메모리 | L184 `frame.copy()`, L752-755 `frame.copy()`, `embedding.copy()` | 고해상도 프레임(1080p ~6MB)을 다수 복사. `_capture_candidates` 딕셔너리에 최대 수십 개의 프레임이 3초간 유지되며, 각각 frame+embedding 복사본 보유. 메모리 소비 추정: 후보 20개 기준 ~120MB. |
| **낮음** | `_recent_log_embeddings` 무한 성장 방지 불완전 | L475-478 | 쿨다운 시간(기본 300초) 내에만 정리하므로, 짧은 시간에 대량 감지 시 리스트가 급격히 성장. 최대 크기 제한(hard cap) 없음. |

### 1.3 경쟁 조건

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **높음** | QThread + multiprocessing 혼합 | L96, L192 | `DetectionThread`는 `QThread`인데 내부에서 `mp.Process`를 spawn. Qt 이벤트 루프와 multiprocessing이 동일 스레드에서 상호작용할 때, **시그널 emit(L495, L470, L850)이 서브프로세스 결과 처리 루프 안에서 발생**. Qt 시그널은 스레드 안전하지만, 메인 스레드의 슬롯이 `_known_faces` 등 공유 데이터에 접근하면 경쟁 조건 발생. |
| **중간** | `_frame_lock` 범위 불충분 | L176-186 | `set_frame()`에서 `_frame_lock` 안에서 `self._frame = frame`만 설정하고, 이어서 lock 밖에서 `_frame_q.put_nowait(frame.copy())` 호출. 메인 스레드에서 빠르게 `set_frame()`을 연속 호출하면, `_frame`과 Queue에 들어간 프레임이 불일치할 수 있음. |
| **중간** | 플래그 기반 리셋 | L161, L214-215 | `_reset_requested`와 `_cleanup_requested`는 단순 bool 플래그로, 메모리 배리어나 Lock 없이 스레드 간 공유. CPython의 GIL이 보호해주지만, 코드 의도가 명시적이지 않으며 다른 Python 구현체에서는 안전하지 않음. |
| **낮음** | `reload_known_faces()` 외부 호출 | L291-293 | 메인 스레드에서 호출 가능한 메서드인데, 내부에서 `_known_faces` 딕셔너리를 재구성. 감지 스레드가 동시에 `_known_faces`를 읽고 있으면 불완전한 상태를 참조할 수 있음. |

### 1.4 에러 처리

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **높음** | Bare except + 조용한 삼킴 | L44 `except Exception: pass` (YOLO 로드), L71-72 (YOLO 추적), L85-86 (InsightFace 감지) | 서브프로세스 `_inference_loop`에서 세 곳의 `except Exception: pass`. YOLO/InsightFace 실패 시 아무런 로깅 없이 무시하여 디버깅 불가. 특히 L85-86은 얼굴 감지 전체가 조용히 실패. |
| **높음** | 서브프로세스 예외 전파 없음 | L32-93 전체 | `_inference_loop`에서 발생하는 모든 예외가 서브프로세스 내에서만 처리되고, 메인 프로세스로 전파되지 않음. 서브프로세스가 OOM이나 세그폴트로 죽으면 메인 프로세스는 `result_q.get(timeout=0.2)`에서 무한 대기만 반복. |
| **중간** | 부분적 에러 처리 | L238-239 | 감지 처리 오류 시 `logger.error()`만 하고 계속 진행. 연속적으로 같은 오류 발생 시 로그 폭주 가능. Rate-limited 로깅 필요. |

### 1.5 성능 병목

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **중간** | `_rebuild_matrix()` 전체 재구성 | L255-270 | 임베딩 1개 추가/삭제 시에도 전체 numpy 행렬을 `np.vstack()`으로 재구성. 방문자 100명 x 20 임베딩 = 2000개 행렬 재생성. 증분 업데이트(incremental update) 미구현. |
| **중간** | `_is_duplicate_face()` O(N) 스캔 | L692-707 | `_new_face_cooldown` 딕셔너리와 `_pending_embeddings` 리스트를 매번 전체 순회하며 코사인 유사도 계산. 캡처가 누적될수록 성능 저하. |
| **중간** | `_verify_saved_face()` 동기 I/O | L852-870 | 감지 스레드 내에서 이미지 파일 읽기 + InsightFace 재추론 수행. 3초 수집 후 저장 시점에 감지 루프가 일시 정지. |
| **낮음** | frame.copy() 빈번 | L184, L752 | 고해상도 프레임의 반복적 deep copy. numpy 배열의 대규모 memcpy 비용. 참조 카운팅 기반 공유 또는 ring buffer 패턴이 더 효율적. |

---

## 2. Office-Monitor: recording_engine.py

### 2.1 OWASP 보안 취약점

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **중간** | 경로 순회 | L78-80 | `DATA_DIR`이 config.yaml에서 로드되므로, 설정 파일 조작 시 임의 경로에 녹화 파일 생성 가능. `rec_dir` 검증 없음. |
| **낮음** | 코덱 인젝션 | L25 `self._codec = rec_cfg.get("codec", "XVID")` | config.yaml에서 읽은 코덱 문자열을 검증 없이 `cv2.VideoWriter_fourcc()`에 전달. 비정상 문자열 시 OpenCV 내부 오류 유발 가능. 허용 코덱 화이트리스트 필요. |

### 2.2 리소스 누수

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **높음** | VideoWriter 실패 시 파일 핸들 | L89-91 | `isOpened()` 실패 시 `self._writer = None`으로 설정하지만, 이미 파일이 생성되었을 수 있음. 빈 파일이 남고, DB에 기록은 안 되지만 디스크 정리도 안 됨. |
| **중간** | DB ID 누수 | L93 | `_open_new_segment()`에서 `database.add_recording()` 후 writer가 실패해도 DB 레코드는 이미 삽입됨. `finish_recording()`이 호출되지 않아 미완료 레코드가 누적. |
| **중간** | 무한 디스크 사용 | 설계 전반 | 30분 세그먼트 자동 분할은 있으나, 오래된 녹화 파일 자동 삭제 메커니즘 없음. 24시간 연속 녹화 시 ~50GB/일 디스크 소비 (1280x720, XVID, 15fps 기준). |

### 2.3 경쟁 조건

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **높음** | `_recording`/`_paused` 플래그 비보호 | L50-53, L60-67, L69-72, L114 | `start_recording()`, `pause_recording()`, `stop_recording()`은 메인 스레드에서 호출되고, `run()` 루프는 QThread에서 실행. `_recording`, `_paused` 플래그가 Lock 없이 양쪽에서 읽기/쓰기됨. 특히 `pause_recording()`의 토글 로직(L60-67)에서 읽기-수정-쓰기 패턴이 Lock 없이 수행되어, 빠른 연속 클릭 시 상태 불일치 가능. |
| **중간** | `_close_segment()` + `_open_new_segment()` 비원자적 | L122-123 | `run()` 루프 안에서 세그먼트 분할 시 `_open_new_segment()` → `_close_segment()` → 새 writer 생성. 이 과정 중 `stop_recording()`이 호출되면 `_close_segment()`가 이중 호출될 수 있음. `_writer`가 이미 release된 상태에서 다시 release 시도. |

### 2.4 에러 처리

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **중간** | 광범위 예외 포착 | L131-132 | `run()` 루프 전체를 `try/except Exception`으로 감싸고 로깅만 수행. 한 프레임 기록 실패가 아니라 세그먼트 분할 오류(`_open_new_segment`)도 동일하게 처리. 세그먼트 분할 실패 시 `_writer`가 None인 채로 계속 루프 진행. |
| **낮음** | writer None 체크 불완전 | L118 | `frame is not None and self._writer and self._writer.isOpened()` 체크는 있으나, `_open_new_segment()` 실패 후 상태 복구 로직 없음. |

### 2.5 성능 병목

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **중간** | `time.sleep(interval)` 기반 프레임 타이밍 | L134 | `time.sleep(1/15)` = 66ms 간격으로 polling. 실제 프레임 쓰기 시간을 고려하지 않아 FPS가 설정보다 느릴 수 있음. `time.sleep(max(0, interval - write_time))` 패턴 필요. |
| **중간** | 프레임 참조 공유 (copy 미수행) | L116-118 | `set_frame()`에서 `self._frame = frame`으로 참조만 저장하고, `run()`에서 Lock 안에서 `frame = self._frame`으로 참조를 받지만, Lock 밖에서 `self._writer.write(frame)` 수행. write 중에 다른 스레드가 원본 프레임을 수정하면 이미지 티어링 발생. |
| **낮음** | XVID 코덱 CPU 부하 | 설계 | 소프트웨어 인코딩(XVID)은 CPU 집약적. 하드웨어 가속(NVENC, QSV) 옵션 미제공. |

---

## 3. Env-Scan: monitor.py

### 3.1 OWASP 보안 취약점

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **높음** | XSS (Cross-Site Scripting) | L476 `title = sig.get("title_ko") or sig.get("title", "")`, L486-492 HTML 직접 삽입 | JSON 파일에서 읽은 문자열을 **이스케이핑 없이** HTML에 직접 삽입. 공격자가 JSON 데이터에 `<script>alert(1)</script>` 같은 페이로드를 삽입하면 Streamlit의 `unsafe_allow_html=True`를 통해 실행됨. `fssf_type`, `_wf`, `title_ko` 등 모든 JSON 유래 필드에 동일 문제. |
| **높음** | JavaScript 인젝션 | L126-131 `ZOOM` 스크립트 | `components.html()`로 `<script>` 태그를 직접 삽입. 이 자체는 의도된 기능이나, `window.parent.document`에 접근하여 Streamlit 프레임 밖의 DOM을 조작. CSP(Content Security Policy) 위반 가능성. |
| **중간** | 파일 시스템 경로 조작 | L26-27, L380-381 | `PROJECT`, `ENV` 경로를 `__file__` 기반으로 구성하고, 날짜 문자열(`today`)로 파일명을 조합. `data_date`가 `master_id`에서 추출(L231)되므로, JSON 파일 내 `master_id` 값에 `../` 같은 경로 순회 문자가 포함되면 의도하지 않은 파일 접근 가능. |
| **중간** | 안전하지 않은 JSON 역직렬화 | L159 `json.loads(p.read_text(...))` | `json.loads`는 pickle보다 안전하지만, 대용량 또는 재귀 깊이가 깊은 JSON으로 DoS 가능. `json.loads`에 크기 제한 없음. |

### 3.2 리소스 누수

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **중간** | `time.sleep()` 블로킹 | L651, L737-740 | `time.sleep(5)` (live 모드) 또는 `time.sleep(30)` (idle/데이터 없음) 후 `st.rerun()`. Streamlit의 스크립트 모델에서 sleep은 서버 스레드를 점유. 다수 사용자 접속 시 스레드 풀 고갈. |
| **낮음** | 파일 핸들 누수 없음 | L159 | `Path.read_text()`는 with 문 없이도 내부적으로 파일을 열고 닫으므로 누수 없음. 양호. |
| **낮음** | Streamlit 세션 상태 미사용 | 설계 전반 | 매 rerun마다 `_load()` 전체를 재실행하여 모든 JSON 파일을 다시 읽음. `st.session_state` 캐싱이나 `@st.cache_data` 미사용. |

### 3.3 경쟁 조건

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **중간** | 파일 읽기 중 외부 쓰기 | L159, L216-243 | 스캐닝 엔진이 JSON 파일을 쓰는 도중 모니터가 읽으면 불완전한 JSON 파싱 시도. `_j()` 함수가 `except Exception: return None`으로 처리하므로 크래시는 방지되지만, 일시적으로 데이터가 사라지는 현상 발생. 원자적 파일 쓰기(write-to-temp + rename) 필요. |
| **낮음** | `st.rerun()` 타이밍 | L652, L737-740 | sleep 중 다른 요인으로 rerun이 트리거되면 sleep이 완료되지 않은 채 새 실행이 시작. Streamlit이 내부적으로 처리하므로 실질적 문제는 아님. |

### 3.4 에러 처리

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **중간** | 전역 예외 무시 | L159 `except Exception: return None` | `_j()` 함수에서 JSON 파싱 실패, 파일 권한 오류, 인코딩 오류 등 모든 예외를 동일하게 `None` 반환. 로깅 없어 데이터 손상 감지 불가. |
| **중간** | datetime 파싱 실패 무시 | L253-255, L258-260, L298-301 | `datetime.fromisoformat()` 실패 시 `except Exception: pass`. 시간 정보가 손실되어 ETA 계산이 부정확해질 수 있음. |
| **낮음** | `stat().st_mtime` 예외 미처리 | L277 | `master_path.exists()` 체크 후 `stat()`을 호출하나, TOCTOU(Time-Of-Check-Time-Of-Use) 문제로 exists와 stat 사이에 파일 삭제 가능. |

### 3.5 성능 병목

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **중간** | 매 rerun 전체 데이터 재로드 | L545 `s = _load()` | Live 모드에서 5초마다 전체 `_load()` 실행. JSON 파일 4~6개를 매번 디스크에서 읽고 파싱. `@st.cache_data(ttl=5)` 적용 시 중복 사용자 요청 시 효율화 가능. |
| **중간** | `components.html()` 다중 호출 | L543, L674 | `components.html()`은 각각 iframe을 생성. 페이지 내 iframe 2개로 DOM 복잡도 증가 및 렌더링 비용. 가능하면 단일 HTML 블록으로 통합. |
| **낮음** | `glob` + `sorted` + `stat` | L233-241 | 데이터 없을 때 fallback으로 `LOGS.glob("master-status-????-??-??.json")`을 호출하고 `stat().st_mtime`으로 정렬. 로그 파일이 많으면 I/O 비용. 일반적으로는 파일 수가 적어 문제없음. |

---

## 4. 공통 인프라: database.py 보안 검증

detection_engine.py와 recording_engine.py가 공유하는 database.py에 대한 추가 검증.

| 심각도 | 항목 | 위치 | 설명 |
|--------|------|------|------|
| **중간** | 연결 풀링 미사용 | L13-19 `get_connection()` | 매 쿼리마다 새 연결 생성 + 해제. WAL 모드 설정도 매번 재실행. 연결 풀이나 스레드 로컬 연결 패턴 필요. |
| **중간** | f-string SQL 구성 | L320, L328 | `get_old_records()`와 `delete_old_records()`에서 `f"SELECT * FROM {table}"` 사용. `_ALLOWED_TABLES` 화이트리스트(L313)로 보호되나, 화이트리스트 우회 시 SQL 인젝션 가능. |
| **낮음** | check_same_thread=False | L15 | 의도적이나, SQLite의 스레드 안전 모드가 serialized로 컴파일되었는지 확인 필요. |
| **정보** | 마이그레이션 방식 | L102-113 | try/except 기반 ALTER TABLE은 실용적이나, 마이그레이션 버전 관리(migration versioning) 없음. |

---

## 5. 종합 점수표

각 항목을 5점 만점으로 평가 (5=매우 우수, 4=우수, 3=보통, 2=미흡, 1=심각).

| 평가 항목 | detection_engine.py | recording_engine.py | monitor.py | 비고 |
|-----------|:---:|:---:|:---:|------|
| **OWASP 보안** | 3 | 4 | 2 | monitor.py의 XSS가 가장 심각 |
| **리소스 누수** | 2 | 3 | 4 | detection_engine의 Queue/Process 미정리 |
| **경쟁 조건** | 2 | 2 | 4 | 두 엔진 모두 Lock 없는 플래그 공유 문제 |
| **에러 처리** | 2 | 3 | 3 | 서브프로세스 조용한 예외 삼킴이 치명적 |
| **성능 효율** | 3 | 3 | 3 | 전반적으로 최적화 여지 있음 |
| **종합** | **2.4** | **3.0** | **3.2** | |

### 등급 기준
- 4.0 이상: 프로덕션 배포 가능
- 3.0~3.9: 주요 이슈 수정 후 배포 가능
- 2.0~2.9: 상당한 리팩토링 필요
- 2.0 미만: 재설계 권장

---

## 6. 우선 수정 권고사항

### 긴급 (P0) - 즉시 수정

1. **monitor.py XSS 방어**: JSON에서 읽은 모든 문자열에 `html.escape()` 적용
2. **detection_engine.py Queue/Process 정리**: `stop()`에서 `_frame_q.close()`, `_result_q.close()`, `join_thread()`, terminate 후 `join()` 추가
3. **detection_engine.py 서브프로세스 모니터링**: `_inference_proc.is_alive()` 주기적 확인 + 자동 재시작 메커니즘

### 높음 (P1) - 1주 내 수정

4. **recording_engine.py 상태 플래그 Lock 보호**: `_recording`, `_paused` 접근에 Lock 적용
5. **detection_engine.py 서브프로세스 에러 로깅**: `except Exception: pass` → `except Exception as e: logging.error(...)` 최소 변경
6. **monitor.py 경로 순회 방어**: `data_date` 문자열에서 `../`, `\` 등 경로 문자 필터링
7. **database.py 연결 풀링**: 스레드 로컬 연결 또는 연결 풀 도입

### 보통 (P2) - 스프린트 내 수정

8. **detection_engine.py `_rebuild_matrix()` 증분 업데이트**: 전체 재구성 대신 행 추가/삭제
9. **recording_engine.py 프레임 copy**: `write()` 전에 `frame.copy()` 수행하여 티어링 방지
10. **monitor.py `@st.cache_data` 적용**: `_load()` 결과 캐싱으로 중복 I/O 감소
11. **recording_engine.py 디스크 관리**: 오래된 녹화 파일 자동 정리 정책

---

## 7. 검증 결론

**office-monitor** 프로젝트는 멀티프로세스/멀티스레드 아키텍처의 복잡도에 비해 동기화 메커니즘이 불충분하다. 특히 detection_engine.py의 서브프로세스 관리와 에러 전파 체계가 가장 취약한 부분이다. 핵심 기능(얼굴 인식/추적)은 잘 동작하나, 장시간 무인 운영 시 리소스 누수로 인한 성능 저하가 예상된다.

**env-scan/monitor.py**는 읽기 전용 대시보드로 구조적 복잡도는 낮으나, `unsafe_allow_html=True`와 결합된 XSS 취약점이 가장 심각한 보안 이슈다. JSON 데이터 소스를 신뢰할 수 있는 내부 환경이라면 실질적 위험은 낮으나, 방어적 코딩 원칙상 반드시 이스케이핑을 적용해야 한다.

세 파일 모두 **에러 처리의 일관성 부족**이 공통 문제이며, `except Exception: pass` 패턴의 남용이 디버깅과 운영 가시성을 심각하게 저해한다.
