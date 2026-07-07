"""OfficeMonitor — 사무실 출입자 모니터링 시스템"""

import sys
import os
import traceback
import logging
import yaml
import ctypes

# 프로젝트 루트를 path에 추가
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from paths import DATA_DIR, CRASH_LOG, setup_logging
from ui.main_window import MainWindow


def ensure_directories():
    """데이터 디렉토리 구조 확인/생성"""
    dirs = [
        os.path.join(DATA_DIR, "snapshots"),
        os.path.join(DATA_DIR, "recordings"),
        os.path.join(DATA_DIR, "known_faces"),
        os.path.join(DATA_DIR, "saved", "snapshots"),
        os.path.join(DATA_DIR, "saved", "recordings"),
        os.path.join(DATA_DIR, "data"),
        os.path.join(DATA_DIR, "data", "thumbnails"),
        os.path.join(DATA_DIR, "data", "pending_faces"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def load_config() -> dict:
    """config.yaml 로드"""
    config_path = os.path.join(PROJECT_DIR, "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def _global_exception_handler(exc_type, exc_value, exc_tb):
    """처리되지 않은 예외를 로그 파일에 기록 (크래시 방지)"""
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"{__import__('datetime').datetime.now()}\n")
            f.write(msg)
    except Exception:
        pass
    logging.getLogger(__name__).critical("치명적 오류:\n%s", msg)


def _set_native_icon(window, ico_path):
    """Win32 API로 네이티브 아이콘 설정 (작업표시줄 + ALT-TAB 확실 반영)"""
    try:
        hwnd = int(window.winId())
        WM_SETICON = 0x0080
        ICON_BIG = 1
        ICON_SMALL = 0
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010

        # 큰 아이콘 (48x48 — 작업표시줄, ALT-TAB)
        hicon_big = ctypes.windll.user32.LoadImageW(
            0, ico_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
        # 작은 아이콘 (16x16 — 타이틀바)
        hicon_small = ctypes.windll.user32.LoadImageW(
            0, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

        if hicon_big:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
        if hicon_small:
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
    except Exception:
        pass


def main():
    # 로깅 + 전역 예외 핸들러 설치
    setup_logging()
    sys.excepthook = _global_exception_handler

    # ── 중복 실행 방지 (Named Mutex) ──
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "OfficeMonitor_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        # 이미 실행 중인 인스턴스가 있으면 그 창을 앞으로 가져오고 종료
        import win32gui, win32con  # noqa: E401
        def _bring_existing():
            def callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if "Office Monitor" in title or "OfficeMonitor" in title:
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                        return False
                return True
            try:
                win32gui.EnumWindows(callback, None)
            except Exception:
                pass
        _bring_existing()
        sys.exit(0)

    # Windows 작업표시줄 아이콘 표시를 위한 AppUserModelID
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OfficeMonitor.App")

    ensure_directories()
    config = load_config()

    app = QApplication(sys.argv)
    app.setApplicationName("OfficeMonitor")

    # 앱 아이콘 (ICO 우선 — Windows 네이티브 지원)
    ico_path = os.path.join(PROJECT_DIR, "assets", "icon.ico")
    icon = QIcon(ico_path)
    for size in [16, 32, 48, 64, 128, 256]:
        png_path = os.path.join(PROJECT_DIR, "assets", f"icon-{size}.png")
        if os.path.exists(png_path):
            icon.addFile(png_path)

    app.setWindowIcon(icon)

    window = MainWindow(config)
    window.setWindowIcon(icon)
    window.show()

    # Win32 네이티브 아이콘 설정 (작업표시줄 + ALT-TAB 확실 반영)
    _set_native_icon(window, ico_path)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
