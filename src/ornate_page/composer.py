"""
Ornate document composer.

Layers:
  1. Background color fill
  2. Full-page pattern with center rectangle cut out → ornate border
  3. Inner fill pattern clipped to center rectangle at low opacity → anti-copy effect
  4. (Future) State insignia/symbol faintly in center background
  5. Text overlay on top

Everything is pure SVG using clipPath and opacity for layering.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Tuple

from .patterns import (
    FullPageConfig,
    PatternType,
    generate_pattern_elements,
    random_full_page_config,
)


@dataclass
class OrnateDocumentConfig:
    # Page dimensions (pixels at given PPI)
    width: int = 2250
    height: int = 3000

    # Border region
    border_thickness: float = 120.0     # how much of the outer pattern to keep
    corner_radius: float = 8.0          # rounded corners on the inner cutout

    # Colors
    background_color: str = "#D8E4F0"
    border_colors: list[str] = field(default_factory=lambda: ["#2C5C9A", "#1F4A80"])
    inner_colors: list[str] = field(default_factory=lambda: ["#2C5C9A", "#1F4A80"])

    # Outer pattern (becomes the border)
    border_pattern_type: PatternType = PatternType.GUILLOCHE_DIAMOND
    border_pattern_seed: int | None = None

    # Inner fill pattern (anti-copy watermark in center)
    inner_pattern_type: PatternType = PatternType.LISSAJOUS_MESH
    inner_pattern_seed: int | None = None
    inner_opacity: float = 0.12         # very faint for anti-copy effect

    # Optional state insignia (future)
    state_name: str | None = None
    insignia_opacity: float = 0.08

    # Master seed for reproducibility
    seed: int | None = None


def _inner_rect(cfg: OrnateDocumentConfig) -> Tuple[float, float, float, float]:
    """Return (x, y, w, h) of the inner content rectangle."""
    x = cfg.border_thickness
    y = cfg.border_thickness
    w = cfg.width - 2 * cfg.border_thickness
    h = cfg.height - 2 * cfg.border_thickness
    return x, y, w, h


def _generate_border_clip_paths(cfg: OrnateDocumentConfig) -> str:
    """
    Generate SVG <defs> with two clip paths:
      - border-clip: the border region (full page minus inner rect)
      - inner-clip: the inner rectangle only
    """
    ix, iy, iw, ih = _inner_rect(cfg)
    r = cfg.corner_radius

    return f"""  <defs>
    <!-- Clip to border region only (outer minus inner hole) -->
    <clipPath id="border-clip">
      <!-- Full page rect -->
      <rect x="0" y="0" width="{cfg.width}" height="{cfg.height}"/>
    </clipPath>
    <!-- Mask to cut out the inner rectangle from the border pattern -->
    <mask id="border-mask">
      <rect x="0" y="0" width="{cfg.width}" height="{cfg.height}" fill="white"/>
      <rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="{r}" ry="{r}" fill="black"/>
    </mask>
    <!-- Clip to inner rectangle only -->
    <clipPath id="inner-clip">
      <rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" rx="{r}" ry="{r}"/>
    </clipPath>
  </defs>"""


def _generate_inner_frame(cfg: OrnateDocumentConfig) -> str:
    """Generate a thin decorative frame line around the inner rectangle."""
    ix, iy, iw, ih = _inner_rect(cfg)
    r = cfg.corner_radius
    color = cfg.border_colors[0]
    return (
        f'  <rect x="{ix}" y="{iy}" width="{iw}" height="{ih}" '
        f'rx="{r}" ry="{r}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" opacity="0.6"/>'
    )


def _generate_state_insignia_placeholder(cfg: OrnateDocumentConfig) -> list[str]:
    """
    Generate a faint text-based state insignia in the center.
    This is a placeholder — future versions will use actual state seal SVG paths.
    """
    if not cfg.state_name:
        return []

    cx, cy = cfg.width / 2, cfg.height / 2
    color = cfg.border_colors[0]
    elements = []

    # Large faint state name as watermark
    elements.append(
        f'  <text x="{cx}" y="{cy}" text-anchor="middle" '
        f'font-family="Palatino, serif" font-size="120" font-weight="bold" '
        f'fill="{color}" opacity="{cfg.insignia_opacity}" '
        f'transform="rotate(-30, {cx}, {cy})">'
        f'{cfg.state_name}</text>'
    )

    # Circular text ring around center
    ring_radius = min(cfg.width, cfg.height) * 0.2
    ring_text = f"STATE OF {cfg.state_name.upper()} "
    # Repeat to fill the circle
    ring_text = (ring_text * 4)[:120]
    elements.append(
        f'  <defs><path id="insignia-ring" d="M {cx},{cy - ring_radius} '
        f'a {ring_radius},{ring_radius} 0 1,1 0,{2 * ring_radius} '
        f'a {ring_radius},{ring_radius} 0 1,1 0,{-2 * ring_radius}"/></defs>'
    )
    elements.append(
        f'  <text font-family="Palatino, serif" font-size="18" '
        f'fill="{color}" opacity="{cfg.insignia_opacity * 1.2:.3f}" '
        f'letter-spacing="3">'
        f'<textPath href="#insignia-ring">{ring_text}</textPath></text>'
    )

    # Concentric decorative circles
    for i, r_frac in enumerate([0.15, 0.22, 0.28]):
        r = min(cfg.width, cfg.height) * r_frac
        elements.append(
            f'  <circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="none" '
            f'stroke="{color}" stroke-width="0.5" '
            f'opacity="{cfg.insignia_opacity * (0.8 + 0.2 * i):.3f}" '
            f'stroke-dasharray="4,4"/>'
        )

    return elements


def compose_ornate_document(cfg: OrnateDocumentConfig) -> str:
    """
    Compose a full ornate document SVG with layered patterns.

    Returns a complete SVG string ready to be saved or embedded.
    """
    rng = random.Random(cfg.seed)

    # Generate border pattern config
    border_cfg = random_full_page_config(
        width=cfg.width,
        height=cfg.height,
        colors=cfg.border_colors,
        pattern_type=cfg.border_pattern_type,
        seed=cfg.border_pattern_seed or rng.randint(0, 2**32),
    )

    # Generate inner fill pattern config
    inner_cfg = random_full_page_config(
        width=cfg.width,
        height=cfg.height,
        colors=cfg.inner_colors,
        pattern_type=cfg.inner_pattern_type,
        seed=cfg.inner_pattern_seed or rng.randint(0, 2**32),
    )

    # Get pattern SVG elements
    border_elements = generate_pattern_elements(border_cfg)
    inner_elements = generate_pattern_elements(inner_cfg)

    # Build the SVG
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{cfg.width}" height="{cfg.height}" '
        f'viewBox="0 0 {cfg.width} {cfg.height}">',
    ]

    # Background
    parts.append(
        f'  <rect width="{cfg.width}" height="{cfg.height}" '
        f'fill="{cfg.background_color}"/>'
    )

    # Clip/mask definitions
    parts.append(_generate_border_clip_paths(cfg))

    # Layer 1: Border pattern (full page pattern masked to border region only)
    parts.append('  <!-- Border: full-page pattern with center cut out -->')
    parts.append('  <g mask="url(#border-mask)">')
    for elem in border_elements:
        parts.append(f"    {elem}")
    parts.append("  </g>")

    # Layer 2: Inner fill pattern (clipped to center rect, low opacity)
    ix, iy, iw, ih = _inner_rect(cfg)
    parts.append('  <!-- Inner fill: anti-copy watermark pattern -->')
    parts.append(
        f'  <g clip-path="url(#inner-clip)" opacity="{cfg.inner_opacity}">'
    )
    for elem in inner_elements:
        parts.append(f"    {elem}")
    parts.append("  </g>")

    # Layer 3: State insignia (if provided)
    if cfg.state_name:
        parts.append('  <!-- State insignia watermark -->')
        parts.append('  <g clip-path="url(#inner-clip)">')
        insignia_elements = _generate_state_insignia_placeholder(cfg)
        for elem in insignia_elements:
            parts.append(f"    {elem}")
        parts.append("  </g>")

    # Decorative inner frame line
    parts.append(_generate_inner_frame(cfg))

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Random document generator
# ---------------------------------------------------------------------------

def random_ornate_document_config(
    width: int = 2250,
    height: int = 3000,
    border_colors: list[str] | None = None,
    inner_colors: list[str] | None = None,
    background_color: str | None = None,
    state_name: str | None = None,
    seed: int | None = None,
) -> OrnateDocumentConfig:
    """Generate a fully randomized ornate document configuration."""
    rng = random.Random(seed)

    if border_colors is None:
        border_colors = ["#2C5C9A", "#1F4A80"]
    if inner_colors is None:
        inner_colors = border_colors
    if background_color is None:
        background_color = "#D8E4F0"

    # Pick different pattern types for border vs inner
    all_types = list(PatternType)
    border_type = rng.choice(all_types)
    inner_type = rng.choice([t for t in all_types if t != border_type])

    border_thickness = rng.uniform(80, 160)

    return OrnateDocumentConfig(
        width=width,
        height=height,
        border_thickness=border_thickness,
        corner_radius=rng.uniform(4.0, 16.0),
        background_color=background_color,
        border_colors=border_colors,
        inner_colors=inner_colors,
        border_pattern_type=border_type,
        border_pattern_seed=rng.randint(0, 2**32),
        inner_pattern_type=inner_type,
        inner_pattern_seed=rng.randint(0, 2**32),
        inner_opacity=rng.uniform(0.08, 0.18),
        state_name=state_name,
        insignia_opacity=rng.uniform(0.05, 0.12),
        seed=seed,
    )
