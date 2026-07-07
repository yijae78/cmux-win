"""PPTX에서 슬라이드 이미지를 추출

사용법: python extract_pptx_images.py <pptx_path> <output_dir>

NLM이 생성한 PPTX의 ppt/media/ 안에 있는 이미지를 순서대로 추출하여
<output_dir>/slide_01.png, slide_02.png ... 형태로 저장한다.
"""

import sys
import zipfile
import shutil
from pathlib import Path


def extract(pptx_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(pptx_path, "r") as z:
        media = sorted(
            [n for n in z.namelist() if n.startswith("ppt/media/") and not n.endswith("/")],
            key=lambda x: (len(x), x),
        )
        if not media:
            print(f"No media files in {pptx_path}")
            return

        for i, name in enumerate(media, 1):
            ext = Path(name).suffix or ".png"
            dest = output_dir / f"slide_{i:02d}{ext}"
            with z.open(name) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            print(f"✓ {dest.name}")

    print(f"\n{len(media)} images extracted → {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python extract_pptx_images.py <pptx_path> <output_dir>")
        sys.exit(1)
    extract(Path(sys.argv[1]), Path(sys.argv[2]))
