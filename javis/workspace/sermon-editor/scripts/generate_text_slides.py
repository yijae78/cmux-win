"""성경말씀 / 텍스트 슬라이드 PNG 자동 생성 (v2)

slots.json의 text 필드(title/body/highlight)를 읽어
대시보드용 16:9 검정 배경 PPT 이미지를 생성한다.

표준 (2026-05-01):
- 1280x720 (16:9)
- 검정 배경
- 노랑(#FFFF00) = 1순위 강조 / 시안(#00FFFF) = 제목 / 흰색 = 본문
- 좌측 황금 세로 바 (PPT 시그니처)
- **본문은 좌측 정렬** (요청 반영)
- **나눔명조 ExtraBold** (한글) + **Times New Roman Bold** (헬라어/히브리어)
- 본문 폰트 자동 전환 (Hebrew U+0590-05FF, Greek U+0370-03FF)

사용:
    python scripts/generate_text_slides.py <설교폴더>
"""

import sys
import json
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. pip install Pillow")
    sys.exit(1)


# 한글 폰트 후보 (나눔명조 ExtraBold 우선)
KOREAN_FONT_CANDIDATES = [
    "C:/Users/yijae/AppData/Local/Microsoft/Windows/Fonts/NanumMyeongjoExtraBold.ttf",
    "C:/Users/yijae/AppData/Local/Microsoft/Windows/Fonts/NanumMyeongjoBold.ttf",
    "C:/Windows/Fonts/NanumMyeongjoExtraBold.ttf",
    "C:/Windows/Fonts/NanumMyeongjoBold.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
]

# 원어(헬라어·히브리어) 폰트 후보
ORIGINAL_LANG_FONT_CANDIDATES = [
    "C:/Windows/Fonts/timesbd.ttf",  # Times New Roman Bold (Hebrew + Greek)
    "C:/Windows/Fonts/times.ttf",
    "C:/Windows/Fonts/Cardo-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
]

# 한자(CJK) 폰트 후보 — 나눔명조엔 한자 글리프가 없어 두부(□)가 되므로 별도 폴백.
# 명조 계열(함초롬바탕→바탕) 우선으로 한글(나눔명조)과 시각 톤을 맞춘다.
CJK_FONT_CANDIDATES = [
    "C:/Windows/Fonts/HANBatang.ttf",   # 함초롬바탕 (한자 포함, 명조 계열)
    "C:/Windows/Fonts/batang.ttc",      # 바탕 (한자 포함, 명조 계열)
    "C:/Windows/Fonts/malgunbd.ttf",    # 맑은 고딕 Bold (최후 폴백)
    "C:/Windows/Fonts/malgun.ttf",
]

W, H = 1280, 720
BG = (10, 14, 26)              # 깊은 검정
TITLE_COLOR = (0, 255, 255)    # 시안
BODY_COLOR = (241, 245, 249)   # 흰색 약간 회색
HIGHLIGHT = (255, 255, 0)      # 노랑
SUB_COLOR = (148, 163, 184)    # 옅은 회색
ACCENT_BAR = (251, 191, 36)    # 황금

# 본문 슬라이드 기본 헤더 밴드 (모든 부서 공통 표준) — slots의 band_* 필드로 override 가능
DEFAULT_HEADER_BAND = True
DEFAULT_BAND_COLOR = (14, 32, 62)    # 진네이비
DEFAULT_BAND_TEXT = (255, 255, 255)  # 흰 글씨
DEFAULT_BAND_EDGE = (251, 191, 36)   # 황금 하단 엣지

# 좌측 본문 시작 X 좌표 (좌측 정렬)
LEFT_MARGIN = 90  # 좌측 황금 바(0~10px) 이후 여백


def find_font(candidates, size):
    for path in candidates:
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def is_original_lang_char(ch):
    """헬라어 또는 히브리어 문자 여부."""
    code = ord(ch)
    if 0x0590 <= code <= 0x05FF: return True   # Hebrew
    if 0xFB1D <= code <= 0xFB4F: return True   # Hebrew Presentation
    if 0x0370 <= code <= 0x03FF: return True   # Greek
    if 0x1F00 <= code <= 0x1FFF: return True   # Greek Extended
    return False


def is_cjk_han_char(ch):
    """한자(CJK 한자) 여부 — 나눔명조에 글리프가 없어 별도 폰트로 폴백한다."""
    code = ord(ch)
    if 0x4E00 <= code <= 0x9FFF: return True    # CJK Unified Ideographs
    if 0x3400 <= code <= 0x4DBF: return True    # Extension A
    if 0xF900 <= code <= 0xFAFF: return True    # CJK Compatibility Ideographs
    if 0x20000 <= code <= 0x2A6DF: return True  # Extension B
    return False


# 폰트 글리프 실측 폴백 — 범위 분류만으로는 라틴 확장(ē, ō 등)·특수 기호가
# 나눔명조에 없어 두부(□)가 된다. 실제 글리프 유무를 측정해 폰트를 고른다.
_probe_face_cache = {}


def _probe_face(candidates):
    key = tuple(candidates)
    if key not in _probe_face_cache:
        face = None
        if _HB_OK:
            for p in candidates:
                if Path(p).exists():
                    try:
                        face = _ft.Face(p)
                        break
                    except Exception:
                        continue
        _probe_face_cache[key] = face
    return _probe_face_cache[key]


def _glyph_in(candidates, ch):
    """후보 폰트(첫 존재 파일)에 글자 글리프가 있는지. freetype 없으면 보수적으로 True."""
    face = _probe_face(candidates)
    if face is None:
        return True
    try:
        return face.get_char_index(ord(ch)) != 0
    except Exception:
        return True


def char_category(ch):
    """글자를 폰트 종류로 분류: 'orig'(원어) / 'cjk'(한자) / 'kor'(한글·그 외).

    범위 분류 후, 'kor'로 보낼 글자가 나눔명조에 실제 글리프가 없으면
    (라틴 확장·특수 기호 등) 함초롬바탕 → 원어 폰트 순으로 폴백한다.
    """
    if is_original_lang_char(ch):
        return "orig"
    if is_cjk_han_char(ch):
        return "cjk"
    if _glyph_in(KOREAN_FONT_CANDIDATES, ch):
        return "kor"
    if _glyph_in(CJK_FONT_CANDIDATES, ch):
        return "cjk"
    if _glyph_in(ORIGINAL_LANG_FONT_CANDIDATES, ch):
        return "orig"
    return "kor"


def text_width(draw, text, font):
    if _HB_OK and _has_hebrew(text):
        try:
            return _hebrew_advance(text, font.path, font.size)
        except Exception:
            pass
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
    except Exception:
        return int(len(text) * font.size * 0.55)


def text_height(font):
    try:
        m = font.getmetrics()
        return m[0] + m[1]
    except Exception:
        return font.size + 4


def font_ascent(font):
    try:
        return font.getmetrics()[0]
    except Exception:
        return int(font.size * 0.8)


# 히브리어 셰이핑 (HarfBuzz + freetype) — RTL 순서 + 니쿠드(모음 부호) 정확 배치
# PIL은 raqm 미지원 시 히브리어 모음이 어긋남 → HarfBuzz로 직접 셰이핑·래스터한다.
try:
    import uharfbuzz as _hb
    import freetype as _ft
    _HB_OK = True
except Exception:
    _HB_OK = False

_hb_font_cache = {}
_ft_face_cache = {}


def _has_hebrew(s):
    return any('֐' <= c <= '׿' or 'יִ' <= c <= 'ﭏ' for c in s)


def _get_hb_font(font_path, px):
    key = (font_path, px)
    if key not in _hb_font_cache:
        with open(font_path, "rb") as f:
            data = f.read()
        face = _hb.Face(data)
        font = _hb.Font(face)
        font.scale = (px * 64, px * 64)
        _hb_font_cache[key] = font
    return _hb_font_cache[key]


def _get_ft_face(font_path, px):
    key = (font_path, px)
    if key not in _ft_face_cache:
        face = _ft.Face(font_path)
        face.set_pixel_sizes(0, px)
        _ft_face_cache[key] = face
    return _ft_face_cache[key]


def _shape_hebrew(text, font_path, px):
    font = _get_hb_font(font_path, px)
    buf = _hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()   # 스크립트=Hebrew, 방향=RTL 자동
    _hb.shape(font, buf)
    return buf.glyph_infos, buf.glyph_positions


def _hebrew_advance(text, font_path, px):
    _, positions = _shape_hebrew(text, font_path, px)
    return int(sum(p.x_advance for p in positions) / 64)


def _render_hebrew(text, font_path, px, color):
    """히브리어를 HarfBuzz로 셰이핑 후 freetype로 래스터. (RGBA img, baseline) 반환."""
    infos, positions = _shape_hebrew(text, font_path, px)
    ft = _get_ft_face(font_path, px)
    ascent = ft.size.ascender >> 6
    descent = (-ft.size.descender) >> 6
    w = int(sum(p.x_advance for p in positions) / 64) + 6
    h = ascent + descent + 6
    img = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    pen = 0.0
    baseline = ascent + 2
    col_rgb = tuple(color)
    for info, pos in zip(infos, positions):
        ft.load_glyph(info.codepoint, _ft.FT_LOAD_RENDER)
        bmp = ft.glyph.bitmap
        bw, bh = bmp.width, bmp.rows
        if bw and bh:
            gimg = Image.frombytes("L", (bw, bh), bytes(bmp.buffer))
            col = Image.new("RGBA", (bw, bh), col_rgb + (0,))
            col.putalpha(gimg)
            gx = int(pen + pos.x_offset / 64 + ft.glyph.bitmap_left)
            gy = int(baseline - pos.y_offset / 64 - ft.glyph.bitmap_top)
            img.alpha_composite(col, (max(0, gx), max(0, gy)))
        pen += pos.x_advance / 64
    return img, baseline


def split_runs(text):
    """원어/한자/한글 혼합 텍스트를 같은 카테고리의 run 단위로 분할.

    반환: [(run_text, category), ...]  category ∈ {'orig','cjk','kor'}
    """
    runs = []
    if not text:
        return runs
    cur = text[0]
    cur_cat = char_category(text[0])
    for ch in text[1:]:
        cat = char_category(ch)
        if cat == cur_cat:
            cur += ch
        else:
            runs.append((cur, cur_cat))
            cur = ch
            cur_cat = cat
    if cur:
        runs.append((cur, cur_cat))
    return runs


def _font_for(cat, kor_font, orig_font, cjk_font):
    if cat == "orig":
        return orig_font
    if cat == "cjk":
        return cjk_font
    return kor_font


def draw_mixed_line(draw, img, x, y, text, kor_font, orig_font, cjk_font, base_color, highlight_words, hl_color):
    """원어/한자/한글 혼합 + 강조 단어 처리.

    1) 강조 단어로 자르고
    2) 각 조각을 원어/한자/한글 run으로 다시 자른다
    """
    # 1) 강조 vs 일반 청크
    chunks = []
    sorted_hl = sorted(highlight_words or [], key=len, reverse=True)
    rem = text
    while rem:
        hit = None
        for hw in sorted_hl:
            if rem.startswith(hw):
                hit = hw
                break
        if hit:
            chunks.append((hit, hl_color))
            rem = rem[len(hit):]
        else:
            chunks.append((rem[0], base_color))
            rem = rem[1:]

    # 2) 같은 색 청크 합치기
    merged = []
    for tok, color in chunks:
        if merged and merged[-1][1] == color:
            merged[-1][0] += tok
        else:
            merged.append([tok, color])

    # 베이스라인 정렬 — 한글·원어·한자 폰트 ascent가 달라도 글자가 같은 선 위에 앉도록
    max_ascent = max(font_ascent(kor_font), font_ascent(orig_font), font_ascent(cjk_font))

    cx = x
    for tok, color in merged:
        # 원어/한자/한글 run 단위로 폰트 전환
        for run_text, cat in split_runs(tok):
            font = _font_for(cat, kor_font, orig_font, cjk_font)
            # 각 run을 (baseline - 자체 ascent) 위치에 그려서 글자 바닥선 정렬
            run_y = y + (max_ascent - font_ascent(font))
            if cat == "orig" and _HB_OK and _has_hebrew(run_text):
                # 히브리어: HarfBuzz 셰이핑 이미지로 합성 (니쿠드 정확 배치)
                himg, hbaseline = _render_hebrew(run_text, font.path, font.size, color)
                paste_y = int(y + max_ascent - hbaseline)
                img.paste(himg, (int(cx), paste_y), himg)
                cx += _hebrew_advance(run_text, font.path, font.size)
            else:
                draw.text((cx, run_y), run_text, font=font, fill=color)
                cx += text_width(draw, run_text, font)


def measure_line_width(draw, text, kor_font, orig_font, cjk_font):
    total = 0
    for run_text, cat in split_runs(text):
        font = _font_for(cat, kor_font, orig_font, cjk_font)
        total += text_width(draw, run_text, font)
    return total


def wrap_line(draw, text, kor_font, orig_font, cjk_font, max_w):
    """한 줄이 max_w(px)를 넘으면 어절(공백) → 글자 단위로 줄바꿈해 잘림 방지."""
    def fits(s):
        return measure_line_width(draw, s, kor_font, orig_font, cjk_font) <= max_w

    if fits(text):
        return [text]
    out = []
    cur = ""
    for word in text.split(" "):
        trial = (cur + " " + word) if cur else word
        if fits(trial):
            cur = trial
            continue
        if cur:
            out.append(cur)
            cur = ""
        if not fits(word):
            # 한 어절 자체가 너무 길면 글자 단위로 분해
            piece = ""
            for ch in word:
                if fits(piece + ch):
                    piece += ch
                else:
                    if piece:
                        out.append(piece)
                    piece = ch
            cur = piece
        else:
            cur = word
    if cur:
        out.append(cur)
    return out


def generate_text_slide(slot_num, title, body, highlight, footer, output_path, header_band=False, band_color=None, band_text_color=None, band_gradient=None, band_gradient_dir=None, band_bottom_edge=None):
    # 방어: highlight가 문자열이면 리스트로 감싼다.
    # (문자열을 그대로 sorted()하면 글자 단위로 쪼개져 엉뚱한 글자가 강조됨)
    if isinstance(highlight, str):
        highlight = [highlight] if highlight.strip() else []
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # 좌측 황금 세로 바
    draw.rectangle([(0, 0), (10, H)], fill=ACCENT_BAR)

    footer_kor = find_font(KOREAN_FONT_CANDIDATES, 22)
    footer_orig = find_font(ORIGINAL_LANG_FONT_CANDIDATES, 22)

    # 상단 제목 (좌측 정렬, 혼합 스크립트 + 멀티라인 지원)
    title_lines = [l.strip() for l in title.split("\n") if l.strip()]

    # 폰트: 밴드 헤더는 본문과 동일하게 80pt에서 시작, 폭이 넘치면 자동 축소.
    #       일반 헤더는 기존 52pt.
    if header_band:
        title_size = 80
        while title_size >= 44:
            title_kor = find_font(KOREAN_FONT_CANDIDATES, title_size)
            title_orig = find_font(ORIGINAL_LANG_FONT_CANDIDATES, title_size)
            title_cjk = find_font(CJK_FONT_CANDIDATES, title_size)
            max_tw = max(
                (measure_line_width(draw, l, title_kor, title_orig, title_cjk) for l in title_lines),
                default=0,
            )
            if max_tw <= W - LEFT_MARGIN - 40:
                break
            title_size -= 4
    else:
        title_kor = find_font(KOREAN_FONT_CANDIDATES, 52)
        title_orig = find_font(ORIGINAL_LANG_FONT_CANDIDATES, 52)
        title_cjk = find_font(CJK_FONT_CANDIDATES, 52)

    title_line_h = max(text_height(title_kor), text_height(title_orig)) + 6
    title_y = 35

    # header_band: 상단 전체를 시안 밴드로 채우고 제목은 검정 글씨. 밴드 높이는 글씨에 맞춤.
    if header_band:
        band_h = title_y + len(title_lines) * title_line_h + 22
        if band_gradient:
            # 그라데이션: 시작색 → 끝색 (방향: horizontal=좌→우 / vertical=위→아래)
            sc, ec = band_gradient
            gdir = band_gradient_dir or "horizontal"
            if gdir == "vertical":
                for y in range(band_h):
                    tt = y / max(1, band_h - 1)
                    col = tuple(int(sc[i] + (ec[i] - sc[i]) * tt) for i in range(3))
                    draw.line([(0, y), (W, y)], fill=col)
            else:
                for x in range(W):
                    tt = x / max(1, W - 1)
                    col = tuple(int(sc[i] + (ec[i] - sc[i]) * tt) for i in range(3))
                    draw.line([(x, 0), (x, band_h)], fill=col)
        else:
            draw.rectangle([(0, 0), (W, band_h)], fill=tuple(band_color) if band_color else TITLE_COLOR)
        # 밴드 하단 엣지 라인 (본문과 분리감)
        if band_bottom_edge:
            draw.rectangle([(0, band_h - 6), (W, band_h)], fill=tuple(band_bottom_edge))
        draw.rectangle([(0, 0), (10, band_h)], fill=ACCENT_BAR)  # 좌측 황금 바 유지
        title_fill = tuple(band_text_color) if band_text_color else (0, 0, 0)  # 글씨색
    else:
        title_fill = TITLE_COLOR

    for tl in title_lines:
        draw_mixed_line(draw, img, LEFT_MARGIN, title_y, tl, title_kor, title_orig, title_cjk,
                        title_fill, [], HIGHLIGHT)
        title_y += title_line_h

    # 제목 아래 구분선 — 밴드일 때는 생략(밴드가 구분 역할)
    divider_y = max(110, title_y + 5)
    if header_band:
        divider_y = band_h
    else:
        draw.line([(LEFT_MARGIN, divider_y), (W - 60, divider_y)], fill=(51, 65, 85), width=1)

    # 본문 — 좌측 정렬, 줄바꿈 그대로
    body_lines = body.split("\n")

    # ⭐ 자동 폰트 + 컴팩트 레이아웃 (반응형)
    # 너비: 1280 - LEFT_MARGIN(90) - 60 = 1130px
    # 높이: 720 - BODY_TOP - 50(푸터). BODY_TOP은 제목 줄 수에 따라 동적
    BODY_TOP = divider_y + 30  # 구분선 아래 30px
    BODY_BOTTOM_GAP = 50
    body_max_w = W - LEFT_MARGIN - 60
    body_max_h = H - BODY_TOP - BODY_BOTTOM_GAP

    # 줄 수가 많으면 줄간격 자동 축소: 4줄 이하=+18 / 5~6줄=+14 / 7줄+=+10
    nonblank = sum(1 for l in body_lines if l.strip())
    line_pad = 18 if nonblank <= 4 else (14 if nonblank <= 6 else 10)

    body_font_size = 80
    wrapped_lines = body_lines
    body_kor = body_orig = body_cjk = None
    line_h = 0
    while body_font_size >= 44:
        body_kor = find_font(KOREAN_FONT_CANDIDATES, body_font_size)
        body_orig = find_font(ORIGINAL_LANG_FONT_CANDIDATES, body_font_size)
        body_cjk = find_font(CJK_FONT_CANDIDATES, body_font_size)
        line_h = max(text_height(body_kor), text_height(body_orig)) + line_pad
        # 긴 줄은 캔버스 폭에 맞춰 자동 줄바꿈(어절→글자) — 우측 잘림 방지
        # 들여쓰기: 선행 공백 1칸 = 글자 폭 1.5배 픽셀 오프셋
        INDENT_PX_PER_SPACE = int(body_font_size * 0.6)
        wrapped_lines = []
        indent_map = {}  # wrapped_lines 인덱스 → 들여쓰기 px
        for line in body_lines:
            if not line.strip():
                wrapped_lines.append("")
            else:
                leading = len(line) - len(line.lstrip())
                indent_px = leading * INDENT_PX_PER_SPACE
                avail_w = body_max_w - indent_px
                wl = wrap_line(draw, line.strip(), body_kor, body_orig, body_cjk, avail_w)
                for w in wl:
                    indent_map[len(wrapped_lines)] = indent_px
                    wrapped_lines.append(w)
        # 줄바꿈이 너비를 보장하므로 전체 높이만 확인
        total_h = sum(line_h if l.strip() else line_h // 2 for l in wrapped_lines)
        if total_h <= body_max_h:
            break
        body_font_size -= 4

    # 빈 줄은 절반 높이로 계산
    total_h = sum(line_h if l.strip() else line_h // 2 for l in wrapped_lines)
    start_y = BODY_TOP + max(0, (body_max_h - total_h) // 2)

    cy = start_y
    for idx, line in enumerate(wrapped_lines):
        stripped = line.strip()
        if not stripped:
            cy += line_h // 2
            continue
        x_offset = indent_map.get(idx, 0)
        draw_mixed_line(draw, img, LEFT_MARGIN + x_offset, cy, stripped, body_kor, body_orig, body_cjk,
                        BODY_COLOR, highlight, HIGHLIGHT)
        cy += line_h

    # 하단 푸터(PP 번호 + 본문 라벨) 제거 — 신교수님 지시: 본문 슬라이드 깔끔하게

    img.save(output_path, "PNG", optimize=True)
    return output_path


def main(sermon_dir):
    sermon_dir = Path(sermon_dir).resolve()
    slots_file = sermon_dir / "slots.json"
    images_dir = sermon_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    if not slots_file.exists():
        print(f"slots.json 없음: {slots_file}")
        sys.exit(1)

    slots = json.loads(slots_file.read_text(encoding="utf-8"))

    generated = []
    missing_text = []  # has_image:false 인데 text 필드 비어있는 슬롯 (실수 가능성 큼)
    deleted = []
    for slot in slots:
        if slot.get("has_image", True):
            continue
        text = slot.get("text")
        out = images_dir / f"text_PP{slot['num']}.png"
        if not text:
            # has_image:false 슬롯에서 text 필드가 없으면 워크플로우 누락일 가능성 큼.
            # 이전엔 조용히 스킵했지만, 2026-05-02 룻기 아동부 누락 사고 이후
            # 명시적 누락 슬롯으로 추적해 종료 코드 2로 강제 알림.
            missing_text.append(slot["num"])
            if out.exists():
                out.unlink()
                deleted.append(out.name)
            continue
        title = text.get("title", "")
        body = text.get("body", "")
        highlight = text.get("highlight", [])
        footer = slot.get("desc", "").split("—")[-1].strip() if "—" in slot.get("desc", "") else ""
        generate_text_slide(slot["num"], title, body, highlight, footer, out,
                             header_band=slot.get("header_band", DEFAULT_HEADER_BAND),
                             band_color=slot.get("band_color") or DEFAULT_BAND_COLOR,
                             band_text_color=slot.get("band_text_color") or DEFAULT_BAND_TEXT,
                             band_gradient=slot.get("band_gradient"),
                             band_gradient_dir=slot.get("band_gradient_dir"),
                             band_bottom_edge=slot.get("band_bottom_edge") or DEFAULT_BAND_EDGE)
        generated.append(out.name)
        print(f"[OK] {out.name}")

    print(f"\n생성: {len(generated)}개")
    if deleted:
        print(f"삭제: {', '.join(deleted)}")
    if missing_text:
        print()
        print("=" * 60)
        print(f"⛔ 본문 슬라이드 누락 경고 — has_image:false 슬롯 {len(missing_text)}개에 text 필드 없음")
        print(f"   누락 슬롯: PP{', PP'.join(missing_text)}")
        print(f"   조치: slots.json의 해당 슬롯에 다음 필드 추가 후 재실행")
        print(f'   "text": {{"title": "...", "body": "...", "highlight": ["..."]}}')
        print("=" * 60)
        sys.exit(2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용: python scripts/generate_text_slides.py <설교폴더>")
        sys.exit(1)
    main(sys.argv[1])
