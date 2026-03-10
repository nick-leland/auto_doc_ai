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


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels. Returns list of lines."""
    words = text.split()
    if not words:
        return [text]

    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)

    lines = []
    current = words[0]
    for word in words[1:]:
        test = current + " " + word
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _render_text_to_png(
    text: str,
    font_path: Path,
    font_size: int,
    color: tuple[int, int, int] = (10, 10, 10),
    max_width_px: int | None = None,
) -> Image.Image:
    """Render text to a transparent PNG using PIL.

    Clean rendering — no rotation, no blur. Tight crop around text.
    If max_width_px is provided and the text exceeds it, wraps to multiple lines.
    """
    font = ImageFont.truetype(str(font_path), size=font_size)

    # Determine lines (wrap if needed)
    if max_width_px is not None:
        lines = _wrap_text(text, font, max_width_px)
    else:
        lines = [text]

    # Measure each line and compute total size
    dummy = Image.new("RGBA", (4000, 800), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)

    line_metrics = []
    max_w = 0
    for line in lines:
        left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
        lw, lh = right - left, bottom - top
        line_metrics.append((left, top, lw, lh))
        max_w = max(max_w, lw)

    line_spacing = int(font_size * 1.3)
    total_h = line_spacing * len(lines)

    # Render on transparent background
    pad = max(10, int(font_size * 0.15))
    canvas_w = max_w + pad * 2
    canvas_h = total_h + pad * 2
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for i, (line, (left, top, lw, lh)) in enumerate(zip(lines, line_metrics)):
        y = pad + i * line_spacing - top
        draw.text((pad - left, y), line, font=font, fill=(*color, 255))

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
    font_size: int | None = None,
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
        font_size: Fixed PIL font size for consistent text across fields.
            If None, derived from box height.
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

    # Use fixed font size if provided, otherwise derive from box
    render_size = font_size if font_size is not None else max(48, int(height * 2))

    # Compute max width in render pixels so text wraps if it won't fit.
    # Scale factor is 0.5 when font_size is fixed (1 render px = 0.5 SVG units),
    # so SVG width / 0.5 = render px. Use 90% to leave margin.
    scale_est = 0.5 if font_size is not None else (height * 0.9) / render_size
    max_width_px = int(width * 0.9 / scale_est) if scale_est > 0 else None

    img = _render_text_to_png(text, font_path, render_size, color=color,
                              max_width_px=max_width_px)

    # Scale: if font_size is fixed, use a constant scale factor derived from
    # the render size so text looks the same across all fields regardless
    # of their box height.
    img_w, img_h = img.size
    if font_size is not None:
        # Fixed scale: 1 render pixel -> a fixed number of SVG units.
        # Target: the rendered font_size maps to roughly 0.5 * font_size SVG units.
        scale = 0.5
        # But don't exceed the box width or height
        if img_w * scale > width * 0.95:
            scale = (width * 0.95) / img_w
        if img_h * scale > height * 0.85:
            scale = (height * 0.85) / img_h
    else:
        scale = min(width / img_w, height / img_h) * 0.9

    display_w = img_w * scale
    display_h = img_h * scale

    # Left-align; top-align with small padding so single-line text
    # sits on the first line rather than floating between lines
    img_x = x + height * 0.05
    img_y = y + display_h * 0.1

    data_uri = _img_to_data_uri(img)

    g = drawing.g()
    g.add(drawing.image(
        href=data_uri,
        insert=(img_x, img_y),
        size=(display_w, display_h),
    ))
    return g
