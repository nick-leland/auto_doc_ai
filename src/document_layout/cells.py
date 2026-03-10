"""
Cell and block definitions for vehicle title document layout.

Each semantic section of a title (header, vehicle info, owner, lien, etc.)
is a BlockType. Each BlockType has multiple visual variants with different
label text, field arrangements, and proportions.

A document layout is an ordered list of chosen BlockVariants plus a font family.
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BlockType(str, Enum):
    HEADER = "header"
    VEHICLE_INFO = "vehicle_info"
    TITLE_META = "title_meta"
    OWNER = "owner"
    LIEN = "lien"
    LEGAL = "legal"


class FieldStyle(str, Enum):
    UNDERLINE = "underline"     # label above, underline for value
    BOX = "box"                 # label above, rectangular box for value
    INLINE = "inline"           # label: _______ on one line
    LABEL_ONLY = "label_only"   # just text, no input area


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FieldDef:
    """One fillable field within a block."""
    name: str               # machine key: "vin", "owner_name", etc.
    label: str              # display label: "VEHICLE IDENTIFICATION NUMBER"
    col_span: float = 1.0   # fraction of row width (0.0–1.0)
    style: FieldStyle = FieldStyle.UNDERLINE
    field_type: str = "text"     # "text", "date", "signature", "checkbox"
    height_lines: int = 1        # how many text lines tall


@dataclass
class RowDef:
    """A horizontal row of fields within a block."""
    fields: list[FieldDef]


@dataclass
class BlockVariant:
    """One visual variant of a semantic block."""
    block_type: BlockType
    variant_id: str
    title: str | None = None
    rows: list[RowDef] = field(default_factory=list)
    height_weight: float = 1.0
    title_style: Literal["banner", "left", "center", "none"] = "left"


@dataclass
class DocumentLayout:
    """A complete document layout: ordered list of blocks + font info."""
    blocks: list[BlockVariant]
    font_family: str = "Helvetica"
    font_size: float = 0.0  # solved by packing engine
    border_text: str = ""          # state identity text for the top border
    bottom_border_text: str = ""   # void/legal text for the bottom border


# ---------------------------------------------------------------------------
# Font pool
# ---------------------------------------------------------------------------

FONT_FAMILIES = [
    "Helvetica",
    "Arial",
    "Times New Roman",
    "Courier New",
    "Georgia",
    "Palatino",
]


# ---------------------------------------------------------------------------
# Variant pool
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Border text pool (rendered via border_text() on the document border)
# ---------------------------------------------------------------------------

BORDER_TEXT_TEMPLATES: list[str] = [
    "{STATE_NAME}",
    "STATE OF {STATE_NAME}",
    "{STATE_NAME} DEPARTMENT OF MOTOR VEHICLES",
    "{STATE_NAME} DMV",
    "STATE OF {STATE_NAME} DMV",
]


# ---------------------------------------------------------------------------
# Document title pool (rendered as header block inside the content area)
# ---------------------------------------------------------------------------

DOCUMENT_TITLES: list[str] = [
    "CERTIFICATE OF TITLE",
    "VEHICLE TITLE CERTIFICATE",
    "CERTIFICATE OF TITLE FOR A MOTOR VEHICLE",
    "MOTOR VEHICLE CERTIFICATE OF TITLE",
    "CERTIFICATE OF OWNERSHIP",
]


def _header_variants() -> list[BlockVariant]:
    """Header variants — document title only (state name goes in the border)."""
    return [
        BlockVariant(
            block_type=BlockType.HEADER,
            variant_id="header_v1",
            title=None,
            title_style="none",
            height_weight=0.5,
            rows=[
                RowDef([FieldDef("doc_title", "{DOC_TITLE}", style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.HEADER,
            variant_id="header_v2",
            title=None,
            title_style="none",
            height_weight=0.7,
            rows=[
                RowDef([FieldDef("doc_title", "{DOC_TITLE}", style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef("subtitle", "FOR A MOTOR VEHICLE", style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
    ]


def _vehicle_info_variants() -> list[BlockVariant]:
    return [
        BlockVariant(
            block_type=BlockType.VEHICLE_INFO,
            variant_id="vehicle_info_v1",
            title="VEHICLE DESCRIPTION",
            title_style="left",
            height_weight=1.5,
            rows=[
                RowDef([FieldDef("vin", "VEHICLE IDENTIFICATION NO.")]),
                RowDef([
                    FieldDef("year", "YEAR", col_span=0.2),
                    FieldDef("make", "MAKE", col_span=0.3),
                    FieldDef("model", "MODEL", col_span=0.3),
                    FieldDef("body", "BODY TYPE", col_span=0.2),
                ]),
                RowDef([
                    FieldDef("weight", "WEIGHT", col_span=0.33),
                    FieldDef("cylinders", "CYL", col_span=0.33),
                    FieldDef("fuel", "FUEL", col_span=0.34),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.VEHICLE_INFO,
            variant_id="vehicle_info_v2",
            title="DESCRIPTION OF VEHICLE",
            title_style="center",
            height_weight=1.6,
            rows=[
                RowDef([
                    FieldDef("vin", "VIN", col_span=0.6),
                    FieldDef("year", "YEAR", col_span=0.4),
                ]),
                RowDef([
                    FieldDef("make", "MAKE", col_span=0.5),
                    FieldDef("model", "MODEL", col_span=0.5),
                ]),
                RowDef([
                    FieldDef("body", "BODY STYLE", col_span=0.25),
                    FieldDef("weight", "GVW", col_span=0.25),
                    FieldDef("cylinders", "CYL", col_span=0.25),
                    FieldDef("color", "COLOR", col_span=0.25),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.VEHICLE_INFO,
            variant_id="vehicle_info_v3",
            title="VEHICLE INFORMATION",
            title_style="left",
            height_weight=1.2,
            rows=[
                RowDef([FieldDef("vin", "VEHICLE IDENTIFICATION NUMBER")]),
                RowDef([
                    FieldDef("year", "YR", col_span=0.12),
                    FieldDef("make", "MAKE", col_span=0.23),
                    FieldDef("model", "MODEL", col_span=0.23),
                    FieldDef("body", "BODY", col_span=0.14),
                    FieldDef("weight", "WT", col_span=0.14),
                    FieldDef("cylinders", "CYL", col_span=0.14),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.VEHICLE_INFO,
            variant_id="vehicle_info_v4",
            title="MOTOR VEHICLE DESCRIPTION",
            title_style="banner",
            height_weight=1.8,
            rows=[
                RowDef([FieldDef("vin", "VEHICLE IDENTIFICATION NUMBER")]),
                RowDef([
                    FieldDef("year", "YEAR OF MANUFACTURE", col_span=0.5),
                    FieldDef("make", "MANUFACTURER", col_span=0.5),
                ]),
                RowDef([
                    FieldDef("model", "MODEL / SERIES", col_span=0.5),
                    FieldDef("body", "BODY TYPE / STYLE", col_span=0.5),
                ]),
                RowDef([
                    FieldDef("weight", "GROSS VEHICLE WEIGHT", col_span=0.33),
                    FieldDef("cylinders", "NO. OF CYLINDERS", col_span=0.33),
                    FieldDef("fuel", "FUEL TYPE", col_span=0.34),
                ]),
            ],
        ),
    ]


def _title_meta_variants() -> list[BlockVariant]:
    return [
        BlockVariant(
            block_type=BlockType.TITLE_META,
            variant_id="title_meta_v1",
            title=None,
            title_style="none",
            height_weight=0.7,
            rows=[
                RowDef([
                    FieldDef("title_no", "TITLE NO.", col_span=0.33),
                    FieldDef("date_issued", "DATE ISSUED", col_span=0.33, field_type="date"),
                    FieldDef("date_first_sold", "DATE FIRST SOLD", col_span=0.34, field_type="date"),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.TITLE_META,
            variant_id="title_meta_v2",
            title=None,
            title_style="none",
            height_weight=1.0,
            rows=[
                RowDef([
                    FieldDef("title_no", "TITLE SEQUENCE NUMBER", col_span=0.5),
                    FieldDef("date_issued", "ISSUE DATE", col_span=0.5, field_type="date"),
                ]),
                RowDef([
                    FieldDef("date_first_sold", "IF NEW, DATE FIRST SOLD", col_span=0.5, field_type="date"),
                    FieldDef("odometer", "ODOMETER READING", col_span=0.5),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.TITLE_META,
            variant_id="title_meta_v3",
            title=None,
            title_style="none",
            height_weight=0.6,
            rows=[
                RowDef([
                    FieldDef("title_no", "TITLE NO.", col_span=0.25),
                    FieldDef("date_issued", "ISSUED", col_span=0.25, field_type="date"),
                    FieldDef("date_first_sold", "FIRST SOLD", col_span=0.25, field_type="date"),
                    FieldDef("odometer", "ODOMETER", col_span=0.25),
                ]),
            ],
        ),
    ]


def _owner_variants() -> list[BlockVariant]:
    return [
        BlockVariant(
            block_type=BlockType.OWNER,
            variant_id="owner_v1",
            title="OWNER(S)",
            title_style="left",
            height_weight=1.5,
            rows=[
                RowDef([FieldDef("owner_name_1", "NAME")]),
                RowDef([FieldDef("owner_name_2", "AND / OR")]),
                RowDef([FieldDef("owner_address", "ADDRESS", height_lines=2)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.OWNER,
            variant_id="owner_v2",
            title="REGISTERED OWNER",
            title_style="center",
            height_weight=1.8,
            rows=[
                RowDef([
                    FieldDef("owner_first", "FIRST NAME", col_span=0.4),
                    FieldDef("owner_mi", "MI", col_span=0.1),
                    FieldDef("owner_last", "LAST NAME", col_span=0.5),
                ]),
                RowDef([FieldDef("owner_street", "STREET ADDRESS")]),
                RowDef([
                    FieldDef("owner_city", "CITY", col_span=0.5),
                    FieldDef("owner_state", "STATE", col_span=0.2),
                    FieldDef("owner_zip", "ZIP CODE", col_span=0.3),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.OWNER,
            variant_id="owner_v3",
            title="VEHICLE OWNER(S)",
            title_style="left",
            height_weight=1.3,
            rows=[
                RowDef([FieldDef("owner_name", "OWNER NAME(S)")]),
                RowDef([FieldDef("owner_address", "MAILING ADDRESS", height_lines=2)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.OWNER,
            variant_id="owner_v4",
            title="TITLED OWNER",
            title_style="banner",
            height_weight=1.6,
            rows=[
                RowDef([
                    FieldDef("owner_last", "LAST NAME / BUSINESS NAME", col_span=0.6),
                    FieldDef("owner_first", "FIRST NAME", col_span=0.4),
                ]),
                RowDef([
                    FieldDef("owner_last_2", "CO-OWNER LAST NAME", col_span=0.6),
                    FieldDef("owner_first_2", "CO-OWNER FIRST NAME", col_span=0.4),
                ]),
                RowDef([FieldDef("owner_address", "ADDRESS")]),
                RowDef([
                    FieldDef("owner_city", "CITY", col_span=0.5),
                    FieldDef("owner_state", "STATE", col_span=0.15),
                    FieldDef("owner_zip", "ZIP", col_span=0.35),
                ]),
            ],
        ),
    ]


def _lien_variants(ordinal: str = "FIRST") -> list[BlockVariant]:
    tag = ordinal.lower()
    return [
        BlockVariant(
            block_type=BlockType.LIEN,
            variant_id=f"lien_{tag}_v1",
            title=f"{ordinal} LIENHOLDER",
            title_style="left",
            height_weight=2.0,
            rows=[
                RowDef([FieldDef(f"{tag}_lien_name", "NAME OF LIENHOLDER")]),
                RowDef([FieldDef(f"{tag}_lien_address", "ADDRESS")]),
                RowDef([
                    FieldDef(f"{tag}_lien_date", "DATE OF LIEN", col_span=0.5, field_type="date"),
                    FieldDef(f"{tag}_lien_elt", "ELT NUMBER", col_span=0.5),
                ]),
                RowDef([FieldDef(f"{tag}_release_label",
                        f"RELEASE OF LIEN ({ordinal} LIEN) — Interest in the above described vehicle is hereby released.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_release_sig", "SIGNATURE", col_span=0.6, field_type="signature"),
                    FieldDef(f"{tag}_release_date", "DATE RELEASED", col_span=0.4, field_type="date"),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.LIEN,
            variant_id=f"lien_{tag}_v2",
            title=f"{ordinal} SECURITY INTEREST",
            title_style="center",
            height_weight=1.7,
            rows=[
                RowDef([
                    FieldDef(f"{tag}_lien_name", "LIENHOLDER", col_span=0.6),
                    FieldDef(f"{tag}_lien_date", "DATE", col_span=0.4, field_type="date"),
                ]),
                RowDef([FieldDef(f"{tag}_lien_address", "LIENHOLDER ADDRESS")]),
                RowDef([FieldDef(f"{tag}_release_label",
                        "RELEASE: The undersigned hereby releases all interest in the vehicle described herein.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_release_sig", "AUTHORIZED SIGNATURE", col_span=0.5, field_type="signature"),
                    FieldDef(f"{tag}_release_date", "DATE", col_span=0.25, field_type="date"),
                    FieldDef(f"{tag}_release_title", "TITLE (IF ANY)", col_span=0.25),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.LIEN,
            variant_id=f"lien_{tag}_v3",
            title=f"{ordinal} LIEN",
            title_style="banner",
            height_weight=2.2,
            rows=[
                RowDef([FieldDef(f"{tag}_lien_name", "NAME AND ADDRESS OF LIENHOLDER", height_lines=2)]),
                RowDef([
                    FieldDef(f"{tag}_lien_date", "DATE OF LIEN", col_span=0.33, field_type="date"),
                    FieldDef(f"{tag}_lien_elt", "ELECTRONIC LIEN", col_span=0.33),
                    FieldDef(f"{tag}_lien_id", "LIEN ID NUMBER", col_span=0.34),
                ]),
                RowDef([FieldDef(f"{tag}_release_label",
                        f"RELEASE OF {ordinal} LIEN — I certify that the lien on the vehicle described herein has been satisfied.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_release_sig", "SIGNATURE OF LIENHOLDER OR AGENT", field_type="signature")]),
                RowDef([
                    FieldDef(f"{tag}_release_date", "DATE RELEASED", col_span=0.5, field_type="date"),
                    FieldDef(f"{tag}_release_title", "PRINTED NAME / TITLE", col_span=0.5),
                ]),
            ],
        ),
    ]


def _legal_variants() -> list[BlockVariant]:
    return [
        BlockVariant(
            block_type=BlockType.LEGAL,
            variant_id="legal_v1",
            title=None,
            title_style="none",
            height_weight=0.4,
            rows=[
                RowDef([FieldDef("legal_text",
                        "VOID UNLESS OFFICIALLY STAMPED. This document is proof of ownership. Keep it in a safe place.",
                        style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.LEGAL,
            variant_id="legal_v2",
            title=None,
            title_style="none",
            height_weight=0.5,
            rows=[
                RowDef([FieldDef("legal_text",
                        "THIS CERTIFICATE OF TITLE IS VOID IF ALTERED OR ERASED. "
                        "Keep this document in a safe place — not with your registration or in your vehicle.",
                        style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.LEGAL,
            variant_id="legal_v3",
            title=None,
            title_style="none",
            height_weight=0.6,
            rows=[
                RowDef([FieldDef("legal_text",
                        "THIS DOCUMENT IS PROOF OF YOUR OWNERSHIP OF THIS VEHICLE. "
                        "Keep it in a safe place, not with your license, registration, or in your car. "
                        "To dispose of your vehicle, complete the transfer section on the reverse side "
                        "and give the title to the new owner.",
                        style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.LEGAL,
            variant_id="legal_v4",
            title=None,
            title_style="none",
            height_weight=0.5,
            rows=[
                RowDef([FieldDef("legal_text",
                        "ANY ALTERATION OR ERASURE VOIDS THIS TITLE. "
                        "Any false statement herein may be punishable as a misdemeanor or felony.",
                        style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Complete variant pool
# ---------------------------------------------------------------------------

VARIANT_POOL: dict[BlockType, list[BlockVariant]] = {
    BlockType.HEADER: _header_variants(),
    BlockType.VEHICLE_INFO: _vehicle_info_variants(),
    BlockType.TITLE_META: _title_meta_variants(),
    BlockType.OWNER: _owner_variants(),
    BlockType.LIEN: [],  # built dynamically with ordinal
    BlockType.LEGAL: _legal_variants(),
}


# ---------------------------------------------------------------------------
# Layout builder
# ---------------------------------------------------------------------------

# Front side block order
FRONT_BLOCK_ORDER: list[BlockType] = [
    BlockType.HEADER,
    BlockType.VEHICLE_INFO,
    BlockType.TITLE_META,
    BlockType.OWNER,
    BlockType.LIEN,     # first lien
    BlockType.LIEN,     # second lien (may be omitted)
    BlockType.LEGAL,
]


def build_random_layout(
    state_name: str = "SAMPLE STATE",
    rng: random.Random | None = None,
) -> DocumentLayout:
    """Pick one variant per block type and assemble a document layout.

    Returns a DocumentLayout with:
      - blocks: ordered list of BlockVariants for the content area
      - border_text: state identity string for the document border
      - font_family: randomly chosen font
    """
    if rng is None:
        rng = random.Random()

    font_family = rng.choice(FONT_FAMILIES)

    # Pick border text (state identity) and document title (no overlap)
    border_template = rng.choice(BORDER_TEXT_TEMPLATES)
    border_text_str = border_template.replace("{STATE_NAME}", state_name.upper())
    doc_title = rng.choice(DOCUMENT_TITLES)

    # Pick bottom border text (void/legal message)
    from src.data.static import BOTTOM_TEXT
    bottom_border_str = rng.choice(BOTTOM_TEXT)

    blocks: list[BlockVariant] = []

    # Always include both lien blocks on the front page
    num_liens = 2
    lien_ordinals = ["FIRST", "SECOND"]

    # Pre-generate lien variants
    lien_variants_by_ordinal: dict[str, list[BlockVariant]] = {}
    # Pick one lien style index, use it for both liens (consistent look)
    lien_style_idx = rng.randint(0, 2)

    for ordinal in lien_ordinals[:num_liens]:
        variants = _lien_variants(ordinal)
        idx = min(lien_style_idx, len(variants) - 1)
        lien_variants_by_ordinal[ordinal] = [variants[idx]]

    lien_counter = 0
    for block_type in FRONT_BLOCK_ORDER:
        if block_type == BlockType.LIEN:
            if lien_counter >= num_liens:
                continue
            ordinal = lien_ordinals[lien_counter]
            variant = lien_variants_by_ordinal[ordinal][0]
            lien_counter += 1
        else:
            pool = VARIANT_POOL[block_type]
            variant = rng.choice(pool)

        # Deep-copy and substitute placeholders
        variant = _copy_variant(variant, state_name, doc_title)
        blocks.append(variant)

    return DocumentLayout(
        blocks=blocks,
        font_family=font_family,
        border_text=border_text_str,
        bottom_border_text=bottom_border_str,
    )


def _copy_variant(variant: BlockVariant, state_name: str, doc_title: str = "") -> BlockVariant:
    """Create a copy of a variant with placeholders replaced."""
    new_rows = []
    for row in variant.rows:
        new_fields = []
        for f in row.fields:
            label = f.label.replace("{STATE_NAME}", state_name.upper())
            label = label.replace("{DOC_TITLE}", doc_title)
            new_fields.append(FieldDef(
                name=f.name, label=label, col_span=f.col_span,
                style=f.style, field_type=f.field_type,
                height_lines=f.height_lines,
            ))
        new_rows.append(RowDef(new_fields))

    return BlockVariant(
        block_type=variant.block_type,
        variant_id=variant.variant_id,
        title=variant.title,
        rows=new_rows,
        height_weight=variant.height_weight,
        title_style=variant.title_style,
    )
