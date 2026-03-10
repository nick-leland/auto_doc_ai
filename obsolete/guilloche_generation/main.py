import math
import hashlib
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class GuillocheConfig:
    width: int = 800                        # outer SVG width (px)
    height: int = 1040                      # outer SVG height (px)
    border_thickness: float = 40.0          # thickness of the guilloche band
    margin: float = 20.0                    # offset from SVG edge to border center
    num_curves: int = 18                    # curves layered in the band
    samples: int = 800                      # points per side
    # wave parameters: each curve i gets freq_base + i*freq_step, etc.
    freq_base: float = 20.0                 # base oscillation frequency
    freq_step: float = 2.0                  # frequency increment per curve
    amp_base: float = 0.25                  # base amplitude (fraction of border_thickness/2)
    amp_step: float = 0.04                  # amplitude increment per curve
    phase_step: float = 0.35                # phase offset increment per curve (radians)
    stroke_width: float = 0.6
    colors: list[str] = field(default_factory=lambda: ["#2a6e3f", "#1a5c30"])
    background_color: str = "none"
    corner_radius: float = 12.0            # rounded corners


def _stable_seed(text: str) -> int:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def _wave_offset(t: float, curve_idx: int, cfg: GuillocheConfig) -> float:
    """Compute the perpendicular wave offset for a point along the border."""
    freq = cfg.freq_base + curve_idx * cfg.freq_step
    amp = (cfg.border_thickness / 2) * (cfg.amp_base + curve_idx * cfg.amp_step)
    phase = curve_idx * cfg.phase_step
    return amp * math.sin(2 * math.pi * freq * t + phase)


def _sample_quadrant(cfg: GuillocheConfig) -> list[Tuple[float, float, float, float]]:
    """
    Sample points for the top-right quadrant of the border centerline.
    Path goes from top-center -> top-right corner -> right-center.
    Returns list of (x, y, nx, ny) where (nx, ny) is the inward-pointing normal.
    """
    w = cfg.width - 2 * cfg.margin
    h = cfg.height - 2 * cfg.margin
    r = min(cfg.corner_radius, w / 2, h / 2)
    ox = cfg.margin
    oy = cfg.margin
    mid_x = cfg.width / 2

    half_top = w / 2 - r
    corner_arc = 0.5 * math.pi * r
    half_right = h / 2 - r
    total = half_top + corner_arc + half_right

    points = []
    n = cfg.samples // 4

    for i in range(n):
        d = (i / max(n - 1, 1)) * total

        # Top edge: center to right
        if d <= half_top:
            frac = d / half_top if half_top > 0 else 0
            x = mid_x + frac * half_top
            y = oy
            points.append((x, y, 0.0, 1.0))
            continue

        d2 = d - half_top

        # Top-right corner arc
        if d2 <= corner_arc:
            angle = -math.pi / 2 + (d2 / corner_arc) * (math.pi / 2)
            ccx = ox + w - r
            ccy = oy + r
            x = ccx + r * math.cos(angle)
            y = ccy + r * math.sin(angle)
            points.append((x, y, -math.cos(angle), -math.sin(angle)))
            continue

        d3 = d2 - corner_arc

        # Right edge: top to center
        frac = d3 / half_right if half_right > 0 else 0
        x = ox + w
        y = oy + r + frac * half_right
        points.append((x, y, -1.0, 0.0))

    return points


def _points_to_svg_path(points: list[Tuple[float, float]]) -> str:
    """Convert a list of (x, y) points into an SVG path string."""
    if not points:
        return ""
    parts = [f"M {points[0][0]:.2f},{points[0][1]:.2f}"]
    for x, y in points[1:]:
        parts.append(f"L {x:.2f},{y:.2f}")
    parts.append("Z")
    return " ".join(parts)


def generate_guilloche(cfg: GuillocheConfig | None = None) -> str:
    """
    Generate an SVG string containing a rectangular guilloche border pattern.
    Produces perfect horizontal and vertical symmetry by generating one quadrant
    and mirroring it.
    """
    if cfg is None:
        cfg = GuillocheConfig()

    cx = cfg.width / 2
    cy = cfg.height / 2

    qtr_points = _sample_quadrant(cfg)
    n = len(qtr_points)
    if not qtr_points:
        return ""

    def mirror_x(pt: Tuple[float, float]) -> Tuple[float, float]:
        return (2 * cx - pt[0], pt[1])

    def mirror_y(pt: Tuple[float, float]) -> Tuple[float, float]:
        return (pt[0], 2 * cy - pt[1])

    def mirror_xy(pt: Tuple[float, float]) -> Tuple[float, float]:
        return (2 * cx - pt[0], 2 * cy - pt[1])

    paths_svg = []

    for ci in range(cfg.num_curves):
        color = cfg.colors[ci % len(cfg.colors)]

        # Compute wave offsets for quadrant points
        qtr_displaced = []
        for i, (bx, by, nx, ny) in enumerate(qtr_points):
            t = i / n
            off = _wave_offset(t, ci, cfg)
            qtr_displaced.append((bx + nx * off, by + ny * off))

        # Build full closed path by mirroring (clockwise):
        # 1. left-center -> top-center (mirror-x of quadrant, reversed)
        seg1 = [mirror_x(p) for p in reversed(qtr_displaced)]
        # 2. top-center -> right-center (quadrant as-is)
        seg2 = qtr_displaced
        # 3. right-center -> bottom-center (mirror-y of quadrant, reversed)
        seg3 = [mirror_y(p) for p in reversed(qtr_displaced)]
        # 4. bottom-center -> left-center (mirror-xy of quadrant)
        seg4 = [mirror_xy(p) for p in qtr_displaced]

        full_path = seg1 + seg2 + seg3 + seg4

        d = _points_to_svg_path(full_path)
        paths_svg.append(
            f'  <path d="{d}" fill="none" stroke="{color}" '
            f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" '
            f'stroke-linejoin="round" opacity="0.85"/>'
        )

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{cfg.width}" height="{cfg.height}" '
        f'viewBox="0 0 {cfg.width} {cfg.height}">',
    ]

    if cfg.background_color != "none":
        svg_parts.append(
            f'  <rect width="{cfg.width}" height="{cfg.height}" '
            f'fill="{cfg.background_color}"/>'
        )

    svg_parts.extend(paths_svg)
    svg_parts.append("</svg>")

    return "\n".join(svg_parts)


if __name__ == "__main__":
    # Default green pattern
    cfg = GuillocheConfig()
    svg = generate_guilloche(cfg)
    with open("guilloche_border.svg", "w") as f:
        f.write(svg)
    print("Wrote guilloche_border.svg")

    # Alternate: dense blue security pattern
    cfg2 = GuillocheConfig(
        border_thickness=55.0,
        num_curves=24,
        samples=1000,
        freq_base=30.0,
        freq_step=1.5,
        amp_base=0.20,
        amp_step=0.03,
        phase_step=0.25,
        stroke_width=0.4,
        colors=["#1a3a6e", "#2a5090", "#1a3a6e"],
        corner_radius=16.0,
    )
    svg2 = generate_guilloche(cfg2)
    with open("guilloche_border_blue.svg", "w") as f:
        f.write(svg2)
    print("Wrote guilloche_border_blue.svg")
