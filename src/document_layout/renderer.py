"""
SVG renderer for vehicle title document layouts.

Takes a solved LayoutResult and draws all blocks, fields, and labels onto
an svgwrite.Drawing. Also produces a metadata dict describing every field's
bounding box for downstream value population.
"""

import json
import random
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
        # Legal / disclaimer / checkbox text — same size as field labels
        fs = font_size * LABEL_FONT_RATIO
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
    title_fs = font_size * 0.9
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
                "height_lines": fp.field_def.height_lines,
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


# ---------------------------------------------------------------------------
# Field types that get handwriting vs machine text
# ---------------------------------------------------------------------------

# Front-side: only lien release fields are handwritten (lienholder fills in later)
FRONT_HANDWRITING_PATTERNS = {"_release_sig", "_release_title", "_release_date"}

# Back-side block types where ALL fillable fields are handwritten
# (people fill these in by hand at time of sale/transfer)
BACK_HANDWRITING_BLOCKS = {
    "back_warning", "transfer", "dealer_reassignment",
    "notary", "damage_disclosure", "vin_verification",
    "power_of_attorney", "back_legal",
}

# Exception: dealer business details are machine (rubber stamp / pre-printed)
DEALER_MACHINE_PATTERNS = {
    "_dealer_name", "_dealer_license", "_dealer_address",
    "_dealer_city", "_dealer_state",
}


def _is_handwriting_field(
    field_name: str, field_type: str, block_type: str = "",
) -> bool:
    """Determine if a field should be rendered with handwriting.

    Front side: only signatures and lien release fields.
    Back side: everything is handwritten except tax/fee (DMV-printed)
    and dealer business details (rubber stamp).
    """
    if field_type == "signature":
        return True

    # Front-side lien release fields
    for pattern in FRONT_HANDWRITING_PATTERNS:
        if pattern in field_name:
            return True

    # Back-side logic: check block type
    if block_type in BACK_HANDWRITING_BLOCKS:
        # Dealer business details are machine (stamp)
        for pattern in DEALER_MACHINE_PATTERNS:
            if pattern in field_name:
                return False
        return True

    # tax_fee and front-side blocks default to machine
    return False


def _get_handwriting_group(field_name: str) -> str:
    """Determine which 'person' is writing this field.

    Fields written by the same person share a handwriting font.
    On a real title, the seller fills in most of the transfer section,
    the buyer fills in their own info, each dealer agent fills their
    section, etc.
    """
    # Front: lien releases
    if field_name.startswith("first_"):
        return "first_lien"
    elif field_name.startswith("second_"):
        return "second_lien"

    # Back: transfer by owner
    # Seller fills in most fields (odometer, date, price, their DL, lien info)
    # Buyer fills in their own name/address/DL/signature
    elif field_name.startswith("transfer_buyer"):
        return "transfer_buyer"
    elif field_name.startswith("transfer_"):
        return "transfer_seller"  # seller fills the rest

    # Back: dealer reassignment — agent vs buyer
    elif field_name.startswith("dealer_first_buyer"):
        return "dealer_first_buyer"
    elif field_name.startswith("dealer_first_agent"):
        return "dealer_first_agent"
    elif field_name.startswith("dealer_first_"):
        return "dealer_first_agent"  # agent fills lien/odometer/date fields
    elif field_name.startswith("dealer_second_buyer"):
        return "dealer_second_buyer"
    elif field_name.startswith("dealer_second_agent"):
        return "dealer_second_agent"
    elif field_name.startswith("dealer_second_"):
        return "dealer_second_agent"

    # Notary — separate person
    elif field_name.startswith("notary"):
        return "notary"

    # Damage disclosure — seller fills most, buyer co-signs
    elif field_name.startswith("damage_buyer"):
        return "transfer_buyer"
    elif field_name.startswith("damage_"):
        return "transfer_seller"

    # Witness lines
    elif "witness1" in field_name:
        return "witness1"
    elif "witness2" in field_name:
        return "witness2"

    # VIN verification — inspector fills everything
    elif field_name.startswith("vin_verify"):
        return "vin_inspector"

    # Power of attorney — owner fills in attorney info + signs
    elif field_name.startswith("poa_co_grantor"):
        return "poa_co_grantor"
    elif field_name.startswith("poa_grantor"):
        return "poa_grantor"
    elif field_name.startswith("poa_"):
        return "poa_grantor"  # owner writes attorney details

    return "default"


def _estimate_label_text_width(label: str, doc_font_size: float) -> float:
    """Approximate printed label width in SVG units."""
    return len(label) * doc_font_size * LABEL_FONT_RATIO * 0.58


def _handwriting_placement(
    field: dict,
    handwriting_font_size: int,
    doc_font_size: float,
) -> tuple[float, float, float, float, bool]:
    """Choose the handwriting placement box.

    Small one-line fields cannot always accommodate realistic handwriting
    below the printed label. In those cases, move the handwriting to the
    right of the label and let it use the full field height.
    """
    bbox = field["bbox"]
    label_rect = field["label_rect"]
    value_rect = field["value_rect"]
    style = field["style"]
    line_slots = max(1, int(field.get("height_lines", 1)))

    if style != "inline" and line_slots == 1:
        target_svg_height = handwriting_font_size * 0.5
        if target_svg_height > value_rect["h"] * 1.05:
            label_w = min(
                label_rect["w"] * 0.9,
                _estimate_label_text_width(field["label"], doc_font_size),
            )
            pad = max(3.0, doc_font_size * 0.4)
            x = label_rect["x"] + label_w + pad
            right = bbox["x"] + bbox["w"]
            width = right - x
            if width > bbox["w"] * 0.28:
                return x, bbox["y"], width, bbox["h"], False

    return value_rect["x"], value_rect["y"], value_rect["w"], value_rect["h"], line_slots > 1


def fill_values(
    drawing: svgwrite.Drawing,
    metadata: dict,
    values: dict,
    rng: random.Random | None = None,
    machine_font_path: Path | str | None = None,
) -> None:
    """Fill field values onto the SVG drawing using the layout metadata.

    Machine-filled fields (VIN, year, owner name, etc.) are rendered with
    machinewriting using one consistent font. Handwriting fields (signatures,
    release dates/titles) are rendered per-person — each lienholder gets a
    different handwriting font, but all fields from the same person match.

    Args:
        drawing: The svgwrite.Drawing to add text to.
        metadata: The metadata dict returned by render_layout().
        values: Dict mapping field names to string values.
        rng: Random instance for reproducibility.
        machine_font_path: Specific machine font, or None for random.
    """
    from src.utils.handwriting import (
        FONT_FILES as HW_FONTS,
        render_handwriting,
        render_signature,
    )
    from src.utils.machinewriting import (
        FONT_FILES as MW_FONTS,
        render_machinetext,
    )

    if rng is None:
        rng = random.Random()

    # Pick machine font once for the whole document
    if machine_font_path is None:
        machine_font_path = rng.choice(MW_FONTS)

    # Pick a different handwriting font per person (lienholder)
    # Shuffle to avoid the same font for different people
    hw_pool = list(HW_FONTS)
    rng.shuffle(hw_pool)
    hw_font_by_group: dict[str, Path] = {}

    def _get_hw_font(group: str) -> Path:
        if group not in hw_font_by_group:
            idx = len(hw_font_by_group) % len(hw_pool)
            hw_font_by_group[group] = hw_pool[idx]
        return hw_font_by_group[group]

    # Compute a consistent font size from the layout.
    # Use the median value_rect height of fillable fields to set a uniform
    # render size for both machine and handwriting text.
    fillable_heights = []
    for block in metadata["blocks"]:
        for field in block["fields"]:
            if field["style"] == "label_only":
                continue
            h = field["value_rect"]["h"]
            if h > 0:
                fillable_heights.append(h)

    if fillable_heights:
        fillable_heights.sort()
        median_h = fillable_heights[len(fillable_heights) // 2]
        doc_font_size = float(metadata["document"].get("font_size", median_h))
        # Render size in PIL pixels — scaled down by 0.5 for SVG placement.
        machine_font_size = max(16, int(median_h * 1.5))
        handwriting_font_size = max(28, int(median_h * 2.2), int(doc_font_size * 4.0))
        signature_font_size = max(handwriting_font_size + 10, int(handwriting_font_size * 1.2))
    else:
        doc_font_size = 18.0
        machine_font_size = 72
        handwriting_font_size = 80
        signature_font_size = 96

    for block in metadata["blocks"]:
        block_type = block.get("block_type", "")
        for field in block["fields"]:
            name = field["name"]
            field_type = field["field_type"]
            style = field["style"]

            # Skip label-only fields (static text, not fillable)
            if style == "label_only":
                continue

            # Get value from the values dict
            value = values.get(name)
            if value is None:
                continue

            vr = field["value_rect"]
            x, y, w, h = vr["x"], vr["y"], vr["w"], vr["h"]

            # Skip if the value rect has no area
            if w <= 0 or h <= 0:
                continue

            line_slots = max(1, int(field.get("height_lines", 1)))

            if _is_handwriting_field(name, field_type, block_type):
                group = _get_handwriting_group(name)
                hw_font = _get_hw_font(group)
                hx, hy, hw, hh, align_top = _handwriting_placement(
                    field, handwriting_font_size, doc_font_size,
                )

                if field_type == "signature":
                    g = render_signature(
                        drawing, value, hx, hy, hw, hh,
                        font_path=hw_font,
                        font_size=signature_font_size,
                        line_slots=1,
                        align_top=align_top,
                        rng=rng,
                    )
                else:
                    g = render_handwriting(
                        drawing, value, hx, hy, hw, hh,
                        font_path=hw_font,
                        font_size=handwriting_font_size,
                        line_slots=line_slots,
                        align_top=align_top,
                        rng=rng,
                    )
            else:
                g = render_machinetext(
                    drawing, value, x, y, w, h,
                    font_path=machine_font_path,
                    font_size=machine_font_size,
                    line_slots=line_slots,
                    align_top=line_slots > 1,
                    rng=rng,
                )

            drawing.add(g)
