"""
1. Convert PNG insignias to SVG via potrace (bitmap tracing)
2. Normalize all insignia SVGs to single-color for use as background watermarks
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

INSIGNIAS_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("insignias")
FILL_COLOR = "#000000"  # single color — opacity controlled at use time
CANVAS_SIZE = 800


def png_to_svg(png_path: Path) -> Path:
    """Convert a PNG to SVG using potrace. Returns the SVG path."""
    svg_path = png_path.with_suffix(".svg")

    # Convert to PBM (potrace input format) via Pillow
    img = Image.open(png_path).convert("L")  # grayscale
    # Threshold to black/white
    bw = img.point(lambda x: 0 if x < 128 else 255, "1")

    pbm_path = png_path.with_suffix(".pbm")
    bw.save(str(pbm_path))

    # Run potrace
    result = subprocess.run(
        ["potrace", str(pbm_path), "-s", "-o", str(svg_path),
         "--flat", "--turdsize", "5"],
        capture_output=True, text=True,
    )

    if pbm_path.exists():
        pbm_path.unlink()

    if result.returncode != 0:
        print(f"  potrace failed: {result.stderr}")
        return None

    print(f"  Traced: {png_path.name} -> {svg_path.name}")
    return svg_path


def normalize_svg_color(svg_path: Path):
    """Rewrite an SVG to use a single fill color, no stroke colors."""
    content = svg_path.read_text(encoding="utf-8", errors="replace")

    # Replace all fill colors with our single color
    content = re.sub(r'fill\s*=\s*"(?!none)[^"]*"', f'fill="{FILL_COLOR}"', content)
    content = re.sub(r'fill\s*:\s*(?!none)[^;}"]+', f'fill:{FILL_COLOR}', content)

    # Replace all stroke colors with same color
    content = re.sub(r'stroke\s*=\s*"(?!none)[^"]*"', f'stroke="{FILL_COLOR}"', content)
    content = re.sub(r'stroke\s*:\s*(?!none)[^;}"]+', f'stroke:{FILL_COLOR}', content)

    # Remove any inline opacity/fill-opacity that might interfere
    # (we want opacity controlled at embed time, not baked in)
    content = re.sub(r'fill-opacity\s*[:=]\s*"?[\d.]+%?"?', '', content)
    content = re.sub(r'(?<!\w)opacity\s*[:=]\s*"?[\d.]+%?"?', '', content)

    svg_path.write_text(content, encoding="utf-8")


def main():
    if not INSIGNIAS_DIR.exists():
        print(f"Directory not found: {INSIGNIAS_DIR}")
        sys.exit(1)

    # Step 1: Convert PNGs to SVGs
    pngs = sorted(INSIGNIAS_DIR.glob("*.png"))
    if pngs:
        print(f"Converting {len(pngs)} PNGs to SVG...")
        for png in pngs:
            svg = png_to_svg(png)
            if svg:
                png.unlink()  # remove the PNG now that we have SVG
    else:
        print("No PNGs to convert.")

    # Step 2: Normalize all SVGs to single color
    svgs = sorted(INSIGNIAS_DIR.glob("*.svg"))
    print(f"\nNormalizing {len(svgs)} SVGs to single color ({FILL_COLOR})...")
    for svg in svgs:
        normalize_svg_color(svg)
        print(f"  {svg.name}")

    print(f"\nDone. {len(svgs)} single-color SVGs in {INSIGNIAS_DIR}/")


if __name__ == "__main__":
    main()
