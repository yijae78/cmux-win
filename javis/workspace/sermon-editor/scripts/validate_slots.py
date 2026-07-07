"""설교 폴더 슬롯 무결성 검증 스크립트 (2026-05-02 정립)

NLM 트리거 직전과 대시보드 기동 직전에 호출.
slots.json + images/ 폴더를 점검해 다음 누락을 잡아낸다:

[1] has_image:true 슬롯에 candidates 비어있음 (이미지 후보 없음)
[2] has_image:false 슬롯에 text 필드 없음 (본문 슬라이드 못 만듦)
[3] has_image:false + text 있지만 images/text_PP{n}.png 없음 (생성 안 됨)
[4] candidates에 명시된 이미지 파일이 images/에 없음

사용:
    python scripts/validate_slots.py <설교폴더>

종료 코드:
    0 = 무결
    2 = 누락 발견 (NLM 트리거/대시보드 기동 전 반드시 수정)
"""

import sys
import json
from pathlib import Path


def validate(sermon_dir: Path) -> int:
    slots_file = sermon_dir / "slots.json"
    images_dir = sermon_dir / "images"

    if not slots_file.exists():
        print(f"⛔ slots.json 없음: {slots_file}")
        return 2

    slots = json.loads(slots_file.read_text(encoding="utf-8"))

    issues = []
    image_slots = 0
    text_slots = 0

    for slot in slots:
        num = slot.get("num", "??")
        if slot.get("has_image", True):
            image_slots += 1
            cands = slot.get("candidates") or {}
            non_null = {k: v for k, v in cands.items() if v}
            if not non_null:
                issues.append(f"PP{num}: 이미지 슬롯인데 candidates 비어있음")
            else:
                # 후보 파일 존재 확인
                for prefix, page in non_null.items():
                    img = images_dir / f"{prefix}_{page}.png"
                    if not img.exists():
                        issues.append(f"PP{num}: 후보 {prefix}_{page}.png 파일 없음 ({img})")
        else:
            text_slots += 1
            text = slot.get("text")
            if not text:
                issues.append(f"PP{num}: 본문 슬롯인데 text 필드 없음 (title/body/highlight 작성 필요)")
                continue
            if not text.get("title") and not text.get("body"):
                issues.append(f"PP{num}: text 필드 있지만 title·body 모두 비어있음")
            text_png = images_dir / f"text_PP{num}.png"
            if not text_png.exists():
                issues.append(f"PP{num}: text_PP{num}.png 없음 (generate_text_slides.py 실행 필요)")

    print(f"검사 결과: 이미지 슬롯 {image_slots}개 / 본문 슬롯 {text_slots}개")

    if issues:
        print()
        print("=" * 60)
        print(f"⛔ {len(issues)}개 누락 발견")
        for i, msg in enumerate(issues, 1):
            print(f"  {i}. {msg}")
        print("=" * 60)
        print("조치 후 다시 검증하세요.")
        return 2

    print("✅ 무결 — NLM 트리거 / 대시보드 기동 진행 가능")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용: python scripts/validate_slots.py <설교폴더>")
        sys.exit(1)
    sys.exit(validate(Path(sys.argv[1]).resolve()))
