"""설교 이미지 편집 도구 — NLM 슬라이드에서 추출한 이미지를 PPT용으로 가공"""

import sys
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

# === 편집 기능 모음 ===

def crop_image(img_path, output_path, left=0, top=0, right=0, bottom=0):
    """이미지 자르기 (가장자리 제거)

    Args:
        img_path: 원본 이미지 경로
        output_path: 저장 경로
        left, top, right, bottom: 잘라낼 픽셀 수 (가장자리에서 안쪽으로)
    """
    img = Image.open(img_path)
    w, h = img.size
    cropped = img.crop((left, top, w - right, h - bottom))
    cropped.save(output_path, quality=95)
    print(f"  Cropped: {img.size} → {cropped.size} → {output_path}")
    return cropped


def crop_ratio(img_path, output_path, top_pct=0, bottom_pct=0, left_pct=0, right_pct=0):
    """비율 기반 자르기 (% 단위)

    Args:
        top_pct: 상단에서 잘라낼 비율 (0~100)
        bottom_pct: 하단에서 잘라낼 비율 (0~100)
        left_pct: 좌측에서 잘라낼 비율 (0~100)
        right_pct: 우측에서 잘라낼 비율 (0~100)
    """
    img = Image.open(img_path)
    w, h = img.size
    left = int(w * left_pct / 100)
    top = int(h * top_pct / 100)
    right = int(w * (100 - right_pct) / 100)
    bottom = int(h * (100 - bottom_pct) / 100)
    cropped = img.crop((left, top, right, bottom))
    cropped.save(output_path, quality=95)
    print(f"  Crop({top_pct}%/{bottom_pct}%/{left_pct}%/{right_pct}%): {img.size} → {cropped.size}")
    return cropped


def resize_to_slide(img_path, output_path, width=1920, height=1080):
    """PPT 슬라이드 크기(16:9)로 리사이즈 — 비율 유지하며 fit"""
    img = Image.open(img_path)
    img_ratio = img.width / img.height
    target_ratio = width / height

    if img_ratio > target_ratio:
        # 이미지가 더 넓음 → 높이 기준으로 맞추고 좌우 크롭
        new_h = height
        new_w = int(height * img_ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - width) // 2
        img = img.crop((left, 0, left + width, height))
    else:
        # 이미지가 더 높음 → 너비 기준으로 맞추고 상하 크롭
        new_w = width
        new_h = int(width / img_ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        top = (new_h - height) // 2
        img = img.crop((0, top, width, top + height))

    img.save(output_path, quality=95)
    print(f"  Resized to {width}x{height} → {output_path}")
    return img


def add_gradient_overlay(img_path, output_path, direction="bottom", color=(0, 0, 0), intensity=0.7):
    """그라데이션 오버레이 추가 (텍스트 영역 가리기용)

    Args:
        direction: "top", "bottom", "left", "right"
        color: RGB 튜플
        intensity: 최대 불투명도 (0~1)
    """
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    max_alpha = int(255 * intensity)

    if direction == "bottom":
        for y in range(h // 3, h):
            alpha = int(max_alpha * (y - h // 3) / (h * 2 // 3))
            draw.rectangle([(0, y), (w, y + 1)], fill=(*color, min(alpha, max_alpha)))
    elif direction == "top":
        for y in range(0, h * 2 // 3):
            alpha = int(max_alpha * (1 - y / (h * 2 // 3)))
            draw.rectangle([(0, y), (w, y + 1)], fill=(*color, min(alpha, max_alpha)))
    elif direction == "left":
        for x in range(0, w * 2 // 3):
            alpha = int(max_alpha * (1 - x / (w * 2 // 3)))
            draw.rectangle([(x, 0), (x + 1, h)], fill=(*color, min(alpha, max_alpha)))
    elif direction == "right":
        for x in range(w // 3, w):
            alpha = int(max_alpha * (x - w // 3) / (w * 2 // 3))
            draw.rectangle([(x, 0), (x + 1, h)], fill=(*color, min(alpha, max_alpha)))

    result = Image.alpha_composite(img, overlay).convert("RGB")
    result.save(output_path, quality=95)
    print(f"  Gradient({direction}, {intensity}) → {output_path}")
    return result


def darken_image(img_path, output_path, factor=0.6):
    """이미지 어둡게 (시네마틱 효과)

    Args:
        factor: 0.0(완전 검정) ~ 1.0(원본) ~ 2.0(밝게)
    """
    img = Image.open(img_path)
    enhancer = ImageEnhance.Brightness(img)
    result = enhancer.enhance(factor)
    result.save(output_path, quality=95)
    print(f"  Darkened(x{factor}) → {output_path}")
    return result


def increase_contrast(img_path, output_path, factor=1.3):
    """대비 강화"""
    img = Image.open(img_path)
    enhancer = ImageEnhance.Contrast(img)
    result = enhancer.enhance(factor)
    result.save(output_path, quality=95)
    print(f"  Contrast(x{factor}) → {output_path}")
    return result


def warm_tint(img_path, output_path, strength=30):
    """따뜻한 색조 (금빛 하이라이트 효과)"""
    img = Image.open(img_path).convert("RGB")
    r, g, b = img.split()
    r = r.point(lambda x: min(255, x + strength))
    g = g.point(lambda x: min(255, x + strength // 3))
    result = Image.merge("RGB", (r, g, b))
    result.save(output_path, quality=95)
    print(f"  Warm tint(+{strength}) → {output_path}")
    return result


def blur_region(img_path, output_path, region, radius=15):
    """특정 영역 블러 (텍스트 가리기용)

    Args:
        region: (left, top, right, bottom) 픽셀 좌표
        radius: 블러 강도
    """
    img = Image.open(img_path)
    box = img.crop(region)
    blurred = box.filter(ImageFilter.GaussianBlur(radius=radius))
    img.paste(blurred, region)
    img.save(output_path, quality=95)
    print(f"  Blur region{region} → {output_path}")
    return img


def fill_region(img_path, output_path, region, color=(15, 23, 42)):
    """특정 영역을 단색으로 채우기 (텍스트 완전 제거)

    Args:
        region: (left, top, right, bottom) 픽셀 좌표
        color: RGB 튜플 (기본: 다크 네이비)
    """
    img = Image.open(img_path)
    draw = ImageDraw.Draw(img)
    draw.rectangle(region, fill=color)
    img.save(output_path, quality=95)
    print(f"  Fill region{region} → {output_path}")
    return img


def extract_center(img_path, output_path, center_pct=60):
    """이미지 중앙부만 추출 (상하단 텍스트 제거)

    Args:
        center_pct: 중앙 영역 비율 (0~100)
    """
    margin = (100 - center_pct) / 2
    return crop_ratio(img_path, output_path, top_pct=margin, bottom_pct=margin)


def combine_horizontal(img_paths, output_path, gap=0):
    """이미지 가로 합성"""
    images = [Image.open(p) for p in img_paths]
    heights = [img.height for img in images]
    max_h = max(heights)

    # 높이 맞추기
    resized = []
    for img in images:
        if img.height != max_h:
            ratio = max_h / img.height
            img = img.resize((int(img.width * ratio), max_h), Image.LANCZOS)
        resized.append(img)

    total_w = sum(img.width for img in resized) + gap * (len(resized) - 1)
    result = Image.new("RGB", (total_w, max_h), (15, 23, 42))

    x = 0
    for img in resized:
        result.paste(img, (x, 0))
        x += img.width + gap

    result.save(output_path, quality=95)
    print(f"  Combined {len(images)} images → {output_path}")
    return result


# === 배치 처리 (JSON 명령 파일) ===

def process_batch(commands_file):
    """JSON 명령 파일로 배치 편집

    commands.json 예시:
    [
        {"action": "crop_ratio", "input": "slide_03.png", "output": "edited_03.png",
         "params": {"top_pct": 15, "bottom_pct": 10}},
        {"action": "darken", "input": "edited_03.png", "output": "final_03.png",
         "params": {"factor": 0.7}},
        {"action": "resize", "input": "final_03.png", "output": "final_03.png",
         "params": {"width": 1920, "height": 1080}}
    ]
    """
    with open(commands_file, 'r', encoding='utf-8') as f:
        commands = json.load(f)

    actions = {
        "crop": crop_image,
        "crop_ratio": crop_ratio,
        "resize": resize_to_slide,
        "gradient": add_gradient_overlay,
        "darken": darken_image,
        "contrast": increase_contrast,
        "warm": warm_tint,
        "blur": blur_region,
        "fill": fill_region,
        "center": extract_center,
    }

    for i, cmd in enumerate(commands):
        action = cmd["action"]
        inp = cmd["input"]
        out = cmd["output"]
        params = cmd.get("params", {})

        print(f"[{i+1}/{len(commands)}] {action}: {inp} → {out}")

        if action in actions:
            func = actions[action]
            func(inp, out, **params)
        elif action == "combine":
            combine_horizontal(cmd["inputs"], out, **params)
        else:
            print(f"  Unknown action: {action}")

    print(f"\nDone! {len(commands)} operations completed.")


# === CLI ===

def main():
    if len(sys.argv) < 2:
        print("""
사용법:
  python image_editor.py batch <commands.json>     — JSON 배치 처리
  python image_editor.py crop <input> <output> <top%> <bottom%>  — 상하 크롭
  python image_editor.py center <input> <output> [center%]       — 중앙 추출
  python image_editor.py darken <input> <output> [factor]        — 어둡게
  python image_editor.py resize <input> <output> [width] [height] — 리사이즈
  python image_editor.py warm <input> <output> [strength]        — 따뜻한 색조
  python image_editor.py gradient <input> <output> <direction>   — 그라데이션
        """)
        return

    action = sys.argv[1]

    if action == "batch":
        process_batch(sys.argv[2])
    elif action == "crop":
        crop_ratio(sys.argv[2], sys.argv[3],
                   top_pct=float(sys.argv[4]) if len(sys.argv) > 4 else 0,
                   bottom_pct=float(sys.argv[5]) if len(sys.argv) > 5 else 0)
    elif action == "center":
        extract_center(sys.argv[2], sys.argv[3],
                       center_pct=float(sys.argv[4]) if len(sys.argv) > 4 else 60)
    elif action == "darken":
        darken_image(sys.argv[2], sys.argv[3],
                     factor=float(sys.argv[4]) if len(sys.argv) > 4 else 0.6)
    elif action == "resize":
        resize_to_slide(sys.argv[2], sys.argv[3],
                        width=int(sys.argv[4]) if len(sys.argv) > 4 else 1920,
                        height=int(sys.argv[5]) if len(sys.argv) > 5 else 1080)
    elif action == "warm":
        warm_tint(sys.argv[2], sys.argv[3],
                  strength=int(sys.argv[4]) if len(sys.argv) > 4 else 30)
    elif action == "gradient":
        add_gradient_overlay(sys.argv[2], sys.argv[3],
                             direction=sys.argv[4] if len(sys.argv) > 4 else "bottom")
    else:
        print(f"Unknown action: {action}")


if __name__ == "__main__":
    main()
