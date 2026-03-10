"""
Handwriting text renderer for SVG documents.

Renders text using cursive/handwriting fonts via PIL (raster), then embeds
the result as a transparent PNG inside an SVG <image> element. This ensures
the handwriting fonts render correctly regardless of the SVG viewer.

Returns svgwrite groups that can be added to any svgwrite.Drawing.
"""

import base64
import io
import random
from pathlib import Path

import svgwrite
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Handwriting font directory
FONTS_DIR = Path("src/data/handwriting_fonts")
FONT_FILES = sorted(
    [f for f in FONTS_DIR.iterdir() if f.suffix.lower() in (".ttf", ".otf")]
) if FONTS_DIR.exists() else []


def _render_text_to_png(
    text: str,
    font_path: Path,
    font_size: int,
    color: tuple[int, int, int] = (20, 20, 20),
    blur: float = 0.6,
    rng: random.Random | None = None,
) -> Image.Image:
    """Render text to a transparent PNG using PIL.

    Returns an RGBA image cropped tightly around the text with slight
    random offset, rotation, and ink-bleed blur applied.
    """
    if rng is None:
        rng = random.Random()

    font = ImageFont.truetype(str(font_path), size=font_size)

    # Measure text size
    dummy = Image.new("RGBA", (4000, 800), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top

    # Render on transparent background with padding for rotation
    pad = max(40, int(font_size * 0.4))
    canvas_w = tw + pad * 2
    canvas_h = th + pad * 2
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Slight random offset
    dx = rng.randint(-3, 3)
    dy = rng.randint(-3, 3)
    draw.text((pad - left + dx, pad - top + dy), text, font=font,
              fill=(*color, 255))

    # Slight rotation
    angle = rng.uniform(-4, 4)
    img = img.rotate(angle, expand=True, resample=Image.BICUBIC,
                     fillcolor=(0, 0, 0, 0))

    # Ink bleed blur (applied to RGB, preserve alpha)
    if blur > 0:
        r, g, b, a = img.split()
        rgb = Image.merge("RGB", (r, g, b))
        rgb = rgb.filter(ImageFilter.GaussianBlur(blur))
        r2, g2, b2 = rgb.split()
        img = Image.merge("RGBA", (r2, g2, b2, a))

    # Crop to content (non-transparent pixels)
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


def render_handwriting(
    drawing: svgwrite.Drawing,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_path: Path | str | None = None,
    color: tuple[int, int, int] = (20, 20, 20),
    rng: random.Random | None = None,
) -> svgwrite.container.Group:
    """Render handwriting text into an SVG group positioned at (x, y, width, height).

    Renders via PIL with a handwriting font, then embeds the result as a
    transparent PNG in the SVG.

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

    # Render at high resolution then scale to fit the box
    render_size = max(48, int(height * 2))
    img = _render_text_to_png(text, font_path, render_size, color=color,
                              blur=0.6, rng=rng)

    # Scale image to fit within the value box (maintain aspect ratio)
    img_w, img_h = img.size
    scale = min(width / img_w, height / img_h) * 0.9
    display_w = img_w * scale
    display_h = img_h * scale

    # Center vertically, left-align with small offset
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


def render_signature(
    drawing: svgwrite.Drawing,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_path: Path | str | None = None,
    color: tuple[int, int, int] = (20, 20, 20),
    rng: random.Random | None = None,
) -> svgwrite.container.Group:
    """Render a signature — same as handwriting but with more aggressive effects."""
    if rng is None:
        rng = random.Random()

    if font_path is None:
        font_path = rng.choice(FONT_FILES)
    else:
        font_path = Path(font_path)

    render_size = max(64, int(height * 2.5))
    img = _render_text_to_png(text, font_path, render_size, color=color,
                              blur=0.8, rng=rng)

    img_w, img_h = img.size
    scale = min(width / img_w, height / img_h) * 0.85
    display_w = img_w * scale
    display_h = img_h * scale

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
