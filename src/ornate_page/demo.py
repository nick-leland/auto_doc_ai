#!/usr/bin/env python3
"""
Demo script: generates full-page SVG patterns for each pattern type.
Outputs to demo_output/svg/ and demo_output/png/.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.ornate_page.patterns import (
    PatternType,
    generate_pattern_elements,
    random_full_page_config,
)


def main():
    svg_dir = "demo_output/svg"
    png_dir = "demo_output/png"
    os.makedirs(svg_dir, exist_ok=True)
    os.makedirs(png_dir, exist_ok=True)

    bg_color = "#D8E4F0"

    for pt in PatternType:
        cfg = random_full_page_config(
            width=800, height=1040,
            colors=["#2C5C9A", "#1F4A80", "#3A6FB0"],
            pattern_type=pt,
            seed=42,
        )
        elements = generate_pattern_elements(cfg)
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{cfg.width}" height="{cfg.height}" '
            f'viewBox="0 0 {cfg.width} {cfg.height}">',
            f'  <rect width="{cfg.width}" height="{cfg.height}" fill="{bg_color}"/>',
        ]
        svg_parts.extend(f"  {e}" for e in elements)
        svg_parts.append("</svg>")
        svg = "\n".join(svg_parts)

        svg_path = os.path.join(svg_dir, f"{pt.value}.svg")
        png_path = os.path.join(png_dir, f"{pt.value}.png")

        with open(svg_path, "w") as f:
            f.write(svg)

        subprocess.run(
            ["rsvg-convert", "-w", "1600", svg_path, "-o", png_path],
            check=True, capture_output=True,
        )
        print(f"  {pt.value}")

    print(f"\nWrote {len(PatternType)} patterns to {svg_dir}/ and {png_dir}/")


if __name__ == "__main__":
    main()
