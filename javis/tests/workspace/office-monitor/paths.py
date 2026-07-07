"""경로 설정 — config.yaml의 storage.data_dir을 단일 진실의 원천으로"""

import os
import logging
import yaml

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_data_dir():
    config_path = os.path.join(PROJECT_DIR, "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("storage", {}).get("data_dir", r"C:\OfficeMonitor")
    return r"C:\OfficeMonitor"


DATA_DIR = _load_data_dir()
DB_PATH = os.path.join(DATA_DIR, "data", "monitor.db")
THUMBNAILS_DIR = os.path.join(DATA_DIR, "data", "thumbnails")
PENDING_FACES_DIR = os.path.join(DATA_DIR, "data", "pending_faces")
SNAPSHOTS_DIR = os.path.join(DATA_DIR, "snapshots")
RECORDINGS_DIR = os.path.join(DATA_DIR, "recordings")
CRASH_LOG = os.path.join(DATA_DIR, "crash.log")
LOG_FILE = os.path.join(DATA_DIR, "app.log")


def setup_logging():
    """앱 전체 로깅 설정 (콘솔 + 파일 회전)"""
    from logging.handlers import RotatingFileHandler

    os.makedirs(DATA_DIR, exist_ok=True)

    root = logging.getLogger()
    if root.handlers:
        return  # 핫리로드 시 핸들러 중복 방지
    root.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "[%(asctime)s] %(name)s %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 파일 핸들러 (5MB × 3개 회전)
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # 콘솔 핸들러
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    root.addHandler(ch)
