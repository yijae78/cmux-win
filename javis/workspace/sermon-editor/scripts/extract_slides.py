"""
NLM 슬라이드 PDF → 개별 PNG 이미지 추출 스크립트
사용법: python extract_slides.py <images_folder_path>

images/ 폴더 안의 모든 slides-*.pdf 파일을 찾아서
각 페이지를 개별 PNG 파일로 추출한다.

출력 파일명: {PDF파일명에서 추출한 접두사}-{페이지번호}.png
예) slides-D-korean.pdf → D-01.png, D-02.png, ...
"""

import sys
import os
import re

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF가 설치되어 있지 않습니다. pip install PyMuPDF")
    sys.exit(1)


def extract_prefix(filename):
    """slides-X-description.pdf → X"""
    match = re.match(r'slides-([A-Z])', filename)
    if match:
        return match.group(1)
    # fallback: 파일명 첫 글자 사용
    return filename.replace('slides-', '').replace('.pdf', '')[0].upper()


def extract_slides(images_dir, dpi=200):
    """images 폴더 내 모든 slides PDF를 PNG로 추출"""
    if not os.path.isdir(images_dir):
        print(f"폴더를 찾을 수 없습니다: {images_dir}")
        sys.exit(1)

    pdf_files = sorted([f for f in os.listdir(images_dir) if f.startswith('slides-') and f.endswith('.pdf')])

    if not pdf_files:
        print(f"슬라이드 PDF 파일이 없습니다: {images_dir}")
        sys.exit(1)

    total = 0
    for pdf_file in pdf_files:
        prefix = extract_prefix(pdf_file)
        pdf_path = os.path.join(images_dir, pdf_file)
        doc = fitz.open(pdf_path)

        page_count = len(doc)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            out_name = f"{prefix}-{i+1:02d}.png"
            out_path = os.path.join(images_dir, out_name)
            pix.save(out_path)
            print(f"  추출: {out_name}")
            total += 1

        doc.close()
        print(f"  {pdf_file}: {page_count} 페이지 추출 완료")

    print(f"\n총 {total}개 이미지 추출 완료")
    return total


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python extract_slides.py <images_folder_path>")
        sys.exit(1)

    images_dir = sys.argv[1]
    extract_slides(images_dir)
