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

# --- Test data (front — works for any state, field names are generic) ---
with open("test_title.json") as f:
    front_values = json.load(f)

# Texas-specific overrides for the small doc
texas_front_values = dict(front_values)
texas_front_values.update({
    "title_no": "TX-2024-1193847",
    "owner_address": "4210 BLUEBONNET LN, AUSTIN TX 78704",
    "owner_street": "4210 BLUEBONNET LN",
    "owner_city": "AUSTIN",
    "owner_state": "TX",
    "owner_zip": "78704",
    "first_lien_address": "PO BOX 650000, DALLAS TX 75265",
})

# --- Test data (back) ---
back_values = {
    "transfer_buyer_name": "DAVID A MARTINEZ",
    "transfer_buyer_address": "88 OAK AVENUE, CRANSTON RI 02920",
    "transfer_new_lien": "NONE",
    "transfer_new_lien_date": "",
    "transfer_new_lien_address": "",
    "transfer_odometer": "52140",
    "transfer_seller_sig": "Michael R. Johnson",
    "transfer_buyer_sig": "David A. Martinez",
    "transfer_seller_print": "MICHAEL R JOHNSON",
    "transfer_buyer_print": "DAVID A MARTINEZ",
    "transfer_date": "03/01/2025",

    "dealer_first_buyer_name": "JAMES T WILSON",
    "dealer_first_buyer_address": "204 PINE ST, WARWICK RI 02886",
    "dealer_first_new_lien": "ALLY FINANCIAL",
    "dealer_first_new_lien_date": "03/10/2025",
    "dealer_first_new_lien_address": "PO BOX 951, HORSHAM PA 19044",
    "dealer_first_odometer": "52305",
    "dealer_first_dealer_name": "RHODE ISLAND AUTO GROUP",
    "dealer_first_dealer_license": "DLR-4821",
    "dealer_first_dealer_address": "500 POST RD",
    "dealer_first_dealer_city": "WARWICK",
    "dealer_first_dealer_state": "RI",
    "dealer_first_date": "03/10/2025",
    "dealer_first_agent_sig": "Frank Pellegrino",
    "dealer_first_buyer_sig": "James T. Wilson",
    "dealer_first_agent_print": "FRANK PELLEGRINO",
    "dealer_first_buyer_print": "JAMES T WILSON",

    "dealer_second_buyer_name": "LINDA K CHEN",
    "dealer_second_buyer_address": "77 ELM STREET, EAST PROVIDENCE RI 02914",
    "dealer_second_new_lien": "NONE",
    "dealer_second_new_lien_date": "",
    "dealer_second_new_lien_address": "",
    "dealer_second_odometer": "53891",
    "dealer_second_dealer_name": "EAST BAY MOTORS LLC",
    "dealer_second_dealer_license": "DLR-7103",
    "dealer_second_dealer_address": "1200 WARREN AVE",
    "dealer_second_dealer_city": "EAST PROVIDENCE",
    "dealer_second_dealer_state": "RI",
    "dealer_second_date": "04/15/2025",
    "dealer_second_agent_sig": "Nancy Oliveira",
    "dealer_second_buyer_sig": "Linda K. Chen",
    "dealer_second_agent_print": "NANCY OLIVEIRA",
    "dealer_second_buyer_print": "LINDA K CHEN",
}

texas_back_values = dict(back_values)
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
    render_border_text(
        drawing, front_layout.side_border_text, w, h, border_size,
        orientation="Sides", fg_color=bg_col, bg_color=border_col, rng=border_rng,
    )
    render_border_text(
        drawing, front_layout.bottom_border_text, w, h, border_size,
        orientation="Bottom", fg_color=bg_col, bg_color=border_col, rng=border_rng,
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

    margin = 30 if name == "large" else 12
    back_content_rect = (margin, margin, w - 2 * margin, h - 2 * margin)
    back_result = solve_layout(back_layout, back_content_rect)
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
