"""환경스캐닝 브리핑 대시보드 — 원클릭 실행기.

Usage:
    python launch_monitor.py
"""
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

MONITOR = Path(__file__).resolve().parent / "monitor.py"
PORT = 8504


def main() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(MONITOR),
         "--server.port", str(PORT),
         "--server.headless", "true",
         "--theme.base", "dark"],
        cwd=str(MONITOR.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    webbrowser.open(f"http://localhost:{PORT}")
    print(f"대시보드 실행 중: http://localhost:{PORT}")
    print("종료하려면 Ctrl+C")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()
