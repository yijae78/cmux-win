"""슬롯 ↔ 원고 양방향 PP 제목 동기화

방향 옵션:
  --from slots --to manuscript: slots.json의 desc를 원고.md ▶PPN 직후에 주석으로 삽입
  --from manuscript --to slots: 원고의 [이미지N] / [본문N] 라인을 slots.json desc로 갱신

원고 변경은 비파괴적: ▶PPN 다음에 빈 주석 라인 `<!-- PP{n} desc: ... -->` 형태로 추가.
이 주석은 다음 동기화에서 자동 갱신됨.

사용:
    python scripts/sync_pp_titles.py <설교폴더> --from slots --to manuscript
    python scripts/sync_pp_titles.py <설교폴더> --from manuscript --to slots
"""

import sys
import re
import json
from pathlib import Path


PP_RE = re.compile(r"^▶PP(\d{1,2})\s*$")
DESC_COMMENT_RE = re.compile(r"^<!--\s*PP(\d+)\s+desc:\s*(.+?)\s*-->\s*$")
DESC_VISIBLE_RE = re.compile(r"^>\s*\*\*📌 PPT(\d+)\*\*\s*·\s*(.+?)\s*$")
IMAGE_LINE_RE = re.compile(r"^\[이미지(\d+)\]\s*(.+)$")


def find_sermon_file(sermon_dir: Path):
    for name in ["원고.md", "원고_v2.md", "원고_v3.md", "manuscript.md"]:
        p = sermon_dir / name
        if p.exists():
            return p
    return None


def slots_to_manuscript(sermon_dir: Path, dry_run: bool = False):
    """slots.json의 desc를 원고.md ▶PPN 다음 주석 라인으로 삽입/갱신."""
    slots_file = sermon_dir / "slots.json"
    manuscript = find_sermon_file(sermon_dir)
    if not slots_file.exists() or not manuscript:
        print("필요 파일 없음")
        return

    slots = json.loads(slots_file.read_text(encoding="utf-8"))
    desc_by_num = {s["num"]: s.get("desc", "") for s in slots}

    lines = manuscript.read_text(encoding="utf-8").splitlines(keepends=True)
    out = []
    changed = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        m = PP_RE.match(line.strip())
        out.append(line)
        if m:
            num = m.group(1).zfill(2)
            desired = desc_by_num.get(num, "").strip()
            # 다음 라인이 기존 desc(주석 또는 가시 마크다운)면 갱신
            if i + 1 < len(lines):
                nxt = lines[i + 1]
                stripped = nxt.strip()
                cm = DESC_COMMENT_RE.match(stripped)  # 구 HTML 주석 형식
                vm = DESC_VISIBLE_RE.match(stripped)  # 신규 가시 마크다운 형식
                if cm or vm:
                    cur_text = (cm or vm).group(2).strip()
                    if cur_text != desired:
                        out.append(f"> **📌 PPT{num}** · {desired}\n")
                        changed += 1
                    else:
                        # 기존 형식이 HTML 주석이면 가시 마크다운으로 업그레이드
                        if cm:
                            out.append(f"> **📌 PPT{num}** · {desired}\n")
                            changed += 1
                        else:
                            out.append(nxt)
                    i += 2
                    continue
            if desired:
                out.append(f"> **📌 PPT{num}** · {desired}\n")
                changed += 1
        i += 1

    if not dry_run:
        backup = manuscript.with_suffix(manuscript.suffix + ".bak")
        if not backup.exists():
            manuscript.replace(backup)
            backup.replace(manuscript)  # 그냥 백업만 두고 원본은 다시
        manuscript.write_text("".join(out), encoding="utf-8")
    print(f"[slots → 원고] {changed}개 desc 라인 갱신")


def manuscript_to_slots(sermon_dir: Path, dry_run: bool = False):
    """원고의 [이미지N] / [본문] 라인을 slots.json desc로 갱신."""
    slots_file = sermon_dir / "slots.json"
    manuscript = find_sermon_file(sermon_dir)
    if not slots_file.exists() or not manuscript:
        print("필요 파일 없음")
        return

    lines = manuscript.read_text(encoding="utf-8").splitlines()
    desc_from_md = {}
    cur_pp = None
    for line in lines:
        m = PP_RE.match(line.strip())
        if m:
            cur_pp = m.group(1).zfill(2)
            continue
        if cur_pp:
            ml = IMAGE_LINE_RE.match(line.strip())
            if ml:
                desc_from_md[cur_pp] = ml.group(2)
                cur_pp = None

    slots = json.loads(slots_file.read_text(encoding="utf-8"))
    changed = 0
    for s in slots:
        new_desc = desc_from_md.get(s["num"])
        if new_desc and s.get("desc") != new_desc:
            s["desc"] = new_desc
            changed += 1

    if not dry_run:
        backup = slots_file.with_suffix(".json.synced.bak")
        backup.write_text(slots_file.read_text(encoding="utf-8"), encoding="utf-8")
        slots_file.write_text(json.dumps(slots, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[원고 → slots] {changed}개 desc 갱신")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sermon_dir = Path(sys.argv[1]).resolve()

    direction = "slots-to-manuscript"  # 기본
    if "--from" in sys.argv:
        idx = sys.argv.index("--from")
        if sys.argv[idx + 1] == "manuscript":
            direction = "manuscript-to-slots"

    dry = "--dry-run" in sys.argv

    if direction == "slots-to-manuscript":
        slots_to_manuscript(sermon_dir, dry_run=dry)
    else:
        manuscript_to_slots(sermon_dir, dry_run=dry)


if __name__ == "__main__":
    main()
