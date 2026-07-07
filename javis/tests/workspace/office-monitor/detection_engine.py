"""얼굴 감지/인식 + 사람 추적 스레드
— InsightFace (다중 임베딩) + YOLO11n + ByteTrack"""

import time
import os
import logging
import cv2
import numpy as np
import multiprocessing as mp
import queue as queue_mod
from PyQt6.QtCore import QThread, pyqtSignal
from insightface.app import FaceAnalysis
import database
from paths import PENDING_FACES_DIR, THUMBNAILS_DIR

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 추론 서브프로세스 (GIL 완전 분리)
# ═══════════════════════════════════════════

class _FaceProxy:
    """서브프로세스 결과를 InsightFace face 객체처럼 사용"""
    def __init__(self, data: dict):
        self.bbox = np.array(data['bbox'], dtype=np.float32)
        self.det_score = data['det_score']
        self.embedding = data['embedding']
        self.kps = np.array(data['kps']) if data.get('kps') is not None else None


def _inference_loop(frame_q, result_q, stop_evt, model_name, det_size, score_thresh):
    """별도 프로세스: YOLO + InsightFace 추론 (메인 프로세스 GIL과 무관)"""
    import queue as _q
    from insightface.app import FaceAnalysis as FA

    app = FA(name=model_name, providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=det_size)

    yolo = None
    try:
        from ultralytics import YOLO
        yolo = YOLO("yolo11n.pt")
    except Exception:
        pass

    while not stop_evt.is_set():
        try:
            frame = frame_q.get(timeout=0.5)
        except _q.Empty:
            continue
        if frame is None:
            break

        tracks = []
        faces_data = []
        has_yolo = yolo is not None

        if has_yolo:
            try:
                tr = yolo.track(frame, classes=[0], persist=True,
                                tracker="bytetrack.yaml", verbose=False,
                                conf=0.4, iou=0.5)
                if tr and tr[0].boxes is not None and len(tr[0].boxes):
                    bxs = tr[0].boxes
                    for i in range(len(bxs)):
                        bbox = bxs.xyxy[i].cpu().numpy().astype(int).tolist()
                        conf = float(bxs.conf[i].cpu())
                        tid = int(bxs.id[i].cpu()) if bxs.id is not None else -1
                        tracks.append((tid, bbox, conf))
            except Exception:
                has_yolo = False

        if tracks or not has_yolo:
            try:
                for face in app.get(frame):
                    if face.det_score < score_thresh:
                        continue
                    faces_data.append({
                        'bbox': face.bbox.astype(int).tolist(),
                        'det_score': float(face.det_score),
                        'embedding': face.embedding.copy() if face.embedding is not None else None,
                        'kps': face.kps.copy() if hasattr(face, 'kps') and face.kps is not None else None,
                    })
            except Exception:
                pass

        # 최신 결과만 유지
        try:
            result_q.get_nowait()
        except _q.Empty:
            pass
        result_q.put({'tracks': tracks, 'faces': faces_data, 'has_yolo': has_yolo})


class DetectionThread(QThread):
    """얼굴 인식 + 사람 추적 통합 스레드

    파이프라인:
    1. YOLO11n → 사람 바운딩박스 (모든 각도)
    2. ByteTrack → track_id 부여/유지
    3. InsightFace → 얼굴 검출 시 임베딩 매칭 → track_id에 이름 바인딩
    4. 얼굴 미검출 → track_id의 기존 이름 유지 (뒷모습도 OK)
    """

    faces_detected = pyqtSignal(list)   # [{bbox, name, confidence, track_id, ...}]
    visit_logged = pyqtSignal(str, bool, str)  # name, is_registered, thumbnail_path
    face_captured = pyqtSignal(int)  # pending_face_id

    MAX_EMBEDDINGS_PER_VISITOR = 20
    MIN_FACE_SIZE = 60          # 최소 얼굴 크기 (px)
    MIN_BLUR_SCORE = 25.0       # 최소 선명도 (라플라시안 분산)
    MIN_CAPTURE_DET_SCORE = 0.40  # 수집 최소 감지 점수
    DUPLICATE_SIM_THRESHOLD = 0.55  # 같은 사람 판정 임계값
    CROP_PAD_RATIO = 0.7       # 얼굴 크기 대비 여백 비율
    MIN_SAVE_SIZE = 200         # 최종 저장 이미지 최소 크기 (px)
    CAPTURE_DURATION = 3.0      # 최고 프레임 수집 시간 (초)
    MIN_QUALITY_SCORE = 25.0    # 최소 품질 점수 (완전 불량만 차단)
    MIN_FRONTAL_DET_SCORE = 0.45  # 신원 매칭 최소 감지 점수 (측면/뒷모습 차단)

    def __init__(self, config: dict):
        super().__init__()
        self._running = False
        self._frame = None
        self._frame_lock = __import__("threading").Lock()

        det_cfg = config.get("detection", {})
        self._model_name = det_cfg.get("model", "buffalo_l")
        self._det_size = tuple(det_cfg.get("det_size", [640, 640]))
        self._interval = det_cfg.get("interval_ms", 200) / 1000.0
        self._score_threshold = det_cfg.get("score_threshold", 0.35)
        self._similarity_threshold = det_cfg.get("similarity_threshold", 0.4)
        self._cooldown = det_cfg.get("cooldown_seconds", 300)
        self._auto_augment = det_cfg.get("auto_augment_embeddings", True)

        self._app = None        # InsightFace (등록/검증 전용)
        self._known_faces = {}  # {visitor_id: {"name", "embeddings": [...]}}
        self._cooldown_map = {}
        self._new_face_cooldown = {}

        # pending_faces 임베딩 캐시 (중복 방지용)
        self._pending_embeddings = []  # [(pending_id, embedding)]

        # 최고 프레임 수집 후보 (3초간 프레임 비교 후 최고만 저장)
        # {candidate_key: {"start": float, "score": float,
        #                   "frame": ndarray, "bbox": list,
        #                   "embedding": ndarray, "det_score": float,
        #                   "count": int}}
        self._capture_candidates = {}

        # track_id → visitor 이름 매핑 (ByteTrack 추적용)
        self._track_names = {}       # {track_id: name}
        self._track_visitors = {}    # {track_id: visitor_id or None}
        self._track_registered = {}  # {track_id: bool}
        self._track_last_seen = {}   # {track_id: timestamp}
        self._track_embeddings = {}  # {track_id: embedding} — 최근 임베딩 저장

        # 최근 방문 로그 임베딩 (같은 사람 중복 로그 방지)
        self._recent_log_embeddings = []  # [(embedding, name, timestamp)]

        self._reset_requested = False  # 스레드 안전 리셋 플래그
        self._cleanup_requested = False

        # 추론 서브프로세스
        self._frame_q = mp.Queue(maxsize=2)
        self._result_q = mp.Queue(maxsize=2)
        self._stop_evt = mp.Event()
        self._inference_proc = None

        # 임베딩 행렬 캐시 (고속 매칭용)
        self._known_matrix = None    # (N, 512) ndarray
        self._known_norms = None     # (N,) ndarray
        self._known_meta = []        # [(visitor_id, name), ...]

    def set_frame(self, frame: np.ndarray):
        with self._frame_lock:
            self._frame = frame
        # 서브프로세스에 최신 프레임 전달 (오래된 것 버림)
        try:
            self._frame_q.get_nowait()
        except Exception:
            pass
        try:
            self._frame_q.put_nowait(frame.copy())
        except Exception:
            pass

    def run(self):
        self._running = True

        # 추론 서브프로세스 시작 (GIL 완전 분리)
        self._stop_evt.clear()
        self._inference_proc = mp.Process(
            target=_inference_loop,
            args=(self._frame_q, self._result_q, self._stop_evt,
                  self._model_name, self._det_size, self._score_threshold),
            daemon=True,
        )
        self._inference_proc.start()
        logger.info("추론 서브프로세스 시작 (PID: %s)", self._inference_proc.pid)

        # 로컬 InsightFace (등록/검증 전용 — 추론과 별개)
        try:
            self._app = FaceAnalysis(name=self._model_name, providers=["CPUExecutionProvider"])
            self._app.prepare(ctx_id=-1, det_size=self._det_size)
        except Exception as e:
            logger.error("InsightFace 로컬 초기화 실패: %s", e)
            self._app = None

        self._load_known_faces()
        self._load_pending_embeddings()

        while self._running:
            if self._reset_requested:
                self._do_reset()
            if self._cleanup_requested:
                self._cleanup_requested = False
                self._do_cleanup_bad_faces()

            # 서브프로세스 결과 수신
            try:
                result = self._result_q.get(timeout=0.2)
            except Exception:
                continue

            try:
                with self._frame_lock:
                    frame = self._frame
                if frame is not None:
                    now = time.time()
                    tracks = result['tracks']
                    all_faces = [_FaceProxy(fd) for fd in result['faces']]
                    if result.get('has_yolo', True):
                        self._detect_with_tracking(frame, now, tracks, all_faces)
                    else:
                        self._detect_face_only(frame, now, all_faces)
                    self._finalize_candidates(now)
            except Exception as e:
                logger.error("감지 처리 오류: %s", e)

    def _load_known_faces(self):
        self._known_faces = {}
        try:
            rows = database.get_all_embeddings()
            for row in rows:
                vid = row["visitor_id"]
                emb = np.frombuffer(row["embedding"], dtype=np.float32).copy()
                if vid not in self._known_faces:
                    self._known_faces[vid] = {"name": row["name"], "embeddings": []}
                self._known_faces[vid]["embeddings"].append(emb)
        except Exception as e:
            logger.warning("알려진 얼굴 로드 실패: %s", e)
        self._rebuild_matrix()

    def _rebuild_matrix(self):
        """임베딩 행렬 캐시 재구성 (고속 매칭용)"""
        all_embs = []
        meta = []
        for vid, info in self._known_faces.items():
            for emb in info["embeddings"]:
                all_embs.append(emb)
                meta.append((vid, info["name"]))
        if all_embs:
            self._known_matrix = np.vstack(all_embs).astype(np.float32)
            self._known_norms = np.linalg.norm(self._known_matrix, axis=1)
            self._known_meta = meta
        else:
            self._known_matrix = None
            self._known_norms = None
            self._known_meta = []

    def reset_tracking(self):
        """오늘 초기화 시 호출 — 플래그만 세우고, 감지 스레드가 안전하게 리셋"""
        self._reset_requested = True

    def _do_reset(self):
        """감지 스레드 내부에서 실행 — 스레드 안전한 리셋"""
        self._cooldown_map.clear()
        self._track_names.clear()
        self._track_visitors.clear()
        self._track_registered.clear()
        self._track_last_seen.clear()
        self._track_embeddings.clear()
        self._recent_log_embeddings.clear()
        self._new_face_cooldown.clear()
        self._capture_candidates.clear()
        # ByteTrack은 서브프로세스에 있으므로 track 매핑만 초기화
        self._reset_requested = False
        logger.info("추적 캐시 리셋 완료")

    def reload_known_faces(self):
        self._load_known_faces()
        self._load_pending_embeddings()

    def _is_frontal_enough(self, face) -> bool:
        """얼굴이 신원 매칭에 충분히 정면인지 확인 (측면/뒷모습 오인식 방지)

        기준:
        - det_score >= 0.45 (InsightFace 감지 신뢰도)
        - 양쪽 눈 사이 거리 >= 15px (극단 측면 차단)
        - 코 위치가 양 눈 중심에서 크게 벗어나지 않음 (측면 차단)
        """
        if face.det_score < self.MIN_FRONTAL_DET_SCORE:
            return False
        if not hasattr(face, 'kps') or face.kps is None or len(face.kps) < 3:
            return False
        left_eye, right_eye, nose = face.kps[0], face.kps[1], face.kps[2]
        eye_dist = abs(left_eye[0] - right_eye[0])
        if eye_dist < 15:
            return False
        nose_offset_x = abs(nose[0] - (left_eye[0] + right_eye[0]) / 2) / eye_dist
        return nose_offset_x < 0.45

    def _detect_with_tracking(self, frame: np.ndarray, now: float,
                              tracks: list, all_faces: list):
        """서브프로세스에서 받은 추론 결과를 처리 (매칭/로깅/캡처)"""
        active_track_ids = set()
        for tid, _, _ in tracks:
            active_track_ids.add(tid)

        if not tracks:
            self.faces_detected.emit([])
            return

        # 각 얼굴 → 가장 가까운 YOLO person bbox에 1:1 매칭
        track_face = {}  # track_id → face 객체
        for face in all_faces:
            if face.det_score < self._score_threshold:
                continue
            fb = face.bbox.astype(int)
            face_cx = (fb[0] + fb[2]) / 2
            face_cy = (fb[1] + fb[3]) / 2

            best_tid = None
            best_dist = float('inf')
            for track_id, pbbox, _ in tracks:
                if pbbox[0] <= face_cx <= pbbox[2] and pbbox[1] <= face_cy <= pbbox[3]:
                    pcx = (pbbox[0] + pbbox[2]) / 2
                    pcy = (pbbox[1] + pbbox[3]) / 2
                    dist = ((face_cx - pcx) ** 2 + (face_cy - pcy) ** 2) ** 0.5
                    if dist < best_dist:
                        best_dist = dist
                        best_tid = track_id

            if best_tid is not None:
                if best_tid in track_face:
                    if track_face[best_tid].det_score < face.det_score:
                        track_face[best_tid] = face
                else:
                    track_face[best_tid] = face

        # 4단계: 각 track 처리 — ID 매칭 + 결과 생성
        results = []
        for track_id, person_bbox, person_conf in tracks:
            face = track_face.get(track_id)

            name = self._track_names.get(track_id, "미등록")
            visitor_id = self._track_visitors.get(track_id)
            is_registered = self._track_registered.get(track_id, False)
            face_abs_bbox = None
            embedding = None
            best_sim = 0.0

            if face is not None:
                face_abs_bbox = face.bbox.astype(int).tolist()

                if face.embedding is not None:
                    embedding = face.embedding
                    matched_name, matched_vid, matched_sim, matched_reg = self._match_face(embedding)
                    best_sim = matched_sim
                    frontal = self._is_frontal_enough(face)

                    if matched_reg and frontal:
                        name = matched_name
                        visitor_id = matched_vid
                        is_registered = True
                        self._track_names[track_id] = name
                        self._track_visitors[track_id] = visitor_id
                        self._track_registered[track_id] = True
                        self._track_embeddings[track_id] = embedding.copy()

                        if self._auto_augment:
                            q = self._compute_quality_score(
                                frame, face_abs_bbox,
                                float(face.det_score), face)
                            self._try_augment_embedding(visitor_id, embedding, q)
                    else:
                        # 이미 등록자로 캐시된 track → 유지 (각도 변화 무시)
                        if is_registered:
                            pass
                        elif track_id not in self._track_names:
                            # 새 track — 정면 얼굴일 때만 기존 track에서 승계
                            inherited = False
                            if frontal:
                                for prev_tid, prev_emb in self._track_embeddings.items():
                                    if self._track_registered.get(prev_tid, False):
                                        if self._cosine_sim(embedding, prev_emb) >= self._similarity_threshold:
                                            name = self._track_names[prev_tid]
                                            visitor_id = self._track_visitors[prev_tid]
                                            is_registered = True
                                            self._track_names[track_id] = name
                                            self._track_visitors[track_id] = visitor_id
                                            self._track_registered[track_id] = True
                                            self._track_embeddings[track_id] = embedding.copy()
                                            inherited = True
                                            break
                            if not inherited:
                                self._track_names[track_id] = "미등록"
                                self._track_visitors[track_id] = None
                                self._track_registered[track_id] = False
                                self._track_embeddings[track_id] = embedding.copy()

                        # 미등록 얼굴 → 조용히 최고 프레임 수집
                        if not is_registered:
                            self._notify_new_face(
                                frame, face_abs_bbox, embedding, now,
                                det_score=float(face.det_score),
                                track_id=track_id, face=face)

            if face_abs_bbox is None:
                # 얼굴 미검출 — person bbox로 표시 (뒷모습 등)
                results.append({
                    "bbox": person_bbox,
                    "name": name,
                    "confidence": person_conf,
                    "similarity": float(best_sim),
                    "is_registered": is_registered,
                    "visitor_id": visitor_id,
                    "track_id": track_id,
                    "embedding": None,
                    "type": "person_body",
                })
                continue

            results.append({
                "bbox": face_abs_bbox,
                "name": name,
                "confidence": person_conf,
                "similarity": float(best_sim),
                "is_registered": is_registered,
                "visitor_id": visitor_id,
                "track_id": track_id,
                "embedding": embedding,
                "type": "person",
            })

            # 방문 로그 (등록자: visitor_id 기준, 미등록자: 임베딩 유사도 기반 쿨다운)
            cooldown_key = visitor_id if visitor_id else f"track_{track_id}"
            last_seen = self._cooldown_map.get(cooldown_key, 0)
            should_log = now - last_seen > self._cooldown

            # 미등록자: track_id가 바뀌어도 같은 얼굴이면 중복 로그 방지
            if should_log and not is_registered and embedding is not None:
                for prev_emb, prev_name, prev_time in self._recent_log_embeddings:
                    if now - prev_time < self._cooldown:
                        if self._cosine_sim(embedding, prev_emb) >= self._similarity_threshold:
                            should_log = False
                            break

            if should_log:
                self._cooldown_map[cooldown_key] = now
                thumb_path = self._save_thumbnail(frame, face_abs_bbox)
                database.add_visit_log(
                    visitor_id=visitor_id,
                    visitor_name=name,
                    confidence=person_conf,
                    thumbnail_path=thumb_path,
                    is_registered=is_registered,
                )
                self.visit_logged.emit(name, is_registered, thumb_path)
                # 최근 로그 임베딩 기록
                if embedding is not None:
                    self._recent_log_embeddings.append((embedding.copy(), name, now))
                    # 오래된 항목 정리
                    self._recent_log_embeddings = [
                        (e, n, t) for e, n, t in self._recent_log_embeddings
                        if now - t < self._cooldown
                    ]

        # 사라진 track_id 정리
        for tid in active_track_ids:
            self._track_last_seen[tid] = now
        stale_tids = [
            tid for tid in list(self._track_names.keys())
            if tid not in active_track_ids
            and now - self._track_last_seen.get(tid, 0) > 30
        ]
        for tid in stale_tids:
            self._track_names.pop(tid, None)
            self._track_visitors.pop(tid, None)
            self._track_registered.pop(tid, None)
            self._track_last_seen.pop(tid, None)
            self._track_embeddings.pop(tid, None)

        self.faces_detected.emit(results)

    def _detect_face_only(self, frame: np.ndarray, now: float,
                          faces: list = None):
        """YOLO 없이 InsightFace만 사용하는 폴백 모드"""
        if faces is None:
            try:
                faces = self._app.get(frame)
            except Exception as e:
                logger.debug("InsightFace 폴백 감지 오류: %s", e)
                return

        results = []
        for face in faces:

            bbox = face.bbox.astype(int).tolist()
            embedding = face.embedding
            name, visitor_id, best_sim, is_registered = self._match_face(embedding)

            if is_registered and self._auto_augment and embedding is not None:
                q = self._compute_quality_score(frame, bbox, float(face.det_score), face)
                self._try_augment_embedding(visitor_id, embedding, q)

            results.append({
                "bbox": bbox,
                "name": name,
                "confidence": float(face.det_score),
                "similarity": float(best_sim),
                "is_registered": is_registered,
                "visitor_id": visitor_id,
                "track_id": -1,
                "embedding": embedding,
                "type": "face",
            })

            cooldown_key = visitor_id if visitor_id else f"unknown_{bbox[0]}_{bbox[1]}"
            last_seen = self._cooldown_map.get(cooldown_key, 0)
            if now - last_seen > self._cooldown:
                self._cooldown_map[cooldown_key] = now
                thumb_path = self._save_thumbnail(frame, bbox)
                database.add_visit_log(
                    visitor_id=visitor_id, visitor_name=name,
                    confidence=float(face.det_score),
                    thumbnail_path=thumb_path, is_registered=is_registered,
                )
                self.visit_logged.emit(name, is_registered, thumb_path)

            if not is_registered and embedding is not None:
                self._notify_new_face(frame, bbox, embedding, now,
                                      det_score=float(face.det_score),
                                      track_id=-1, face=face)

        self.faces_detected.emit(results)

    def _match_face(self, embedding: np.ndarray):
        """임베딩 매칭 → (name, visitor_id, best_sim, is_registered)
        numpy 행렬 연산으로 전체 임베딩을 한번에 비교 (브루트포스 대비 3~5배 빠름)"""
        name = "방문자"
        visitor_id = None
        is_registered = False
        best_sim = 0.0

        if embedding is not None and self._known_matrix is not None:
            emb_norm = np.linalg.norm(embedding)
            if emb_norm > 0:
                sims = (self._known_matrix @ embedding) / (self._known_norms * emb_norm)
                best_idx = int(np.argmax(sims))
                best_sim = float(sims[best_idx])
                if best_sim >= self._similarity_threshold:
                    visitor_id, name = self._known_meta[best_idx]
                    is_registered = True

        return name, visitor_id, best_sim, is_registered

    def _try_augment_embedding(self, visitor_id: int, embedding: np.ndarray, quality: float = 0.0):
        info = self._known_faces.get(visitor_id)
        if not info:
            return

        # numpy float → Python float 변환 (SQLite BLOB 저장 방지)
        quality = float(quality)

        # 기존 임베딩과 너무 유사하면 스킵 (다양성 확보)
        max_sim = max(self._cosine_sim(embedding, e) for e in info["embeddings"])
        if max_sim > 0.85:
            return

        emb_bytes = embedding.astype(np.float32).tobytes()

        if len(info["embeddings"]) < self.MAX_EMBEDDINGS_PER_VISITOR:
            # 10개 미만이면 추가
            database.add_embedding(visitor_id, emb_bytes, quality)
            info["embeddings"].append(embedding.copy())
            self._rebuild_matrix()
        else:
            # 10개 꽉 찼으면: 새 것이 가장 낮은 품질보다 좋을 때만 교체
            lowest = database.get_lowest_quality_embedding(visitor_id)
            if lowest:
                lowest_q = lowest["quality"]
                # DB에 BLOB으로 저장된 quality 복구 (numpy.float32 → bytes 문제)
                if isinstance(lowest_q, bytes):
                    import struct
                    lowest_q = struct.unpack('f', lowest_q)[0] if len(lowest_q) == 4 else 0.0
                if quality > lowest_q:
                    database.delete_embedding(lowest["id"])
                    database.add_embedding(visitor_id, emb_bytes, quality)
                    # 해당 visitor만 캐시 갱신 (전체 재로드 방지)
                    rows = database.get_embeddings_for_visitor(visitor_id)
                    info["embeddings"] = [
                        np.frombuffer(r["embedding"], dtype=np.float32).copy()
                        for r in (rows or [])
                    ]
                    self._rebuild_matrix()

    def _load_pending_embeddings(self):
        """DB의 pending_faces 임베딩을 캐시로 로드 (중복 방지용)"""
        self._pending_embeddings = []
        try:
            rows = database.get_pending_faces("pending")
            for row in rows:
                emb = np.frombuffer(row["embedding"], dtype=np.float32).copy()
                self._pending_embeddings.append((row["id"], emb))
        except Exception as e:
            logger.warning("pending 임베딩 로드 실패: %s", e)

    # ═══════════════════════════════════════════
    # 최고 프레임 선별 시스템 (3초 수집 → 최고 1장 저장)
    # ═══════════════════════════════════════════

    def _compute_quality_score(self, frame: np.ndarray, bbox: list,
                               det_score: float, face=None) -> float:
        """얼굴 품질 종합 점수 (0~100)

        - 감지 점수 (30%) — InsightFace det_score
        - 얼굴 크기 (25%) — 클수록 좋음 (최대 200px에서 만점)
        - 선명도   (25%) — 라플라시안 분산
        - 정면도   (20%) — 좌우 눈 수평 대칭
        """
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
        face_w = x2 - x1
        face_h = y2 - y1

        # 1. 감지 점수 (0~30)
        score_det = min(det_score / 1.0, 1.0) * 30

        # 2. 얼굴 크기 (0~25) — 200px 이상이면 만점
        face_size = max(face_w, face_h)
        score_size = min(face_size / 200.0, 1.0) * 25

        # 3. 선명도 (0~25)
        face_region = frame[max(0,y1):min(h,y2), max(0,x1):min(w,x2)]
        score_blur = 0.0
        if face_region.size > 0:
            gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
            blur_val = cv2.Laplacian(gray, cv2.CV_64F).var()
            score_blur = min(blur_val / 200.0, 1.0) * 25

        # 4. 정면도 (0~20) — 좌우 기울기 + 상하 각도(코 위치)
        score_front = 5.0  # 기본 낮은 점수
        if face is not None and hasattr(face, 'kps') and face.kps is not None:
            kps = face.kps
            if len(kps) >= 3:
                left_eye, right_eye, nose = kps[0], kps[1], kps[2]
                eye_center_x = (left_eye[0] + right_eye[0]) / 2
                eye_center_y = (left_eye[1] + right_eye[1]) / 2
                eye_dist_x = abs(left_eye[0] - right_eye[0])

                if eye_dist_x > 0:
                    # 좌우 기울기 (0~10)
                    tilt_ratio = abs(left_eye[1] - right_eye[1]) / eye_dist_x
                    tilt_score = max(0, 1.0 - tilt_ratio * 5) * 10

                    # 상하 각도: 코가 눈 중심 바로 아래에 있어야 정면 (0~10)
                    nose_offset_x = abs(nose[0] - eye_center_x) / eye_dist_x
                    nose_below = (nose[1] - eye_center_y) / eye_dist_x
                    # 코가 눈 아래 0.3~0.8 범위에 있고, 좌우 편차 적으면 정면
                    if 0.2 < nose_below < 1.0 and nose_offset_x < 0.3:
                        vert_score = max(0, 1.0 - nose_offset_x * 3) * 10
                    else:
                        vert_score = 0.0

                    score_front = tilt_score + vert_score

        elif face is not None and hasattr(face, 'landmark_2d_106'):
            lm = face.landmark_2d_106
            if lm is not None and len(lm) >= 106:
                left_eye_y = np.mean(lm[33:42, 1])
                right_eye_y = np.mean(lm[87:96, 1])
                eye_diff = abs(left_eye_y - right_eye_y)
                eye_dist = abs(np.mean(lm[33:42, 0]) - np.mean(lm[87:96, 0]))
                if eye_dist > 0:
                    tilt_ratio = eye_diff / eye_dist
                    score_front = max(0, 1.0 - tilt_ratio * 5) * 20

        return score_det + score_size + score_blur + score_front

    def _is_duplicate_face(self, embedding: np.ndarray, now: float) -> bool:
        """이미 캡처된 얼굴인지 확인 (메모리 쿨다운 + DB pending_faces + 수집중 후보)"""
        # 1. 메모리 쿨다운
        for key, (last_time, prev_emb) in list(self._new_face_cooldown.items()):
            if now - last_time > self._cooldown:
                del self._new_face_cooldown[key]
                continue
            if self._cosine_sim(embedding, prev_emb) >= self.DUPLICATE_SIM_THRESHOLD:
                return True

        # 2. DB pending_faces 캐시
        for pid, prev_emb in self._pending_embeddings:
            if self._cosine_sim(embedding, prev_emb) >= self.DUPLICATE_SIM_THRESHOLD:
                return True

        return False

    def _find_candidate_key(self, embedding: np.ndarray, track_id: int) -> str:
        """현재 얼굴에 해당하는 수집 후보 키 찾기"""
        # track_id가 있으면 track 기반
        if track_id >= 0:
            return f"track_{track_id}"
        # track_id 없으면 임베딩 유사도로 기존 후보 매칭
        for key, cand in self._capture_candidates.items():
            if self._cosine_sim(embedding, cand["embedding"]) >= self.DUPLICATE_SIM_THRESHOLD:
                return key
        return f"emb_{id(embedding)}_{int(time.time()*1000)}"

    def _notify_new_face(self, frame: np.ndarray, bbox: list, embedding: np.ndarray,
                         now: float, det_score: float = 0.6,
                         track_id: int = -1, face=None):
        """미등록 얼굴 → 3초간 프레임 수집, 최고 품질만 저장"""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
        face_w = x2 - x1
        face_h = y2 - y1

        # 기본 필터 (최소 크기, 가장자리 잘림)
        if face_w < self.MIN_FACE_SIZE or face_h < self.MIN_FACE_SIZE:
            return
        margin = min(face_w, face_h) * 0.1
        if x1 < margin or y1 < margin or x2 > w - margin or y2 > h - margin:
            return

        # 이미 저장 완료된 얼굴인지 확인
        if self._is_duplicate_face(embedding, now):
            return

        # 품질 점수 계산
        score = self._compute_quality_score(frame, bbox, det_score, face)

        # 후보 키 찾기/생성
        cand_key = self._find_candidate_key(embedding, track_id)

        if cand_key in self._capture_candidates:
            # 기존 후보 — 더 좋은 프레임이면 교체
            cand = self._capture_candidates[cand_key]
            cand["count"] += 1
            if score > cand["score"]:
                cand["score"] = score
                cand["frame"] = frame.copy()
                cand["bbox"] = bbox
                cand["embedding"] = embedding.copy()
                cand["det_score"] = det_score
        else:
            # 새 후보 시작
            self._capture_candidates[cand_key] = {
                "start": now,
                "score": score,
                "frame": frame.copy(),
                "bbox": bbox,
                "embedding": embedding.copy(),
                "det_score": det_score,
                "count": 1,
            }

    def _finalize_candidates(self, now: float):
        """수집 시간이 지난 후보를 확정하여 저장 (최소 품질 미달 시 폐기)"""
        done_keys = []
        for key, cand in self._capture_candidates.items():
            if now - cand["start"] < self.CAPTURE_DURATION:
                continue
            done_keys.append(key)

            # 최소 품질 점수 미달 → 폐기
            if cand["score"] < self.MIN_QUALITY_SCORE:
                continue

            # 최종 저장
            self._save_best_capture(cand, now)

        for key in done_keys:
            del self._capture_candidates[key]

    def _make_quality_crop(self, frame: np.ndarray, bbox: list) -> np.ndarray:
        """얼굴 bbox → 머리~어깨 포함 고품질 크롭"""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
        face_w = x2 - x1
        face_h = y2 - y1

        pad_x = int(face_w * self.CROP_PAD_RATIO)
        pad_y_top = int(face_h * 0.8)
        pad_y_bot = int(face_h * 0.9)
        cx1 = max(0, x1 - pad_x)
        cy1 = max(0, y1 - pad_y_top)
        cx2 = min(w, x2 + pad_x)
        cy2 = min(h, y2 + pad_y_bot)
        crop = frame[cy1:cy2, cx1:cx2]

        if crop.size == 0:
            return None

        # 최소 크기 보장
        ch, cw = crop.shape[:2]
        if cw < self.MIN_SAVE_SIZE or ch < self.MIN_SAVE_SIZE:
            scale = max(self.MIN_SAVE_SIZE / cw, self.MIN_SAVE_SIZE / ch)
            crop = cv2.resize(crop, (int(cw * scale), int(ch * scale)),
                              interpolation=cv2.INTER_LANCZOS4)
        return crop

    def _save_best_capture(self, cand: dict, now: float):
        """후보의 최고 프레임을 파일로 저장"""
        frame = cand["frame"]
        bbox = cand["bbox"]
        embedding = cand["embedding"]

        face_crop = self._make_quality_crop(frame, bbox)
        if face_crop is None:
            return

        # 선명도 최종 체크 (크롭 이미지 기준, 완전 블러만 차단)
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        if cv2.Laplacian(gray, cv2.CV_64F).var() < self.MIN_BLUR_SCORE * 0.5:
            return

        pending_dir = PENDING_FACES_DIR
        os.makedirs(pending_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        img_path = os.path.join(pending_dir, f"face_{ts}_{bbox[0]}.jpg")
        cv2.imwrite(img_path, face_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

        # 저장된 이미지 재검증
        if not self._verify_saved_face(img_path):
            try:
                os.remove(img_path)
            except OSError:
                pass
            return

        emb_bytes = embedding.astype(np.float32).tobytes()
        pending_id = database.add_pending_face(img_path, emb_bytes)

        # 캐시 업데이트
        emb_copy = embedding.astype(np.float32).copy()
        self._pending_embeddings.append((pending_id, emb_copy))
        self._new_face_cooldown[f"saved_{int(now*1000)}"] = (now, emb_copy)

        self.face_captured.emit(pending_id)

    def _verify_saved_face(self, img_path: str) -> bool:
        """저장된 이미지에서 얼굴 재감지 — 완전 불량만 거부"""
        try:
            img = cv2.imread(img_path)
            if img is None:
                return False
            h, w = img.shape[:2]
            if h < 50 or w < 50:
                return False
            # InsightFace로 얼굴 재감지 — 크롭 이미지에서 얼굴이 아예 안 잡히면 불량
            faces = self._app.get(img)
            if not faces:
                return False
            best = max(faces, key=lambda f: f.det_score)
            if best.det_score < 0.3:
                return False
            return True
        except Exception:
            return False

    def cleanup_bad_pending_faces(self):
        """기존 pending_faces 중 불량 이미지 자동 삭제"""
        try:
            rows = database.get_pending_faces("pending")
        except Exception:
            return 0
        removed = 0
        for row in (rows or []):
            img_path = row["image_path"]
            # 파일 없음 → 삭제
            if not os.path.exists(img_path):
                database.hard_delete_pending_face(row["id"])
                self._pending_embeddings = [
                    (pid, e) for pid, e in self._pending_embeddings if pid != row["id"]
                ]
                removed += 1
                continue
            # 품질 재검사
            if not self._verify_saved_face(img_path):
                try:
                    os.remove(img_path)
                except OSError:
                    pass
                database.hard_delete_pending_face(row["id"])
                self._pending_embeddings = [
                    (pid, e) for pid, e in self._pending_embeddings if pid != row["id"]
                ]
                removed += 1
        return removed

    def request_cleanup(self):
        """메인 스레드에서 호출 — 감지 스레드 내부에서 안전하게 실행"""
        self._cleanup_requested = True

    def _do_cleanup_bad_faces(self):
        """감지 스레드 내부에서 실행 — 불량 캡처 정리"""
        removed = self.cleanup_bad_pending_faces()
        if removed > 0:
            logger.info("불량 캡처 %d개 자동 삭제됨", removed)

    def _save_thumbnail(self, frame: np.ndarray, bbox: list) -> str:
        h, w = frame.shape[:2]
        x1 = max(0, bbox[0] - 20)
        y1 = max(0, bbox[1] - 20)
        x2 = min(w, bbox[2] + 20)
        y2 = min(h, bbox[3] + 20)
        crop = frame[y1:y2, x1:x2]

        ts = time.strftime("%Y%m%d_%H%M%S")
        thumb_dir = THUMBNAILS_DIR
        os.makedirs(thumb_dir, exist_ok=True)
        path = os.path.join(thumb_dir, f"thumb_{ts}_{bbox[0]}.jpg")
        cv2.imwrite(path, crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return path

    @staticmethod
    def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return float(dot / norm) if norm > 0 else 0.0

    def register_face(self, name: str, embedding: np.ndarray) -> int:
        """방문자 등록 — 같은 이름이 이미 있으면 임베딩만 추가"""
        emb_copy = embedding.astype(np.float32).copy()
        emb_bytes = emb_copy.tobytes()

        # 같은 이름의 기존 방문자가 있는지 확인
        existing = database.find_visitor_by_name(name.strip())
        if existing:
            visitor_id = existing["id"]
            # 기존 방문자에 임베딩 추가 (최대 개수 체크)
            current_embs = database.get_embeddings_for_visitor(visitor_id)
            if current_embs and len(current_embs) >= self.MAX_EMBEDDINGS_PER_VISITOR:
                # 가장 오래된 임베딩 삭제
                oldest_id = current_embs[0]["id"]
                database.execute("DELETE FROM face_embeddings WHERE id=?", (oldest_id,))
            database.add_embedding(visitor_id, emb_bytes)
            # 메모리 캐시 업데이트
            if visitor_id in self._known_faces:
                self._known_faces[visitor_id]["embeddings"].append(emb_copy)
                # 최대 개수 유지
                if len(self._known_faces[visitor_id]["embeddings"]) > self.MAX_EMBEDDINGS_PER_VISITOR:
                    self._known_faces[visitor_id]["embeddings"].pop(0)
            else:
                self._known_faces[visitor_id] = {
                    "name": name,
                    "embeddings": [emb_copy],
                }
        else:
            # 새 방문자 생성
            visitor_id = database.add_visitor(name)
            database.add_embedding(visitor_id, emb_bytes)
            self._known_faces[visitor_id] = {
                "name": name,
                "embeddings": [emb_copy],
            }
        return visitor_id

    def stop(self):
        self._running = False
        # 서브프로세스 종료
        self._stop_evt.set()
        try:
            self._frame_q.put_nowait(None)  # poison pill
        except Exception:
            pass
        if self._inference_proc and self._inference_proc.is_alive():
            self._inference_proc.join(timeout=5)
            if self._inference_proc.is_alive():
                self._inference_proc.terminate()
        self.wait(3000)
