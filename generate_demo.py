"""Generate demo SVGs: small (Texas/green) + large (Rhode Island/blue), front + back."""

import json
import random
from pathlib import Path

import svgwrite

from src.document_layout import (
    build_random_layout,
    build_random_back_layout,
    solve_layout,
    render_layout,
    save_metadata,
    fill_values,
)
from src.utils.background_generation import (
    BackgroundParams,
    add_background_to_drawing,
    add_background_no_border,
)
from src.utils.border_text import render_border_text
from src.utils.state_insignia import add_state_insignia

# --- Load all field values (front + back are in the same file now) ---
FIXTURE_PATH = Path(__file__).resolve().parent / "examples" / "fixtures" / "test_title.json"
with open(FIXTURE_PATH) as f:
    all_values = json.load(f)

# Strip _comment keys used for documentation in the JSON
all_values = {k: v for k, v in all_values.items() if not k.startswith("_comment")}

# Split into front/back for the large (Rhode Island) doc
front_values = all_values
back_values = all_values  # fill_values only uses fields that exist in the layout

# Texas-specific overrides for the small doc
texas_front_values = dict(all_values)
texas_front_values.update({
    "title_no": "TX-2024-1193847",
    "owner_address": "4210 BLUEBONNET LN, AUSTIN TX 78704",
    "owner_street": "4210 BLUEBONNET LN",
    "owner_city": "AUSTIN",
    "owner_state": "TX",
    "owner_zip": "78704",
    "county": "TRAVIS",
    "plate_no": "TX-LBJ42",
    "first_lien_address": "PO BOX 650000, DALLAS TX 75265",
    "vin_verify_agency": "TRAVIS COUNTY SHERIFF DEPT",
    "poa_attorney_address": "100 CONGRESS AVE STE 200, AUSTIN TX 78701",
})

texas_back_values = dict(all_values)
texas_back_values.update({
    "transfer_buyer_address": "1502 CONGRESS AVE, AUSTIN TX 78701",
    "dealer_first_buyer_address": "910 LAMAR BLVD, AUSTIN TX 78703",
    "dealer_first_dealer_name": "LONE STAR AUTO GROUP",
    "dealer_first_dealer_address": "7800 N IH-35",
    "dealer_first_dealer_city": "AUSTIN",
    "dealer_first_dealer_state": "TX",
    "dealer_second_buyer_address": "205 E 6TH ST, SAN ANTONIO TX 78205",
    "dealer_second_dealer_name": "ALAMO CITY MOTORS LLC",
    "dealer_second_dealer_address": "3400 SW MILITARY DR",
    "dealer_second_dealer_city": "SAN ANTONIO",
    "dealer_second_dealer_state": "TX",
})

# --- Document configs: each size gets its own state + color scheme ---
docs = [
    {
        "name": "small",
        "size": (800, 1040),
        "state": "TEXAS",
        "seed": 99,
        "bg_color": "#E4F0E0",
        "border_color": "#2F6F3E",
        "front_values": texas_front_values,
        "back_values": texas_back_values,
    },
    {
        "name": "large",
        "size": (2250, 3000),
        "state": "RHODE ISLAND",
        "seed": 42,
        "bg_color": "#E0E8F0",
        "border_color": "#2C5C9A",
        "front_values": front_values,
        "back_values": back_values,
    },
]

out_dir = Path("demo_output")
out_dir.mkdir(exist_ok=True)

for doc in docs:
    name = doc["name"]
    w, h = doc["size"]
    state = doc["state"]
    seed = doc["seed"]
    bg_col = doc["bg_color"]
    border_col = doc["border_color"]

    rng = random.Random(seed)
    border_size = 0.06 * w

    # ===================== FRONT =====================
    front_layout = build_random_layout(state_name=state, rng=rng)

    drawing = svgwrite.Drawing(
        filename=str(out_dir / f"demo_{name}_front.svg"),
        size=(w, h),
    )

    bg_params = BackgroundParams(
        width=w, height=h,
        border_size=border_size,
        bg_color=bg_col,
        border_color=border_col,
        seed=seed,
    )
    add_background_to_drawing(drawing, bg_params)

    # State seal watermark
    inner_rect = (
        border_size, border_size,
        w - 2 * border_size, h - 2 * border_size,
    )
    add_state_insignia(
        drawing, state, inner_rect,
        color=border_col, bg_color=bg_col,
        opacity=0.07, scale_fraction=0.45,
        rng=random.Random(seed),
    )

    # Border text
    border_rng = random.Random(seed)
    render_border_text(
        drawing, front_layout.border_text, w, h, border_size,
        orientation="Top", fg_color=bg_col, bg_color=border_col, rng=border_rng,
    )
    bottom_banner_height = render_border_text(
        drawing, front_layout.bottom_border_text, w, h, border_size,
        orientation="Bottom", fg_color=bg_col, bg_color=border_col, rng=border_rng,
    )
    if front_layout.side_border_text and border_rng.random() < 0.3:
        render_border_text(
            drawing, front_layout.side_border_text, w, h, border_size,
            orientation="Sides",
            fg_color=bg_col,
            bg_color=border_col,
            target_display_height=bottom_banner_height,
            rng=border_rng,
        )

    content_rect = (
        border_size + 10,
        border_size + 10,
        w - 2 * (border_size + 10),
        h - 2 * (border_size + 10),
    )
    result = solve_layout(front_layout, content_rect)
    metadata = render_layout(drawing, result, font_family=front_layout.font_family)
    fill_values(drawing, metadata, doc["front_values"], rng=random.Random(seed))

    drawing.save()
    save_metadata(metadata, str(out_dir / f"demo_{name}_front_meta.json"))
    print(f"{name} front ({state}): {w}x{h}, font={result.font_size:.1f}")

    # ===================== BACK =====================
    rng2 = random.Random(seed + 1)
    back_layout = build_random_back_layout(state_name=state, rng=rng2)

    drawing_back = svgwrite.Drawing(
        filename=str(out_dir / f"demo_{name}_back.svg"),
        size=(w, h),
    )

    bg_params_back = BackgroundParams(
        width=w, height=h,
        border_size=0,
        bg_color=bg_col,
        border_color=border_col,
        seed=seed + 1,
    )
    add_background_no_border(drawing_back, bg_params_back)

    back_content_rect = (
        border_size + 10, border_size + 10,
        w - 2 * (border_size + 10), h - 2 * (border_size + 10),
    )
    back_result = solve_layout(back_layout, back_content_rect, compact=True)
    back_metadata = render_layout(drawing_back, back_result, font_family=back_layout.font_family)
    fill_values(drawing_back, back_metadata, doc["back_values"], rng=random.Random(seed + 1))

    drawing_back.save()
    save_metadata(back_metadata, str(out_dir / f"demo_{name}_back_meta.json"))
    print(f"{name} back  ({state}): {w}x{h}, font={back_result.font_size:.1f}")

# --- Convert to PNG ---
print("\nConverting to PNG...")
import subprocess
png_dir = out_dir / "png"
png_dir.mkdir(exist_ok=True)
for svg_file in sorted(out_dir.glob("demo_*.svg")):
    png_file = png_dir / (svg_file.stem + ".png")
    subprocess.run(["rsvg-convert", str(svg_file), "-o", str(png_file)], check=True)
    print(f"  {png_file.name}")

print("\nDone! SVGs in demo_output/, PNGs in demo_output/png/")
