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
    # Front side
    HEADER = "header"
    VEHICLE_INFO = "vehicle_info"
    TITLE_META = "title_meta"
    OWNER = "owner"
    LIEN = "lien"
    LEGAL = "legal"
    # Back side
    BACK_WARNING = "back_warning"
    TRANSFER = "transfer"
    DEALER_REASSIGNMENT = "dealer_reassignment"
    NOTARY = "notary"
    DAMAGE_DISCLOSURE = "damage_disclosure"
    VIN_VERIFICATION = "vin_verification"
    POWER_OF_ATTORNEY = "power_of_attorney"
    TAX_FEE = "tax_fee"
    BACK_LEGAL = "back_legal"


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
    side_border_text: str = ""     # void/fraud warning for the side borders
    bottom_border_text: str = ""   # void/legal text for the bottom border


# ---------------------------------------------------------------------------
# Font pool
# ---------------------------------------------------------------------------

FONT_FAMILIES = [
    "Helvetica",
    "Arial",
    "Frutiger",
    "Myriad Pro",
    "Univers",
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
            height_weight=1.8,
            rows=[
                RowDef([FieldDef("vin", "VEHICLE IDENTIFICATION NO.")]),
                RowDef([
                    FieldDef("year", "YEAR", col_span=0.15),
                    FieldDef("make", "MAKE", col_span=0.25),
                    FieldDef("model", "MODEL", col_span=0.25),
                    FieldDef("body", "BODY TYPE", col_span=0.15),
                    FieldDef("color", "COLOR", col_span=0.2),
                ]),
                RowDef([
                    FieldDef("weight", "WEIGHT", col_span=0.25),
                    FieldDef("cylinders", "CYL", col_span=0.25),
                    FieldDef("fuel", "FUEL", col_span=0.25),
                    FieldDef("plate_no", "PLATE NO.", col_span=0.25),
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
                    FieldDef("make", "MAKE", col_span=0.35),
                    FieldDef("model", "MODEL", col_span=0.35),
                    FieldDef("color", "MAJOR COLOR", col_span=0.3),
                ]),
                RowDef([
                    FieldDef("body", "BODY STYLE", col_span=0.25),
                    FieldDef("weight", "GVW", col_span=0.25),
                    FieldDef("cylinders", "CYL", col_span=0.25),
                    FieldDef("plate_no", "LICENSE PLATE", col_span=0.25),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.VEHICLE_INFO,
            variant_id="vehicle_info_v3",
            title="VEHICLE INFORMATION",
            title_style="left",
            height_weight=1.5,
            rows=[
                RowDef([FieldDef("vin", "VEHICLE IDENTIFICATION NUMBER")]),
                RowDef([
                    FieldDef("year", "YR", col_span=0.1),
                    FieldDef("make", "MAKE", col_span=0.2),
                    FieldDef("model", "MODEL", col_span=0.2),
                    FieldDef("body", "BODY", col_span=0.12),
                    FieldDef("color", "COLOR", col_span=0.12),
                    FieldDef("weight", "WT", col_span=0.12),
                    FieldDef("cylinders", "CYL", col_span=0.12),
                ]),
                RowDef([
                    FieldDef("fuel", "FUEL TYPE", col_span=0.33),
                    FieldDef("plate_no", "PLATE NUMBER", col_span=0.33),
                    FieldDef("prev_title_state", "PREVIOUS TITLE STATE", col_span=0.34),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.VEHICLE_INFO,
            variant_id="vehicle_info_v4",
            title="MOTOR VEHICLE DESCRIPTION",
            title_style="banner",
            height_weight=2.0,
            rows=[
                RowDef([FieldDef("vin", "VEHICLE IDENTIFICATION NUMBER")]),
                RowDef([
                    FieldDef("year", "YEAR OF MANUFACTURE", col_span=0.35),
                    FieldDef("make", "MANUFACTURER", col_span=0.35),
                    FieldDef("color", "COLOR", col_span=0.3),
                ]),
                RowDef([
                    FieldDef("model", "MODEL / SERIES", col_span=0.5),
                    FieldDef("body", "BODY TYPE / STYLE", col_span=0.5),
                ]),
                RowDef([
                    FieldDef("weight", "GROSS VEHICLE WEIGHT", col_span=0.25),
                    FieldDef("cylinders", "NO. OF CYLINDERS", col_span=0.25),
                    FieldDef("fuel", "FUEL TYPE", col_span=0.25),
                    FieldDef("plate_no", "LICENSE PLATE NO.", col_span=0.25),
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
            height_weight=1.0,
            rows=[
                RowDef([
                    FieldDef("title_no", "TITLE NO.", col_span=0.25),
                    FieldDef("title_type", "TITLE TYPE", col_span=0.25),
                    FieldDef("date_issued", "DATE ISSUED", col_span=0.25, field_type="date"),
                    FieldDef("date_first_sold", "DATE FIRST SOLD", col_span=0.25, field_type="date"),
                ]),
                RowDef([
                    FieldDef("title_brand", "BRANDS / REMARKS", col_span=0.5),
                    FieldDef("county", "COUNTY", col_span=0.5),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.TITLE_META,
            variant_id="title_meta_v2",
            title=None,
            title_style="none",
            height_weight=1.3,
            rows=[
                RowDef([
                    FieldDef("title_no", "TITLE SEQUENCE NUMBER", col_span=0.4),
                    FieldDef("title_type", "TYPE", col_span=0.2),
                    FieldDef("date_issued", "ISSUE DATE", col_span=0.4, field_type="date"),
                ]),
                RowDef([
                    FieldDef("date_first_sold", "IF NEW, DATE FIRST SOLD", col_span=0.5, field_type="date"),
                    FieldDef("odometer", "ODOMETER READING", col_span=0.5),
                ]),
                RowDef([
                    FieldDef("title_brand", "TITLE BRAND / STATUS", col_span=0.5),
                    FieldDef("prev_title_no", "PREVIOUS TITLE NO.", col_span=0.5),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.TITLE_META,
            variant_id="title_meta_v3",
            title=None,
            title_style="none",
            height_weight=0.7,
            rows=[
                RowDef([
                    FieldDef("title_no", "TITLE NO.", col_span=0.2),
                    FieldDef("title_type", "TYPE", col_span=0.15),
                    FieldDef("date_issued", "ISSUED", col_span=0.2, field_type="date"),
                    FieldDef("date_first_sold", "FIRST SOLD", col_span=0.2, field_type="date"),
                    FieldDef("odometer", "ODOMETER", col_span=0.25),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.TITLE_META,
            variant_id="title_meta_v4",
            title=None,
            title_style="none",
            height_weight=1.0,
            rows=[
                RowDef([
                    FieldDef("title_no", "DOCUMENT NUMBER", col_span=0.35),
                    FieldDef("date_issued", "DATE ISSUED", col_span=0.35, field_type="date"),
                    FieldDef("county", "COUNTY OF ISSUANCE", col_span=0.3),
                ]),
                RowDef([
                    FieldDef("title_type", "TITLE TYPE", col_span=0.25),
                    FieldDef("title_brand", "REMARKS", col_span=0.4),
                    FieldDef("odometer", "ODOMETER", col_span=0.35),
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
            height_weight=1.8,
            rows=[
                RowDef([FieldDef("owner_name_1", "NAME")]),
                RowDef([
                    FieldDef("owner_name_2", "AND / OR", col_span=0.7),
                    FieldDef("ownership_type", "OWNERSHIP", col_span=0.3),
                ]),
                RowDef([FieldDef("owner_address", "ADDRESS", height_lines=2)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.OWNER,
            variant_id="owner_v2",
            title="REGISTERED OWNER",
            title_style="center",
            height_weight=2.1,
            rows=[
                RowDef([
                    FieldDef("owner_first", "FIRST NAME", col_span=0.35),
                    FieldDef("owner_mi", "MI", col_span=0.1),
                    FieldDef("owner_last", "LAST NAME", col_span=0.35),
                    FieldDef("owner_dl", "DL / ID NO.", col_span=0.2),
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
            height_weight=1.8,
            rows=[
                RowDef([
                    FieldDef("owner_name", "OWNER NAME(S)", col_span=0.7),
                    FieldDef("ownership_type", "[ ] AND  [ ] OR  [ ] JTWROS", col_span=0.3),
                ]),
                RowDef([FieldDef("owner_address", "MAILING ADDRESS", height_lines=2)]),
                RowDef([FieldDef("owner_tod", "TRANSFER ON DEATH BENEFICIARY (if applicable)")]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.OWNER,
            variant_id="owner_v4",
            title="TITLED OWNER",
            title_style="banner",
            height_weight=2.0,
            rows=[
                RowDef([
                    FieldDef("owner_last", "LAST NAME / BUSINESS NAME", col_span=0.5),
                    FieldDef("owner_first", "FIRST NAME", col_span=0.3),
                    FieldDef("owner_dl", "DL / ID NO.", col_span=0.2),
                ]),
                RowDef([
                    FieldDef("owner_last_2", "CO-OWNER LAST NAME", col_span=0.4),
                    FieldDef("owner_first_2", "CO-OWNER FIRST NAME", col_span=0.3),
                    FieldDef("ownership_type", "OWNERSHIP TYPE", col_span=0.3),
                ]),
                RowDef([FieldDef("owner_address", "ADDRESS")]),
                RowDef([
                    FieldDef("owner_city", "CITY", col_span=0.5),
                    FieldDef("owner_state", "STATE", col_span=0.15),
                    FieldDef("owner_zip", "ZIP", col_span=0.35),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.OWNER,
            variant_id="owner_v5",
            title="OWNER INFORMATION",
            title_style="left",
            height_weight=2.2,
            rows=[
                RowDef([
                    FieldDef("owner_name_1", "OWNER NAME", col_span=0.6),
                    FieldDef("owner_dl", "DRIVER LICENSE NO.", col_span=0.4),
                ]),
                RowDef([
                    FieldDef("owner_name_2", "CO-OWNER NAME", col_span=0.6),
                    FieldDef("owner_dl_2", "CO-OWNER DL NO.", col_span=0.4),
                ]),
                RowDef([
                    FieldDef("ownership_type", "OWNERSHIP (AND/OR/JTWROS)", col_span=0.5),
                    FieldDef("owner_tod", "TOD BENEFICIARY", col_span=0.5),
                ]),
                RowDef([FieldDef("owner_address", "MAILING ADDRESS", height_lines=2)]),
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
# Back side variants
# ---------------------------------------------------------------------------

def _back_warning_variants() -> list[BlockVariant]:
    return [
        BlockVariant(
            block_type=BlockType.BACK_WARNING,
            variant_id="back_warning_v1",
            title=None,
            title_style="none",
            height_weight=0.6,
            rows=[
                RowDef([FieldDef("warning_text",
                        "WARNING: FEDERAL AND STATE LAWS REQUIRE THAT YOU STATE THE MILEAGE IN CONNECTION "
                        "WITH THE TRANSFER OF OWNERSHIP. FAILURE TO COMPLETE OR PROVIDING A FALSE STATEMENT "
                        "MAY RESULT IN FINES AND/OR IMPRISONMENT.",
                        style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.BACK_WARNING,
            variant_id="back_warning_v2",
            title=None,
            title_style="none",
            height_weight=0.6,
            rows=[
                RowDef([FieldDef("warning_text",
                        "IMPORTANT: FEDERAL AND STATE LAW REQUIRES DISCLOSURE OF THE VEHICLE MILEAGE UPON "
                        "TRANSFER OF OWNERSHIP. AN INACCURATE OR INCOMPLETE STATEMENT MAY SUBJECT YOU TO "
                        "CRIMINAL AND/OR CIVIL PENALTIES.",
                        style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.BACK_WARNING,
            variant_id="back_warning_v3",
            title=None,
            title_style="none",
            height_weight=0.5,
            rows=[
                RowDef([FieldDef("warning_text",
                        "NOTICE: ODOMETER DISCLOSURE IS REQUIRED BY FEDERAL AND STATE LAW. "
                        "FALSE STATEMENTS ARE PUNISHABLE BY FINE AND/OR IMPRISONMENT.",
                        style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
    ]


def _transfer_variants(tag: str = "transfer") -> list[BlockVariant]:
    """Transfer by owner section. Tag prefixes all field names."""
    return [
        BlockVariant(
            block_type=BlockType.TRANSFER,
            variant_id=f"{tag}_v1",
            title="TRANSFER BY OWNER",
            title_style="banner",
            height_weight=4.0,
            rows=[
                RowDef([FieldDef(f"{tag}_preamble",
                        "The undersigned hereby assign and warrant title of this vehicle, subject to the liens "
                        "described on the face of this certificate, to:",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_buyer_name", "BUYER(S) NAME")]),
                RowDef([FieldDef(f"{tag}_buyer_address", "ADDRESS", height_lines=2)]),
                RowDef([
                    FieldDef(f"{tag}_new_lien", "LIENHOLDER (if none, state none)", col_span=0.6),
                    FieldDef(f"{tag}_new_lien_date", "DATE OF LIEN", col_span=0.4, field_type="date"),
                ]),
                RowDef([FieldDef(f"{tag}_new_lien_address", "LIENHOLDER ADDRESS")]),
                RowDef([FieldDef(f"{tag}_odom_label",
                        "ODOMETER DISCLOSURE STATEMENT",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odometer", "I state that the odometer now reads (NO TENTHS) miles:")]),
                RowDef([FieldDef(f"{tag}_odom_check1",
                        "[ ] Mileage is in excess of its mechanical limits.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odom_check2",
                        "[ ] Odometer reading is NOT the actual mileage. WARNING — ODOMETER DISCREPANCY.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odom_exempt",
                        "[ ] EXEMPT — Vehicle is 20 model years or older and not required to have odometer disclosure.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_gift_check",
                        "[ ] GIFT — This vehicle is being transferred as a gift. No consideration was given.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_seller_sig", "SIGNATURE(S) OF SELLER(S)", col_span=0.5, field_type="signature"),
                    FieldDef(f"{tag}_buyer_sig", "SIGNATURE(S) OF BUYER(S)", col_span=0.5, field_type="signature"),
                ]),
                RowDef([
                    FieldDef(f"{tag}_seller_print", "HAND PRINT NAME OF SELLER(S)", col_span=0.5),
                    FieldDef(f"{tag}_buyer_print", "HAND PRINT NAME OF BUYER(S)", col_span=0.5),
                ]),
                RowDef([
                    FieldDef(f"{tag}_seller_dl", "SELLER DL / ID NO.", col_span=0.5),
                    FieldDef(f"{tag}_buyer_dl", "BUYER DL / ID NO.", col_span=0.5),
                ]),
                RowDef([
                    FieldDef(f"{tag}_date", "DATE", col_span=0.5, field_type="date"),
                    FieldDef(f"{tag}_sale_price", "PURCHASE PRICE $", col_span=0.5),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.TRANSFER,
            variant_id=f"{tag}_v2",
            title="ASSIGNMENT OF TITLE BY OWNER",
            title_style="left",
            height_weight=3.5,
            rows=[
                RowDef([FieldDef(f"{tag}_preamble",
                        "I/We hereby assign, transfer, and warrant title to the vehicle described on the face "
                        "of this certificate to the following purchaser(s):",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_buyer_name", "NAME OF BUYER(S)", col_span=0.4),
                    FieldDef(f"{tag}_date", "DATE OF SALE", col_span=0.3, field_type="date"),
                    FieldDef(f"{tag}_sale_price", "SALE PRICE $", col_span=0.3),
                ]),
                RowDef([FieldDef(f"{tag}_buyer_address", "BUYER ADDRESS", height_lines=2)]),
                RowDef([
                    FieldDef(f"{tag}_new_lien", "NEW LIENHOLDER", col_span=0.5),
                    FieldDef(f"{tag}_new_lien_address", "LIENHOLDER ADDRESS", col_span=0.5),
                ]),
                RowDef([FieldDef(f"{tag}_new_lien_date", "DATE OF LIEN", field_type="date")]),
                RowDef([FieldDef(f"{tag}_odom_label",
                        "ODOMETER DISCLOSURE — I state that the odometer now reads:",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odometer", "MILES (NO TENTHS)")]),
                RowDef([FieldDef(f"{tag}_odom_check1",
                        "[ ] EXCEEDS MECHANICAL LIMITS  [ ] ODOMETER DISCREPANCY  [ ] EXEMPT",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_gift_check",
                        "[ ] GIFT TRANSFER — No monetary consideration was exchanged for this vehicle.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_seller_sig", "SELLER SIGNATURE", col_span=0.5, field_type="signature"),
                    FieldDef(f"{tag}_buyer_sig", "BUYER SIGNATURE", col_span=0.5, field_type="signature"),
                ]),
                RowDef([
                    FieldDef(f"{tag}_seller_print", "SELLER PRINTED NAME", col_span=0.5),
                    FieldDef(f"{tag}_buyer_print", "BUYER PRINTED NAME", col_span=0.5),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.TRANSFER,
            variant_id=f"{tag}_v3",
            title="TRANSFER OF OWNERSHIP",
            title_style="center",
            height_weight=3.5,
            rows=[
                RowDef([FieldDef(f"{tag}_preamble",
                        "The undersigned seller(s) certify that the described vehicle is transferred to the "
                        "buyer(s) named below, subject to any liens noted herein.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_buyer_name", "PURCHASER(S) NAME (PLEASE PRINT)")]),
                RowDef([FieldDef(f"{tag}_buyer_address", "PURCHASER ADDRESS", height_lines=2)]),
                RowDef([
                    FieldDef(f"{tag}_new_lien", "LIENHOLDER (IF NONE, STATE NONE)", col_span=0.6),
                    FieldDef(f"{tag}_new_lien_date", "LIEN DATE", col_span=0.4, field_type="date"),
                ]),
                RowDef([FieldDef(f"{tag}_new_lien_address", "LIENHOLDER ADDRESS")]),
                RowDef([FieldDef(f"{tag}_odom_label",
                        "ODOMETER DISCLOSURE STATEMENT",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odometer",
                        "THE ODOMETER NOW READS (NO TENTHS) MILES")]),
                RowDef([FieldDef(f"{tag}_odom_check1",
                        "[ ] Mileage in excess of mechanical limits  [ ] Odometer reading is not actual mileage  [ ] Exempt",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_seller_sig", "SIGNATURE OF SELLER(S)", col_span=0.5, field_type="signature"),
                    FieldDef(f"{tag}_date", "DATE", col_span=0.5, field_type="date"),
                ]),
                RowDef([
                    FieldDef(f"{tag}_buyer_sig", "SIGNATURE OF BUYER(S)", col_span=0.5, field_type="signature"),
                    FieldDef(f"{tag}_buyer_print", "PRINT BUYER NAME", col_span=0.5),
                ]),
                RowDef([
                    FieldDef(f"{tag}_seller_print", "PRINT SELLER NAME", col_span=0.35),
                    FieldDef(f"{tag}_seller_dl", "SELLER DL NO.", col_span=0.3),
                    FieldDef(f"{tag}_sale_price", "PURCHASE PRICE $", col_span=0.35),
                ]),
            ],
        ),
    ]


def _dealer_reassignment_variants(ordinal: str = "FIRST") -> list[BlockVariant]:
    """Dealer reassignment section. Ordinal is FIRST or SECOND."""
    tag = f"dealer_{ordinal.lower()}"
    return [
        BlockVariant(
            block_type=BlockType.DEALER_REASSIGNMENT,
            variant_id=f"{tag}_v1",
            title=f"{ordinal} REASSIGNMENT BY A LICENSED DEALER",
            title_style="banner",
            height_weight=4.0,
            rows=[
                RowDef([FieldDef(f"{tag}_preamble",
                        "The undersigned dealer hereby assigns and warrants title of this vehicle to:",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_buyer_name", "BUYER(S) NAME")]),
                RowDef([FieldDef(f"{tag}_buyer_address", "ADDRESS", height_lines=2)]),
                RowDef([
                    FieldDef(f"{tag}_new_lien", "LIENHOLDER (if none, state none)", col_span=0.6),
                    FieldDef(f"{tag}_new_lien_date", "DATE OF LIEN", col_span=0.4, field_type="date"),
                ]),
                RowDef([FieldDef(f"{tag}_new_lien_address", "LIENHOLDER ADDRESS")]),
                RowDef([FieldDef(f"{tag}_odom_label",
                        "ODOMETER DISCLOSURE STATEMENT",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odometer", "I state that the odometer now reads (NO TENTHS) miles:")]),
                RowDef([FieldDef(f"{tag}_odom_check1",
                        "[ ] Mileage is in excess of its mechanical limits.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odom_check2",
                        "[ ] Odometer reading is NOT the actual mileage. WARNING — ODOMETER DISCREPANCY.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odom_exempt",
                        "[ ] EXEMPT — Vehicle is 20 model years or older and not required to have odometer disclosure.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odom_cert",
                        "WE, THE BUYER AND SELLER, HEREBY CERTIFY THAT WE HAVE BOTH VIEWED THE ODOMETER.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_dealer_name", "NAME OF DEALERSHIP", col_span=0.6),
                    FieldDef(f"{tag}_dealer_license", "DEALER LICENSE NO.", col_span=0.4),
                ]),
                RowDef([FieldDef(f"{tag}_dealer_address", "DEALER ADDRESS")]),
                RowDef([
                    FieldDef(f"{tag}_dealer_city", "CITY", col_span=0.5),
                    FieldDef(f"{tag}_dealer_state", "STATE", col_span=0.2),
                    FieldDef(f"{tag}_date", "DATE", col_span=0.3, field_type="date"),
                ]),
                RowDef([
                    FieldDef(f"{tag}_agent_sig", "SIGNATURE OF AUTHORIZED AGENT", col_span=0.5, field_type="signature"),
                    FieldDef(f"{tag}_buyer_sig", "SIGNATURE OF BUYER(S)", col_span=0.5, field_type="signature"),
                ]),
                RowDef([
                    FieldDef(f"{tag}_agent_print", "PRINT NAME OF AUTHORIZED AGENT", col_span=0.5),
                    FieldDef(f"{tag}_buyer_print", "PRINT NAME OF BUYER(S)", col_span=0.5),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.DEALER_REASSIGNMENT,
            variant_id=f"{tag}_v2",
            title=f"{ordinal} DEALER REASSIGNMENT",
            title_style="left",
            height_weight=4.0,
            rows=[
                RowDef([FieldDef(f"{tag}_preamble",
                        "The undersigned licensed dealer assigns and warrants title to the purchaser(s) below.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_buyer_name", "BUYER NAME", col_span=0.6),
                    FieldDef(f"{tag}_date", "DATE OF SALE", col_span=0.4, field_type="date"),
                ]),
                RowDef([FieldDef(f"{tag}_buyer_address", "BUYER ADDRESS", height_lines=2)]),
                RowDef([
                    FieldDef(f"{tag}_new_lien", "NEW LIENHOLDER", col_span=0.5),
                    FieldDef(f"{tag}_new_lien_address", "LIENHOLDER ADDRESS", col_span=0.5),
                ]),
                RowDef([FieldDef(f"{tag}_new_lien_date", "DATE OF LIEN", field_type="date")]),
                RowDef([FieldDef(f"{tag}_odom_label",
                        "ODOMETER DISCLOSURE — The odometer now reads:",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odometer", "MILES (NO TENTHS)")]),
                RowDef([FieldDef(f"{tag}_odom_check1",
                        "[ ] EXCEEDS MECHANICAL LIMITS  [ ] ODOMETER DISCREPANCY  [ ] EXEMPT",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_odom_cert",
                        "BUYER AND SELLER CERTIFY THEY HAVE BOTH VIEWED THE ODOMETER.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_dealer_name", "DEALERSHIP", col_span=0.5),
                    FieldDef(f"{tag}_dealer_license", "LICENSE NO.", col_span=0.5),
                ]),
                RowDef([
                    FieldDef(f"{tag}_dealer_address", "ADDRESS", col_span=0.4),
                    FieldDef(f"{tag}_dealer_city", "CITY", col_span=0.3),
                    FieldDef(f"{tag}_dealer_state", "STATE", col_span=0.3),
                ]),
                RowDef([
                    FieldDef(f"{tag}_agent_sig", "AUTHORIZED AGENT SIGNATURE", col_span=0.5, field_type="signature"),
                    FieldDef(f"{tag}_buyer_sig", "BUYER SIGNATURE", col_span=0.5, field_type="signature"),
                ]),
                RowDef([
                    FieldDef(f"{tag}_agent_print", "AGENT PRINTED NAME", col_span=0.5),
                    FieldDef(f"{tag}_buyer_print", "BUYER PRINTED NAME", col_span=0.5),
                ]),
            ],
        ),
    ]


def _notary_variants(tag: str = "notary") -> list[BlockVariant]:
    """Notary acknowledgment block. Required in ~15+ states for title transfers."""
    return [
        BlockVariant(
            block_type=BlockType.NOTARY,
            variant_id=f"{tag}_v1",
            title="NOTARY ACKNOWLEDGMENT",
            title_style="left",
            height_weight=2.0,
            rows=[
                RowDef([FieldDef(f"{tag}_preamble",
                        "STATE OF __________ COUNTY OF __________",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef(f"{tag}_body",
                        "On this date, before me, the undersigned notary public, personally appeared the above-named "
                        "person(s), known to me (or proved on the basis of satisfactory evidence) to be the person(s) "
                        "whose name(s) is/are subscribed to the within instrument.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_sig", "NOTARY SIGNATURE", col_span=0.5, field_type="signature"),
                    FieldDef(f"{tag}_date", "DATE", col_span=0.5, field_type="date"),
                ]),
                RowDef([
                    FieldDef(f"{tag}_name", "NOTARY PRINTED NAME", col_span=0.5),
                    FieldDef(f"{tag}_commission_exp", "COMMISSION EXPIRES", col_span=0.5, field_type="date"),
                ]),
                RowDef([FieldDef(f"{tag}_seal_area",
                        "[NOTARY SEAL / STAMP]",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_witness1_sig", "WITNESS 1 SIGNATURE", col_span=0.5, field_type="signature"),
                    FieldDef(f"{tag}_witness1_print", "WITNESS 1 PRINTED NAME", col_span=0.5),
                ]),
                RowDef([
                    FieldDef(f"{tag}_witness2_sig", "WITNESS 2 SIGNATURE", col_span=0.5, field_type="signature"),
                    FieldDef(f"{tag}_witness2_print", "WITNESS 2 PRINTED NAME", col_span=0.5),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.NOTARY,
            variant_id=f"{tag}_v2",
            title="NOTARIZATION",
            title_style="banner",
            height_weight=1.8,
            rows=[
                RowDef([FieldDef(f"{tag}_body",
                        "Subscribed and sworn to (or affirmed) before me on this date by the person(s) named above.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef(f"{tag}_sig", "SIGNATURE OF NOTARY PUBLIC", col_span=0.6, field_type="signature"),
                    FieldDef(f"{tag}_date", "DATE", col_span=0.4, field_type="date"),
                ]),
                RowDef([
                    FieldDef(f"{tag}_name", "PRINTED NAME", col_span=0.4),
                    FieldDef(f"{tag}_commission_no", "COMMISSION NO.", col_span=0.3),
                    FieldDef(f"{tag}_commission_exp", "EXPIRES", col_span=0.3, field_type="date"),
                ]),
            ],
        ),
    ]


def _damage_disclosure_variants() -> list[BlockVariant]:
    """Damage disclosure statement. Required in ~6+ states (NY, NC, ND, IA, MN)."""
    return [
        BlockVariant(
            block_type=BlockType.DAMAGE_DISCLOSURE,
            variant_id="damage_disclosure_v1",
            title="DAMAGE DISCLOSURE STATEMENT",
            title_style="left",
            height_weight=1.5,
            rows=[
                RowDef([FieldDef("damage_preamble",
                        "Has the vehicle sustained damage in excess of the threshold amount or been declared "
                        "a total loss by an insurance company?",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef("damage_check",
                        "[ ] YES — Vehicle has sustained damage  [ ] NO — Vehicle has NOT sustained damage",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef("damage_seller_sig", "SELLER SIGNATURE", col_span=0.5, field_type="signature"),
                    FieldDef("damage_date", "DATE", col_span=0.5, field_type="date"),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.DAMAGE_DISCLOSURE,
            variant_id="damage_disclosure_v2",
            title="DISCLOSURE OF DAMAGE",
            title_style="banner",
            height_weight=1.8,
            rows=[
                RowDef([FieldDef("damage_preamble",
                        "SELLER MUST DISCLOSE: Has this vehicle been damaged by flood, fire, collision, or other "
                        "event resulting in damage exceeding 25% of the vehicle's fair market value?",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef("damage_check",
                        "[ ] YES  [ ] NO  [ ] UNKNOWN",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef("damage_description", "IF YES, DESCRIBE DAMAGE")]),
                RowDef([
                    FieldDef("damage_seller_sig", "SELLER SIGNATURE", col_span=0.5, field_type="signature"),
                    FieldDef("damage_buyer_sig", "BUYER SIGNATURE", col_span=0.5, field_type="signature"),
                ]),
            ],
        ),
    ]


def _vin_verification_variants() -> list[BlockVariant]:
    """VIN verification / inspection block. Required in FL, CA, CO, NH."""
    return [
        BlockVariant(
            block_type=BlockType.VIN_VERIFICATION,
            variant_id="vin_verify_v1",
            title="VIN VERIFICATION",
            title_style="banner",
            height_weight=2.0,
            rows=[
                RowDef([FieldDef("vin_verify_label",
                        "THE VEHICLE IDENTIFICATION NUMBER (VIN) HAS BEEN PHYSICALLY INSPECTED AND VERIFIED.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef("vin_verify_vin", "VIN AS INSPECTED")]),
                RowDef([
                    FieldDef("vin_verify_location", "LOCATION OF VIN ON VEHICLE", col_span=0.5),
                    FieldDef("vin_verify_date", "DATE OF INSPECTION", col_span=0.5, field_type="date"),
                ]),
                RowDef([
                    FieldDef("vin_verify_inspector_sig", "INSPECTOR SIGNATURE", col_span=0.5, field_type="signature"),
                    FieldDef("vin_verify_badge", "BADGE / ID NUMBER", col_span=0.5),
                ]),
                RowDef([
                    FieldDef("vin_verify_inspector_name", "INSPECTOR PRINTED NAME", col_span=0.5),
                    FieldDef("vin_verify_agency", "AGENCY / ORGANIZATION", col_span=0.5),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.VIN_VERIFICATION,
            variant_id="vin_verify_v2",
            title="VEHICLE IDENTIFICATION NUMBER INSPECTION",
            title_style="left",
            height_weight=1.8,
            rows=[
                RowDef([FieldDef("vin_verify_label",
                        "I certify that I have physically examined the vehicle described herein and the VIN "
                        "shown is the VIN assigned to the vehicle.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef("vin_verify_vin", "VEHICLE IDENTIFICATION NUMBER", col_span=0.6),
                    FieldDef("vin_verify_date", "DATE", col_span=0.4, field_type="date"),
                ]),
                RowDef([
                    FieldDef("vin_verify_inspector_sig", "AUTHORIZED AGENT SIGNATURE", col_span=0.6, field_type="signature"),
                    FieldDef("vin_verify_badge", "BADGE / CERT. NO.", col_span=0.4),
                ]),
                RowDef([FieldDef("vin_verify_agency", "AGENCY NAME AND ADDRESS")]),
            ],
        ),
    ]


def _power_of_attorney_variants() -> list[BlockVariant]:
    """Power of attorney section. Used in TX, NC, CA, OR for title transfers."""
    return [
        BlockVariant(
            block_type=BlockType.POWER_OF_ATTORNEY,
            variant_id="poa_v1",
            title="POWER OF ATTORNEY",
            title_style="banner",
            height_weight=2.2,
            rows=[
                RowDef([FieldDef("poa_preamble",
                        "I/We hereby appoint the following individual as my/our attorney-in-fact to execute "
                        "and deliver all documents necessary to transfer title to the vehicle described herein.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef("poa_attorney_name", "NAME OF ATTORNEY-IN-FACT")]),
                RowDef([FieldDef("poa_attorney_address", "ADDRESS OF ATTORNEY-IN-FACT")]),
                RowDef([
                    FieldDef("poa_grantor_sig", "SIGNATURE OF VEHICLE OWNER", col_span=0.5, field_type="signature"),
                    FieldDef("poa_date", "DATE", col_span=0.5, field_type="date"),
                ]),
                RowDef([
                    FieldDef("poa_grantor_print", "PRINTED NAME OF OWNER", col_span=0.5),
                    FieldDef("poa_grantor_dl", "OWNER DL / ID NO.", col_span=0.5),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.POWER_OF_ATTORNEY,
            variant_id="poa_v2",
            title="SECURE POWER OF ATTORNEY",
            title_style="left",
            height_weight=2.5,
            rows=[
                RowDef([FieldDef("poa_preamble",
                        "I/We authorize the person named below to act on my/our behalf to sign all forms "
                        "necessary to transfer ownership of the motor vehicle described on the face of this title.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([FieldDef("poa_vin_label",
                        "THIS POWER OF ATTORNEY IS ONLY VALID FOR THE VIN LISTED ON THIS TITLE.",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef("poa_attorney_name", "ATTORNEY-IN-FACT NAME", col_span=0.6),
                    FieldDef("poa_attorney_dl", "ATTORNEY DL / ID NO.", col_span=0.4),
                ]),
                RowDef([FieldDef("poa_attorney_address", "ATTORNEY ADDRESS")]),
                RowDef([
                    FieldDef("poa_grantor_sig", "OWNER SIGNATURE", col_span=0.5, field_type="signature"),
                    FieldDef("poa_co_grantor_sig", "CO-OWNER SIGNATURE", col_span=0.5, field_type="signature"),
                ]),
                RowDef([
                    FieldDef("poa_grantor_print", "OWNER PRINTED NAME", col_span=0.5),
                    FieldDef("poa_co_grantor_print", "CO-OWNER PRINTED NAME", col_span=0.5),
                ]),
                RowDef([FieldDef("poa_date", "DATE SIGNED", field_type="date")]),
            ],
        ),
    ]


def _tax_fee_variants() -> list[BlockVariant]:
    """Tax / fee section. Used in PA, CT, IN and other states."""
    return [
        BlockVariant(
            block_type=BlockType.TAX_FEE,
            variant_id="tax_fee_v1",
            title="TAX AND FEE INFORMATION",
            title_style="left",
            height_weight=1.5,
            rows=[
                RowDef([
                    FieldDef("tax_purchase_price", "PURCHASE PRICE $", col_span=0.5),
                    FieldDef("tax_trade_in", "TRADE-IN ALLOWANCE $", col_span=0.5),
                ]),
                RowDef([
                    FieldDef("tax_net_price", "NET PURCHASE PRICE $", col_span=0.5),
                    FieldDef("tax_rate", "TAX RATE %", col_span=0.5),
                ]),
                RowDef([
                    FieldDef("tax_sales_tax", "SALES / USE TAX $", col_span=0.5),
                    FieldDef("tax_title_fee", "TITLE FEE $", col_span=0.5),
                ]),
                RowDef([
                    FieldDef("tax_registration_fee", "REGISTRATION FEE $", col_span=0.5),
                    FieldDef("tax_total", "TOTAL FEES $", col_span=0.5),
                ]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.TAX_FEE,
            variant_id="tax_fee_v2",
            title="FEES AND TAXES",
            title_style="banner",
            height_weight=1.8,
            rows=[
                RowDef([FieldDef("tax_label",
                        "FOR OFFICIAL USE ONLY — TO BE COMPLETED BY THE ISSUING AUTHORITY",
                        style=FieldStyle.LABEL_ONLY)]),
                RowDef([
                    FieldDef("tax_purchase_price", "SALE PRICE $", col_span=0.33),
                    FieldDef("tax_trade_in", "TRADE-IN $", col_span=0.33),
                    FieldDef("tax_net_price", "TAXABLE AMOUNT $", col_span=0.34),
                ]),
                RowDef([
                    FieldDef("tax_sales_tax", "STATE TAX $", col_span=0.33),
                    FieldDef("tax_local_tax", "LOCAL TAX $", col_span=0.33),
                    FieldDef("tax_total_tax", "TOTAL TAX $", col_span=0.34),
                ]),
                RowDef([
                    FieldDef("tax_title_fee", "TITLE FEE $", col_span=0.33),
                    FieldDef("tax_registration_fee", "REG. FEE $", col_span=0.33),
                    FieldDef("tax_total", "TOTAL DUE $", col_span=0.34),
                ]),
                RowDef([
                    FieldDef("tax_receipt_no", "RECEIPT NUMBER", col_span=0.5),
                    FieldDef("tax_date_paid", "DATE PAID", col_span=0.5, field_type="date"),
                ]),
            ],
        ),
    ]


def _back_legal_variants() -> list[BlockVariant]:
    return [
        BlockVariant(
            block_type=BlockType.BACK_LEGAL,
            variant_id="back_legal_v1",
            title=None,
            title_style="none",
            height_weight=0.4,
            rows=[
                RowDef([FieldDef("back_legal_text",
                        "ANY FALSE STATEMENT MAY BE PUNISHABLE AS A MISDEMEANOR OR FELONY. "
                        "ANY CHANGE OR ERASURE WILL VOID THIS TITLE.",
                        style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.BACK_LEGAL,
            variant_id="back_legal_v2",
            title=None,
            title_style="none",
            height_weight=0.4,
            rows=[
                RowDef([FieldDef("back_legal_text",
                        "WARNING: ANY ALTERATION, FORGERY, OR FALSE STATEMENT ON THIS DOCUMENT "
                        "IS A VIOLATION OF LAW AND MAY BE SUBJECT TO CRIMINAL PROSECUTION.",
                        style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
        BlockVariant(
            block_type=BlockType.BACK_LEGAL,
            variant_id="back_legal_v3",
            title=None,
            title_style="none",
            height_weight=0.3,
            rows=[
                RowDef([FieldDef("back_legal_text",
                        "FALSE STATEMENTS ARE PUNISHABLE BY LAW. THIS TITLE IS VOID IF ALTERED OR ERASED.",
                        style=FieldStyle.LABEL_ONLY)]),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Complete variant pool
# ---------------------------------------------------------------------------

VARIANT_POOL: dict[BlockType, list[BlockVariant]] = {
    # Front
    BlockType.HEADER: _header_variants(),
    BlockType.VEHICLE_INFO: _vehicle_info_variants(),
    BlockType.TITLE_META: _title_meta_variants(),
    BlockType.OWNER: _owner_variants(),
    BlockType.LIEN: [],  # built dynamically with ordinal
    BlockType.LEGAL: _legal_variants(),
    # Back
    BlockType.BACK_WARNING: _back_warning_variants(),
    BlockType.TRANSFER: [],  # built dynamically with tag
    BlockType.DEALER_REASSIGNMENT: [],  # built dynamically with ordinal
    BlockType.NOTARY: [],  # built dynamically with tag
    BlockType.DAMAGE_DISCLOSURE: _damage_disclosure_variants(),
    BlockType.VIN_VERIFICATION: _vin_verification_variants(),
    BlockType.POWER_OF_ATTORNEY: _power_of_attorney_variants(),
    BlockType.TAX_FEE: _tax_fee_variants(),
    BlockType.BACK_LEGAL: _back_legal_variants(),
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

# Back side block order
BACK_BLOCK_ORDER: list[BlockType] = [
    BlockType.BACK_WARNING,
    BlockType.TRANSFER,
    BlockType.DEALER_REASSIGNMENT,   # first dealer reassignment
    BlockType.DEALER_REASSIGNMENT,   # second dealer reassignment
    BlockType.BACK_LEGAL,
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

    # Pick side and bottom border text (void/fraud warnings)
    from src.data.static import SIDE_TEXT, BOTTOM_TEXT
    side_border_str = rng.choice(SIDE_TEXT)
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
        side_border_text=side_border_str,
        bottom_border_text=bottom_border_str,
    )


def build_random_back_layout(
    state_name: str = "SAMPLE STATE",
    rng: random.Random | None = None,
) -> DocumentLayout:
    """Pick one variant per back-side block type and assemble a layout.

    The back side has NO border — just a light background pattern.
    Randomly includes optional sections (notary, damage disclosure)
    to simulate variation across states.
    """
    if rng is None:
        rng = random.Random()

    font_family = rng.choice(FONT_FAMILIES)

    # Decide which optional sections to include
    include_notary = rng.random() < 0.4        # ~40% of states require notary
    include_damage = rng.random() < 0.3        # ~30% of states have damage disclosure
    include_vin_verify = rng.random() < 0.25   # ~25% of states (FL, CA, CO, NH)
    include_poa = rng.random() < 0.20          # ~20% of states (TX, NC, CA, OR)
    include_tax_fee = rng.random() < 0.25      # ~25% of states (PA, CT, IN)

    # Build the block order dynamically
    block_order: list[BlockType] = [BlockType.BACK_WARNING, BlockType.TRANSFER]
    if include_notary:
        block_order.append(BlockType.NOTARY)
    if include_damage:
        block_order.append(BlockType.DAMAGE_DISCLOSURE)
    if include_poa:
        block_order.append(BlockType.POWER_OF_ATTORNEY)
    block_order.append(BlockType.DEALER_REASSIGNMENT)  # first
    block_order.append(BlockType.DEALER_REASSIGNMENT)  # second
    if include_vin_verify:
        block_order.append(BlockType.VIN_VERIFICATION)
    if include_tax_fee:
        block_order.append(BlockType.TAX_FEE)
    block_order.append(BlockType.BACK_LEGAL)

    blocks: list[BlockVariant] = []

    # Dealer reassignment ordinals
    dealer_ordinals = ["FIRST", "SECOND"]
    dealer_style_idx = rng.randint(0, 1)

    dealer_variants_by_ordinal: dict[str, BlockVariant] = {}
    for ordinal in dealer_ordinals:
        variants = _dealer_reassignment_variants(ordinal)
        idx = min(dealer_style_idx, len(variants) - 1)
        dealer_variants_by_ordinal[ordinal] = variants[idx]

    dealer_counter = 0
    for block_type in block_order:
        if block_type == BlockType.DEALER_REASSIGNMENT:
            ordinal = dealer_ordinals[dealer_counter]
            variant = dealer_variants_by_ordinal[ordinal]
            dealer_counter += 1
        elif block_type == BlockType.TRANSFER:
            variants = _transfer_variants("transfer")
            variant = rng.choice(variants)
        elif block_type == BlockType.NOTARY:
            variants = _notary_variants("notary")
            variant = rng.choice(variants)
        elif block_type in (BlockType.VIN_VERIFICATION, BlockType.POWER_OF_ATTORNEY, BlockType.TAX_FEE):
            pool = VARIANT_POOL[block_type]
            variant = rng.choice(pool)
        else:
            pool = VARIANT_POOL[block_type]
            variant = rng.choice(pool)

        variant = _copy_variant(variant, state_name)
        blocks.append(variant)

    return DocumentLayout(
        blocks=blocks,
        font_family=font_family,
        border_text="",
        bottom_border_text="",
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
