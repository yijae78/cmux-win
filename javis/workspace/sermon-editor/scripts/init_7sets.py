"""init_7sets.py — NLM 슬라이드 7벌 초기 생성 스크립트

설교 폴더의 .nlm_notebook을 읽어, 7개의 다른 focus 프롬프트로 슬라이드 7벌 생성.
각 세트마다: NLM slides create → 완료 대기 → PPTX 다운로드 → 이미지 추출 → A/B/C/D/E/F/G 프리픽스로 저장

사용:
  python scripts/init_7sets.py --dir <설교폴더>

진행 상황은 stdout과 images/_init_progress.json 파일에 기록.
"""

import sys
import os
import io
import json
import time
from pathlib import Path
from datetime import datetime

# Windows cp949 인코딩 이슈 방지 — auto_regen import 전에 처리
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# auto_regen.py 모듈 import (같은 scripts 폴더)
sys.path.insert(0, str(Path(__file__).parent))
from auto_regen import (
    run_nlm,
    parse_artifact_id,
    wait_for_completion,
    extract_images_from_pptx,
    NLM_BASE_FOCUS,
)


# 자체 log 함수 (auto_regen의 log를 import하지 않고 직접 정의)
def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    try:
        print(f"[{ts}] {msg}", flush=True)
    except Exception:
        # stdout이 닫혔을 때 fallback: 파일에 직접 쓰기
        try:
            with open(_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
        except Exception:
            pass


# 전역 로그 파일 경로 (main에서 설정)
_LOG_FILE = None


# ──────────────────────────────────────────────
# 7벌 focus 프롬프트 (시편 95:1-11 "마음의 예배" 전용)
# ──────────────────────────────────────────────
SEVEN_SETS = [
    {
        "prefix": "A",
        "name": "립싱크 무대 (서두)",
        "focus": (
            "Cinematic close-up scenes of KOREAN singers on dramatic concert stages. "
            "One scene shows a Korean performer with empty hollow eyes lip-syncing under harsh spotlights. "
            "Another shows a passionate Korean live singer with tears, hand over chest. "
            "All performers must be Korean people with Korean facial features. "
            "Dramatic film noir lighting, theatrical atmosphere, photorealistic emotional contrast."
        ),
    },
    {
        "prefix": "B",
        "name": "큰 왕 창조주 (1-5절)",
        "focus": (
            "Vast epic scenes of God's creation showing his greatness. "
            "Deep ocean trenches reaching into darkness, towering mountain peaks touching the clouds, "
            "endless seas under dramatic stormy skies, divine golden light piercing through cosmic darkness. "
            "A tiny Korean worshipper figure standing small against the immensity of God's creative power, "
            "looking up in awe at the vast creation. "
            "Movie concept art quality, epic biblical scale."
        ),
    },
    {
        "prefix": "C",
        "name": "양과 목자 (6-7a절)",
        "focus": (
            "Intimate scenes of Korean worshippers depicted as sheep following their Shepherd. "
            "A group of Korean Christians (adults) kneeling together in a field at golden hour, "
            "Korean believers with peaceful faces looking up toward divine light. "
            "A Korean man or woman carrying a small lamb in their arms. "
            "Alternative: silhouette of Korean worshippers gathered around a divine light, like sheep around a shepherd. "
            "Warm golden hour lighting, cinematic pastoral spirituality."
        ),
    },
    {
        "prefix": "D",
        "name": "완악·미혹된 마음 (8-10절)",
        "focus": (
            "Dramatic cinematic scenes depicting hardened and wandering hearts. "
            "A Korean adult with a stone-like hardened face turning away from divine light. "
            "A Korean figure lost and wandering in a harsh wilderness landscape, confused and alone. "
            "A visual metaphor: a Korean worshipper's heart visualized as cracked stone versus soft flesh. "
            "Dust storm in the background, dramatic harsh sunlight. "
            "Biblical epic film quality with modern Korean figures."
        ),
    },
    {
        "prefix": "E",
        "name": "마음 문 두드리시는 예수 (계 3:20)",
        "focus": (
            "Cinematic scenes inspired by Holman Hunt's 'Light of the World'. "
            "A silhouette of Jesus Christ (traditional depiction) standing before an old wooden door, hand raised knocking gently. "
            "Inside the door: a Korean believer in modern attire sitting in darkness, slowly turning toward the knocking sound. "
            "Warm golden divine light spilling through cracks in the door. "
            "Close-up of a hand knocking on weathered wood. "
            "Alternative: a Korean worshipper opening a heart-shaped door to let divine light flood in. "
            "Emotional intimate atmosphere, cinematic dramatic lighting."
        ),
    },
    {
        "prefix": "F",
        "name": "안식의 자리 메누하 (11절)",
        "focus": (
            "Peaceful scenes of divine rest for Korean believers. "
            "A weary Korean man or woman finally finding rest by still waters at golden hour. "
            "A Korean family or group of Korean worshippers resting peacefully in green pastures under warm divine light. "
            "A Korean figure lying at peace in a sunlit field, face turned upward with a gentle smile. "
            "Atmosphere of profound peace and spiritual rest, cinematic warm art."
        ),
    },
    {
        "prefix": "G",
        "name": "무릎 꿇은 한국 예배자 (종합 클라이맥스)",
        "focus": (
            "Powerful cinematic scenes of Korean Christians in true worship and surrender. "
            "A Korean adult (man or woman) kneeling with bowed head before a great divine light, tears of repentance on their face. "
            "Korean worshippers with hands raised in surrender against a dramatic sunset sky. "
            "A Korean believer's heart visually transforming from cracked stone to warm soft flesh under divine golden light. "
            "Close-up of a Korean face with eyes closed in deep worship, golden light illuminating their features. "
            "Dark dramatic background with golden firelight highlights, cinematic spiritual climax."
        ),
    },
]


# ──────────────────────────────────────────────
# 진행 상황 기록
# ──────────────────────────────────────────────
def write_progress(images_dir, status, current=None, total=7, message=""):
    """images/_init_progress.json에 진행 상황 기록"""
    progress = {
        "status": status,  # "running", "completed", "failed"
        "current": current,
        "total": total,
        "message": message,
        "updated_at": datetime.now().isoformat(),
    }
    progress_file = images_dir / "_init_progress.json"
    progress_file.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    global _LOG_FILE

    # 인자 파싱
    sermon_dir = None
    for i, arg in enumerate(sys.argv):
        if arg == "--dir" and i + 1 < len(sys.argv):
            sermon_dir = Path(sys.argv[i + 1]).resolve()
            break
    if not sermon_dir or not sermon_dir.exists():
        log(f"[ERROR] --dir <설교폴더> 인자 필요")
        sys.exit(1)

    images_dir = sermon_dir / "images"
    images_dir.mkdir(exist_ok=True)
    _LOG_FILE = images_dir / "_init_log.txt"
    # 로그 파일 초기화
    _LOG_FILE.write_text(f"=== init_7sets started at {datetime.now().isoformat()} ===\n", encoding="utf-8")

    # 노트북 ID 읽기
    nb_file = sermon_dir / ".nlm_notebook"
    if not nb_file.exists():
        log(f"[ERROR] .nlm_notebook 파일이 없습니다: {nb_file}")
        sys.exit(1)
    notebook_id = nb_file.read_text(encoding="utf-8").strip()
    log(f"[INFO] Notebook ID: {notebook_id}")
    log(f"[INFO] Sermon dir: {sermon_dir}")
    log(f"[INFO] Generating {len(SEVEN_SETS)} sets sequentially...")

    write_progress(images_dir, "running", current=0, total=len(SEVEN_SETS), message="시작")

    # 7벌 순차 생성
    for idx, set_info in enumerate(SEVEN_SETS, start=1):
        prefix = set_info["prefix"]
        name = set_info["name"]
        focus = NLM_BASE_FOCUS + " " + set_info["focus"]
        pptx_path = images_dir / f"nlm_{prefix}.pptx"

        log(f"\n========================================")
        log(f"[{idx}/{len(SEVEN_SETS)}] Set {prefix}: {name}")
        log(f"========================================")
        write_progress(images_dir, "running", current=idx, total=len(SEVEN_SETS),
                       message=f"세트 {prefix} ({name}) 생성 중...")

        # 이미 PPTX가 있으면 생성/다운로드 스킵 (재시작 시 효율)
        if pptx_path.exists() and pptx_path.stat().st_size > 1000:
            log(f"  [SKIP] {pptx_path.name} 이미 존재 ({pptx_path.stat().st_size // 1024}KB). 추출만 진행")
        else:
            # 1) NLM slides create (비동기)
            log(f"  [1] NLM slides create...")
            r = run_nlm([
                "slides", "create", notebook_id,
                "--language", "ko",
                "--focus", focus,
                "--confirm",
            ], timeout=180)
            if r is None or r.returncode != 0:
                log(f"  [FAIL] Set {prefix} create failed")
                continue

            # 2) Artifact ID 추출
            artifact_id = parse_artifact_id(r.stdout)
            if not artifact_id:
                log(f"  [WARN] Artifact ID 추출 실패. 60초 대기 후 다운로드 시도")
                time.sleep(60)
            else:
                log(f"  Artifact ID: {artifact_id}")
                # 3) 완료까지 폴링 대기
                if not wait_for_completion(notebook_id, artifact_id, max_wait=900, poll_interval=15):
                    log(f"  [FAIL] Set {prefix} 완료 대기 실패")
                    continue

            # 4) PPTX 다운로드
            log(f"  [4] Downloading PPTX → {pptx_path.name}")
            dl_args = [
                "download", "slide-deck", notebook_id,
                "--format", "pptx",
                "--output", str(pptx_path),
                "--no-progress",
            ]
            if artifact_id:
                dl_args += ["--id", artifact_id]
            r = run_nlm(dl_args, timeout=120)
            if r is None or r.returncode != 0 or not pptx_path.exists():
                log(f"  [FAIL] Set {prefix} 다운로드 실패")
                continue

        # 5) 이미지 추출
        log(f"  [5] Extracting images from PPTX...")
        images = extract_images_from_pptx(pptx_path)
        log(f"  Extracted {len(images)} images")
        if not images:
            log(f"  [WARN] Set {prefix}: 추출된 이미지 없음")
            continue

        # 6) 저장 (raw 형태로 — Claude가 나중에 슬롯 매핑)
        # extract_images_from_pptx는 dict 리스트 반환: {"slide_idx", "blob", "content_type", "size"}
        for img_idx, img_dict in enumerate(images):
            blob = img_dict["blob"]
            ct = img_dict.get("content_type", "")
            ext = "png"
            if "jpeg" in ct or "jpg" in ct:
                ext = "jpg"
            out_path = images_dir / f"{prefix}_raw_{img_idx:02d}.{ext}"
            with open(out_path, "wb") as f:
                f.write(blob)
            log(f"    Saved: {out_path.name} ({len(blob)//1024}KB)")

        log(f"  [OK] Set {prefix} 완료 ({len(images)} images)")

    # 모든 세트 완료
    log(f"\n========================================")
    log(f"[DONE] All {len(SEVEN_SETS)} sets generated")
    log(f"========================================")
    write_progress(images_dir, "completed", current=len(SEVEN_SETS), total=len(SEVEN_SETS),
                   message="7벌 생성 완료. Claude 검수 대기 중.")

    # _review.json 생성 — Claude가 감지하여 슬롯 매핑 작업 시작
    review_file = images_dir / "_review.json"
    review_data = {
        "type": "init_review",
        "sets": [s["prefix"] for s in SEVEN_SETS],
        "created_at": datetime.now().isoformat(),
        "message": "7벌 초기 생성 완료. 각 raw 이미지를 시각 검수하여 PPT 슬롯에 매핑 필요.",
    }
    review_file.write_text(json.dumps(review_data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[INFO] _review.json 작성됨 — Claude 매핑 대기")


if __name__ == "__main__":
    main()
