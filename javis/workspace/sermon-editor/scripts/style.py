"""DOCX v2 스타일 설정 — 미리보기 HTML CSS 매핑 (2026-04-22 잠금).

이 파일만 수정해도 전체 DOCX 외관이 바뀐다.
결정 근거: docs/docx_upgrade_decisions.md
"""

from docx.shared import Pt, Cm, RGBColor


# ============================================================
# 색상 (RGBColor / HEX)
# ============================================================
COLOR_H1 = RGBColor(0x3B, 0x82, 0xF6)       # 파랑 (H1)
COLOR_H2 = RGBColor(0xDC, 0x26, 0x26)       # 빨강 (H2)
COLOR_H3 = RGBColor(0xDC, 0x26, 0x26)       # 빨강 (H3) + 밑줄
COLOR_BOLD = RGBColor(0xD4, 0xAF, 0x37)     # 옅은 황금 (볼드 강조)
COLOR_PP_TEXT = RGBColor(0xB4, 0x85, 0x10)  # 황금 어두운 톤 (PP 마커 텍스트)
COLOR_BENED_TEXT = RGBColor(0x1E, 0x40, 0xAF)  # 축도 본문 색 (진한 파랑)

# HEX (OXML 셀 배경 / 테두리용)
HEX_PP_BG = "FEF3C7"            # 황금 라이트 (PP 배경)
HEX_PP_BORDER = "D4AF37"        # 황금 (PP 테두리)
HEX_QUOTE_BG = "F1F5F9"         # 회색 (성경 박스 배경)
HEX_QUOTE_BORDER = "3B82F6"     # 파랑 (성경 박스 좌측 테두리)
HEX_BENED_BG = "F3F4F6"         # 약간 짙은 회색 (축도)
HEX_BENED_BORDER = "1E40AF"     # 진한 파랑 (축도 테두리)
HEX_HR = "CCCCCC"               # 수평선 색
HEX_H1_UNDERLINE = "3B82F6"     # H1 하단선

# v3.1 신규 — 1인칭 모놀로그 박스 (금테 + 옅은 금배경)
HEX_MONO_BG = "FEF9E7"          # 옅은 금배경
HEX_MONO_BORDER = "D4AF37"      # 황금 테두리
COLOR_MONO_TEXT = RGBColor(0x33, 0x33, 0x33)  # 검정 본문

# v3.1 신규 — 회중 합송 선포문 박스 (빨강 테 + 흰배경)
HEX_PROC_BG = "FFFFFF"          # 흰 배경
HEX_PROC_BORDER = "DC2626"      # 빨강 테두리
COLOR_PROC_TEXT = RGBColor(0x33, 0x33, 0x33)  # 검정 본문 (굵게)

# ============================================================
# 폰트
# ============================================================
FONT_BODY = "나눔명조"


# ============================================================
# 크기 (pt)
# ============================================================
SIZE_H1 = 22
SIZE_H2 = 17
SIZE_H3 = 15
SIZE_BODY = 15
SIZE_QUOTE = 14          # 성경 박스 본문
SIZE_BENEDICTION = 14    # 축도
SIZE_PP = 13             # PP 마커
SIZE_HYMN_INFO = 12      # 찬송 정보 (*)
SIZE_META = 11           # 수정 이력 등
SIZE_MONOLOGUE = 16      # v3.1 신규 — 1인칭 모놀로그 (큰 폰트)
SIZE_PROCLAMATION = 15   # v3.1 신규 — 선포문 (중앙정렬 굵게)


# ============================================================
# 한글 문서 특성
# ============================================================
CHAR_WIDTH_SCALE = 85        # % 장평
CHAR_SPACING_TWIPS = -9      # 자간 (-3%의 twips 근사, 음수 = 좁음)


# ============================================================
# 페이지 (Cm)
# ============================================================
PAGE_WIDTH_CM = 21.0
PAGE_HEIGHT_CM = 29.7
MARGIN_TOP_CM = 2.0
MARGIN_BOTTOM_CM = 2.0
MARGIN_LEFT_CM = 2.5
MARGIN_RIGHT_CM = 2.5


# ============================================================
# 기본 문단 간격
# ============================================================
LINE_SPACING_PT = 22
PARA_SPACE_AFTER_PT = 4
PARA_SPACE_BEFORE_PT = 0

# 헤더별 문단 간격
H1_SPACE_BEFORE_PT = 8
H1_SPACE_AFTER_PT = 8
H2_SPACE_BEFORE_PT = 14
H2_SPACE_AFTER_PT = 6
H3_SPACE_BEFORE_PT = 10
H3_SPACE_AFTER_PT = 6


# ============================================================
# 이미지
# ============================================================
IMAGE_WIDTH_CM = 13.0   # 본문 너비의 약 85%


# ============================================================
# 통합 설정 — import 용이성
# ============================================================
STYLE = {
    # 색상
    "COLOR_H1": COLOR_H1,
    "COLOR_H2": COLOR_H2,
    "COLOR_H3": COLOR_H3,
    "COLOR_BOLD": COLOR_BOLD,
    "COLOR_PP_TEXT": COLOR_PP_TEXT,
    "COLOR_BENED_TEXT": COLOR_BENED_TEXT,
    "HEX_PP_BG": HEX_PP_BG,
    "HEX_PP_BORDER": HEX_PP_BORDER,
    "HEX_QUOTE_BG": HEX_QUOTE_BG,
    "HEX_QUOTE_BORDER": HEX_QUOTE_BORDER,
    "HEX_BENED_BG": HEX_BENED_BG,
    "HEX_BENED_BORDER": HEX_BENED_BORDER,
    "HEX_HR": HEX_HR,
    "HEX_H1_UNDERLINE": HEX_H1_UNDERLINE,
    # 폰트·크기
    "FONT_BODY": FONT_BODY,
    "SIZE_H1": SIZE_H1,
    "SIZE_H2": SIZE_H2,
    "SIZE_H3": SIZE_H3,
    "SIZE_BODY": SIZE_BODY,
    "SIZE_QUOTE": SIZE_QUOTE,
    "SIZE_BENEDICTION": SIZE_BENEDICTION,
    "SIZE_PP": SIZE_PP,
    "SIZE_HYMN_INFO": SIZE_HYMN_INFO,
    "SIZE_META": SIZE_META,
    # 한글 특성
    "CHAR_WIDTH_SCALE": CHAR_WIDTH_SCALE,
    "CHAR_SPACING_TWIPS": CHAR_SPACING_TWIPS,
    # 페이지
    "PAGE_WIDTH_CM": PAGE_WIDTH_CM,
    "PAGE_HEIGHT_CM": PAGE_HEIGHT_CM,
    "MARGIN_TOP_CM": MARGIN_TOP_CM,
    "MARGIN_BOTTOM_CM": MARGIN_BOTTOM_CM,
    "MARGIN_LEFT_CM": MARGIN_LEFT_CM,
    "MARGIN_RIGHT_CM": MARGIN_RIGHT_CM,
    # 간격
    "LINE_SPACING_PT": LINE_SPACING_PT,
    "PARA_SPACE_AFTER_PT": PARA_SPACE_AFTER_PT,
    "PARA_SPACE_BEFORE_PT": PARA_SPACE_BEFORE_PT,
    "H1_SPACE_BEFORE_PT": H1_SPACE_BEFORE_PT,
    "H1_SPACE_AFTER_PT": H1_SPACE_AFTER_PT,
    "H2_SPACE_BEFORE_PT": H2_SPACE_BEFORE_PT,
    "H2_SPACE_AFTER_PT": H2_SPACE_AFTER_PT,
    "H3_SPACE_BEFORE_PT": H3_SPACE_BEFORE_PT,
    "H3_SPACE_AFTER_PT": H3_SPACE_AFTER_PT,
    # 이미지
    "IMAGE_WIDTH_CM": IMAGE_WIDTH_CM,
}
