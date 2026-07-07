"""python-docx가 직접 지원하지 않는 저수준 OXML 조작 헬퍼.

주 용도:
  - 테이블 셀 배경색 (shading)
  - 테이블 셀 테두리 (선택적 side)
  - run 장평 / 자간 / 동아시아 폰트
  - paragraph 하단 테두리 (H1 밑줄)
  - 수평선 (HR)
"""

from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# ============================================================
# 셀 배경색 / 테두리
# ============================================================
def set_cell_shading(cell, hex_color):
    """테이블 셀에 배경색 적용. hex_color는 'RRGGBB' 형식."""
    tcPr = cell._tc.get_or_add_tcPr()
    # 기존 shd 제거
    existing = tcPr.find(qn("w:shd"))
    if existing is not None:
        tcPr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def set_cell_border(cell, sides=None, hex_color="000000", size_pt=1.0):
    """테이블 셀 테두리. sides는 ['left','top','right','bottom'] 중 선택."""
    if sides is None:
        sides = ["left", "top", "right", "bottom"]
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    for side in sides:
        existing = tcBorders.find(qn(f"w:{side}"))
        if existing is not None:
            tcBorders.remove(existing)
        border = OxmlElement(f"w:{side}")
        border.set(qn("w:val"), "single")
        border.set(qn("w:sz"), str(int(size_pt * 8)))  # 1/8 pt 단위
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), hex_color)
        tcBorders.append(border)


def remove_cell_borders_all(cell):
    """모든 셀 테두리를 'nil'로 설정 (테두리 완전 제거)."""
    tcPr = cell._tc.get_or_add_tcPr()
    existing = tcPr.find(qn("w:tcBorders"))
    if existing is not None:
        tcPr.remove(existing)
    tcBorders = OxmlElement("w:tcBorders")
    for side in ["top", "left", "bottom", "right"]:
        border = OxmlElement(f"w:{side}")
        border.set(qn("w:val"), "nil")
        tcBorders.append(border)
    tcPr.append(tcBorders)


# ============================================================
# Run 스타일 (장평, 자간, 한글 폰트)
# ============================================================
def set_run_scale(run, scale_pct=85):
    """장평 (문자 가로 비율) 설정. 기본 100%, 85%는 좁게."""
    rPr = run._element.get_or_add_rPr()
    existing = rPr.find(qn("w:w"))
    if existing is not None:
        rPr.remove(existing)
    w = OxmlElement("w:w")
    w.set(qn("w:val"), str(scale_pct))
    rPr.append(w)


def set_run_spacing(run, spacing_twips):
    """자간 (문자 간격) 설정. twips 단위, 음수 = 좁음.

    참고: 1pt = 20 twips. -3% of 15pt ≈ -9 twips.
    """
    rPr = run._element.get_or_add_rPr()
    existing = rPr.find(qn("w:spacing"))
    if existing is not None:
        rPr.remove(existing)
    sp = OxmlElement("w:spacing")
    sp.set(qn("w:val"), str(spacing_twips))
    rPr.append(sp)


def set_run_korean_font(run, font_name):
    """한국어(동아시아) 폰트 명시. ascii/hAnsi/eastAsia/cs 모두 설정."""
    rPr = run._element.get_or_add_rPr()
    existing = rPr.find(qn("w:rFonts"))
    if existing is not None:
        rPr.remove(existing)
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), font_name)
    rFonts.set(qn("w:hAnsi"), font_name)
    rFonts.set(qn("w:eastAsia"), font_name)
    rFonts.set(qn("w:cs"), font_name)
    rPr.insert(0, rFonts)


# ============================================================
# Paragraph 테두리 / 수평선
# ============================================================
def add_paragraph_border_bottom(para, hex_color="CCCCCC", size_pt=0.5):
    """Paragraph 하단 테두리 (H1 밑줄용)."""
    pPr = para._element.get_or_add_pPr()
    pBdr = pPr.find(qn("w:pBdr"))
    if pBdr is None:
        pBdr = OxmlElement("w:pBdr")
        pPr.append(pBdr)
    existing = pBdr.find(qn("w:bottom"))
    if existing is not None:
        pBdr.remove(existing)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(int(size_pt * 8)))
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), hex_color)
    pBdr.append(bottom)


def add_horizontal_rule(doc, hex_color="CCCCCC"):
    """문서에 수평선(HR) 추가."""
    p = doc.add_paragraph()
    pPr = p._element.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), hex_color)
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


def set_paragraph_shading(para, hex_color):
    """Paragraph 배경색 (단일 문단 음영)."""
    pPr = para._element.get_or_add_pPr()
    existing = pPr.find(qn("w:shd"))
    if existing is not None:
        pPr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    pPr.append(shd)
