"""
Generate SVG outlines of each US state for use as document watermarks.
Downloads GeoJSON boundary data and converts to clean, static-sized SVGs.
"""

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen, Request

# Static SVG canvas size
SVG_WIDTH = 800
SVG_HEIGHT = 800
PADDING = 40

# Simplified US state boundaries GeoJSON (Census Bureau via public CDN)
GEOJSON_URL = "https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36"
}


def fetch_geojson() -> dict:
    print("Downloading US state boundaries...")
    req = Request(GEOJSON_URL, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    print(f"Got {len(data['features'])} state features")
    return data


def extract_polygons(geometry: dict) -> list[list[tuple[float, float]]]:
    """Extract list of polygon rings from a GeoJSON geometry."""
    polygons = []
    if geometry["type"] == "Polygon":
        for ring in geometry["coordinates"]:
            polygons.append([(lon, lat) for lon, lat in ring])
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            for ring in polygon:
                polygons.append([(lon, lat) for lon, lat in ring])
    return polygons


def fit_to_canvas(polygons: list[list[tuple]], width: int, height: int, padding: int):
    """Scale and translate polygons to fit within the SVG canvas."""
    all_lons = [p[0] for ring in polygons for p in ring]
    all_lats = [p[1] for ring in polygons for p in ring]

    min_lon, max_lon = min(all_lons), max(all_lons)
    min_lat, max_lat = min(all_lats), max(all_lats)

    geo_w = max_lon - min_lon or 1
    geo_h = max_lat - min_lat or 1

    usable_w = width - 2 * padding
    usable_h = height - 2 * padding

    scale = min(usable_w / geo_w, usable_h / geo_h)

    # Center the shape
    scaled_w = geo_w * scale
    scaled_h = geo_h * scale
    offset_x = padding + (usable_w - scaled_w) / 2
    offset_y = padding + (usable_h - scaled_h) / 2

    transformed = []
    for ring in polygons:
        new_ring = []
        for lon, lat in ring:
            x = (lon - min_lon) * scale + offset_x
            # Flip Y axis (latitude increases up, SVG Y increases down)
            y = (max_lat - lat) * scale + offset_y
            new_ring.append((round(x, 2), round(y, 2)))
        transformed.append(new_ring)

    return transformed


def rings_to_path(rings: list[list[tuple]]) -> str:
    """Convert polygon rings to an SVG path data string."""
    parts = []
    for ring in rings:
        if len(ring) < 3:
            continue
        d = f"M {ring[0][0]},{ring[0][1]}"
        for x, y in ring[1:]:
            d += f" L {x},{y}"
        d += " Z"
        parts.append(d)
    return " ".join(parts)


def generate_svg(path_data: str, width: int, height: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <path d="{path_data}" fill="none" stroke="#000000" stroke-width="2" stroke-linejoin="round" opacity="0.3"/>
</svg>"""


def main():
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("borders")
    output_dir.mkdir(parents=True, exist_ok=True)

    geojson = fetch_geojson()

    generated = 0
    for feature in geojson["features"]:
        name = feature["properties"].get("name", "Unknown")
        safe_name = name.replace(" ", "_")

        polygons = extract_polygons(feature["geometry"])
        if not polygons:
            print(f"  [{name}] No polygon data, skipping")
            continue

        fitted = fit_to_canvas(polygons, SVG_WIDTH, SVG_HEIGHT, PADDING)
        path_data = rings_to_path(fitted)
        svg_content = generate_svg(path_data, SVG_WIDTH, SVG_HEIGHT)

        svg_path = output_dir / f"{safe_name}.svg"
        svg_path.write_text(svg_content)
        generated += 1
        print(f"  [{name}] {svg_path}")

    print(f"\nGenerated {generated} SVGs in {output_dir}/")


if __name__ == "__main__":
    main()
