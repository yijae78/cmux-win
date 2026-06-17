# Office Monitor 코드 리뷰 보고서

> **대상**: `detection_engine.py` (983줄), `monitor_engine.py` (156줄), `recording_engine.py` (150줄)
> **리뷰 일시**: 2026-06-17
> **분석 관점**: 아키텍처, 보안, 성능, 에러 처리

---

## 1. 아키텍처 분석

### 1.1 전체 구조 — 강점

| 항목 | 평가 |
|------|------|
| **스레드 분리** | 카메라 캡처(`CameraThread`), 감지/인식(`DetectionThread`), 녹화(`RecordingThread`) 3개 QThread로 책임 분리. 각 스레드가 독립적으로 동작하며 프레임 락으로 데이터 교환 |
| **GIL 우회** | `DetectionThread`가 `multiprocessing.Process`로 추론 서브프로세스를 분리하여 GIL 병목 해소. CPU 바운드 추론(YOLO + InsightFace)을 완전 분리한 설계가 우수 |
| **다단계 파이프라인** | YOLO(사람 감지) → ByteTrack(추적) → InsightFace(얼굴 임베딩) → 코사인 유사도 매칭의 4단계 파이프라인이 명확 |
| **Graceful Fallback** | YOLO 실패 시 InsightFace-only 모드(`_detect_face_only`)로 자동 전환 |
| **최고 프레임 선별** | 3초간 프레임 수집 후 품질 점수(감지·크기·선명도·정면도) 최고 1장만 저장 — 불량 캡처 최소화 |

### 1.2 아키텍처 — 문제점

#### (A-1) God Class: `DetectionThread` — 983줄, 30+ 메서드

`DetectionThread`가 다음 역할을 모두 담당하는 God Class:
- 얼굴 감지/인식 (YOLO + InsightFace)
- 사람 추적 (ByteTrack track_id 관리)
- 임베딩 매칭 (코사인 유사도)
- 방문 로그 기록 (DB 쓰기 + 시그널)
- 미등록 얼굴 캡처 (품질 평가 + 파일 저장)
- 임베딩 자동 증강 (augmentation)
- 캐시 관리 (행렬 재구성, pending 캐시)
- 방문자 등록 (`register_face`)

**권장**: 최소한 다음 분리가 필요:
- `FaceMatcher` — 임베딩 매칭 + 행렬 캐시
- `FaceCaptureManager` — 후보 수집 + 품질 평가 + 파일 저장
- `VisitLogger` — 방문 로그 + 쿨다운 관리

#### (A-2) `_FaceProxy` ↔ 서브프로세스 직렬화 병목

서브프로세스에서 `dict`로 직렬화한 후 메인 스레드에서 `_FaceProxy`로 재구성한다. 임베딩(`numpy.ndarray` 512-float32 = 2KB)이 매 프레임마다 pickle/unpickle되므로 얼굴 수가 많아지면 IPC 오버헤드가 증가한다.

**권장**: `multiprocessing.shared_memory` 또는 `numpy` 공유 메모리 버퍼 사용 고려

#### (A-3) `CameraThread` — 프레임 발행 방식 불일치

`CameraThread`는 `frame_ready` 시그널을 선언하지만 `run()` 루프에서 실제로 `emit()`을 호출하지 않는다. 대신 `get_frame()` 폴링 메서드를 제공한다. 시그널-슬롯과 폴링이 혼재되어 있다.

```python
# 선언됨 (L16)
frame_ready = pyqtSignal(np.ndarray, float)

# run()에서 emit() 호출 없음 — 사용되지 않는 시그널
```

**권장**: 시그널을 사용하지 않으면 제거. 사용한다면 `run()`에서 `emit()` 추가

#### (A-4) `RecordingThread` — 프레임 복사 부재

`set_frame()`에서 프레임 참조만 저장하고 `frame.copy()`를 하지 않는다:

```python
# recording_engine.py L44
def set_frame(self, frame: np.ndarray):
    with self._frame_lock:
        self._frame = frame  # 참조만 저장 — 원본이 변경되면 녹화 프레임도 변경
```

호출자(카메라 스레드)가 동일 버퍼를 재사용하면 녹화된 프레임이 손상될 수 있다.

**권장**: `self._frame = frame.copy()`

#### (A-5) `database` 모듈 직접 호출 — 추상화 부재

`detection_engine.py`와 `recording_engine.py`가 `database` 모듈을 직접 호출한다. 특히 `detection_engine.py` L947에서 `database.execute("DELETE FROM ...")` raw SQL을 실행하는데, 이는 데이터 접근 계층 경계를 위반한다.

---

## 2. 보안 분석

### (S-1) 파일 경로에 타임스탬프만 사용 — 충돌/덮어쓰기 위험

```python
# detection_engine.py L830-831
ts = time.strftime("%Y%m%d_%H%M%S")
img_path = os.path.join(pending_dir, f"face_{ts}_{bbox[0]}.jpg")
```

동일 초에 동일 bbox[0] 좌표의 얼굴이 감지되면 파일이 덮어쓰기된다. `recording_engine.py`도 동일 패턴(L77-80).

**권장**: `uuid.uuid4().hex[:8]` 또는 `time.time_ns()` 추가로 고유성 보장

### (S-2) 얼굴 이미지/임베딩 데이터 — 개인정보 보호 부재

- 얼굴 이미지가 `PENDING_FACES_DIR`과 `THUMBNAILS_DIR`에 평문 JPEG로 저장
- 임베딩(생체 정보)이 `database`에 raw bytes로 저장
- 삭제 시 `os.remove()`만 호출 — 포렌식 복구 가능

생체 인식 데이터는 GDPR Article 9, 한국 개인정보보호법 제23조(민감정보)에 해당하며, 최소한의 암호화/접근 제어가 필요하다.

**권장**:
- 저장 시 AES 암호화 적용
- 보존 기간 정책 + 자동 삭제 스케줄러
- 접근 로그 기록

### (S-3) 임베딩 유사도 임계값 하드코딩

```python
DUPLICATE_SIM_THRESHOLD = 0.55   # 같은 사람 판정
_similarity_threshold = 0.4       # 등록자 매칭 (config에서 오버라이드 가능)
MIN_FRONTAL_DET_SCORE = 0.45     # 정면 판정
```

`0.4`의 유사도 임계값은 얼굴 인식에서 상당히 낮다. False Positive(오인식)로 인해 다른 사람이 등록자로 인식될 위험이 있다. 특히 사무실 출입 보안 목적이라면 `0.5~0.6` 이상이 권장된다.

### (S-4) 서브프로세스 YOLO 모델 경로 하드코딩

```python
# detection_engine.py L43
yolo = YOLO("yolo11n.pt")
```

상대 경로로 모델을 로드하므로 CWD에 따라 다른 파일이 로드될 수 있다. 악의적인 `.pt` 파일이 pickle 역직렬화를 통해 임의 코드를 실행할 수 있다(PyTorch pickle exploit).

**권장**: 절대 경로 + 체크섬 검증

---

## 3. 성능 분석

### (P-1) `_rebuild_matrix()` 빈번한 전체 재구성

임베딩 1개가 추가/삭제될 때마다 전체 행렬을 `np.vstack()`으로 재구성한다:

```python
# detection_engine.py L264
self._known_matrix = np.vstack(all_embs).astype(np.float32)
```

방문자 100명 × 임베딩 20개 = 2,000행 행렬을 매번 재구성하는 것은 비효율적.

**권장**: 증분 업데이트 — `np.concatenate`로 행 추가, 삭제 시에만 전체 재구성

### (P-2) `_is_duplicate_face()` — O(N) 선형 탐색 반복

```python
# detection_engine.py L695-706
for key, (last_time, prev_emb) in list(self._new_face_cooldown.items()):
    ...
for pid, prev_emb in self._pending_embeddings:
    ...
```

쿨다운 맵 + pending 임베딩을 매 프레임마다 순차 탐색한다. 미등록 얼굴이 많아지면 감지 루프 지연이 발생한다.

**권장**: pending 임베딩도 행렬화하여 벡터 연산으로 일괄 비교

### (P-3) `RecordingThread.run()` — `time.sleep(interval)` 기반 타이밍

```python
# recording_engine.py L134
time.sleep(interval)  # interval = 1.0 / fps
```

`sleep()` 기반 프레임 타이밍은 OS 스케줄러 정밀도(Windows: ~15ms)에 의존하여 15fps 목표에서 실제 11~13fps로 저하될 수 있다. 또한 프레임 처리 시간을 고려하지 않아 누적 지연이 발생한다.

**권장**: `time.monotonic()` 기반 절대 시간 타이밍

```python
next_time = time.monotonic()
while self._running:
    # ... write frame ...
    next_time += interval
    sleep_time = next_time - time.monotonic()
    if sleep_time > 0:
        time.sleep(sleep_time)
```

### (P-4) 카메라 안정화 — 30프레임 블로킹 읽기

```python
# monitor_engine.py L41-43
for _ in range(30):
    if not self._running:
        return
    self._cap.read()
```

카메라 안정화를 위해 30프레임을 동기적으로 읽고 버린다. 30fps 카메라에서 ~1초, 느린 카메라에서 수 초간 스레드가 블로킹된다. `_running` 체크는 있으나 UI 피드백이 없다.

### (P-5) `_detect_with_tracking()` — 매 프레임 O(T × F) 매칭

```python
# detection_engine.py L326-350
for face in all_faces:       # F faces
    for track_id, pbbox, _ in tracks:  # T tracks
        ...
```

얼굴-트랙 매칭이 O(T × F) 브루트포스. 보통 T, F < 10이므로 문제 없으나, 대규모 사무실에서는 Hungarian Algorithm 등이 더 적합하다.

### (P-6) `frame.copy()` 과다 호출

`set_frame()`(L184), `_notify_new_face()`(L752, L754), `_track_embeddings` 저장(L380, L404, L411) 등에서 프레임/임베딩 복사가 빈번하다. 특히 `frame.copy()`는 1280×720×3 = 2.7MB를 매번 복사한다.

---

## 4. 에러 처리 분석

### 4.1 에러 처리 — 강점

| 항목 | 평가 |
|------|------|
| **카메라 재연결** | `CameraThread`의 지수 백오프(1→2→4→8→16→30초) 재연결이 견고함 |
| **스레드 안전 리셋** | `reset_tracking()`이 플래그만 세우고 감지 스레드가 안전하게 처리 — 교차 스레드 직접 조작 방지 |
| **서브프로세스 종료** | poison pill(`None`) → `join(5)` → `terminate()` 3단계 종료 순서가 적절 |
| **최고 프레임 선별** | 불량 프레임 자동 폐기 + 저장 후 재검증(`_verify_saved_face`) 2중 필터 |
| **세그먼트 분할** | 녹화 파일이 설정된 분 단위로 자동 분할 — 단일 거대 파일 방지 |

### 4.2 에러 처리 — 문제점

#### (E-1) 광범위 `except Exception` + 무시 패턴

```python
# detection_engine.py L44-45
except Exception:
    pass  # YOLO 로드 실패

# detection_engine.py L85-86
except Exception:
    pass  # InsightFace 감지 실패

# detection_engine.py L71-72
except Exception:
    has_yolo = False  # YOLO 추적 실패
```

서브프로세스 `_inference_loop`에서 YOLO와 InsightFace 오류를 모두 삼킨다. 모델 로드 실패, 메모리 부족, CUDA 오류 등이 로그 없이 무시되어 디버깅이 불가능하다.

**권장**: 최소한 `logger.warning()` 추가

#### (E-2) `_inference_loop` — 프로세스 크래시 복구 없음

서브프로세스가 예외로 종료되면 메인 스레드의 `result_q.get(timeout=0.2)`이 영원히 빈 큐를 폴링하게 된다. 프로세스 생존 확인이나 재시작 로직이 없다.

```python
# detection_engine.py L221-223
try:
    result = self._result_q.get(timeout=0.2)
except Exception:
    continue  # 서브프로세스 죽어도 영원히 continue
```

**권장**: `self._inference_proc.is_alive()` 주기적 확인 + 재시작

#### (E-3) `RecordingThread` — VideoWriter 실패 시 무한 무효 녹화

```python
# recording_engine.py L89-92
if not self._writer.isOpened():
    logger.error("VideoWriter 초기화 실패: %s", self._current_path)
    self._writer = None
    return
```

`_open_new_segment()` 실패 시 `self._writer = None`으로 설정하고 `return`하지만, `run()` 루프는 계속 돌며 `self._writer`가 None인 상태에서 세그먼트 분할 타이머가 만료되면 다시 `_open_new_segment()`을 시도한다. 디스크 공간 부족 같은 영구적 실패에서 무한 재시도가 발생한다.

**권장**: 연속 N회 실패 시 녹화 자동 중단 + 사용자 알림

#### (E-4) `register_face()` — 스레드 안전성 위반

```python
# detection_engine.py L933-968
def register_face(self, name: str, embedding: np.ndarray) -> int:
    ...
    self._known_faces[visitor_id] = ...
    ...
```

이 메서드는 메인 스레드(UI)에서 호출되지만 `self._known_faces`를 직접 수정한다. 동시에 감지 스레드에서 `_match_face()`가 같은 딕셔너리를 읽고 있으므로 race condition이 발생한다. `_rebuild_matrix()` 호출도 빠져있어 등록 직후 새 임베딩이 매칭에 반영되지 않는다.

**권장**: 
- `reset_tracking()` 패턴처럼 플래그 기반으로 감지 스레드에서 처리
- 또는 `_known_faces` 접근에 Lock 추가

#### (E-5) `_try_augment_embedding` — struct 언팩 방어 코드

```python
# detection_engine.py L595-597
if isinstance(lowest_q, bytes):
    import struct
    lowest_q = struct.unpack('f', lowest_q)[0] if len(lowest_q) == 4 else 0.0
```

DB에 `numpy.float32`가 BLOB으로 저장되는 버그에 대한 workaround가 코드 중간에 존재. 이는 근본 원인(DB 저장 시 타입 변환)을 수정해야 하며, 임시 방편이 영구적으로 남아 있다.

#### (E-6) `CameraThread.run()` — 재연결 루프에서 `_running` 체크 타이밍

```python
# monitor_engine.py L57-68
while self._running:
    self.camera_status.emit(...)
    time.sleep(retry_delay)    # <-- sleep 중 stop() 호출 시 최대 30초 지연
    if not self._running:
        break
```

`stop()` 호출 시 최대 30초(`retry_delay` 최대값)간 스레드가 블로킹된다. `QThread.wait(3000)` 타임아웃(3초)과 충돌하여 앱 종료가 지연될 수 있다.

**권장**: `threading.Event` 기반 대기로 변경하여 즉시 깨우기 가능하게

```python
self._stop_event = threading.Event()
# sleep 대신:
self._stop_event.wait(timeout=retry_delay)
```

---

## 5. 종합 평가

| 영역 | 점수 | 요약 |
|------|------|------|
| **아키텍처** | 6/10 | 스레드 분리와 GIL 우회 설계 우수. `DetectionThread` God Class, 미사용 시그널, 프레임 복사 누락이 주요 문제 |
| **보안** | 4/10 | 생체 정보(얼굴 임베딩) 무암호화 저장, 낮은 유사도 임계값, 모델 경로 하드코딩 — 개인정보보호법 관점에서 심각 |
| **성능** | 6/10 | 행렬 연산 매칭, 서브프로세스 분리 양호. `_rebuild_matrix` 전체 재구성, sleep 기반 타이밍, 과다 frame.copy() 개선 필요 |
| **에러 처리** | 5/10 | 카메라 재연결, 스레드 안전 리셋 양호. 서브프로세스 크래시 복구 없음, 예외 삼킴 과다, register_face() race condition 심각 |

### 우선 수정 권장 사항

| 우선도 | 항목 | 파일 | 설명 |
|--------|------|------|------|
| **Critical** | `register_face()` race condition | detection_engine.py L933 | 메인 스레드에서 감지 스레드 딕셔너리 직접 수정 — 데이터 손상 가능 |
| **Critical** | 서브프로세스 크래시 복구 | detection_engine.py L221 | 추론 프로세스 죽으면 감지 기능 전체 중단 |
| **Critical** | 생체 데이터 암호화 | detection_engine.py 전반 | 얼굴 이미지·임베딩 평문 저장 — 개인정보보호법 위반 |
| **High** | RecordingThread 프레임 복사 | recording_engine.py L45 | `frame.copy()` 누락 — 프레임 손상 가능 |
| **High** | 카메라 재연결 sleep 블로킹 | monitor_engine.py L60 | 앱 종료 최대 30초 지연 |
| **High** | 예외 삼킴 패턴 | detection_engine.py L44,72,85 | 서브프로세스 모든 오류 무시 — 디버깅 불가 |
| **Medium** | `DetectionThread` God Class 분리 | detection_engine.py 전체 | 983줄, 7+개 책임 — 유지보수 곤란 |
| **Medium** | `_rebuild_matrix()` 증분 업데이트 | detection_engine.py L255 | 임베딩 1개 변경에 전체 행렬 재구성 |
| **Medium** | sleep 기반 녹화 타이밍 | recording_engine.py L134 | Windows에서 FPS 부정확 — monotonic 타이밍 권장 |
| **Low** | 미사용 `frame_ready` 시그널 | monitor_engine.py L16 | 선언만 있고 emit() 없음 |
| **Low** | 파일명 고유성 | detection_engine.py L831 | 동일 초 충돌 가능 — UUID 추가 권장 |
