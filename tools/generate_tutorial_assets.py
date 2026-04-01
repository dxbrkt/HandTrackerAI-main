from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH = 450
HEIGHT = 378
ASSETS_DIR = (
    Path(__file__).resolve().parent.parent / "src" / "handtracker_ai" / "pngfortutor"
)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_background() -> Image.Image:
    base = Image.new("RGB", (WIDTH, HEIGHT), "#0a0e16")
    draw = ImageDraw.Draw(base)
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        r = int(10 + 18 * (1 - t))
        g = int(14 + 12 * (1 - t))
        b = int(22 + 22 * (1 - t))
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((250, 30, 520, 260), fill=(120, 150, 255, 42))
    glow_draw.ellipse((-80, 10, 180, 250), fill=(255, 180, 120, 26))
    glow = glow.filter(ImageFilter.GaussianBlur(34))
    base = Image.alpha_composite(base.convert("RGBA"), glow)

    panel = ImageDraw.Draw(base)
    panel.rounded_rectangle(
        (4, 4, WIDTH - 4, HEIGHT - 4),
        radius=14,
        outline=(115, 122, 140, 180),
        width=2,
    )
    panel.rectangle((0, HEIGHT - 86, WIDTH, HEIGHT), fill=(18, 21, 28, 255))
    panel.line((0, HEIGHT - 86, WIDTH, HEIGHT - 86), fill=(86, 92, 110, 255), width=2)
    return base.convert("RGB")


def draw_monitor(draw: ImageDraw.ImageDraw, area: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = area
    draw.rounded_rectangle((x0, y0, x1, y1), radius=10, fill="#2d3343", outline="#8f98ad", width=2)
    draw.rounded_rectangle((x0 + 10, y0 + 10, x1 - 10, y1 - 14), radius=8, fill="#54637f")
    draw.rectangle((x0 + 65, y1, x1 - 65, y1 + 14), fill="#bfc5d6")
    draw.polygon(
        [(x0 + 92, y1 + 14), (x1 - 92, y1 + 14), (x1 - 70, y1 + 36), (x0 + 70, y1 + 36)],
        fill="#8e96a8",
    )


def draw_scroll_icon(draw: ImageDraw.ImageDraw, center: tuple[int, int], up: bool) -> None:
    cx, cy = center
    draw.rounded_rectangle((cx - 34, cy - 48, cx + 34, cy + 48), radius=18, fill="#f3f5fb", outline="#d2d7e5", width=2)
    draw.rounded_rectangle((cx - 8, cy - 34, cx + 8, cy + 34), radius=8, fill="#d9deea")
    if up:
        arrow = [(cx, cy - 28), (cx - 22, cy + 2), (cx - 8, cy + 2), (cx - 8, cy + 28), (cx + 8, cy + 28), (cx + 8, cy + 2), (cx + 22, cy + 2)]
    else:
        arrow = [(cx, cy + 28), (cx - 22, cy - 2), (cx - 8, cy - 2), (cx - 8, cy - 28), (cx + 8, cy - 28), (cx + 8, cy - 2), (cx + 22, cy - 2)]
    draw.polygon(arrow, fill="#4c74ff")


def draw_volume_icon(draw: ImageDraw.ImageDraw, center: tuple[int, int], down: bool) -> None:
    cx, cy = center
    draw.polygon(
        [(cx - 42, cy - 12), (cx - 24, cy - 12), (cx - 4, cy - 28), (cx - 4, cy + 28), (cx - 24, cy + 12), (cx - 42, cy + 12)],
        fill="#d7dceb",
        outline="#9ca8c2",
    )
    for offset in (10, 24):
        draw.arc((cx - 2, cy - offset, cx + 24 + offset, cy + offset), start=308, end=52, fill="#8e9aba", width=4)
    color = "#e25656" if down else "#9cdd67"
    draw.rectangle((cx + 48, cy - 34, cx + 58, cy + 34), fill=color)
    if down:
        draw.rectangle((cx + 34, cy - 5, cx + 72, cy + 5), fill=color)


def draw_hand(draw: ImageDraw.ImageDraw, pose: str) -> None:
    skin = "#efb087"
    skin_shadow = "#db9a73"
    outline = "#c48061"

    palm = (86, 118, 246, 292)
    draw.rounded_rectangle(palm, radius=80, fill=skin, outline=outline, width=3)
    draw.ellipse((112, 270, 228, 342), fill=skin_shadow, outline=outline, width=2)

    if pose == "thumbs_down":
        for rect in ((96, 134, 144, 238), (138, 126, 186, 222), (180, 132, 226, 226), (216, 148, 256, 234)):
            draw.rounded_rectangle(rect, radius=22, fill=skin, outline=outline, width=3)
        draw.rounded_rectangle((198, 220, 264, 346), radius=28, fill=skin, outline=outline, width=3)
    else:
        draw.rounded_rectangle((90, 112, 136, 292), radius=24, fill=skin, outline=outline, width=3)
        draw.rounded_rectangle((138, 86, 186, 274), radius=24, fill=skin, outline=outline, width=3)
        draw.rounded_rectangle((186, 144, 230, 236), radius=20, fill=skin, outline=outline, width=3)
        draw.rounded_rectangle((220, 154, 260, 228), radius=18, fill=skin, outline=outline, width=3)
        draw.rounded_rectangle((70, 220, 120, 318), radius=24, fill=skin, outline=outline, width=3)


def draw_caption(draw: ImageDraw.ImageDraw, text: str) -> None:
    font = load_font(38, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(((WIDTH - text_width) / 2, HEIGHT - 63), text, fill="#f5f7fb", font=font)


def build_card(filename: str, pose: str, detail: str, caption: str) -> None:
    image = make_background()
    draw = ImageDraw.Draw(image)

    if pose == "thumbs_down":
        draw_hand(draw, "thumbs_down")
        draw_volume_icon(draw, (338, 150), down=True)
    else:
        draw_hand(draw, "two_fingers")
        draw_monitor(draw, (270, 58, 428, 184))
        draw_scroll_icon(draw, (349, 157), up=pose == "two_fingers_up")

    subtitle_font = load_font(20, bold=False)
    draw.text((28, 28), detail, fill="#c3cadc", font=subtitle_font)
    draw_caption(draw, caption)
    image.save(ASSETS_DIR / f"{filename}.png")


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    build_card("volumedown", "thumbs_down", "thumbs_down", "thumbs_down")
    build_card("twofingersup", "two_fingers_up", "two_fingers_up", "two_fingers_up")
    build_card("twofingersdown", "two_fingers_down", "two_fingers_down", "two_fingers_down")


if __name__ == "__main__":
    main()
