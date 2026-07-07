"""recover_all.py — 이미지 생성 단계 전체 복구 및 상태 점검 스크립트

CLI 재시작 후 호출하면:
  1. _state.json을 읽어서 모든 세트의 목표 상태 확인
  2. NLM studio status 호출하여 각 아티팩트의 최신 NLM 상태 확인
  3. completed인데 아직 extracted 안된 세트를 자동 다운로드 + 추출
  4. in_progress인 세트는 완료까지 대기 (--wait 옵션) 또는 보고만 (--report)
  5. failed/missing G 세트는 hammer_g.sh 재실행 제안
  6. 현재 종합 상태를 콘솔에 보고

사용:
  python scripts/recover_all.py --dir <설교폴더> [--wait] [--report]
"""

import sys
import os
import io
import json
import time
import subprocess
import re
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# auto_regen에서 추출 함수 재사용
sys.path.insert(0, str(Path(__file__).parent))
from auto_regen import extract_images_from_pptx


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_nlm(args, timeout=180):
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


def get_nlm_status(notebook_id):
    """NLM studio에서 모든 아티팩트 상태 가져오기"""
    r = run_nlm(["studio", "status", notebook_id], timeout=60)
    if r is None or r.returncode != 0:
        return {}
    try:
        data = json.loads(r.stdout)
        return {x["id"]: x.get("status", "unknown") for x in data}
    except Exception:
        return {}


def download_artifact(notebook_id, artifact_id, output_path):
    """특정 아티팩트 PPTX 다운로드"""
    r = run_nlm([
        "download", "slide-deck", notebook_id,
        "--format", "pptx",
        "--output", str(output_path),
        "--no-progress",
        "--id", artifact_id,
    ], timeout=180)
    return r is not None and r.returncode == 0 and output_path.exists()


def extract_and_save(pptx_path, images_dir, prefix):
    """PPTX에서 이미지 추출 후 {prefix}_raw_NN.png로 저장"""
    images = extract_images_from_pptx(pptx_path)
    if not images:
        return 0
    count = 0
    for idx, img_dict in enumerate(images):
        blob = img_dict["blob"]
        ct = img_dict.get("content_type", "")
        ext = "jpg" if ("jpeg" in ct or "jpg" in ct) else "png"
        out_path = images_dir / f"{prefix}_raw_{idx:02d}.{ext}"
        with open(out_path, "wb") as f:
            f.write(blob)
        count += 1
    return count


def is_extracted(images_dir, prefix):
    """{prefix}_raw_*.png/jpg 파일이 이미 있는지 확인"""
    pngs = list(images_dir.glob(f"{prefix}_raw_*.png"))
    jpgs = list(images_dir.glob(f"{prefix}_raw_*.jpg"))
    return len(pngs) + len(jpgs) > 0


def load_state(sermon_dir):
    """_state.json 읽기"""
    state_file = sermon_dir / "images" / "_state.json"
    if not state_file.exists():
        log(f"[ERROR] _state.json 없음: {state_file}")
        return None
    return json.loads(state_file.read_text(encoding="utf-8"))


def save_state(sermon_dir, state):
    """_state.json 저장"""
    state["updated_at"] = datetime.now().isoformat()
    state_file = sermon_dir / "images" / "_state.json"
    state_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    # 인자 파싱
    sermon_dir = None
    wait_mode = False
    report_only = False
    for i, arg in enumerate(sys.argv):
        if arg == "--dir" and i + 1 < len(sys.argv):
            sermon_dir = Path(sys.argv[i + 1]).resolve()
        elif arg == "--wait":
            wait_mode = True
        elif arg == "--report":
            report_only = True

    if not sermon_dir or not sermon_dir.exists():
        log(f"[ERROR] --dir <설교폴더> 인자 필요")
        sys.exit(1)

    images_dir = sermon_dir / "images"
    state = load_state(sermon_dir)
    if not state:
        sys.exit(1)

    notebook_id = state["nlm"]["notebook_id"]
    log(f"=" * 60)
    log(f"복구 시작: {state['sermon']['title']}")
    log(f"Notebook: {notebook_id}")
    log(f"=" * 60)

    # NLM에서 최신 상태 가져오기
    log(f"\n[STEP 1] NLM studio 최신 상태 조회...")
    nlm_statuses = get_nlm_status(notebook_id)
    log(f"  NLM에 {len(nlm_statuses)}개 아티팩트 존재")

    # 각 세트 처리
    log(f"\n[STEP 2] 각 세트 상태 점검 및 복구...")
    summary = {
        "already_extracted": [],
        "downloaded_now": [],
        "still_in_progress": [],
        "failed_or_missing": [],
    }

    for prefix in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]:
        set_info = state["sets"].get(prefix)
        if not set_info:
            continue

        artifact_id = set_info.get("artifact_id")
        name = set_info.get("name", "")

        # 이미 추출되어 있는지
        if is_extracted(images_dir, prefix):
            log(f"  [{prefix}] ✅ 이미 추출됨 ({name})")
            summary["already_extracted"].append(prefix)
            set_info["extraction_status"] = "extracted"
            continue

        # artifact_id 없는 경우 (G 같은 submission_failed)
        if not artifact_id:
            log(f"  [{prefix}] ⚠️ artifact_id 없음 ({name}) — 재제출 필요")
            # G의 경우 _set_g.json 확인
            if prefix == "G":
                g_file = images_dir / "_set_g.json"
                if g_file.exists():
                    g_data = json.loads(g_file.read_text(encoding="utf-8"))
                    artifact_id = g_data.get("artifact_id")
                    if artifact_id:
                        log(f"    _set_g.json에서 artifact_id 복구: {artifact_id}")
                        set_info["artifact_id"] = artifact_id
            if not artifact_id:
                summary["failed_or_missing"].append(prefix)
                continue

        # NLM 상태 확인
        nlm_status = nlm_statuses.get(artifact_id, "unknown")
        set_info["nlm_status"] = nlm_status
        log(f"  [{prefix}] NLM 상태: {nlm_status} ({name})")

        if nlm_status == "completed":
            # 다운로드 + 추출
            pptx_path = images_dir / f"nlm_{prefix}.pptx"
            if not pptx_path.exists():
                log(f"    [DL] PPTX 다운로드 중...")
                if download_artifact(notebook_id, artifact_id, pptx_path):
                    log(f"    [OK] {pptx_path.name} 다운로드 완료 ({pptx_path.stat().st_size//1024}KB)")
                    set_info["download_status"] = "downloaded"
                    set_info["pptx_file"] = pptx_path.name
                else:
                    log(f"    [FAIL] 다운로드 실패")
                    summary["failed_or_missing"].append(prefix)
                    continue
            else:
                log(f"    [SKIP] {pptx_path.name} 이미 존재")

            # 추출
            log(f"    [EXT] 이미지 추출 중...")
            count = extract_and_save(pptx_path, images_dir, prefix)
            if count > 0:
                log(f"    [OK] {count}개 raw 이미지 추출 완료")
                set_info["extraction_status"] = "extracted"
                set_info["raw_image_count"] = count
                summary["downloaded_now"].append(prefix)
            else:
                log(f"    [FAIL] 추출 실패")
                summary["failed_or_missing"].append(prefix)

        elif nlm_status == "in_progress":
            summary["still_in_progress"].append(prefix)
            if wait_mode:
                log(f"    [WAIT] 완료 대기 모드 (최대 15분)...")
                # TODO: wait_for_completion 구현 시 여기에 추가

        else:
            log(f"    [UNKNOWN] NLM 상태 {nlm_status}")
            summary["failed_or_missing"].append(prefix)

    # 상태 저장
    save_state(sermon_dir, state)

    # 종합 보고
    log(f"\n" + "=" * 60)
    log(f"복구 완료 — 종합 상태")
    log(f"=" * 60)
    log(f"  ✅ 이미 추출됨: {len(summary['already_extracted'])} ({','.join(summary['already_extracted'])})")
    log(f"  🆕 방금 다운로드+추출: {len(summary['downloaded_now'])} ({','.join(summary['downloaded_now'])})")
    log(f"  🔄 NLM 진행 중: {len(summary['still_in_progress'])} ({','.join(summary['still_in_progress'])})")
    log(f"  ⚠️  실패/누락: {len(summary['failed_or_missing'])} ({','.join(summary['failed_or_missing'])})")

    total_extracted = len(summary['already_extracted']) + len(summary['downloaded_now'])
    total = len(state["sets"])
    log(f"\n  진행률: {total_extracted}/{total} ({int(total_extracted/total*100)}%)")

    # 다음 액션 제안
    log(f"\n다음 액션:")
    if summary["still_in_progress"]:
        log(f"  → 잠시 후 다시 이 스크립트 실행: python scripts/recover_all.py --dir <설교폴더>")
    if "G" in summary["failed_or_missing"]:
        log(f"  → Set G 재투입: bash scripts/hammer_g.sh & (백그라운드)")
    if total_extracted == total:
        log(f"  → 🎉 모든 세트 추출 완료! Claude 시각 검수 + 슬롯 매핑 단계로 진행 가능")

    return 0


if __name__ == "__main__":
    sys.exit(main())
