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


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int | None = None,
) -> list[str]:
    """Word-wrap handwriting text, preserving a fuller first line."""
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
            if max_lines is not None and len(lines) >= max_lines - 1:
                current = test
                continue
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _render_text_to_png(
    text: str,
    font_path: Path,
    font_size: int,
    color: tuple[int, int, int] = (20, 20, 20),
    blur: float = 0.6,
    max_width_px: int | None = None,
    max_lines: int | None = None,
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
    dummy = Image.new("RGBA", (4000, 1600), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)

    if max_width_px is not None:
        lines = _wrap_text(text, font, max_width_px, max_lines=max_lines)
    else:
        lines = [text]

    line_metrics = []
    max_w = 0
    for line in lines:
        left, top, right, bottom = draw.textbbox((0, 0), line, font=font)
        lw, lh = right - left, bottom - top
        line_metrics.append((left, top, lw, lh))
        max_w = max(max_w, lw)

    line_spacing = int(font_size * 1.2)
    total_h = line_spacing * len(lines)

    # Render on transparent background with padding for rotation
    pad = max(40, int(font_size * 0.4))
    canvas_w = max_w + pad * 2
    canvas_h = total_h + pad * 2
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for i, (line, (left, top, _, _)) in enumerate(zip(lines, line_metrics)):
        dx = rng.randint(-3, 3)
        dy = rng.randint(-2, 2)
        text_y = pad + i * line_spacing - top + dy
        draw.text(
            (pad - left + dx, text_y),
            line,
            font=font,
            fill=(*color, 255),
        )

    # Slight rotation — use a distribution that's tight for most cases,
    # with occasional larger angles. Scale down for longer text to avoid
    # going off the line.
    text_len = len(text)
    if text_len > 30:
        max_angle = 1.0
    elif text_len > 15:
        max_angle = 2.0
    else:
        max_angle = 3.5

    # Normal-ish distribution: most angles near 0, rare outliers
    # Use triangular distribution centered at 0 for a natural feel
    angle = rng.triangular(-max_angle, max_angle, 0)
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


def _place_image(
    drawing: svgwrite.Drawing,
    img: Image.Image,
    x: float,
    y: float,
    width: float,
    height: float,
    font_size: int | None,
    line_slots: int = 1,
    align_top: bool = False,
) -> svgwrite.container.Group:
    """Scale and position a rendered text image into a value box."""
    img_w, img_h = img.size

    if font_size is not None:
        # Fixed scale: 1 render pixel -> a fixed number of SVG units.
        # Constant regardless of box height so all handwriting looks the same size.
        scale = 0.5
        if img_w * scale > width * 0.95:
            scale = (width * 0.95) / img_w
        height_limit = height * (0.95 if align_top else 0.85)
        if img_h * scale > height_limit:
            scale = height_limit / img_h
    else:
        scale = min(width / img_w, height / img_h) * 0.9

    display_w = img_w * scale
    display_h = img_h * scale

    img_x = x + height * 0.05
    if align_top:
        per_line_h = height / max(1, line_slots)
        img_y = y + min(per_line_h * 0.08, height * 0.06)
    else:
        img_y = y + (height - display_h) / 2

    data_uri = _img_to_data_uri(img)

    g = drawing.g()
    g.add(drawing.image(
        href=data_uri,
        insert=(img_x, img_y),
        size=(display_w, display_h),
    ))
    return g


def render_handwriting(
    drawing: svgwrite.Drawing,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_path: Path | str | None = None,
    font_size: int | None = None,
    line_slots: int = 1,
    align_top: bool = False,
    color: tuple[int, int, int] = (20, 20, 20),
    rng: random.Random | None = None,
) -> svgwrite.container.Group:
    """Render handwriting text into an SVG group positioned at (x, y, width, height).

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

    render_size = font_size if font_size is not None else max(48, int(height * 2))
    scale_est = 0.5 if font_size is not None else (height * 0.9) / render_size
    max_width_px = int(width * 0.95 / scale_est) if scale_est > 0 else None
    img = _render_text_to_png(
        text,
        font_path,
        render_size,
        color=color,
        blur=0.6,
        max_width_px=max_width_px,
        max_lines=line_slots if line_slots > 1 else 1,
        rng=rng,
    )

    return _place_image(
        drawing, img, x, y, width, height, font_size,
        line_slots=line_slots, align_top=align_top,
    )


def render_signature(
    drawing: svgwrite.Drawing,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_path: Path | str | None = None,
    font_size: int | None = None,
    line_slots: int = 1,
    align_top: bool = False,
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

    render_size = font_size if font_size is not None else max(64, int(height * 2.5))
    scale_est = 0.5 if font_size is not None else (height * 0.9) / render_size
    max_width_px = int(width * 0.95 / scale_est) if scale_est > 0 else None
    img = _render_text_to_png(
        text,
        font_path,
        render_size,
        color=color,
        blur=0.8,
        max_width_px=max_width_px,
        max_lines=line_slots if line_slots > 1 else 1,
        rng=rng,
    )

    return _place_image(
        drawing, img, x, y, width, height, font_size,
        line_slots=line_slots, align_top=align_top,
    )
