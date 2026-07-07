"""최종 컨펌 후 자동 후속 처리 (2026-05-02 정립)

이미지 선택기에서 [🎉 최종 컨펌] 누르면 즉시 자동 호출.

자동 처리:
1. 원고.md의 ▶PP{n} 마커 다음 줄에 이미지 마크다운 삽입/갱신
   - 이미 있으면 update, 없으면 insert
2. PPT 제목 동기화 (sync_pp_titles.py 모듈 호출)
3. HTML 미리보기 재생성 (md_preview.py 모듈 호출)

사용:
    python scripts/post_confirm.py <설교폴더>

종료 코드:
    0 = 모두 성공
    1 = 원고 파일 없음
    2 = selection.json 없거나 status != confirmed
"""

import sys
import re
import json
import subprocess
from pathlib import Path

# 원고 파일명 패턴 (우선순위 순)
MANUSCRIPT_CANDIDATES = ["원고.md", "원고-아동부.md", "원고-청소년부.md", "원고-아동.md"]

# ▶PP 마커: "▶PP1", "## ▶PP1" 둘 다 허용 (## 접두 옵셔널)
PP_MARKER_RE = re.compile(r"^(?:##\s*)?▶PP(\d+)\s*$")
# 직후 라인이 이미 이미지 마크다운인지 확인
EXISTING_IMG_RE = re.compile(r"^!\[[^\]]*\]\([^)]*(?:ppt_|text_PP)\d+\.png\)\s*$")
# sync_pp_titles가 삽입한 가시 마크다운 ("> **📌 PPT01** · ...")
SYNC_DESC_RE = re.compile(r"^>\s*\*\*📌 PPT\d+\*\*\s*·")


def find_manuscript(sermon_dir: Path) -> Path | None:
    for name in MANUSCRIPT_CANDIDATES:
        p = sermon_dir / name
        if p.exists():
            return p
    # 원고-*.md 패턴 fallback
    for p in sermon_dir.glob("원고*.md"):
        return p
    return None


def insert_images_into_manuscript(manuscript: Path, selected: dict, text_slots: set | None = None, images_dir_rel: str = "images") -> tuple[int, int]:
    """원고.md를 읽어 ▶PP{n} 마커 다음 줄에 이미지 마크다운 삽입/갱신.

    Args:
        selected: 컨펌된 이미지 슬롯 {num → 파일명} (image 슬롯)
        text_slots: 본문 슬롯 num 집합 (text_PP{n}.png 삽입)

    Returns: (inserted, updated) — 새로 넣은 개수, 기존 갱신한 개수
    """
    if text_slots is None:
        text_slots = set()
    text = manuscript.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    inserted = 0
    updated = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = PP_MARKER_RE.match(line)
        if m:
            num = m.group(1).zfill(2)
            # 이미지 슬롯이면 ppt_NN.png, 본문 슬롯이면 text_PPNN.png
            if num in selected:
                ppt_img_rel = f"{images_dir_rel}/ppt_{num}.png"
            elif num in text_slots:
                ppt_img_rel = f"{images_dir_rel}/text_PP{num}.png"
            else:
                i += 1
                continue
            if num in selected or num in text_slots:
                img_md = f"![PPT{num}]({ppt_img_rel})"
                # ▶PP 다음 — 빈 줄 + sync 마크다운(`> **📌 PPTnn**`) 모두 건너뛰고
                # 그 다음에 이미지가 있는지 체크 (있으면 갱신, 없으면 삽입)
                next_idx = i + 1
                while next_idx < len(lines) and (
                    lines[next_idx].strip() == "" or SYNC_DESC_RE.match(lines[next_idx])
                ):
                    out.append(lines[next_idx])
                    next_idx += 1
                if next_idx < len(lines) and EXISTING_IMG_RE.match(lines[next_idx]):
                    # 기존 이미지 라인 → 갱신 (위치 유지)
                    out.append(img_md)
                    updated += 1
                    i = next_idx + 1
                    continue
                else:
                    # 새로 삽입 — 직전 출력이 빈 줄 아니면 빈 줄 끼움
                    if not (out and out[-1].strip() == ""):
                        out.append("")
                    out.append(img_md)
                    inserted += 1
                    # 이미지 다음 본문이 바로 붙어있으면 빈 줄 추가
                    if next_idx < len(lines) and lines[next_idx].strip() != "":
                        out.append("")
                    i = next_idx
                    continue
        i += 1

    # 변경 있을 때만 저장
    if inserted or updated:
        manuscript.write_text("\n".join(out) + "\n", encoding="utf-8")
    return inserted, updated


def main(sermon_dir: Path) -> int:
    sermon_dir = sermon_dir.resolve()
    print(f"📂 설교 폴더: {sermon_dir.name}")

    # selection.json 확인 (대시보드는 _selection.json 또는 selection.json 모두 가능)
    sel_file = sermon_dir / "images" / "_selection.json"
    if not sel_file.exists():
        sel_file = sermon_dir / "images" / "selection.json"
    if not sel_file.exists():
        print(f"⛔ selection.json 없음: {sermon_dir / 'images'}")
        return 2
    sel = json.loads(sel_file.read_text(encoding="utf-8"))
    if sel.get("status") != "confirmed":
        print(f"⛔ status != confirmed (현재: {sel.get('status')})")
        return 2

    # 슬롯 키 정규화 (한자리 → 두자리)
    selected_raw = sel.get("selected") or {}
    selected = {str(k).zfill(2): v for k, v in selected_raw.items()}
    print(f"✓ 컨펌된 이미지 슬롯: {len(selected)}개 ({', '.join(sorted(selected.keys()))})")

    # 본문 슬롯 (slots.json의 has_image:false) — text_PPnn.png 자동 삽입
    text_slots: set[str] = set()
    slots_file = sermon_dir / "slots.json"
    if slots_file.exists():
        try:
            slots = json.loads(slots_file.read_text(encoding="utf-8"))
            for s in slots:
                if not s.get("has_image", True):
                    num = str(s.get("num", "")).zfill(2)
                    text_png = sermon_dir / "images" / f"text_PP{num}.png"
                    if text_png.exists():
                        text_slots.add(num)
        except Exception as e:
            print(f"  ⚠ slots.json 읽기 실패: {e}")
    if text_slots:
        print(f"✓ 본문 슬라이드: {len(text_slots)}개 ({', '.join(sorted(text_slots))})")

    # 원고 파일 찾기
    manuscript = find_manuscript(sermon_dir)
    if not manuscript:
        print(f"⛔ 원고 파일 없음 ({MANUSCRIPT_CANDIDATES} 패턴)")
        return 1
    print(f"✓ 원고 파일: {manuscript.name}")

    # 1. 이미지 + 본문 슬라이드 삽입
    inserted, updated = insert_images_into_manuscript(manuscript, selected, text_slots)
    print(f"  → 새 삽입: {inserted}개 / 갱신: {updated}개")

    # 2. PPT 제목 동기화
    sync_script = Path(__file__).parent / "sync_pp_titles.py"
    if sync_script.exists():
        print("✓ sync_pp_titles.py 실행")
        r = subprocess.run(
            [sys.executable, str(sync_script), str(sermon_dir), "--from", "slots", "--to", "manuscript"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            print(f"  ⚠ sync 경고: {r.stderr[-200:] if r.stderr else r.stdout[-200:]}")

    # 3. HTML 미리보기 재생성
    preview_script = Path(__file__).parent / "md_preview.py"
    if preview_script.exists():
        print("✓ md_preview.py 실행")
        r = subprocess.run(
            [sys.executable, str(preview_script), str(sermon_dir), manuscript.name, "preview.html"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            print(f"  ⚠ preview 경고: {r.stderr[-200:] if r.stderr else r.stdout[-200:]}")
        else:
            print(f"  → preview.html 갱신")

    print("✅ 후속 처리 완료")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용: python scripts/post_confirm.py <설교폴더>")
        sys.exit(1)
    sys.exit(main(Path(sys.argv[1])))
