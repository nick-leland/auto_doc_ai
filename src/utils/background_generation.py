"""
Background generation for ornate security-style documents.

Generates an svgwrite.Drawing with:
  1. Background color fill
  2. Full-page heavy pattern masked to border region only
  3. Background-colored rectangle covering the center (content area)
  4. Light pattern clipped to inner rectangle at low opacity (anti-copy)
  5. Decorative frame line around the inner boundary

Usage:
    from src.utils.background_generation import generate_background, random_background_params

    params = random_background_params(width=2250, height=3000, seed=42)
    drawing = generate_background(params)
    drawing.saveas("document.svg")
"""

import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import svgwrite

from src.ornate_page.patterns import (
    PatternType,
    generate_pattern_elements,
    random_full_page_config,
)

# Register SVG namespace to avoid ns0: prefixes on raw elements
ET.register_namespace("", "http://www.w3.org/2000/svg")


# ---------------------------------------------------------------------------
# Pattern categories
# ---------------------------------------------------------------------------

BORDER_PATTERNS: list[PatternType] = [
    PatternType.SPIROGRAPH_LATTICE,
    PatternType.GUILLOCHE_ROSETTE,
    PatternType.EPITROCHOID_LATTICE,
    PatternType.CONCENTRIC_LATHE,
    PatternType.MOIRE_RADIAL,
    PatternType.CROSSHATCH_WEAVE,
    PatternType.LATHE_RINGS,
    PatternType.LISSAJOUS_MESH,
]

INNER_PATTERNS: list[PatternType] = [
    PatternType.GUILLOCHE_DIAMOND,
    PatternType.WOVEN_RIBBON,
    PatternType.WAVE_FIELD,
    PatternType.HEX_ROSETTE_GRID,
    PatternType.CONTOUR_ENGRAVING,
    PatternType.BASKET_WEAVE,
    PatternType.SCROLL_CHAIN,
]


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

@dataclass
class BackgroundParams:
    width: int = 2250
    height: int = 3000
    border_size: float = 120.0
    corner_radius: float = 8.0

    bg_color: str = "#D8E4F0"
    border_color: str = "#2C5C9A"
    border_colors: list[str] = field(default_factory=list)
    inner_colors: list[str] = field(default_factory=list)

    border_pattern_type: PatternType = PatternType.SPIROGRAPH_LATTICE
    inner_pattern_type: PatternType = PatternType.GUILLOCHE_DIAMOND
    inner_opacity: float = 0.12

    seed: int | None = None

    def __post_init__(self):
        if not self.border_colors:
            self.border_colors = [self.border_color, _darken(self.border_color, 20)]
        if not self.inner_colors:
            self.inner_colors = list(self.border_colors)


def _darken(hex_color: str, amount: int) -> str:
    """Darken a hex color by amount percent (0-100)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    factor = 1 - amount / 100
    r, g, b = int(r * factor), int(g * factor), int(b * factor)
    return f"#{r:02X}{g:02X}{b:02X}"


# ---------------------------------------------------------------------------
# Raw SVG element bridge (patterns → svgwrite)
# ---------------------------------------------------------------------------

class _RawSVGElement:
    """Wrapper to inject a raw SVG string into an svgwrite container.

    Satisfies svgwrite's internal interface: needs elementname for validation
    and get_xml() for serialization.
    """

    # Allow as child of any SVG container
    elementname = "path"

    def __init__(self, svg_string: str):
        self._xml = ET.fromstring(svg_string)

    def get_xml(self):
        return self._xml


def _add_raw_elements(group, elements: list[str]):
    """Insert raw SVG element strings into an svgwrite group."""
    for elem_str in elements:
        group.add(_RawSVGElement(elem_str))


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def _inner_rect(params: BackgroundParams) -> tuple[float, float, float, float]:
    """Return (x, y, w, h) of the inner content rectangle."""
    x = params.border_size
    y = params.border_size
    w = params.width - 2 * params.border_size
    h = params.height - 2 * params.border_size
    return x, y, w, h


def add_background_to_drawing(
    drawing: svgwrite.Drawing,
    params: BackgroundParams,
) -> None:
    """Add background layers to an existing svgwrite.Drawing.

    Layers added (bottom to top):
      1. Background color fill
      2. Border pattern (full page, masked to border region)
      3. Background rect over inner area
      4. Inner security pattern (clipped to inner rect, low opacity)
      5. Decorative frame line
    """
    rng = random.Random(params.seed)
    ix, iy, iw, ih = _inner_rect(params)
    r = params.corner_radius

    # --- Layer 1: Background fill ---
    drawing.add(drawing.rect(
        insert=(0, 0),
        size=(params.width, params.height),
        fill=params.bg_color,
    ))

    # --- Defs: mask and clip path ---
    # Border mask: white everywhere, black hole in center
    border_mask = drawing.mask(id="border-mask")
    border_mask.add(drawing.rect(
        insert=(0, 0),
        size=(params.width, params.height),
        fill="white",
    ))
    border_mask.add(drawing.rect(
        insert=(ix, iy),
        size=(iw, ih),
        rx=r, ry=r,
        fill="black",
    ))
    drawing.defs.add(border_mask)

    # Inner clip path
    inner_clip = drawing.clipPath(id="inner-clip")
    inner_clip.add(drawing.rect(
        insert=(ix, iy),
        size=(iw, ih),
        rx=r, ry=r,
    ))
    drawing.defs.add(inner_clip)

    # --- Layer 2: Border pattern (masked to border region) ---
    border_cfg = random_full_page_config(
        width=params.width,
        height=params.height,
        colors=params.border_colors,
        pattern_type=params.border_pattern_type,
        seed=rng.randint(0, 2**32),
    )
    border_elements = generate_pattern_elements(border_cfg)

    border_g = drawing.g(mask="url(#border-mask)")
    _add_raw_elements(border_g, border_elements)
    drawing.add(border_g)

    # --- Layer 3: Inner security pattern (clipped, low opacity) ---
    inner_cfg = random_full_page_config(
        width=params.width,
        height=params.height,
        colors=params.inner_colors,
        pattern_type=params.inner_pattern_type,
        seed=rng.randint(0, 2**32),
    )
    inner_cfg.stroke_width *= 5.0
    inner_elements = generate_pattern_elements(inner_cfg)

    inner_g = drawing.g(
        clip_path="url(#inner-clip)",
        opacity=params.inner_opacity,
    )
    _add_raw_elements(inner_g, inner_elements)
    drawing.add(inner_g)

    # --- Layer 4: Decorative frame line ---
    drawing.add(drawing.rect(
        insert=(ix, iy),
        size=(iw, ih),
        rx=r, ry=r,
        fill="none",
        stroke=params.border_colors[0],
        stroke_width=1.5,
        opacity=0.6,
    ))


def add_background_no_border(
    drawing: svgwrite.Drawing,
    params: BackgroundParams,
) -> None:
    """Add background layers WITHOUT border to an existing drawing.

    For back sides of documents — just the background fill and a light
    inner security pattern across the full page. No border mask, no frame.

    Layers added (bottom to top):
      1. Background color fill
      2. Light security pattern (full page, low opacity)
    """
    rng = random.Random(params.seed)

    # --- Layer 1: Background fill ---
    drawing.add(drawing.rect(
        insert=(0, 0),
        size=(params.width, params.height),
        fill=params.bg_color,
    ))

    # --- Layer 2: Light security pattern (full page, low opacity) ---
    inner_cfg = random_full_page_config(
        width=params.width,
        height=params.height,
        colors=params.inner_colors,
        pattern_type=params.inner_pattern_type,
        seed=rng.randint(0, 2**32),
    )
    inner_cfg.stroke_width *= 5.0
    inner_elements = generate_pattern_elements(inner_cfg)

    inner_g = drawing.g(opacity=params.inner_opacity)
    _add_raw_elements(inner_g, inner_elements)
    drawing.add(inner_g)


def generate_background(params: BackgroundParams) -> svgwrite.Drawing:
    """Generate a full background document as an svgwrite.Drawing."""
    drawing = svgwrite.Drawing(
        size=(params.width, params.height),
    )
    add_background_to_drawing(drawing, params)
    return drawing


# ---------------------------------------------------------------------------
# Random parameter generation
# ---------------------------------------------------------------------------

def random_background_params(
    width: int = 2250,
    height: int = 3000,
    border_size: float | None = None,
    bg_color: str | None = None,
    border_color: str | None = None,
    seed: int | None = None,
) -> BackgroundParams:
    """Generate randomized background parameters.

    If border_size, bg_color, or border_color are None, they are randomized.
    Pattern types are randomly selected from the appropriate category lists.
    """
    rng = random.Random(seed)

    if border_size is None:
        border_size = rng.uniform(80, 160)
    if bg_color is None:
        bg_color = "#D8E4F0"
    if border_color is None:
        border_color = "#2C5C9A"

    border_pattern = rng.choice(BORDER_PATTERNS)
    inner_pattern = rng.choice(INNER_PATTERNS)

    return BackgroundParams(
        width=width,
        height=height,
        border_size=border_size,
        corner_radius=rng.uniform(4.0, 16.0),
        bg_color=bg_color,
        border_color=border_color,
        border_pattern_type=border_pattern,
        inner_pattern_type=inner_pattern,
        inner_opacity=rng.uniform(0.08, 0.18),
        seed=seed,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    params = random_background_params(width=800, height=1040, seed=42)
    drawing = generate_background(params)
    drawing.saveas("background_test.svg")
    print(
        f"Generated background: border={params.border_pattern_type.value}, "
        f"inner={params.inner_pattern_type.value}"
    )
