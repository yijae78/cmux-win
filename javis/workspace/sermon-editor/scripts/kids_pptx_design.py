"""아동부 PPT 디자인 상수 — 19개 실작업 PPT 분석 기반 (장년부와 완전 독립)"""

from pptx.util import Emu, Pt, Inches, Cm
from pptx.dml.color import RGBColor

# ============================================================
# 슬라이드 크기 (16:9 와이드)
# ============================================================
SLIDE_WIDTH = Emu(12192000)    # 13.33 inches = 33.87 cm
SLIDE_HEIGHT = Emu(6858000)    # 7.50 inches = 19.05 cm

# ============================================================
# 폰트 4종 (아동부 전용)
# ============================================================
FONT_BODY = "나눔명조 ExtraBold"       # 본문 메인
FONT_HEADER = "나눔고딕 ExtraBold"     # 헤더 태그
FONT_GREEK = "함초롬바탕"              # 헬라어/히브리어
FONT_QUESTION = "SimSun"               # 거대 ? 전용

# ============================================================
# 색상 3색 시스템
# ============================================================
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
YELLOW = RGBColor(0xFF, 0xFF, 0x00)     # 1순위 강조
CYAN = RGBColor(0x00, 0xFF, 0xFF)       # 2순위 강조
RED = RGBColor(0xFF, 0x00, 0x00)        # 마스크 도형 전용
DARK_RED = RGBColor(0xC0, 0x00, 0x00)   # 마스크 도형 변형
BLACK = RGBColor(0x00, 0x00, 0x00)

# ============================================================
# 폰트 크기 계급
# ============================================================
SIZE_BOOK_NAME = Pt(115)        # 성경 책 이름 (표지)
SIZE_TITLE = Pt(96)             # 설교 제목
SIZE_CHAPTER_VERSE = Pt(80)     # 장/절 번호
SIZE_BODY = Pt(60)              # 본문 표준
SIZE_BODY_SUB = Pt(54)          # 본문 보조
SIZE_SERIES_TAG = Pt(45)        # 시리즈 태그
SIZE_HEADER_TAG = Pt(44)        # 헤더 태그 ("성경 말씀")
SIZE_REF_TAG = Pt(32)           # 장절 참조
SIZE_GREEK_LARGE = Pt(180)      # 원어 대형
SIZE_GREEK_MEDIUM = Pt(88)      # 원어 중형
SIZE_GREEK_SMALL = Pt(40)       # 원어 소형

# 거대 ? 크기 (점점 커지는 패턴)
SIZE_QUESTION_S = Pt(250)
SIZE_QUESTION_M = Pt(300)
SIZE_QUESTION_L = Pt(360)
SIZE_QUESTION_XL = Pt(432)
SIZE_QUESTION_XXL = Pt(518)

# ============================================================
# 자간 (Character Spacing) — 19개 PPT 분석 결과
# 단위: Emu 100분의 1pt. pptx XML spc 속성에 직접 적용
# ============================================================
CHAR_SPACING_BODY = -20         # 나눔명조 본문: -0.2pt (원본 spc=-20)
CHAR_SPACING_HEADER = 0         # 나눔고딕 헤더: 0pt
CHAR_SPACING_QUESTION = 0       # SimSun ?: 0pt

# ============================================================
# 행간 (Line Spacing) — 19개 PPT 분석 결과
# 단위: 1000분의 1 퍼센트 (pptx XML spcPct val)
# ============================================================
LINE_SPACING_NORMAL = 100000    # 100% — 기본 (SimSun, 나눔고딕)
LINE_SPACING_WIDE = 150000      # 150% — 예외적 넓은 행간

# ============================================================
# 단락 전/후 간격 — 19개 PPT 분석 결과
# 단위: 100분의 1pt (pptx XML spcPts val)
# ============================================================
SPACE_BEFORE = 0                # 0pt
SPACE_AFTER = 0                 # 0pt

# ============================================================
# 그라디언트 헤더 바 (표지 3장에 사용)
# 위치: (0, 0), 크기: 전체 폭 × 2.38cm
# ============================================================
HEADER_BAR_LEFT = 0
HEADER_BAR_TOP = 0
HEADER_BAR_WIDTH = Emu(12192000)   # 33.87cm
HEADER_BAR_HEIGHT = Emu(857250)    # 2.38cm (0.94")

HEADER_BAR_XML = '''<p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="HeaderBar"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm>
      <a:off x="0" y="0"/>
      <a:ext cx="12192000" cy="857250"/>
    </a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    <a:gradFill flip="none" rotWithShape="1">
      <a:gsLst>
        <a:gs pos="0">
          <a:schemeClr val="accent5">
            <a:lumMod val="20000"/>
            <a:lumOff val="80000"/>
          </a:schemeClr>
        </a:gs>
        <a:gs pos="25000"><a:srgbClr val="21D6E0"/></a:gs>
        <a:gs pos="75000"><a:srgbClr val="0087E6"/></a:gs>
        <a:gs pos="100000"><a:srgbClr val="005CBF"/></a:gs>
      </a:gsLst>
      <a:lin ang="0" scaled="1"/>
      <a:tileRect/>
    </a:gradFill>
    <a:ln><a:noFill/></a:ln>
  </p:spPr>
  <p:txBody>
    <a:bodyPr anchor="ctr"/>
    <a:lstStyle/>
    <a:p><a:endParaRPr lang="ko-KR"/></a:p>
  </p:txBody>
</p:sp>'''

# ============================================================
# 위치/크기 상수 (Emu 단위, 분석 결과 기반)
# ============================================================

# 표지 슬라이드 — 헤더 태그 텍스트 ("성경 말씀")
COVER_TAG_POS = (Cm(0.77), Cm(0.0), Cm(6.85), Cm(2.14))

# 표지 슬라이드 — 성경 책 이름 + 장절 (우하단 배치)
COVER_BOOK_POS = (Cm(6.25), Cm(5.91), Cm(21.36), Cm(8.93))

# 본문 슬라이드 — 성경 본문 텍스트 박스 (테두리 직사각형 안)
SCRIPTURE_BOX_POS = (Cm(0.77), Cm(2.82), Cm(31.95), Cm(13.94))
SCRIPTURE_FRAME_POS = SCRIPTURE_BOX_POS

# 본문 슬라이드 — 헤더 태그 "성경 말씀(절)"
SCRIPTURE_TAG_POS = (Cm(0.77), Cm(0.0), Cm(11.17), Cm(2.14))

# 제목 슬라이드 — 제목 텍스트
TITLE_POS = (Cm(3.67), Cm(7.68), Cm(25.78), Cm(4.36))

# 제목 슬라이드 — 시리즈 태그
SERIES_TAG_POS = (Cm(4.54), Cm(6.51), Cm(9.95), Cm(2.18))

# 개역개정 아이콘 위치 (우하단)
BIBLE_ICON_POS = (Cm(22.12), Cm(12.75), Cm(8.32), Cm(4.45))

# 거대 ? 위치 (슬라이드 우측 중앙)
QUESTION_POS = (Cm(18.72), Cm(8.83), Cm(8.54), Cm(10.94))
QUESTION_HEIGHT_MAP = {
    250: Cm(10.94),
    300: Cm(13.08),
    360: Cm(15.65),
    432: Cm(18.72),
    518: Cm(22.40),
}

# 이미지 풀스크린
IMAGE_FULLSCREEN = (Emu(0), Emu(0), SLIDE_WIDTH, SLIDE_HEIGHT)

# 빨간 마스크 기본 크기 (다양하게 변형됨)
RED_MASK_OVAL_DEFAULT = (Cm(4.0), Cm(4.0))     # 너비, 높이
RED_MASK_RECT_DEFAULT = (Cm(8.0), Cm(2.0))     # 너비, 높이

# 레이아웃 인덱스
LAYOUT_TITLE = 0        # 제목 슬라이드
LAYOUT_CONTENT = 1      # 제목 및 내용
LAYOUT_BLANK = 6        # 빈 화면

# ============================================================
# 개역개정 아이콘 파일 경로 (상대)
# ============================================================
BIBLE_ICON_FILENAME = "bible_icon.png"
