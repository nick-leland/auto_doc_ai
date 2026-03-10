"""
Machine text renderer for SVG documents.

Renders text using monospaced/typewriter fonts via PIL (raster), then embeds
the result as a transparent PNG inside an SVG <image> element.

Simulates DMV-printed fields: clean, precise, no rotation or blur.

Returns svgwrite groups that can be added to any svgwrite.Drawing.
"""

import base64
import io
import random
from pathlib import Path

import svgwrite
from PIL import Image, ImageDraw, ImageFont

# Machine font directory
FONTS_DIR = Path("src/data/machine_fonts")
FONT_FILES = sorted(
    [f for f in FONTS_DIR.iterdir()
     if f.suffix.lower() in (".ttf", ".otf") and not f.name.startswith(".")]
) if FONTS_DIR.exists() else []


def _render_text_to_png(
    text: str,
    font_path: Path,
    font_size: int,
    color: tuple[int, int, int] = (10, 10, 10),
) -> Image.Image:
    """Render text to a transparent PNG using PIL.

    Clean rendering — no rotation, no blur. Tight crop around text.
    """
    font = ImageFont.truetype(str(font_path), size=font_size)

    # Measure text size
    dummy = Image.new("RGBA", (4000, 800), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top

    # Render on transparent background
    pad = max(10, int(font_size * 0.15))
    canvas_w = tw + pad * 2
    canvas_h = th + pad * 2
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((pad - left, pad - top), text, font=font, fill=(*color, 255))

    # Crop to content
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    return img


def _img_to_data_uri(img: Image.Image) -> str:
    """Convert a PIL Image to a base64 PNG data URI."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def render_machinetext(
    drawing: svgwrite.Drawing,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_path: Path | str | None = None,
    color: tuple[int, int, int] = (10, 10, 10),
    rng: random.Random | None = None,
) -> svgwrite.container.Group:
    """Render machine-printed text into an SVG group at (x, y, width, height).

    Clean, precise rendering — no rotation, no blur. Simulates DMV
    typewriter or dot-matrix printing.

    Args:
        drawing: The svgwrite.Drawing (used for creating elements).
        text: The text to render.
        x, y, width, height: The bounding box to place the text in.
        font_path: Specific font file to use, or None for random selection.
        color: RGB tuple for text color.
        rng: Random instance for reproducibility.

    Returns:
        An svgwrite Group element (caller should add it to the drawing).
    """
    if rng is None:
        rng = random.Random()

    if font_path is None:
        font_path = rng.choice(FONT_FILES)
    else:
        font_path = Path(font_path)

    # Render at high resolution then scale to fit
    render_size = max(48, int(height * 2))
    img = _render_text_to_png(text, font_path, render_size, color=color)

    # Scale to fit within the value box (maintain aspect ratio)
    img_w, img_h = img.size
    scale = min(width / img_w, height / img_h) * 0.9
    display_w = img_w * scale
    display_h = img_h * scale

    # Left-align, vertically center
    img_x = x + height * 0.05
    img_y = y + (height - display_h) / 2

    data_uri = _img_to_data_uri(img)

    g = drawing.g()
    g.add(drawing.image(
        href=data_uri,
        insert=(img_x, img_y),
        size=(display_w, display_h),
    ))
    return g
