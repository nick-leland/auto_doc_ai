"""Stress test: generate documents with min → max optional sections.

Forces every combination of optional back-side sections to ensure nothing
breaks at any field count. Generates both small (800x1040) and large
(2250x3000) documents for each configuration.
"""

import json
import random
import itertools
from pathlib import Path

import svgwrite

from src.document_layout import (
    build_random_layout,
    solve_layout,
    render_layout,
    fill_values,
)
from src.document_layout.cells import (
    BlockType,
    BlockVariant,
    DocumentLayout,
    VARIANT_POOL,
    FONT_FAMILIES,
    BORDER_TEXT_TEMPLATES,
    DOCUMENT_TITLES,
    _transfer_variants,
    _dealer_reassignment_variants,
    _notary_variants,
    _back_warning_variants,
    _damage_disclosure_variants,
    _vin_verification_variants,
    _power_of_attorney_variants,
    _tax_fee_variants,
    _back_legal_variants,
    _copy_variant,
)
from src.utils.background_generation import (
    BackgroundParams,
    add_background_to_drawing,
    add_background_no_border,
)
from src.utils.border_text import render_border_text
from src.utils.state_insignia import add_state_insignia

# Load all values
FIXTURE_PATH = Path(__file__).resolve().parent / "examples" / "fixtures" / "test_title.json"
with open(FIXTURE_PATH) as f:
    all_values = json.load(f)
all_values = {k: v for k, v in all_values.items() if not k.startswith("_comment")}

# Optional section flags
OPTIONAL_SECTIONS = ["notary", "damage", "vin_verify", "poa", "tax_fee"]

out_dir = Path("stress_test_output")
out_dir.mkdir(exist_ok=True)

SIZES = {
    "small": (800, 1040),
    "large": (2250, 3000),
}

STATE = "RHODE ISLAND"
BG_COL = "#E0E8F0"
BORDER_COL = "#2C5C9A"


def build_forced_back_layout(
    state_name: str,
    include_notary: bool,
    include_damage: bool,
    include_vin_verify: bool,
    include_poa: bool,
    include_tax_fee: bool,
    rng: random.Random,
) -> DocumentLayout:
    """Build a back layout with forced inclusion/exclusion of optional sections."""
    font_family = rng.choice(FONT_FAMILIES)

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

    dealer_ordinals = ["FIRST", "SECOND"]
    dealer_style_idx = rng.randint(0, 1)
    dealer_variants_by_ordinal = {}
    for ordinal in dealer_ordinals:
        variants = _dealer_reassignment_variants(ordinal)
        idx = min(dealer_style_idx, len(variants) - 1)
        dealer_variants_by_ordinal[ordinal] = variants[idx]

    dealer_counter = 0
    for block_type in block_order:
        if block_type == BlockType.DEALER_REASSIGNMENT:
            variant = dealer_variants_by_ordinal[dealer_ordinals[dealer_counter]]
            dealer_counter += 1
        elif block_type == BlockType.TRANSFER:
            variant = rng.choice(_transfer_variants("transfer"))
        elif block_type == BlockType.NOTARY:
            variant = rng.choice(_notary_variants("notary"))
        elif block_type in (BlockType.VIN_VERIFICATION, BlockType.POWER_OF_ATTORNEY, BlockType.TAX_FEE):
            variant = rng.choice(VARIANT_POOL[block_type])
        else:
            variant = rng.choice(VARIANT_POOL[block_type])
        variant = _copy_variant(variant, state_name)
        blocks.append(variant)

    return DocumentLayout(
        blocks=blocks,
        font_family=font_family,
        border_text="",
        bottom_border_text="",
    )


def generate_one(name: str, size: tuple[int, int], seed: int,
                 front_layout, back_layout, values: dict) -> None:
    """Generate front + back SVGs for a single configuration."""
    w, h = size
    rng = random.Random(seed)
    border_size = 0.06 * w

    # --- FRONT ---
    drawing = svgwrite.Drawing(
        filename=str(out_dir / f"{name}_front.svg"),
        size=(w, h),
    )
    bg_params = BackgroundParams(
        width=w, height=h, border_size=border_size,
        bg_color=BG_COL, border_color=BORDER_COL, seed=seed,
    )
    add_background_to_drawing(drawing, bg_params)

    inner_rect = (border_size, border_size, w - 2 * border_size, h - 2 * border_size)
    add_state_insignia(
        drawing, STATE, inner_rect,
        color=BORDER_COL, bg_color=BG_COL,
        opacity=0.07, scale_fraction=0.45, rng=random.Random(seed),
    )

    border_rng = random.Random(seed)
    render_border_text(
        drawing, front_layout.border_text, w, h, border_size,
        orientation="Top", fg_color=BG_COL, bg_color=BORDER_COL, rng=border_rng,
    )
    render_border_text(
        drawing, front_layout.side_border_text, w, h, border_size,
        orientation="Sides", fg_color=BG_COL, bg_color=BORDER_COL, rng=border_rng,
    )
    render_border_text(
        drawing, front_layout.bottom_border_text, w, h, border_size,
        orientation="Bottom", fg_color=BG_COL, bg_color=BORDER_COL, rng=border_rng,
    )

    content_rect = (
        border_size + 10, border_size + 10,
        w - 2 * (border_size + 10), h - 2 * (border_size + 10),
    )
    result = solve_layout(front_layout, content_rect)
    metadata = render_layout(drawing, result, font_family=front_layout.font_family)
    fill_values(drawing, metadata, values, rng=random.Random(seed))
    drawing.save()

    # --- BACK ---
    drawing_back = svgwrite.Drawing(
        filename=str(out_dir / f"{name}_back.svg"),
        size=(w, h),
    )
    bg_params_back = BackgroundParams(
        width=w, height=h, border_size=0,
        bg_color=BG_COL, border_color=BORDER_COL, seed=seed + 1,
    )
    add_background_no_border(drawing_back, bg_params_back)

    back_content_rect = (
        border_size + 10, border_size + 10,
        w - 2 * (border_size + 10), h - 2 * (border_size + 10),
    )
    back_result = solve_layout(back_layout, back_content_rect, compact=True)
    back_metadata = render_layout(drawing_back, back_result, font_family=back_layout.font_family)
    fill_values(drawing_back, back_metadata, values, rng=random.Random(seed + 1))
    drawing_back.save()


def count_fillable_fields(layout) -> int:
    """Count the number of fillable (non-label-only) fields in a layout."""
    count = 0
    for block in layout.blocks:
        for row in block.rows:
            for field in row.fields:
                if field.style.value != "label_only":
                    count += 1
    return count


# Generate all 32 combinations of optional sections (2^5)
combos = list(itertools.product([False, True], repeat=5))

print(f"Generating {len(combos)} configurations × {len(SIZES)} sizes = {len(combos) * len(SIZES)} document pairs...")
print(f"{'Config':<8} {'Sections':<40} {'Size':<6} {'Front#':<8} {'Back#':<8} {'Status'}")
print("-" * 110)

errors = []
for combo_idx, combo in enumerate(combos):
    flags = dict(zip(OPTIONAL_SECTIONS, combo))
    active = [k for k, v in flags.items() if v]
    label = "+".join(active) if active else "minimal"

    seed = 42 + combo_idx

    # Build front layout (same for all combos within a config)
    rng_front = random.Random(seed)
    front_layout = build_random_layout(state_name=STATE, rng=rng_front)

    # Build back layout with forced flags
    rng_back = random.Random(seed + 1)
    back_layout = build_forced_back_layout(
        STATE,
        include_notary=flags["notary"],
        include_damage=flags["damage"],
        include_vin_verify=flags["vin_verify"],
        include_poa=flags["poa"],
        include_tax_fee=flags["tax_fee"],
        rng=rng_back,
    )

    front_fields = count_fillable_fields(front_layout)
    back_fields = count_fillable_fields(back_layout)

    for size_name, size in SIZES.items():
        name = f"stress_{combo_idx:02d}_{size_name}"
        try:
            generate_one(name, size, seed, front_layout, back_layout, all_values)
            status = "OK"
        except Exception as e:
            status = f"FAIL: {e}"
            errors.append((name, label, str(e)))

        print(f"{combo_idx:<8} {label:<40} {size_name:<6} {front_fields:<8} {back_fields:<8} {status}")

print(f"\n{'='*110}")
if errors:
    print(f"\nFAILED: {len(errors)} documents")
    for name, label, err in errors:
        print(f"  {name} ({label}): {err}")
else:
    print(f"\nAll {len(combos) * len(SIZES)} documents generated successfully!")

# Summary stats
print(f"\nField count range across all configurations:")
all_back_counts = []
for combo in combos:
    flags = dict(zip(OPTIONAL_SECTIONS, combo))
    rng = random.Random(99)
    bl = build_forced_back_layout(STATE, **{f"include_{k}": v for k, v in flags.items()}, rng=rng)
    all_back_counts.append(count_fillable_fields(bl))

print(f"  Back side: {min(all_back_counts)} (minimal) → {max(all_back_counts)} (all sections)")
print(f"\nOutput in: {out_dir}/")
