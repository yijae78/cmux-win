"""
cmux-win Icon Generator v2 — Bold, crisp, high-contrast
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

SIZE = 512
CENTER = SIZE // 2
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")

# --- Colors (fully opaque, high contrast) ---
BG = (15, 15, 30)
CYAN = (0, 220, 255)
CYAN_BRIGHT = (100, 240, 255)
WHITE = (240, 245, 255)
PANEL_BG = (25, 28, 45)
PANEL_BORDER = (0, 180, 220)
GREEN = (0, 255, 120)
YELLOW = (255, 210, 0)
RED = (255, 80, 80)


def create_icon():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Background: solid rounded square ---
    pad = 20
    draw.rounded_rectangle((pad, pad, SIZE - pad, SIZE - pad), radius=72, fill=BG)

    # --- Bright cyan border ---
    draw.rounded_rectangle((pad, pad, SIZE - pad, SIZE - pad), radius=72,
                           outline=CYAN, width=4)

    # === THREE SOLID PANELS ===

    # Panel 1 (back-left)
    p1 = (65, 90, 265, 340)
    draw.rounded_rectangle(p1, radius=10, fill=(35, 38, 58), outline=(0, 150, 190), width=2)
    draw.rectangle([p1[0]+2, p1[1]+2, p1[2]-2, p1[1]+30], fill=(0, 150, 190))
    # dots
    for i, c in enumerate([RED, YELLOW, GREEN]):
        draw.ellipse([p1[0]+12+i*16, p1[1]+9, p1[0]+22+i*16, p1[1]+19], fill=c)
    # lines
    for i in range(4):
        lw = [130, 90, 150, 60][i]
        y = p1[1] + 44 + i * 18
        draw.rectangle([p1[0]+14, y, p1[0]+14+lw, y+5], fill=(0, 150, 190, 180))

    # Panel 2 (back-right)
    p2 = (245, 70, 445, 330)
    draw.rounded_rectangle(p2, radius=10, fill=(35, 38, 58), outline=(0, 150, 190), width=2)
    draw.rectangle([p2[0]+2, p2[1]+2, p2[2]-2, p2[1]+30], fill=(0, 150, 190))
    for i, c in enumerate([RED, YELLOW, GREEN]):
        draw.ellipse([p2[0]+12+i*16, p2[1]+9, p2[0]+22+i*16, p2[1]+19], fill=c)
    for i in range(4):
        lw = [140, 100, 80, 120][i]
        y = p2[1] + 44 + i * 18
        draw.rectangle([p2[0]+14, y, p2[0]+14+lw, y+5], fill=(0, 150, 190, 180))

    # Panel 3 (front-center, MAIN — biggest, brightest)
    p3 = (120, 150, 395, 400)
    draw.rounded_rectangle(p3, radius=12, fill=PANEL_BG, outline=CYAN, width=3)
    # Title bar
    draw.rectangle([p3[0]+3, p3[1]+3, p3[2]-3, p3[1]+34], fill=(0, 60, 80))
    # Dots
    for i, c in enumerate([RED, YELLOW, GREEN]):
        draw.ellipse([p3[0]+16+i*18, p3[1]+11, p3[0]+28+i*18, p3[1]+23], fill=c)

    # === LARGE CHEVRON ">" IN MAIN PANEL ===
    cx = CENTER + 5
    cy = p3[1] + 140
    sz = 65

    chevron_pts = [
        (cx - sz, cy - sz),
        (cx + sz - 20, cy),
        (cx - sz, cy + sz),
    ]
    # Bold chevron
    draw.line(chevron_pts, fill=CYAN_BRIGHT, width=14, joint="curve")

    # Cursor bar
    draw.rectangle([cx + sz, cy - 28, cx + sz + 10, cy + 28], fill=CYAN_BRIGHT)

    # Terminal text lines inside main panel (below chevron)
    text_y = cy + sz + 20
    for i in range(3):
        lw = [180, 120, 200][i]
        draw.rectangle([p3[0]+24, text_y, p3[0]+24+lw, text_y+6], fill=CYAN)
        text_y += 18

    # === "cmux" LABEL ===
    try:
        font_path = os.path.join(os.path.expanduser("~"), ".claude", "skills",
                                 "canvas-design", "canvas-fonts", "GeistMono-Bold.ttf")
        font_label = ImageFont.truetype(font_path, 44)
    except Exception:
        font_label = ImageFont.load_default()

    label = "cmux"
    bbox = draw.textbbox((0, 0), label, font=font_label)
    lw = bbox[2] - bbox[0]
    lx = CENTER - lw // 2
    ly = SIZE - pad - 72
    draw.text((lx, ly), label, fill=CYAN_BRIGHT, font=font_label)

    # === Save ===
    os.makedirs(OUT_DIR, exist_ok=True)

    # 256x256 PNG
    icon_256 = img.resize((256, 256), Image.LANCZOS)
    png_path = os.path.join(OUT_DIR, "icon.png")
    icon_256.save(png_path, "PNG")
    print(f"  PNG: {png_path}")

    # ICO (multi-size)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_images = [img.resize((s, s), Image.LANCZOS) for s in sizes]
    ico_path = os.path.join(OUT_DIR, "icon.ico")
    ico_images[0].save(ico_path, format="ICO",
                       sizes=[(s, s) for s in sizes],
                       append_images=ico_images[1:])
    print(f"  ICO: {ico_path}")

    # 512px
    png_512 = os.path.join(OUT_DIR, "icon-512.png")
    img.save(png_512, "PNG")
    print(f"  512: {png_512}")

    return png_path, ico_path


if __name__ == "__main__":
    print("Generating cmux-win icon v2 (bold/crisp)...")
    create_icon()
    print("Done!")
