"""
Layout packing engine for vehicle title documents.

Given a DocumentLayout (list of BlockVariants) and a content rectangle,
solves for the largest font size that fits all blocks vertically, then
computes exact (x, y, w, h) placements for every block and field.
"""

from dataclasses import dataclass, field

from .cells import BlockVariant, DocumentLayout, FieldDef, FieldStyle, RowDef


# ---------------------------------------------------------------------------
# Layout constants (all relative to font_size)
# ---------------------------------------------------------------------------

ROW_HEIGHT_FACTOR = 2.0       # each row = 2.0× font_size (label + value + pad)
TITLE_HEIGHT_FACTOR = 1.5     # section title row
BLOCK_GAP_FACTOR = 0.6        # vertical gap between blocks
PADDING_X_FACTOR = 0.5        # horizontal inset from content rect edges
FIELD_GAP_FACTOR = 0.3        # horizontal gap between fields in a row
LABEL_FONT_RATIO = 0.70       # label text size relative to base font_size
HEADER_FONT_RATIO = 1.6       # header LABEL_ONLY text relative to base font_size

# Compact mode overrides — for back pages with many blocks
COMPACT_ROW_HEIGHT_FACTOR = 1.6
COMPACT_TITLE_HEIGHT_FACTOR = 1.2
COMPACT_BLOCK_GAP_FACTOR = 0.3
COMPACT_PADDING_X_FACTOR = 0.3


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class FieldPlacement:
    field_def: FieldDef
    x: float
    y: float
    width: float
    height: float
    label_rect: tuple[float, float, float, float]   # (x, y, w, h)
    value_rect: tuple[float, float, float, float]    # (x, y, w, h)


@dataclass
class BlockPlacement:
    block: BlockVariant
    x: float
    y: float
    width: float
    height: float
    title_rect: tuple[float, float, float, float] | None  # (x, y, w, h)
    field_placements: list[FieldPlacement] = field(default_factory=list)


@dataclass
class LayoutResult:
    font_size: float
    content_rect: tuple[float, float, float, float]
    block_placements: list[BlockPlacement]


# ---------------------------------------------------------------------------
# Height computation
# ---------------------------------------------------------------------------

def _row_height(row: RowDef, font_size: float, compact: bool = False) -> float:
    """Height of a single row, accounting for multi-line fields."""
    max_lines = max(f.height_lines for f in row.fields)
    factor = COMPACT_ROW_HEIGHT_FACTOR if compact else ROW_HEIGHT_FACTOR
    return font_size * factor * max_lines


def _block_height(block: BlockVariant, font_size: float, compact: bool = False) -> float:
    """Total height a block needs at a given font_size."""
    h = 0.0
    if block.title:
        title_factor = COMPACT_TITLE_HEIGHT_FACTOR if compact else TITLE_HEIGHT_FACTOR
        h += font_size * title_factor
    for row in block.rows:
        h += _row_height(row, font_size, compact)
    return h


def _total_height(blocks: list[BlockVariant], font_size: float, compact: bool = False) -> float:
    """Total height of all blocks + inter-block gaps."""
    if not blocks:
        return 0.0
    gap_factor = COMPACT_BLOCK_GAP_FACTOR if compact else BLOCK_GAP_FACTOR
    h = sum(_block_height(b, font_size, compact) for b in blocks)
    h += font_size * gap_factor * (len(blocks) - 1)
    return h


# ---------------------------------------------------------------------------
# Font size solver (binary search)
# ---------------------------------------------------------------------------

def _solve_font_size(
    blocks: list[BlockVariant],
    available_height: float,
    lo: float = 4.0,
    hi: float = 60.0,
    precision: float = 0.25,
    compact: bool = False,
) -> float:
    """Find the largest font_size where all blocks fit in available_height."""
    best = lo
    while hi - lo > precision:
        mid = (lo + hi) / 2
        if _total_height(blocks, mid, compact) <= available_height:
            best = mid
            lo = mid
        else:
            hi = mid
    return best


# ---------------------------------------------------------------------------
# Field placement within a row
# ---------------------------------------------------------------------------

def _place_row_fields(
    row: RowDef,
    row_x: float,
    row_y: float,
    row_width: float,
    row_height: float,
    font_size: float,
    is_header_block: bool,
) -> list[FieldPlacement]:
    """Compute FieldPlacements for all fields in a row."""
    field_gap = font_size * FIELD_GAP_FACTOR
    placements = []

    cursor_x = row_x
    for i, fdef in enumerate(row.fields):
        fw = fdef.col_span * row_width
        # Subtract gap (except for last field)
        usable_w = fw - (field_gap if i < len(row.fields) - 1 else 0)

        label_h = font_size * LABEL_FONT_RATIO * 1.3  # label text height + small pad

        if fdef.style == FieldStyle.LABEL_ONLY:
            # Entire area is the label (header text, legal text, etc.)
            label_rect = (cursor_x, row_y, usable_w, row_height)
            value_rect = (cursor_x, row_y, 0.0, 0.0)  # no value area
        elif fdef.style == FieldStyle.INLINE:
            # Label and value on the same line
            est_label_w = len(fdef.label) * font_size * LABEL_FONT_RATIO * 0.6 + font_size
            est_label_w = min(est_label_w, usable_w * 0.6)
            label_rect = (cursor_x, row_y, est_label_w, row_height)
            value_rect = (cursor_x + est_label_w, row_y, usable_w - est_label_w, row_height)
        else:
            # UNDERLINE or BOX: label on top, value below
            label_rect = (cursor_x, row_y, usable_w, label_h)
            value_y = row_y + label_h
            value_h = row_height - label_h
            value_rect = (cursor_x, value_y, usable_w, value_h)

        placements.append(FieldPlacement(
            field_def=fdef,
            x=cursor_x,
            y=row_y,
            width=usable_w,
            height=row_height,
            label_rect=label_rect,
            value_rect=value_rect,
        ))
        cursor_x += fw

    return placements


# ---------------------------------------------------------------------------
# Main solver
# ---------------------------------------------------------------------------

def solve_layout(
    layout: DocumentLayout,
    content_rect: tuple[float, float, float, float],
    compact: bool = False,
) -> LayoutResult:
    """Solve for font size and compute all placements.

    Args:
        layout: DocumentLayout with blocks and font_family
        content_rect: (x, y, w, h) of the usable area inside the border
        compact: Use tighter spacing (for back pages with many blocks)

    Returns:
        LayoutResult with font_size and block/field placements
    """
    cx, cy, cw, ch = content_rect
    blocks = layout.blocks

    # Solve font size
    font_size = _solve_font_size(blocks, ch, compact=compact)
    layout.font_size = font_size

    pad_x_factor = COMPACT_PADDING_X_FACTOR if compact else PADDING_X_FACTOR
    gap_factor = COMPACT_BLOCK_GAP_FACTOR if compact else BLOCK_GAP_FACTOR
    title_factor = COMPACT_TITLE_HEIGHT_FACTOR if compact else TITLE_HEIGHT_FACTOR

    pad_x = font_size * pad_x_factor
    inner_x = cx + pad_x
    inner_w = cw - 2 * pad_x
    block_gap = font_size * gap_factor

    # Place blocks top to bottom
    cursor_y = cy
    block_placements: list[BlockPlacement] = []

    for block in blocks:
        bh = _block_height(block, font_size, compact)
        title_rect = None
        field_placements: list[FieldPlacement] = []

        row_y = cursor_y
        is_header = block.block_type.value == "header"

        # Section title
        if block.title:
            title_h = font_size * title_factor
            title_rect = (inner_x, row_y, inner_w, title_h)
            row_y += title_h

        # Rows
        for row in block.rows:
            rh = _row_height(row, font_size, compact)
            fps = _place_row_fields(row, inner_x, row_y, inner_w, rh, font_size, is_header)
            field_placements.extend(fps)
            row_y += rh

        block_placements.append(BlockPlacement(
            block=block,
            x=inner_x,
            y=cursor_y,
            width=inner_w,
            height=bh,
            title_rect=title_rect,
            field_placements=field_placements,
        ))

        cursor_y += bh + block_gap

    return LayoutResult(
        font_size=font_size,
        content_rect=content_rect,
        block_placements=block_placements,
    )
