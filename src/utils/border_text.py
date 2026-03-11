"""
Border text renderer for document borders.

Renders border labels as rasterized text images embedded in the SVG so the
final PNG matches the SVG preview regardless of system font substitution.
"""

import base64
import io
import random
from pathlib import Path

import svgwrite
from PIL import Image, ImageDraw, ImageFont


FONTS_DIR = Path("src/data/document_fonts")
FONT_FILES = sorted(
    [f for f in FONTS_DIR.iterdir() if f.suffix.lower() in (".ttf", ".otf") and not f.name.startswith(".")]
) if FONTS_DIR.exists() else []


def _pick_font_path(rng: random.Random) -> Path | None:
    if not FONT_FILES:
        return None
    preferred = ["Univers.ttf", "frutiger.ttf", "Helvetica.ttf", "arial.ttf"]
    for name in preferred:
        for font in FONT_FILES:
            if font.name == name:
                return font
    return rng.choice(FONT_FILES)


def _render_text_image(
    text: str,
    font_path: Path | None,
    font_size: int,
    fg_rgb: tuple[int, int, int],
    bg_rgb: tuple[int, int, int],
    padding_x: int,
    padding_y: int,
) -> Image.Image:
    if font_path is not None:
        font = ImageFont.truetype(str(font_path), font_size)
    else:
        font = ImageFont.load_default()

    dummy = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_w = right - left
    text_h = bottom - top

    img = Image.new(
        "RGBA",
        (text_w + 2 * padding_x, text_h + 2 * padding_y),
        (*bg_rgb, 255),
    )
    draw = ImageDraw.Draw(img)
    draw.text(
        (padding_x - left, padding_y - top),
        text,
        font=font,
        fill=(*fg_rgb, 255),
    )
    return img


def _img_to_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def render_border_text(
    document: svgwrite.Drawing,
    text_contents: str | list[str],
    width: float,
    height: float,
    band_thickness: float,
    margin: float = 0,
    orientation: str = "Top",
    fg_color: str = "#E0E8F0",
    bg_color: str = "#2C5C9A",
    font_size_px: float | None = None,
    padding_x: float | None = None,
    padding_y: float | None = None,
    rng: random.Random | None = None,
) -> None:
    """Draw border text on the document as embedded raster images."""
    if rng is None:
        rng = random.Random()

    if font_size_px is None:
        doc_scale = (min(width, height) / 800) ** 0.4
        font_size_px = band_thickness * 0.28 * doc_scale
    if padding_x is None:
        padding_x = font_size_px * 0.45
    if padding_y is None:
        padding_y = font_size_px * 0.22

    inner_margin = margin + band_thickness
    band_center = inner_margin / 2
    max_box_width = (height if orientation == "Sides" else width) * 0.85

    if orientation == "Top":
        placements = [(width / 2, band_center, str(text_contents), 0)]
    elif orientation == "Bottom":
        placements = [(width / 2, height - band_center, str(text_contents), 0)]
    elif orientation == "Sides":
        if isinstance(text_contents, (list, tuple)) and len(text_contents) >= 2:
            left_text, right_text = text_contents[0], text_contents[1]
        else:
            side_text = str(text_contents)
            left_text = right_text = side_text
        placements = [
            (band_center, height / 2, left_text, -90),
            (width - band_center, height / 2, right_text, 90),
        ]
    else:
        raise ValueError("orientation must be 'Top', 'Bottom', or 'Sides'")

    font_path = _pick_font_path(rng)
    fg_rgb = _hex_to_rgb(fg_color)
    bg_rgb = _hex_to_rgb(bg_color)

    for cx, cy, text, rotation in placements:
        estimated_fs = min(font_size_px, band_thickness * 0.46)
        scale_factor = 4
        render_font_size = max(18, int(estimated_fs * scale_factor))
        render_pad_x = max(8, int(padding_x * scale_factor))
        render_pad_y = max(6, int(padding_y * scale_factor))

        img = _render_text_image(
            text=text,
            font_path=font_path,
            font_size=render_font_size,
            fg_rgb=fg_rgb,
            bg_rgb=bg_rgb,
            padding_x=render_pad_x,
            padding_y=render_pad_y,
        )

        max_display_width = max_box_width
        max_display_height = band_thickness * 0.92
        img_w, img_h = img.size
        scale = min(max_display_width / img_w, max_display_height / img_h)
        display_w = img_w * scale
        display_h = img_h * scale
        x = cx - display_w / 2
        y = cy - display_h / 2

        image = document.image(
            href=_img_to_data_uri(img),
            insert=(x, y),
            size=(display_w, display_h),
        )

        if rotation != 0:
            group = document.g(transform=f"rotate({rotation}, {cx}, {cy})")
            group.add(image)
            document.add(group)
        else:
            document.add(image)
