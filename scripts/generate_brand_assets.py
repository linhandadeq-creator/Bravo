#!/usr/bin/env python3
"""Generate the Bravo brand assets: macOS .icns + web icons/favicon.

Design: an Apple-style continuous "squircle" tile with a diagonal indigo→sky
gradient, a soft top gloss and a bold rounded-white "Bravo" wordmark (matching
the reference wordmark). Deterministic; no external assets required.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SIZE = 1024
SUPER_ELLIPSE_N = 5.0
RADIUS_RATIO = 0.2237  # Apple-ish corner proportion (reference value)

COLOR_A = (79, 70, 229)    # indigo   #4F46E5  (top-left)
COLOR_B = (14, 165, 233)   # sky      #0EA5E9  (bottom-right)

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/SFNSRounded.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
]


def _squircle_mask(size: int, n: float) -> np.ndarray:
    ys, xs = np.mgrid[0:size, 0:size]
    half = (size - 1) / 2
    nx = (xs - half) / half
    ny = (ys - half) / half
    # soften with a small feather so edges are anti-aliased
    val = np.abs(nx) ** n + np.abs(ny) ** n
    inside = val <= 1.0
    edge = (val > 1.0) & (val <= 1.0 + 0.06)
    alpha = np.zeros((size, size), dtype=np.uint8)
    alpha[inside] = 255
    # simple 1px anti-alias on the boundary
    alpha[edge] = 160
    return alpha


def _gradient(size: int) -> np.ndarray:
    ys, xs = np.mgrid[0:size, 0:size]
    t = (xs + ys) / (2 * (size - 1))  # diagonal 0..1
    rgb = np.zeros((size, size, 3), dtype=np.float32)
    for channel in range(3):
        rgb[..., channel] = COLOR_A[channel] * (1 - t) + COLOR_B[channel] * t
    return rgb


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def build_master() -> Image.Image:
    alpha = _squircle_mask(SIZE, SUPER_ELLIPSE_N)
    rgb = _gradient(SIZE)

    # top gloss: subtle white highlight near the top
    ys = np.arange(SIZE)[:, None]
    gloss = np.clip(1.0 - ys / (SIZE * 0.55), 0.0, 1.0) ** 1.6 * 0.20
    rgb = rgb * (1 - gloss[..., None]) + 255 * gloss[..., None]

    tile = np.dstack([rgb.astype(np.uint8), alpha])

    # subtle inner light edge
    img = Image.fromarray(tile, "RGBA")
    edge = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle(
        [2, 2, SIZE - 3, SIZE - 3], radius=int(SIZE * RADIUS_RATIO),
        outline=(255, 255, 255, 60), width=3,
    )
    img = Image.alpha_composite(img, edge)

    # wordmark
    target_width = SIZE * 0.70
    font_size = 120
    font = _font(font_size)
    while True:
        bbox = font.getbbox("Bravo")
        width = bbox[2] - bbox[0]
        if width >= target_width or font_size > 900:
            break
        font_size += 8
        font = _font(font_size)

    bbox = font.getbbox("Bravo")
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((SIZE - text_w) / 2 - bbox[0], (SIZE - text_h) / 2 - bbox[1] - SIZE * 0.01)

    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text(
        (pos[0], pos[1] + 8), "Bravo", font=font, fill=(0, 0, 0, 70)
    )
    from PIL import ImageFilter

    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, shadow)

    text_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(text_layer).text(pos, "Bravo", font=font, fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, text_layer)
    return img


def write_icns(master: Image.Image, destination: Path) -> None:
    iconset = destination.with_suffix(".iconset")
    iconset.mkdir(parents=True, exist_ok=True)
    specs = [
        (16, "16x16"), (32, "16x16@2x"), (32, "32x32"), (64, "32x32@2x"),
        (128, "128x128"), (256, "128x128@2x"), (256, "256x256"),
        (512, "256x256@2x"), (512, "512x512"), (1024, "512x512@2x"),
    ]
    for px, name in specs:
        master.resize((px, px), Image.LANCZOS).save(iconset / f"icon_{name}.png")
    import subprocess

    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(destination)], check=True
    )
    for item in iconset.glob("*.png"):
        item.unlink()
    iconset.rmdir()


def main() -> None:
    master = build_master()

    desktop_dir = ROOT / "desktop"
    desktop_dir.mkdir(exist_ok=True)
    master.save(desktop_dir / "bravo-icon-1024.png")
    write_icns(master, desktop_dir / "Bravo.icns")

    frontend = ROOT / "frontend"
    (frontend / "app").mkdir(exist_ok=True)
    (frontend / "public").mkdir(exist_ok=True)
    master.resize((512, 512), Image.LANCZOS).save(frontend / "app" / "icon.png")
    master.resize((180, 180), Image.LANCZOS).save(frontend / "app" / "apple-icon.png")
    master.resize((512, 512), Image.LANCZOS).save(frontend / "public" / "bravo-icon.png")
    master.resize((64, 64), Image.LANCZOS).save(
        frontend / "app" / "favicon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )
    print("wrote desktop/Bravo.icns and frontend icons")


if __name__ == "__main__":
    main()
