"""원고.md → slots.json 자동 추출

원고에서 ▶PPN 마커를 찾아 다음 정보를 자동 추출하고 slots.json 골격을 생성한다:

  · num: 두 자리 슬롯 번호
  · has_image: ▶PPN 다음 줄에 [이미지N]이 있으면 True
  · desc_raw: ▶PPN 다음 줄 (가공 없는 원본)
  · context_raw: ▶PPN 마커 앞 5줄 + 뒤 N줄(다음 ▶PP 또는 다음 H1/H2까지) 발췌
  · text_raw: 본문 슬롯의 경우 같은 위치의 본문 인용 (룻 X:Y 같은 구절)

이 골격에 신교수님 톤(서두/본론1/본론2/클라이맥스/결론 라벨 + 신학 키워드 압축)을
Claude가 합성해 desc/context/text 최종 필드로 정제한다.

사용:
    python scripts/extract_pp_context.py <설교폴더>
    python scripts/extract_pp_context.py <설교폴더> --output slots_raw.json
"""

import sys
import re
import json
from pathlib import Path


PP_RE = re.compile(r"^▶PP(\d{1,2})\s*$")
IMAGE_LINE_RE = re.compile(r"^\[이미지(\d+)\]\s*(.+)$")
SCRIPTURE_RE = re.compile(r"^\[(?:본문슬라이드|본문)(\d*)\]\s*(.+)$")


def find_sermon_file(sermon_dir: Path):
    """원고 파일 후보를 찾는다."""
    candidates = [
        sermon_dir / "원고.md",
        sermon_dir / "원고-아동부.md",
        sermon_dir / "원고-청소년부.md",
        sermon_dir / "원고_v2.md",
        sermon_dir / "원고_v3.md",
        sermon_dir / "manuscript.md",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def extract_slots(manuscript_path: Path):
    """▶PPN 마커를 찾아 슬롯 골격 생성."""
    lines = manuscript_path.read_text(encoding="utf-8").splitlines()
    slots = []
    pp_positions = []  # (line_idx, num)

    for i, line in enumerate(lines):
        m = PP_RE.match(line.strip())
        if m:
            num = m.group(1).zfill(2)
            pp_positions.append((i, num))

    for idx, (line_idx, num) in enumerate(pp_positions):
        # 다음 줄(들)에서 [이미지N] 또는 [본문...] 또는 일반 텍스트 추출
        desc_raw = ""
        has_image = False
        text_content = None

        for offset in range(1, 6):
            j = line_idx + offset
            if j >= len(lines):
                break
            content = lines[j].strip()
            if not content:
                continue
            # ▶PP 새 마커 만나면 중단
            if PP_RE.match(content):
                break
            # [이미지N] 패턴
            img_m = IMAGE_LINE_RE.match(content)
            if img_m:
                desc_raw = img_m.group(2)
                has_image = True
                break
            # [본문] 패턴
            scr_m = SCRIPTURE_RE.match(content)
            if scr_m:
                desc_raw = scr_m.group(2)
                has_image = False
                text_content = scr_m.group(2)
                break
            # 일반 텍스트 — 첫 비어있지 않은 줄을 desc_raw로
            if not desc_raw:
                desc_raw = content[:120]

        # 컨텍스트 — 이 ▶PP부터 다음 ▶PP까지의 본문(또는 H1/H2 헤더까지)
        next_idx = pp_positions[idx + 1][0] if idx + 1 < len(pp_positions) else len(lines)
        ctx_lines = []
        # 마커 위 5줄 (앞 컨텍스트)
        for k in range(max(0, line_idx - 5), line_idx):
            ctx_lines.append(lines[k])
        # 마커 다음부터 다음 ▶PP / 헤더까지 (뒤 컨텍스트)
        for k in range(line_idx + 1, next_idx):
            stripped = lines[k].strip()
            # 다른 ▶PP 만나면 멈춤 (이미 next_idx로 처리되지만 안전장치)
            if PP_RE.match(stripped):
                break
            ctx_lines.append(lines[k])

        context_raw = "\n".join(ctx_lines).strip()

        slot = {
            "num": num,
            "has_image": has_image,
            "desc_raw": desc_raw,
            "context_raw": context_raw,
        }
        if text_content and not has_image:
            slot["text_raw"] = text_content
        slots.append(slot)

    return slots


def main():
    if len(sys.argv) < 2:
        print("사용: python scripts/extract_pp_context.py <설교폴더> [--output 파일명]")
        sys.exit(1)
    sermon_dir = Path(sys.argv[1]).resolve()
    output_name = "slots_raw.json"
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_name = sys.argv[idx + 1]

    manuscript = find_sermon_file(sermon_dir)
    if not manuscript:
        print(f"원고 파일을 찾을 수 없음: {sermon_dir}")
        sys.exit(1)

    print(f"원고: {manuscript.name}")
    slots = extract_slots(manuscript)
    out = sermon_dir / output_name
    out.write_text(json.dumps(slots, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"슬롯 {len(slots)}개 추출 → {out.name}")
    print(f"  · 이미지: {sum(1 for s in slots if s['has_image'])}개")
    print(f"  · 본문: {sum(1 for s in slots if not s['has_image'])}개")


if __name__ == "__main__":
    main()
