from __future__ import annotations
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


SIZE = 1024
ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
ICONSET_DIR = ASSETS_DIR / "HandTrackerAI.iconset"
MASTER_ICON = ASSETS_DIR / "handtracker_icon_master.png"
ICNS_ICON = ASSETS_DIR / "HandTrackerAI.icns"


def rounded_rectangle_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def draw_star_icon(size: int = SIZE) -> Image.Image:
    final = Image.new("RGBA", (size, size), "#030303")

    outer_glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    outer_glow_draw = ImageDraw.Draw(outer_glow)
    outer_glow_draw.ellipse(
        (size * 0.22, size * 0.22, size * 0.78, size * 0.78),
        fill=(255, 255, 255, 22),
    )
    outer_glow = outer_glow.filter(ImageFilter.GaussianBlur(radius=size * 0.1))
    final.alpha_composite(outer_glow)

    inner_glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner_glow_draw = ImageDraw.Draw(inner_glow)
    inner_glow_draw.ellipse(
        (size * 0.31, size * 0.31, size * 0.69, size * 0.69),
        fill=(255, 255, 255, 34),
    )
    inner_glow = inner_glow.filter(ImageFilter.GaussianBlur(radius=size * 0.055))
    final.alpha_composite(inner_glow)

    star = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(star)
    center = size * 0.5
    left = size * 0.095
    right = size * 0.905
    top = size * 0.105
    bottom = size * 0.895
    body = size * 0.12

    points = [
        (center, top),
        (center + body * 0.38, center - body * 0.38),
        (right, center),
        (center + body * 0.38, center + body * 0.38),
        (center, bottom),
        (center - body * 0.38, center + body * 0.38),
        (left, center),
        (center - body * 0.38, center - body * 0.38),
    ]
    draw.polygon(points, fill=(255, 255, 255, 255))

    bright_core = star.filter(ImageFilter.GaussianBlur(radius=size * 0.004))
    medium_bloom = star.filter(ImageFilter.GaussianBlur(radius=size * 0.024))
    soft_bloom = star.filter(ImageFilter.GaussianBlur(radius=size * 0.06))
    final.alpha_composite(soft_bloom)
    final.alpha_composite(medium_bloom)
    final.alpha_composite(bright_core)

    mask = rounded_rectangle_mask(size, int(size * 0.22))
    final.putalpha(mask)
    return final


def save_iconset(master: Image.Image) -> None:
    ICONSET_DIR.mkdir(parents=True, exist_ok=True)

    sizes = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }

    for filename, icon_size in sizes.items():
        resized = master.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        resized.save(ICONSET_DIR / filename)


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    master = draw_star_icon()
    master.save(MASTER_ICON)
    master.save(ICNS_ICON)
    save_iconset(master)
    


if __name__ == "__main__":
    main()
