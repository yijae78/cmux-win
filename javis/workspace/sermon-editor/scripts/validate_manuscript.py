#!/usr/bin/env python3
"""설교 원고 v3.1 자동 검증 — 28 항목 체크리스트 grep 검증.

DOCX 변환 전 의무 실행.

사용:
    python scripts/validate_manuscript.py <원고_v2.md>

종료 코드:
    0 = 자동 검증 9항목 모두 통과 (DOCX 변환 허용)
    1 = 위반 1~3 (경고, 변환 가능)
    2 = 위반 4+ (차단, 변환 금지)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def main(md_path: str) -> int:
    md = Path(md_path)
    if not md.exists():
        print(f"⛔ 원고 파일 없음: {md}")
        return 2
    text = md.read_text(encoding="utf-8")

    results: list[tuple[str, bool, str]] = []  # (항목, 통과, 상세)

    # 16. 꼬리물기 본론 — "그런데 —" ≥ 4
    n = len(re.findall(r"그런데 —", text))
    results.append(("(Q) 꼬리물기 — '그런데 —' ≥ 4", n >= 4, f"{n}회"))

    # 17. 자기 부정 응답 — "아닙니다" ≥ 8
    n = len(re.findall(r"아닙니다", text))
    results.append(("(Q) 자기 부정 — '아닙니다' ≥ 8", n >= 8, f"{n}회"))

    # 19. 차원 전환 — "차원이 다르" or "같은 그림" or "차원" ≥ 1 (manual 보조)
    n = len(re.findall(r"차원이 다르|같은 그림|차원", text))
    results.append(("(S) 차원 전환 ≥ 1 (산문 표현 변형 허용)", n >= 1, f"{n}회"))

    # 21. 언어 U-1: "성령 " (단독, 성령님 제외) == 0
    n = len(re.findall(r"성령(?!님)(?=[\s,.!?。])", text))
    results.append(("(U-1) 성령→성령님 단독화 (== 0)", n == 0, f"{n}회 (성령 단독)"))

    # 22. 언어 U-2: "우리" 검사 — manual 권장이지만 카운트만
    n = len(re.findall(r"우리", text))
    results.append(
        ("(U-2) 우리→나 (참고 카운트)", True, f"{n}회 (본문/표/일반 포함 — 청중 호명만 0이어야)"))

    # 23. 언어 U-3: "살아가게" ≥ 1
    n = len(re.findall(r"살아가게", text))
    results.append(("(U-3) 응답→살아가게 ≥ 1", n >= 1, f"{n}회"))

    # 24. 호흡 율격 — (pause) ≥ 5
    n = len(re.findall(r"\(pause\)", text))
    results.append(("(V) 호흡 율격 — (pause) ≥ 5", n >= 5, f"{n}회"))

    # 25. 4겹 원어 펌프 — 📖 원어블럭 ≥ 5 + 개역개정 ≥ 원어블럭
    # (기본틀 모음 + 본문 두 곳 표준이라 개역개정이 원어블럭의 1~2배가 정상)
    n_block = len(re.findall(r"📖 원어블럭", text))
    n_kgae = len(re.findall(r"개역개정", text))
    ok_pump = n_block >= 5 and n_kgae >= n_block
    results.append(
        ("(W) 4겹 원어 펌프 — 원어블럭 ≥ 5 + 개역개정 ≥ 원어블럭",
         ok_pump,
         f"원어블럭 {n_block}회 / 개역개정 {n_kgae}회 (모음+본문 표준)"))

    # 26. 인과 사슬 도표 — ``` 블록 내 → 화살표 등장
    code_blocks = re.findall(r"```\s*\n(.*?)\n\s*```", text, re.DOTALL)
    arrow_blocks = sum(1 for b in code_blocks if b.count("→") >= 3)
    results.append(
        ("(X) 인과 사슬 도표 — ``` 안에 → ≥ 3 (블록 ≥ 1)",
         arrow_blocks >= 1,
         f"화살표 블록 {arrow_blocks}개"))

    # 출력
    print(f"\n=== 설교 원고 v3.1 자동 검증 — {md.name} ===\n")
    fail = 0
    for label, ok, detail in results:
        mark = "✅" if ok else "❌"
        print(f"  {mark}  {label:50s} → {detail}")
        if not ok:
            fail += 1

    print(f"\n총 {len(results)} 항목 / 통과 {len(results)-fail} / 위반 {fail}")

    if fail == 0:
        print("\n✅ 모든 자동 검증 통과 — DOCX 변환 허용")
        return 0
    elif fail <= 3:
        print(f"\n⚠ {fail}개 위반 — 경고 (변환 가능, 수정 권장)")
        return 1
    else:
        print(f"\n⛔ {fail}개 위반 — 차단 (DOCX 변환 금지)")
        return 2


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용: python scripts/validate_manuscript.py <원고_v2.md>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
