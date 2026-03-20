"""
Convert all state insignia SVGs to single-color linework SVGs + PNGs.

Strategy:
- SVGs that render properly: render full color → edge detect → potrace
- SVGs that render as black blobs: apply CSS stroke-only → render → potrace
"""

import re
import subprocess
import numpy as np
from scipy.ndimage import gaussian_filter, convolve
from PIL import Image, ImageFilter, ImageOps
from pathlib import Path

SVG_DIR = Path("insignias/svg")
OUT_SVG = Path("insignias/svg_linework")
OUT_PNG = Path("insignias/png")

OUT_SVG.mkdir(parents=True, exist_ok=True)
OUT_PNG.mkdir(parents=True, exist_ok=True)

RENDER_SIZE = 3000  # high res for edge detection
OUTPUT_SIZE = 800   # final output size


def renders_properly(svg_path: Path) -> bool:
    """Check if an SVG renders with actual detail vs a black blob."""
    subprocess.run(["rsvg-convert", "-w", "200", "-h", "200", "--keep-aspect-ratio",
                    "-b", "white", str(svg_path), "-o", "/tmp/_test.png"],
                   capture_output=True, check=False)
    img = np.array(Image.open("/tmp/_test.png").convert("L"))
    dark_pct = (img < 50).sum() / img.size
    return dark_pct < 0.5


def render_full_color(svg_path: Path, out_path: str, size: int = RENDER_SIZE):
    """Render SVG at high resolution with white background."""
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size),
                    "--keep-aspect-ratio", "-b", "white",
                    str(svg_path), "-o", out_path], check=True)


def apply_stroke_only_css(svg_path: Path) -> Path:
    """Create a modified SVG with stroke-only rendering."""
    svg_text = svg_path.read_text(errors="replace")
    style_block = """<style>
  * { fill: none !important; stroke: #000000 !important; stroke-width: 1.5px !important; }
  text, tspan { fill: #000000 !important; stroke: none !important; }
</style>"""
    svg_modified = re.sub(r"(<svg[^>]*>)", r"\1" + style_block, svg_text, count=1)
    tmp = Path(f"/tmp/_stroke_{svg_path.name}")
    tmp.write_text(svg_modified)
    return tmp


def edge_detect(img_array: np.ndarray, threshold: int = 20) -> np.ndarray:
    """Sobel edge detection returning black lines on white background."""
    smooth = gaussian_filter(img_array.astype(np.float64), sigma=0.8)
    sx = convolve(smooth, [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
    sy = convolve(smooth, [[-1, -2, -1], [0, 0, 0], [1, 2, 1]])
    magnitude = np.sqrt(sx ** 2 + sy ** 2)
    magnitude = (magnitude / max(magnitude.max(), 1) * 255).astype(np.uint8)
    # Black lines on white background
    return np.where(magnitude > threshold, 0, 255).astype(np.uint8)


def dilate_lines(bw_array: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Dilate black lines slightly for better potrace tracing."""
    img = Image.fromarray(bw_array, mode="L")
    for _ in range(iterations):
        img = img.filter(ImageFilter.MinFilter(3))
    return np.array(img)


def potrace_to_svg(bw_png_path: str, svg_out_path: str):
    """Trace a black/white PNG to SVG using potrace."""
    # Convert to PBM first
    img = Image.open(bw_png_path).convert("1")
    pbm_path = bw_png_path.replace(".png", ".pbm")
    img.save(pbm_path)

    subprocess.run(["potrace", pbm_path, "-s", "-o", svg_out_path,
                    "--flat", "--turdsize", "3", "-O", "0.2"],
                   capture_output=True, check=True)

    if Path(pbm_path).exists():
        Path(pbm_path).unlink()


def svg_to_final_png(svg_path: str, png_path: str, size: int = OUTPUT_SIZE):
    """Render the linework SVG to final PNG."""
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size),
                    "--keep-aspect-ratio", "-b", "white",
                    svg_path, "-o", png_path], check=True)


def process_good_svg(svg_path: Path, name: str):
    """Process an SVG that renders properly: render → edge detect → trace."""
    tmp_color = f"/tmp/_color_{name}.png"
    tmp_bw = f"/tmp/_bw_{name}.png"

    render_full_color(svg_path, tmp_color)
    img = np.array(Image.open(tmp_color).convert("L"))
    edges = edge_detect(img, threshold=18)
    edges = dilate_lines(edges, iterations=1)
    Image.fromarray(edges, mode="L").save(tmp_bw)

    svg_out = str(OUT_SVG / f"{name}.svg")
    potrace_to_svg(tmp_bw, svg_out)

    png_out = str(OUT_PNG / f"{name}.png")
    svg_to_final_png(svg_out, png_out)


def process_blob_svg(svg_path: Path, name: str):
    """Process a black-blob SVG: CSS stroke-only → render → trace."""
    stroke_svg = apply_stroke_only_css(svg_path)
    tmp_render = f"/tmp/_stroke_render_{name}.png"
    tmp_bw = f"/tmp/_bw_{name}.png"

    render_full_color(stroke_svg, tmp_render, size=RENDER_SIZE)
    img = np.array(Image.open(tmp_render).convert("L"))

    # For stroke-only renders, threshold directly (already mostly B&W)
    bw = np.where(img < 200, 0, 255).astype(np.uint8)
    bw = dilate_lines(bw, iterations=1)
    Image.fromarray(bw, mode="L").save(tmp_bw)

    svg_out = str(OUT_SVG / f"{name}.svg")
    potrace_to_svg(tmp_bw, svg_out)

    png_out = str(OUT_PNG / f"{name}.png")
    svg_to_final_png(svg_out, png_out)


def main():
    svgs = sorted(SVG_DIR.glob("*.svg"))
    print(f"Processing {len(svgs)} state insignias...\n")

    good = 0
    blob = 0
    failed = []

    for svg in svgs:
        name = svg.stem
        try:
            if renders_properly(svg):
                print(f"  [{name}] Full color → edge detect")
                process_good_svg(svg, name)
                good += 1
            else:
                print(f"  [{name}] Black blob → stroke-only")
                process_blob_svg(svg, name)
                blob += 1
        except Exception as e:
            print(f"  [{name}] FAILED: {e}")
            failed.append(name)

    print(f"\nDone. {good} edge-detected, {blob} stroke-only, {len(failed)} failed.")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
