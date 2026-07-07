"""wait_and_submit_g.py — NLM 큐에 공간이 생기면 Set G를 투입

NLM은 노트북당 동시 슬라이드 덱 생성을 7개로 제한한다.
Set G (무릎 꿇은 예배자) 제출이 실패했으므로, 큐에 공간이 생길 때까지
주기적으로 폴링한 후 자동으로 제출한다.
"""

import sys
import os
import io
import json
import time
import subprocess
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

NB = "5bb2b0a4-61a8-43e0-a87f-b314ffdec303"
MAX_WAIT = 1800  # 30 minutes max
POLL_INTERVAL = 30  # 30 seconds

BASE = (
    "ABSOLUTELY NO TEXT anywhere. NO Korean letters. NO English letters. "
    "NO Greek letters. NO Hebrew letters. ZERO words on any slide. "
    "NO captions, NO titles, NO labels, NO subtitles. "
    "CINEMATIC PHOTOREALISM ONLY. Dark dramatic lighting with golden warm highlights. "
    "ADULT figures only, no children. Movie concept art quality. "
    "ALL HUMAN FIGURES MUST BE KOREAN PEOPLE with Korean facial features, "
    "Korean appearance, Korean skin tone. "
    "Even in biblical or worship contexts, depict figures as modern Korean believers, "
    "Korean worshippers, Korean Christians praying, listening, or kneeling. "
    "NO Western people. Each slide must be a SINGLE powerful photorealistic scene."
)

G_FOCUS = BASE + " " + (
    "Powerful cinematic scenes of Korean Christians in true worship and surrender. "
    "A Korean adult man or woman kneeling with bowed head before a great divine light, "
    "tears of repentance on their face. "
    "Korean worshippers with hands raised in surrender against a dramatic sunset sky. "
    "A Korean believer heart visually transforming from cracked stone to warm soft flesh "
    "under divine golden light. "
    "Close-up of a Korean face with eyes closed in deep worship, "
    "golden light illuminating their features. "
    "Dark dramatic background with golden firelight highlights, cinematic spiritual climax."
)


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_nlm(args, timeout=60):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONLEGACYWINDOWSSTDIO": "utf-8"}
    try:
        return subprocess.run(
            ["nlm"] + args,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=timeout,
        )
    except Exception as e:
        log(f"[ERROR] {e}")
        return None


def count_in_progress():
    r = run_nlm(["studio", "status", NB])
    if r is None or r.returncode != 0:
        return -1
    try:
        data = json.loads(r.stdout)
        return sum(1 for x in data if x.get("status") == "in_progress")
    except Exception:
        return -1


def submit_g():
    r = run_nlm([
        "slides", "create", NB,
        "--language", "ko",
        "--focus", G_FOCUS,
        "--confirm",
    ], timeout=120)
    if r is None:
        return None
    # Parse artifact ID from output
    import re
    match = re.search(r"Artifact ID:\s*([a-f0-9\-]+)", r.stdout)
    if match:
        return match.group(1)
    if "Error" in (r.stdout or "") or "Error" in (r.stderr or ""):
        log(f"  [ERROR] {r.stdout[:200]}")
        return None
    return None


def main():
    log(f"[INFO] Waiting for NLM queue slot, then submitting Set G")
    log(f"[INFO] Max wait: {MAX_WAIT}s, poll: {POLL_INTERVAL}s")

    elapsed = 0
    while elapsed < MAX_WAIT:
        count = count_in_progress()
        if count < 0:
            log(f"  [WARN] Could not query status")
        elif count < 7:
            log(f"  [OK] Queue has space! ({count}/7 in progress) Submitting G...")
            artifact_id = submit_g()
            if artifact_id:
                log(f"  [OK] Set G submitted! Artifact ID: {artifact_id}")
                # Save to _extra_sets.json or separate file
                from pathlib import Path
                sermon_dir = Path(__file__).parent.parent / "20260415-시편95편-오늘"
                g_file = sermon_dir / "images" / "_set_g.json"
                g_file.write_text(json.dumps({
                    "prefix": "G",
                    "name": "무릎 꿇은 예배자",
                    "style": "cinematic_photorealism",
                    "artifact_id": artifact_id,
                    "submitted_at": datetime.now().isoformat(),
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                log(f"  [OK] Saved to {g_file}")
                return 0
            else:
                log(f"  [FAIL] Submission failed, retrying in {POLL_INTERVAL}s")
        else:
            log(f"  [WAIT] Queue full ({count}/7), waiting...")

        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    log(f"[TIMEOUT] Exceeded {MAX_WAIT}s without submitting G")
    return 1


if __name__ == "__main__":
    sys.exit(main())
