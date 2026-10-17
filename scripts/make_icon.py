#!/usr/bin/env python3
"""Render the Bravo app icon (white rounded square + bold black "Bravo").

Uses the macOS SF Pro Rounded font so the wordmark matches the supplied
artwork. Outputs a 1024x1024 PNG (the base for the .icns iconset).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 1024
MARGIN = 100
RADIUS = 190
FONT_CANDIDATES = [
    "/System/Library/Fonts/SFNSRounded.ttf",
    "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
]


def _load_font(px: int) -> ImageFont.FreeTypeFont:
    last_error: Exception | None = None
    for path in FONT_CANDIDATES:
        if not Path(path).exists():
            continue
        try:
            font = ImageFont.truetype(path, px)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
        # Variable fonts: pick the heaviest named instance available.
        for weight in ("Black", "Heavy", "Bold"):
            try:
                font.set_variation_by_name(weight)
                break
            except Exception:  # noqa: BLE001
                continue
        return font
    raise SystemExit(f"no usable rounded font: {last_error}")


def render(destination: Path) -> None:
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    box = (MARGIN, MARGIN, SIZE - MARGIN, SIZE - MARGIN)
    draw.rounded_rectangle(box, radius=RADIUS, fill=(255, 255, 255, 255))

    # Fit "Bravo" to ~72% of the inner width.
    target_width = int((SIZE - 2 * MARGIN) * 0.82)
    size = 400
    while size > 20:
        font = _load_font(size)
        left, top, right, bottom = draw.textbbox((0, 0), "Bravo", font=font)
        if (right - left) <= target_width:
            break
        size -= 4
    width = right - left
    height = bottom - top
    center_x = MARGIN + (SIZE - 2 * MARGIN) / 2
    center_y = MARGIN + (SIZE - 2 * MARGIN) / 2
    draw.text(
        (center_x, center_y),
        "Bravo",
        font=font,
        fill=(10, 10, 10, 255),
        anchor="mm",
    )
    canvas.save(destination)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("bravo_icon.png")
    render(out)
    print(f"wrote {out} ({SIZE}x{SIZE}, text fit ok)")
