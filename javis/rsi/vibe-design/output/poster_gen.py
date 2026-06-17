"""
여름성경학교 포스터 — 바이브디자인 DNA 적용
Design Tokens from DESIGN_DRAFT.md:
  - surface.void: #0a0a0a
  - surface.base: #0c111b
  - surface.raised: #111827
  - glass: rgba(255,255,255,0.04~0.09)
  - accent: golden (#FFB800) + cyan (#00A8FF)
  - gradient: 135deg
  - shadows.glow: 0 0 24px rgba(accent,0.2)
  - typography: NotoSansKR
  - radius.lg: 12px
  - Brand DNA: "어두운 고딕 성당의 황금빛 햇살"
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, os

W, H = 1080, 1920  # 세로 포스터 (인스타/모바일 최적)
img = Image.new('RGB', (W, H), '#0a0a0a')
draw = ImageDraw.Draw(img)

# ── 배경: 다크 그라디언트 (135deg 시뮬레이션) ──
for y in range(H):
    ratio = y / H
    # void → base → raised 3단 그라디언트
    if ratio < 0.3:
        r = int(10 + ratio * 20)
        g = int(10 + ratio * 30)
        b = int(20 + ratio * 40)
    elif ratio < 0.7:
        r = int(12 + (ratio - 0.3) * 15)
        g = int(17 + (ratio - 0.3) * 10)
        b = int(27 + (ratio - 0.3) * 20)
    else:
        r = int(15 - (ratio - 0.7) * 15)
        g = int(20 - (ratio - 0.7) * 15)
        b = int(33 - (ratio - 0.7) * 20)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# ── 별 필드 (밤하늘) ──
import random
random.seed(42)
for _ in range(200):
    x = random.randint(0, W)
    y = random.randint(0, int(H * 0.55))
    size = random.randint(1, 3)
    alpha = random.randint(80, 220)
    draw.ellipse([x-size, y-size, x+size, y+size], fill=(255, 255, 255, alpha))

# ── 황금빛 역광 글로우 (중앙 상단) ──
glow_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
glow_draw = ImageDraw.Draw(glow_layer)

# 메인 골드 글로우
cx, cy = W // 2, int(H * 0.28)
for radius in range(350, 0, -2):
    alpha = int(40 * (1 - radius / 350))
    # 황금빛: RGB(255, 184, 0) = #FFB800
    r_col = 255
    g_col = int(184 + (255 - 184) * (1 - radius / 350))
    b_col = int(0 + 80 * (1 - radius / 350))
    glow_draw.ellipse([cx-radius, cy-radius, cx+radius, cy+radius],
                      fill=(r_col, g_col, b_col, alpha))

# 보조 시안 글로우 (하단)
cx2, cy2 = W // 2, int(H * 0.85)
for radius in range(200, 0, -2):
    alpha = int(20 * (1 - radius / 200))
    glow_draw.ellipse([cx2-radius, cy2-radius, cx2+radius, cy2+radius],
                      fill=(0, 168, 255, alpha))

glow_blurred = glow_layer.filter(ImageFilter.GaussianBlur(radius=60))
img_rgba = img.convert('RGBA')
img_rgba = Image.alpha_composite(img_rgba, glow_blurred)

# ── 소나무 실루엣 (하단) ──
tree_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
tree_draw = ImageDraw.Draw(tree_layer)

def draw_pine(d, cx, base_y, height, width):
    """간단한 소나무 실루엣"""
    color = (8, 15, 10, 200)
    # 줄기
    d.rectangle([cx-4, base_y-height*0.3, cx+4, base_y], fill=color)
    # 삼각형 나뭇잎 3단
    for i, (h_ratio, w_ratio) in enumerate([(0.4, 0.6), (0.3, 0.8), (0.25, 1.0)]):
        top_y = base_y - height + height * (i * 0.2)
        bot_y = top_y + height * h_ratio
        w = width * w_ratio
        d.polygon([(cx, top_y), (cx - w, bot_y), (cx + w, bot_y)], fill=color)

tree_positions = [
    (80, H - 30, 280, 50), (200, H - 20, 320, 55), (350, H - 35, 250, 45),
    (500, H - 25, 300, 52), (650, H - 30, 270, 48), (780, H - 20, 310, 54),
    (900, H - 35, 260, 46), (1020, H - 25, 290, 50),
    (140, H - 15, 200, 35), (430, H - 10, 180, 32), (720, H - 15, 210, 38),
    (950, H - 10, 190, 34),
]
for cx, by, h, w in tree_positions:
    draw_pine(tree_draw, cx, by, h, w)

img_rgba = Image.alpha_composite(img_rgba, tree_layer)

# ── 글래스모피즘 카드 (메인 정보) ──
glass_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
glass_draw = ImageDraw.Draw(glass_layer)

# 메인 카드 — 제목 영역
card_x1, card_y1 = 60, int(H * 0.35)
card_x2, card_y2 = W - 60, int(H * 0.62)
radius_lg = 12

# 글래스 배경
glass_draw.rounded_rectangle(
    [card_x1, card_y1, card_x2, card_y2],
    radius=radius_lg,
    fill=(255, 255, 255, 10),       # opacity.subtle = 0.04 → ~10/255
    outline=(255, 255, 255, 20),    # border opacity 0.08
    width=1
)

# 상단 악센트 보더 (골드)
glass_draw.line(
    [(card_x1 + radius_lg, card_y1), (card_x2 - radius_lg, card_y1)],
    fill=(255, 184, 0, 180), width=3
)

# 하단 정보 카드
info_y1 = int(H * 0.65)
info_y2 = int(H * 0.82)
glass_draw.rounded_rectangle(
    [80, info_y1, W - 80, info_y2],
    radius=radius_lg,
    fill=(255, 255, 255, 8),
    outline=(255, 255, 255, 15),
    width=1
)

img_rgba = Image.alpha_composite(img_rgba, glass_layer)

# ── 텍스트 ──
text_layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
text_draw = ImageDraw.Draw(text_layer)

# 폰트 로드
font_path = 'C:/Windows/Fonts/NotoSansKR-VF.ttf'
noto_path_serif = 'C:/Windows/Fonts/NotoSerifKR-VF.ttf'

def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', size)

font_label = load_font(font_path, 22)
font_year = load_font(font_path, 28)
font_theme_sub = load_font(font_path, 30)
font_theme = load_font(font_path, 72)
font_title = load_font(font_path, 48)
font_info = load_font(font_path, 26)
font_info_bold = load_font(font_path, 28)
font_verse = load_font(noto_path_serif, 22)
font_church = load_font(font_path, 32)

# 상단 라벨
label = "SUMMER BIBLE SCHOOL 2026"
bbox = text_draw.textbbox((0, 0), label, font=font_label)
lw = bbox[2] - bbox[0]
text_draw.text(((W - lw) // 2, int(H * 0.08)), label,
               fill=(0, 168, 255, 200), font=font_label)

# 십자가 + 빛 심볼 (간단한 텍스트 심볼)
cross = "+"
font_cross = load_font(font_path, 120)
bbox = text_draw.textbbox((0, 0), cross, font=font_cross)
cw = bbox[2] - bbox[0]
text_draw.text(((W - cw) // 2, int(H * 0.13)), cross,
               fill=(255, 200, 50, 150), font=font_cross)

# 메인 테마 (카드 안)
theme_sub = "하나님을 알아가는 여정"
bbox = text_draw.textbbox((0, 0), theme_sub, font=font_theme_sub)
tw = bbox[2] - bbox[0]
text_draw.text(((W - tw) // 2, int(H * 0.37)), theme_sub,
               fill=(200, 200, 210, 200), font=font_theme_sub)

# 메인 제목
main_title = "땅에서"
bbox = text_draw.textbbox((0, 0), main_title, font=font_theme)
tw = bbox[2] - bbox[0]
text_draw.text(((W - tw) // 2, int(H * 0.42)), main_title,
               fill=(255, 245, 230, 255), font=font_theme)

main_title2 = "진리를 배우다"
bbox = text_draw.textbbox((0, 0), main_title2, font=font_theme)
tw = bbox[2] - bbox[0]
text_draw.text(((W - tw) // 2, int(H * 0.48)), main_title2,
               fill=(255, 184, 0, 255), font=font_theme)

# 부제
subtitle = "2026 여름성경학교"
bbox = text_draw.textbbox((0, 0), subtitle, font=font_title)
tw = bbox[2] - bbox[0]
text_draw.text(((W - tw) // 2, int(H * 0.56)), subtitle,
               fill=(200, 210, 220, 230), font=font_title)

# 정보 카드 내용
info_items = [
    ("DATE", "2026. 7. 21 (월) ~ 7. 25 (금)"),
    ("TIME", "오전 9:00 ~ 오후 1:00"),
    ("PLACE", "교육관 3층 대예배실"),
    ("AGE", "유치부 ~ 초등부 (5세 ~ 12세)"),
]

info_start_y = int(H * 0.67)
for i, (label_text, value) in enumerate(info_items):
    y = info_start_y + i * 42
    # 라벨 (시안)
    text_draw.text((120, y), label_text, fill=(0, 168, 255, 200), font=font_label)
    # 값
    text_draw.text((250, y - 2), value, fill=(220, 220, 230, 240), font=font_info)

# 성경 구절
verse = '"하나님이 지으신 모든 것을 보시니 보시기에 심히 좋았더라" — 창세기 1:31'
bbox = text_draw.textbbox((0, 0), verse, font=font_verse)
vw = bbox[2] - bbox[0]
text_draw.text(((W - vw) // 2, int(H * 0.86)), verse,
               fill=(180, 170, 150, 180), font=font_verse)

# 교회 이름
church = "대한예수교장로회 OO교회"
bbox = text_draw.textbbox((0, 0), church, font=font_church)
cw = bbox[2] - bbox[0]
text_draw.text(((W - cw) // 2, int(H * 0.91)), church,
               fill=(150, 160, 170, 200), font=font_church)

img_rgba = Image.alpha_composite(img_rgba, text_layer)

# ── 최종 저장 ──
output_path = os.path.join(os.path.dirname(__file__), 'summer_bible_school_poster.png')
img_rgba.convert('RGB').save(output_path, quality=95)
print(f"Poster saved: {output_path}")
print(f"Size: {W}x{H}")
