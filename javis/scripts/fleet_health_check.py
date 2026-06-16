#!/usr/bin/env python3
"""Javis Fleet Health Check — pane 상태 조회 후 fleet_status.json 저장."""

import json
import subprocess
import re
from datetime import datetime
from pathlib import Path

JAVIS_DIR = Path.home() / "bin" / "javis"
MAPPING_FILE = JAVIS_DIR / "fleet_mapping.env"
STATUS_FILE = JAVIS_DIR / "fleet_status.json"

# 상태 판별 키워드
ERROR_PATTERNS = re.compile(
    r"error|traceback|exception|fatal|panic|ENOENT|EACCES|denied|failed|killed",
    re.IGNORECASE,
)
IDLE_PATTERNS = re.compile(
    r"대기|waiting|idle|ready|가동 완료|completed|done|\$\s*$|>\s*$",
    re.IGNORECASE,
)


def run(cmd: str) -> str:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    return r.stdout.strip()


def list_panes() -> list[dict]:
    """tmux list-panes -a 로 전체 pane 목록 파싱."""
    raw = run("tmux list-panes -a -F '#{pane_id}\t#{pane_title}\t#{pane_pid}\t#{pane_current_command}'")
    panes = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            panes.append({
                "pane_id": parts[0],
                "title": parts[1],
                "pid": parts[2],
                "cmd": parts[3],
            })
    return panes


def load_mapping() -> dict[str, str]:
    """fleet_mapping.env → {ROLE: pane_id}."""
    mapping = {}
    if not MAPPING_FILE.exists():
        return mapping
    for line in MAPPING_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            mapping[key.strip()] = val.strip()
    return mapping


def capture_tail(pane_id: str, lines: int = 5) -> str:
    """pane 마지막 N줄 캡처."""
    return run(f"tmux capture-pane -t {pane_id} -p -S -{lines}")


def classify(tail: str) -> str:
    """마지막 5줄 텍스트로 live/idle/error 판별."""
    if not tail or not tail.strip():
        return "idle"
    if ERROR_PATTERNS.search(tail):
        return "error"
    if IDLE_PATTERNS.search(tail):
        return "idle"
    return "live"


def main():
    panes = list_panes()
    pane_lookup = {p["pane_id"]: p for p in panes}
    mapping = load_mapping()

    fleet = []
    for role, pane_id in mapping.items():
        info = pane_lookup.get(pane_id)
        if info is None:
            fleet.append({
                "role": role,
                "pane_id": pane_id,
                "status": "missing",
                "cmd": None,
                "tail": None,
            })
            continue

        tail = capture_tail(pane_id)
        status = classify(tail)
        fleet.append({
            "role": role,
            "pane_id": pane_id,
            "status": status,
            "cmd": info["cmd"],
            "tail": tail[-200:] if tail else "",
        })

    # 매핑에 없는 pane도 others로 수집
    mapped_ids = set(mapping.values())
    others = []
    for p in panes:
        if p["pane_id"] not in mapped_ids:
            tail = capture_tail(p["pane_id"])
            others.append({
                "pane_id": p["pane_id"],
                "status": classify(tail),
                "cmd": p["cmd"],
                "tail": tail[-200:] if tail else "",
            })

    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "fleet": fleet,
        "others": others,
        "summary": {
            "total_panes": len(panes),
            "mapped": len(fleet),
            "live": sum(1 for f in fleet if f["status"] == "live"),
            "idle": sum(1 for f in fleet if f["status"] == "idle"),
            "error": sum(1 for f in fleet if f["status"] == "error"),
            "missing": sum(1 for f in fleet if f["status"] == "missing"),
        },
    }

    STATUS_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
