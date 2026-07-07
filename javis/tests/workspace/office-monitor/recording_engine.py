"""녹화 엔진 — 별도 스레드에서 영상 저장"""

import cv2
import os
import time
import logging
import numpy as np
import threading
from PyQt6.QtCore import QThread, pyqtSignal
import database
from paths import DATA_DIR

logger = logging.getLogger(__name__)


class RecordingThread(QThread):
    """프레임을 받아 영상 파일로 저장하는 스레드"""

    status_changed = pyqtSignal(str)  # "recording" / "paused" / "stopped"
    time_updated = pyqtSignal(str)    # "HH:MM:SS"

    def __init__(self, config: dict):
        super().__init__()
        rec_cfg = config.get("recording", {})
        self._codec = rec_cfg.get("codec", "XVID")
        self._fps = rec_cfg.get("fps", 15)
        self._segment_minutes = rec_cfg.get("segment_minutes", 30)
        self._data_dir = DATA_DIR

        self._running = False
        self._recording = False
        self._paused = False
        self._frame = None
        self._frame_lock = threading.Lock()
        self._writer = None
        self._current_path = None
        self._db_id = None
        self._start_time = 0
        self._elapsed = 0
        self._segment_start = 0
        self._resolution = None

    def set_frame(self, frame: np.ndarray):
        with self._frame_lock:
            self._frame = frame
            if self._resolution is None:
                h, w = frame.shape[:2]
                self._resolution = (w, h)

    def start_recording(self):
        self._recording = True
        self._paused = False
        self._start_time = time.time()
        self._elapsed = 0
        self._segment_start = time.time()
        self._open_new_segment()
        self.status_changed.emit("recording")

    def pause_recording(self):
        if self._recording and not self._paused:
            self._paused = True
            self._elapsed += time.time() - self._start_time
            self.status_changed.emit("paused")
        elif self._recording and self._paused:
            self._paused = False
            self._start_time = time.time()
            self.status_changed.emit("recording")

    def stop_recording(self):
        self._recording = False
        self._paused = False
        self._close_segment()
        self.status_changed.emit("stopped")

    def _open_new_segment(self):
        self._close_segment()
        ts = time.strftime("%Y%m%d_%H%M%S")
        rec_dir = os.path.join(self._data_dir, "recordings")
        os.makedirs(rec_dir, exist_ok=True)
        self._current_path = os.path.join(rec_dir, f"rec_{ts}.avi")

        if self._resolution is None:
            self._resolution = (1280, 720)

        fourcc = cv2.VideoWriter_fourcc(*self._codec)
        self._writer = cv2.VideoWriter(
            self._current_path, fourcc, self._fps, self._resolution
        )
        if not self._writer.isOpened():
            logger.error("VideoWriter 초기화 실패: %s", self._current_path)
            self._writer = None
            return
        self._db_id = database.add_recording(self._current_path, ts)
        self._segment_start = time.time()

    def _close_segment(self):
        if self._writer and self._writer.isOpened():
            self._writer.release()
            if self._current_path and os.path.exists(self._current_path):
                try:
                    size = os.path.getsize(self._current_path)
                    if self._db_id:
                        database.finish_recording(self._db_id, size)
                except OSError as e:
                    logger.warning("녹화 파일 크기 확인 실패: %s", e)
        self._writer = None

    def run(self):
        self._running = True
        interval = 1.0 / self._fps

        while self._running:
            try:
                if self._recording and not self._paused:
                    with self._frame_lock:
                        frame = self._frame

                    if frame is not None and self._writer and self._writer.isOpened():
                        self._writer.write(frame)

                    # 세그먼트 분할
                    if time.time() - self._segment_start > self._segment_minutes * 60:
                        self._open_new_segment()

                    # 경과 시간
                    elapsed = self._elapsed + (time.time() - self._start_time)
                    h = int(elapsed // 3600)
                    m = int((elapsed % 3600) // 60)
                    s = int(elapsed % 60)
                    self.time_updated.emit(f"{h:02d}:{m:02d}:{s:02d}")
            except Exception as e:
                logger.error("녹화 루프 오류: %s", e)

            time.sleep(interval)

        self._close_segment()

    def stop(self):
        self.stop_recording()
        self._running = False
        self.wait(3000)

    @property
    def is_recording(self):
        return self._recording

    @property
    def is_paused(self):
        return self._paused
