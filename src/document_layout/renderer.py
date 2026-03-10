"""
SVG renderer for vehicle title document layouts.

Takes a solved LayoutResult and draws all blocks, fields, and labels onto
an svgwrite.Drawing. Also produces a metadata dict describing every field's
bounding box for downstream value population.
"""

import json
from pathlib import Path

import svgwrite

from .cells import BlockType, FieldStyle
from .packing import (
    HEADER_FONT_RATIO,
    LABEL_FONT_RATIO,
    BlockPlacement,
    FieldPlacement,
    LayoutResult,
)


# ---------------------------------------------------------------------------
# Field renderers
# ---------------------------------------------------------------------------

def _render_field_underline(
    drawing: svgwrite.Drawing,
    fp: FieldPlacement,
    font_size: float,
    font_family: str,
    text_color: str,
    line_color: str,
) -> None:
    """Render a field with label above and underline below."""
    lx, ly, lw, lh = fp.label_rect
    vx, vy, vw, vh = fp.value_rect

    label_fs = font_size * LABEL_FONT_RATIO
    drawing.add(drawing.text(
        fp.field_def.label,
        insert=(lx, ly + label_fs),
        font_size=f"{label_fs:.1f}px",
        font_family=font_family,
        fill=text_color,
    ))

    # Draw underline(s) at bottom of each line
    for line_i in range(fp.field_def.height_lines):
        line_h = vh / fp.field_def.height_lines
        line_y = vy + line_h * (line_i + 1) - 1
        drawing.add(drawing.line(
            start=(vx, line_y),
            end=(vx + vw, line_y),
            stroke=line_color,
            stroke_width=0.75,
        ))


def _render_field_box(
    drawing: svgwrite.Drawing,
    fp: FieldPlacement,
    font_size: float,
    font_family: str,
    text_color: str,
    line_color: str,
) -> None:
    """Render a field with label above and rectangular box below."""
    lx, ly, lw, lh = fp.label_rect
    vx, vy, vw, vh = fp.value_rect

    label_fs = font_size * LABEL_FONT_RATIO
    drawing.add(drawing.text(
        fp.field_def.label,
        insert=(lx, ly + label_fs),
        font_size=f"{label_fs:.1f}px",
        font_family=font_family,
        fill=text_color,
    ))

    drawing.add(drawing.rect(
        insert=(vx, vy),
        size=(vw, vh),
        fill="none",
        stroke=line_color,
        stroke_width=0.5,
    ))


def _render_field_inline(
    drawing: svgwrite.Drawing,
    fp: FieldPlacement,
    font_size: float,
    font_family: str,
    text_color: str,
    line_color: str,
) -> None:
    """Render a field with label and underline on the same line."""
    lx, ly, lw, lh = fp.label_rect
    vx, vy, vw, vh = fp.value_rect

    label_fs = font_size * LABEL_FONT_RATIO
    text_y = ly + lh / 2 + label_fs * 0.35

    drawing.add(drawing.text(
        fp.field_def.label + ":",
        insert=(lx, text_y),
        font_size=f"{label_fs:.1f}px",
        font_family=font_family,
        fill=text_color,
    ))

    line_y = ly + lh - 1
    drawing.add(drawing.line(
        start=(vx, line_y),
        end=(vx + vw, line_y),
        stroke=line_color,
        stroke_width=0.75,
    ))


def _render_field_label_only(
    drawing: svgwrite.Drawing,
    fp: FieldPlacement,
    font_size: float,
    font_family: str,
    text_color: str,
    is_header: bool,
) -> None:
    """Render label-only text (headers, legal disclaimers)."""
    lx, ly, lw, lh = fp.label_rect

    if is_header:
        fs = font_size * HEADER_FONT_RATIO
        text_y = ly + lh / 2 + fs * 0.35
        drawing.add(drawing.text(
            fp.field_def.label,
            insert=(lx + lw / 2, text_y),
            text_anchor="middle",
            font_size=f"{fs:.1f}px",
            font_family=font_family,
            font_weight="bold",
            fill=text_color,
        ))
    else:
        # Legal / disclaimer text — smaller, wrapped appearance
        fs = font_size * LABEL_FONT_RATIO * 0.9
        text_y = ly + fs * 1.2
        drawing.add(drawing.text(
            fp.field_def.label,
            insert=(lx, text_y),
            font_size=f"{fs:.1f}px",
            font_family=font_family,
            fill=text_color,
        ))


# ---------------------------------------------------------------------------
# Block title renderers
# ---------------------------------------------------------------------------

def _render_block_title(
    drawing: svgwrite.Drawing,
    bp: BlockPlacement,
    font_size: float,
    font_family: str,
    text_color: str,
    line_color: str,
) -> None:
    """Render the section title for a block."""
    if not bp.block.title or bp.title_rect is None:
        return

    tx, ty, tw, th = bp.title_rect
    title_fs = font_size * 0.8
    text_y = ty + th / 2 + title_fs * 0.35
    style = bp.block.title_style

    if style == "banner":
        drawing.add(drawing.rect(
            insert=(tx, ty),
            size=(tw, th),
            fill=line_color,
        ))
        drawing.add(drawing.text(
            bp.block.title,
            insert=(tx + tw / 2, text_y),
            text_anchor="middle",
            font_size=f"{title_fs:.1f}px",
            font_family=font_family,
            font_weight="bold",
            fill="white",
        ))
    elif style == "center":
        drawing.add(drawing.text(
            bp.block.title,
            insert=(tx + tw / 2, text_y),
            text_anchor="middle",
            font_size=f"{title_fs:.1f}px",
            font_family=font_family,
            font_weight="bold",
            fill=text_color,
        ))
        drawing.add(drawing.line(
            start=(tx, ty + th - 1),
            end=(tx + tw, ty + th - 1),
            stroke=line_color,
            stroke_width=0.5,
            opacity=0.4,
        ))
    elif style == "left":
        drawing.add(drawing.text(
            bp.block.title,
            insert=(tx, text_y),
            font_size=f"{title_fs:.1f}px",
            font_family=font_family,
            font_weight="bold",
            fill=text_color,
        ))
        drawing.add(drawing.line(
            start=(tx, ty + th - 1),
            end=(tx + tw, ty + th - 1),
            stroke=line_color,
            stroke_width=0.5,
            opacity=0.4,
        ))


# ---------------------------------------------------------------------------
# Block separator
# ---------------------------------------------------------------------------

def _render_block_separator(
    drawing: svgwrite.Drawing,
    x: float,
    y: float,
    width: float,
    line_color: str,
) -> None:
    """Thin horizontal rule between blocks."""
    drawing.add(drawing.line(
        start=(x, y),
        end=(x + width, y),
        stroke=line_color,
        stroke_width=0.5,
        opacity=0.3,
    ))


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def render_layout(
    drawing: svgwrite.Drawing,
    layout_result: LayoutResult,
    font_family: str,
    text_color: str = "#000000",
    line_color: str = "#333333",
) -> dict:
    """Render all blocks and fields onto an svgwrite Drawing.

    Returns a metadata dict describing every field's bounding box.
    """
    cx, cy, cw, ch = layout_result.content_rect
    font_size = layout_result.font_size

    metadata: dict = {
        "document": {
            "width": cx + cw + cx,  # approximate full doc width
            "height": cy + ch + cy,
            "font_family": font_family,
            "font_size": round(font_size, 2),
            "content_rect": {
                "x": round(cx, 2), "y": round(cy, 2),
                "w": round(cw, 2), "h": round(ch, 2),
            },
        },
        "blocks": [],
    }

    for i, bp in enumerate(layout_result.block_placements):
        is_header = bp.block.block_type == BlockType.HEADER

        # Block separator (between blocks, not before first)
        if i > 0:
            sep_y = bp.y - font_size * 0.4  # midpoint of gap
            _render_block_separator(drawing, bp.x, sep_y, bp.width, line_color)

        # Section title
        _render_block_title(drawing, bp, font_size, font_family, text_color, line_color)

        # Fields
        block_meta: dict = {
            "block_type": bp.block.block_type.value,
            "variant_id": bp.block.variant_id,
            "bbox": {
                "x": round(bp.x, 2), "y": round(bp.y, 2),
                "w": round(bp.width, 2), "h": round(bp.height, 2),
            },
            "fields": [],
        }

        for fp in bp.field_placements:
            style = fp.field_def.style

            if style == FieldStyle.UNDERLINE:
                _render_field_underline(drawing, fp, font_size, font_family, text_color, line_color)
            elif style == FieldStyle.BOX:
                _render_field_box(drawing, fp, font_size, font_family, text_color, line_color)
            elif style == FieldStyle.INLINE:
                _render_field_inline(drawing, fp, font_size, font_family, text_color, line_color)
            elif style == FieldStyle.LABEL_ONLY:
                _render_field_label_only(drawing, fp, font_size, font_family, text_color, is_header)

            # Metadata for every field (including label-only for completeness)
            field_meta = {
                "name": fp.field_def.name,
                "label": fp.field_def.label,
                "field_type": fp.field_def.field_type,
                "style": fp.field_def.style.value,
                "bbox": {
                    "x": round(fp.x, 2), "y": round(fp.y, 2),
                    "w": round(fp.width, 2), "h": round(fp.height, 2),
                },
                "label_rect": {
                    "x": round(fp.label_rect[0], 2), "y": round(fp.label_rect[1], 2),
                    "w": round(fp.label_rect[2], 2), "h": round(fp.label_rect[3], 2),
                },
                "value_rect": {
                    "x": round(fp.value_rect[0], 2), "y": round(fp.value_rect[1], 2),
                    "w": round(fp.value_rect[2], 2), "h": round(fp.value_rect[3], 2),
                },
            }
            block_meta["fields"].append(field_meta)

        metadata["blocks"].append(block_meta)

    return metadata


def save_metadata(metadata: dict, path: str | Path) -> None:
    """Write layout metadata to a JSON file."""
    with open(path, "w") as f:
        json.dump(metadata, f, indent=2)
