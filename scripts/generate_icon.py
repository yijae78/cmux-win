"""
cmux-win Icon Generator v4 — Office-Monitor 스타일 참고
크고 굵은 CW + 체브론 + 밝은 시안 링 + 심플/선명
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, math

SIZE = 512
CENTER = SIZE // 2
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")

# ── Colors ──
BG_DARK    = (12, 17, 35)      # 다크 네이비
BG_CENTER  = (18, 26, 55)      # 중앙 약간 밝은 네이비
CYAN       = (0, 200, 255)     # 체브론용 시안
CYAN_LT    = (80, 220, 255)    # 밝은 시안
CYAN_GLOW  = (0, 180, 255)     # 글로우용
NEON_RED   = (255, 30, 60)     # 네온 레드 (테두리)
NEON_RED_LT = (255, 80, 100)   # 밝은 네온 레드
NEON_RED_GLOW = (255, 20, 50)  # 글로우용
WHITE      = (255, 255, 255)
GOLD_DOT   = (255, 140, 60)    # 악센트 도트


def radial_gradient_circle(size, cx, cy, r_inner, r_outer, color_inner, color_outer):
    """원형 방사형 그라디언트."""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    for y in range(size[1]):
        for x in range(size[0]):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            if dist > r_outer:
                continue
            if dist < r_inner:
                t = 0
            else:
                t = (dist - r_inner) / (r_outer - r_inner)
            r = int(color_inner[0] + (color_outer[0] - color_inner[0]) * t)
            g = int(color_inner[1] + (color_outer[1] - color_inner[1]) * t)
            b = int(color_inner[2] + (color_outer[2] - color_inner[2]) * t)
            a = int(color_inner[3] + (color_outer[3] - color_inner[3]) * t)
            img.putpixel((x, y), (r, g, b, a))
    return img


def create_icon():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))

    # ═══ 1. 외곽 글로잉 링 (Office-Monitor 스타일) ═══
    ring_layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring_layer)

    # 외곽 네온 레드 글로우 (큰 원, 블러 2겹)
    glow_outer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_outer)
    gd.ellipse([10, 10, SIZE-10, SIZE-10], fill=(*NEON_RED_GLOW, 70))
    glow_outer = glow_outer.filter(ImageFilter.GaussianBlur(30))
    img = Image.alpha_composite(img, glow_outer)
    glow_outer2 = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(glow_outer2)
    gd2.ellipse([18, 18, SIZE-18, SIZE-18], fill=(*NEON_RED, 50))
    glow_outer2 = glow_outer2.filter(ImageFilter.GaussianBlur(15))
    img = Image.alpha_composite(img, glow_outer2)

    # 밝은 네온 레드 링 (두꺼운 원형 테두리)
    rd.ellipse([24, 24, SIZE-24, SIZE-24], fill=(*NEON_RED, 255))
    # 안쪽 잘라내기 (도넛 모양)
    rd.ellipse([52, 52, SIZE-52, SIZE-52], fill=(0, 0, 0, 0))
    img = Image.alpha_composite(img, ring_layer)

    # ═══ 2. 내부 다크 원형 배경 ═══
    inner_layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    ind = ImageDraw.Draw(inner_layer)

    # 다크 원
    ind.ellipse([50, 50, SIZE-50, SIZE-50], fill=(*BG_DARK, 255))

    # 중앙 살짝 밝은 그라디언트 느낌
    inner_glow = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    igd = ImageDraw.Draw(inner_glow)
    igd.ellipse([100, 100, SIZE-100, SIZE-100], fill=(*BG_CENTER, 120))
    inner_glow = inner_glow.filter(ImageFilter.GaussianBlur(40))
    inner_layer = Image.alpha_composite(inner_layer, inner_glow)

    # 내부 얇은 네온 레드 서클 라인
    ind2 = ImageDraw.Draw(inner_layer)
    ind2.ellipse([58, 58, SIZE-58, SIZE-58], outline=(*NEON_RED, 50), width=1)

    img = Image.alpha_composite(img, inner_layer)

    # ═══ 3. "CW" 텍스트 — 크고 굵게 ═══
    text_layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_layer)

    # Impact 폰트 우선 (초압축 굵은체 — 2글자도 크게 들어감)
    font_cw = None
    for fp, sz in [
        ("C:/Windows/Fonts/impact.ttf", 240),      # Impact — 가장 굵고 좁음
        ("C:/Windows/Fonts/arialbd.ttf", 210),
        ("C:/Windows/Fonts/segoeuib.ttf", 200),
    ]:
        try:
            font_cw = ImageFont.truetype(fp, sz)
            break
        except:
            continue
    if font_cw is None:
        font_cw = ImageFont.load_default()

    label = "CW"
    bbox = td.textbbox((0, 0), label, font=font_cw)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = CENTER - tw // 2
    ty = CENTER - th // 2 - 15  # 거의 정중앙 (체브론 작게)

    # 1) 텍스트 드롭 섀도우 (깊이감)
    shadow_text = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(shadow_text).text((tx + 4, ty + 4), label, fill=(0, 0, 0, 200), font=font_cw)
    shadow_text = shadow_text.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, shadow_text)

    # 2) 넓은 글로우 (원거리)
    glow_text = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(glow_text).text((tx, ty), label, fill=(255, 255, 255, 140), font=font_cw)
    glow_text = glow_text.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img, glow_text)

    # 3) 좁은 글로우 (근거리 — 선명도 부스트)
    glow_text2 = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(glow_text2).text((tx, ty), label, fill=(255, 255, 255, 220), font=font_cw)
    glow_text2 = glow_text2.filter(ImageFilter.GaussianBlur(4))
    img = Image.alpha_composite(img, glow_text2)

    # 4) 순백색 텍스트 (최대 밝기, 선명)
    td.text((tx, ty), label, fill=(255, 255, 255, 255), font=font_cw)
    img = Image.alpha_composite(img, text_layer)

    # ═══ 4. 체브론 ">" — CW 아래에 ═══
    chev_layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    cd = ImageDraw.Draw(chev_layer)

    chev_cx = CENTER + 30
    chev_cy = CENTER + 120  # CW 바로 아래
    chev_size = 22  # 작고 깔끔하게

    # 체브론 글로우
    glow_chev = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    gcd = ImageDraw.Draw(glow_chev)
    pts = [
        (chev_cx - chev_size, chev_cy - chev_size * 0.7),
        (chev_cx + chev_size * 0.5, chev_cy),
        (chev_cx - chev_size, chev_cy + chev_size * 0.7),
    ]
    gcd.line(pts, fill=(*CYAN, 100), width=10, joint="curve")
    glow_chev = glow_chev.filter(ImageFilter.GaussianBlur(5))
    img = Image.alpha_composite(img, glow_chev)

    # 선명한 체브론
    cd.line(pts, fill=(*CYAN_LT, 255), width=6, joint="curve")
    # 커서 바
    cur_x = chev_cx + chev_size * 0.6
    cd.rectangle([cur_x, chev_cy - 10, cur_x + 4, chev_cy + 10], fill=(*CYAN_LT, 240))
    img = Image.alpha_composite(img, chev_layer)

    # ═══ 5. 악센트 도트 (우상단, Office-Monitor 스타일) ═══
    dot_layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dot_layer)

    dot_cx, dot_cy = SIZE - 75, 65
    # 도트 글로우
    glow_dot = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(glow_dot).ellipse([dot_cx-14, dot_cy-14, dot_cx+14, dot_cy+14],
                                      fill=(*GOLD_DOT, 60))
    glow_dot = glow_dot.filter(ImageFilter.GaussianBlur(8))
    img = Image.alpha_composite(img, glow_dot)
    # 선명한 도트
    dd.ellipse([dot_cx-8, dot_cy-8, dot_cx+8, dot_cy+8], fill=(*GOLD_DOT, 220))
    img = Image.alpha_composite(img, dot_layer)

    # ═══ 6. 저장 ═══
    os.makedirs(OUT_DIR, exist_ok=True)

    # 512px
    img.save(os.path.join(OUT_DIR, 'icon-512.png'), 'PNG')
    print(f"  512px: {os.path.join(OUT_DIR, 'icon-512.png')}")

    # 256px
    icon_256 = img.resize((256, 256), Image.LANCZOS)
    icon_256.save(os.path.join(OUT_DIR, 'icon.png'), 'PNG')
    print(f"  256px: {os.path.join(OUT_DIR, 'icon.png')}")

    # ICO
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_imgs = [img.resize((s, s), Image.LANCZOS) for s in ico_sizes]
    ico_path = os.path.join(OUT_DIR, 'icon.ico')
    ico_imgs[0].save(ico_path, format='ICO',
                     sizes=[(s, s) for s in ico_sizes],
                     append_images=ico_imgs[1:])
    print(f"  ICO:   {ico_path}")

    # Preview
    preview = img.resize((128, 128), Image.LANCZOS)
    preview.save(os.path.join(OUT_DIR, 'icon_preview.png'), 'PNG')
    print(f"  Preview: {os.path.join(OUT_DIR, 'icon_preview.png')}")


if __name__ == '__main__':
    print("Generating cmux-win icon v4 (Office-Monitor style)...")
    create_icon()
    print("Done!")
