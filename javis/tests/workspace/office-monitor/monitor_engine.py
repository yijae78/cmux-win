"""카메라 캡처 스레드"""

import cv2
import time
import logging
import threading
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class CameraThread(QThread):
    """카메라 프레임 캡처 전담 스레드"""

    frame_ready = pyqtSignal(np.ndarray, float)  # frame, timestamp
    camera_status = pyqtSignal(str, bool)  # message, is_ok
    camera_info = pyqtSignal(dict)  # 카메라 정보 (해상도, FPS 등)

    def __init__(self, camera_id=0, resolution=(1280, 720), fallback_ids=None):
        super().__init__()
        self._camera_id = camera_id
        self._resolution = resolution
        self._fallback_ids = fallback_ids or []
        self._running = False
        self._cap = None
        self._actual_fps = 0.0
        self._latest_frame = None
        self._latest_ts = 0.0
        self._frame_lock = threading.Lock()

    def run(self):
        self._running = True
        self._cap = self._try_open_camera()

        if self._cap is None:
            self.camera_status.emit("카메라를 찾을 수 없습니다", False)
            return

        # 카메라 안정화 (30프레임 건너뛰기)
        for _ in range(30):
            if not self._running:
                return
            self._cap.read()

        frame_count = 0
        fps_timer = time.time()

        while self._running:
            try:
                ret, frame = self._cap.read()
                if not ret:
                    self.camera_status.emit("카메라 프레임 읽기 실패", False)
                    self._cap.release()
                    # 지수 백오프 재연결 (1→2→4→8→16→30초)
                    retry_delay = 1
                    while self._running:
                        self.camera_status.emit(
                            f"카메라 재연결 시도 ({retry_delay}초 후...)", False)
                        time.sleep(retry_delay)
                        if not self._running:
                            break
                        self._cap = self._try_open_camera()
                        if self._cap is not None:
                            break
                        retry_delay = min(retry_delay * 2, 30)
                    if self._cap is None:
                        break
                    continue

                timestamp = time.time()
                with self._frame_lock:
                    self._latest_frame = frame
                    self._latest_ts = timestamp

                # FPS 계산
                frame_count += 1
                elapsed = timestamp - fps_timer
                if elapsed >= 1.0:
                    self._actual_fps = frame_count / elapsed
                    frame_count = 0
                    fps_timer = timestamp
            except Exception as e:
                logger.error("프레임 처리 오류: %s", e)
                time.sleep(0.5)

            # CPU 부하 제한 (~30fps)
            time.sleep(0.01)

        if self._cap:
            self._cap.release()

    def _is_real_camera(self, cap):
        """가상 카메라(화면 캡처 등) 필터링 — 비표준 비율 거부"""
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 표준 웹캠 비율이 아니면 가상 카메라 의심
        if h > 0:
            ratio = w / h
            standard_ratios = [1/1, 4/3, 3/2, 16/9, 16/10]
            if not any(abs(ratio - r) < 0.15 for r in standard_ratios):
                return False

        return True

    def _try_open_camera(self):
        """카메라 열기 시도 (메인 ID + 폴백, 가상 카메라 제외)"""
        ids_to_try = [self._camera_id] + self._fallback_ids

        for cam_id in ids_to_try:
            cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution[1])

                ret, frame = cap.read()
                if ret:
                    if not self._is_real_camera(cap):
                        self.camera_status.emit(
                            f"Camera {cam_id} 건너뜀 (가상 카메라)", False
                        )
                        cap.release()
                        continue

                    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    info = {
                        "id": cam_id,
                        "width": actual_w,
                        "height": actual_h,
                        "name": f"Camera {cam_id}",
                    }
                    self.camera_info.emit(info)
                    self.camera_status.emit(
                        f"Camera {cam_id} 연결됨 ({actual_w}x{actual_h})", True
                    )
                    return cap

            cap.release()

        return None

    def get_frame(self):
        """최신 프레임 반환 (메인 스레드 폴링용)"""
        with self._frame_lock:
            return self._latest_frame, self._latest_ts

    def stop(self):
        self._running = False
        self.wait(3000)

    @property
    def actual_fps(self):
        return self._actual_fps
