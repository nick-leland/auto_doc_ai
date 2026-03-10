"""
Border text renderer for document borders.

Draws labeled text boxes centered in the border band on each side of the
document (top, bottom, left/right sides).
"""

import random

import svgwrite


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
    """Draw border text on the document.

    Args:
        document: svgwrite Drawing to add elements to.
        text_contents: Text string (or [left, right] for sides).
        width, height: Document dimensions.
        band_thickness: Width of the border band in pixels.
        margin: Extra margin before the band starts.
        orientation: "Top", "Bottom", or "Sides".
        fg_color: Text color.
        bg_color: Box background color.
        font_size_px: Override auto-scaled font size.
        padding_x, padding_y: Override auto-scaled padding.
        rng: Random instance for font selection.
    """
    if rng is None:
        rng = random.Random()

    # Scale font using band thickness * doc scale factor
    if font_size_px is None:
        doc_scale = (min(width, height) / 800) ** 0.4
        font_size_px = band_thickness * 0.35 * doc_scale
    if padding_x is None:
        padding_x = font_size_px * 0.4
    if padding_y is None:
        padding_y = font_size_px * 0.2

    # Center of the visible border region
    inner_margin = margin + band_thickness
    band_center = inner_margin / 2

    box_height = min(font_size_px * 1.15 + 2 * padding_y, band_thickness * 0.9)

    if orientation == "Sides":
        max_box_width = height * 0.85
    else:
        max_box_width = width * 0.85

    if orientation == "Top":
        cx, cy = width / 2, band_center
        text_str = text_contents if isinstance(text_contents, str) else str(text_contents)
        bw = min(len(text_str) * font_size_px * 0.65 + 2 * padding_x, max_box_width)
        placements = [(cx, cy, bw, text_str, 0)]
    elif orientation == "Bottom":
        cx, cy = width / 2, height - band_center
        text_str = text_contents if isinstance(text_contents, str) else str(text_contents)
        bw = min(len(text_str) * font_size_px * 0.65 + 2 * padding_x, max_box_width)
        placements = [(cx, cy, bw, text_str, 0)]
    elif orientation == "Sides":
        if isinstance(text_contents, (list, tuple)) and len(text_contents) >= 2:
            left_text, right_text = text_contents[0], text_contents[1]
        else:
            s = text_contents if isinstance(text_contents, str) else str(text_contents)
            left_text = right_text = s
        mid_y = height / 2
        l_bw = min(len(left_text) * font_size_px * 0.65 + 2 * padding_x, max_box_width)
        r_bw = min(len(right_text) * font_size_px * 0.65 + 2 * padding_x, max_box_width)
        placements = [
            (band_center, mid_y, l_bw, left_text, -90),
            (width - band_center, mid_y, r_bw, right_text, 90),
        ]
    else:
        raise ValueError("orientation must be 'Top', 'Bottom', or 'Sides'")

    font_family = rng.choice(["Palatino Linotype", "Palatino", "serif"])
    for cx, cy, bw, text, rotation in placements:
        natural_width = len(text) * font_size_px * 0.65 + 2 * padding_x
        actual_font_size = font_size_px
        if natural_width > max_box_width:
            actual_font_size = font_size_px * (max_box_width / natural_width) * 0.9

        text_attrs = dict(
            text_anchor="middle",
            font_size=f"{actual_font_size:.1f}px",
            font_family=font_family,
            font_weight="bold",
        )

        box_x = cx - bw / 2
        box_y = cy - box_height / 2
        text_y = cy + actual_font_size * 0.35

        if rotation != 0:
            g = document.g(transform=f"rotate({rotation}, {cx}, {cy})")
            g.add(document.rect(insert=(box_x, box_y), size=(bw, box_height), fill=bg_color))
            g.add(document.text(text, insert=(cx, text_y), fill=fg_color, **text_attrs))
            document.add(g)
        else:
            document.add(document.rect(insert=(box_x, box_y), size=(bw, box_height), fill=bg_color))
            document.add(document.text(text, insert=(cx, text_y), fill=fg_color, **text_attrs))
