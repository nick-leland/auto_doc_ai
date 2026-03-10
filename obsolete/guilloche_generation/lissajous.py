import math
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class LissajousConfig:
    width: int = 800                          # outer SVG width (px)
    height: int = 1040                        # outer SVG height (px)
    margin: float = 20.0                      # offset from SVG edge to border band center
    border_thickness: float = 44.0            # thickness of the border band
    colors: list[str] = field(default_factory=lambda: [
        "#1a4a2e", "#2a6e3f", "#1a5c30", "#0e3d20",
    ])
    stroke_width: float = 0.55
    freq_a: float = 3.0                       # Lissajous a parameter
    freq_b: float = 2.0                       # Lissajous b parameter
    phase_delta: float = 0.0                  # base phase delta between x/y
    num_curves: int = 14                      # overlapping curves for weave density
    samples: int = 900                        # points per quadrant
    amp: float = 0.85                         # amplitude as fraction of border_thickness / 2
    corner_radius: float = 14.0               # rounded corners
    background_color: str = "none"


def _sample_quadrant(cfg: LissajousConfig) -> list[Tuple[float, float, float, float]]:
    """
    Sample centerline points for the top-right quadrant of the border.
    Path: top-center -> top-right corner arc -> right-center.
    Returns (x, y, nx, ny) where (nx, ny) is the inward-pointing normal.
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

    points: list[Tuple[float, float, float, float]] = []
    n = cfg.samples // 4

    for i in range(n):
        d = (i / max(n - 1, 1)) * total

        # Top edge segment: center to corner start
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

        # Right edge segment: corner end to center
        frac = d3 / half_right if half_right > 0 else 0
        x = ox + w
        y = oy + r + frac * half_right
        points.append((x, y, -1.0, 0.0))

    return points


def _lissajous_offset(
    t: float, curve_idx: int, cfg: LissajousConfig
) -> float:
    """
    Compute the perpendicular Lissajous offset for parameter t along the border.

    The Lissajous figure is x(t)=A*sin(a*t+delta), y(t)=B*sin(b*t).
    Here we combine x and y into a single perpendicular displacement by
    summing two sinusoids with the Lissajous freq_a/freq_b ratio.
    Each curve gets a progressive phase shift to create the braided weave.
    """
    max_amp = (cfg.border_thickness / 2) * cfg.amp
    # progressive phase offset per curve creates the interlacing
    curve_phase = curve_idx * (2 * math.pi / max(cfg.num_curves, 1))
    delta = cfg.phase_delta + curve_phase

    # Two superimposed oscillation components at the a:b frequency ratio
    # give the characteristic Lissajous knot pattern
    tau = 2 * math.pi * t
    component_a = math.sin(cfg.freq_a * tau + delta)
    component_b = math.sin(cfg.freq_b * tau)

    # Blend: the two components create the figure-8 / knot crossings
    # Weight component_a more heavily — it carries the main ribbon shape
    offset = max_amp * (0.6 * component_a + 0.4 * component_b)
    return offset


def _points_to_svg_path(points: list[Tuple[float, float]]) -> str:
    """Convert a list of (x, y) points into an SVG path string."""
    if not points:
        return ""
    parts = [f"M {points[0][0]:.2f},{points[0][1]:.2f}"]
    for x, y in points[1:]:
        parts.append(f"L {x:.2f},{y:.2f}")
    parts.append("Z")
    return " ".join(parts)


def generate_lissajous(cfg: LissajousConfig | None = None) -> str:
    """
    Generate an SVG string containing a Lissajous weave border pattern.

    Produces perfect horizontal and vertical symmetry by generating one
    quadrant and mirroring it four ways.  Multiple phase-shifted Lissajous
    curves overlap to create a braided / ribbon look reminiscent of
    security-document borders.
    """
    if cfg is None:
        cfg = LissajousConfig()

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

    paths_svg: list[str] = []

    for ci in range(cfg.num_curves):
        color = cfg.colors[ci % len(cfg.colors)]

        # Displace each quadrant point by the Lissajous offset
        qtr_displaced: list[Tuple[float, float]] = []
        for i, (bx, by, nx, ny) in enumerate(qtr_points):
            t = i / n
            off = _lissajous_offset(t, ci, cfg)
            qtr_displaced.append((bx + nx * off, by + ny * off))

        # Build full closed path by mirroring (clockwise):
        # 1. left-center -> top-center  (mirror-x of quadrant, reversed)
        seg1 = [mirror_x(p) for p in reversed(qtr_displaced)]
        # 2. top-center -> right-center (quadrant as-is)
        seg2 = qtr_displaced
        # 3. right-center -> bottom-center (mirror-y of quadrant, reversed)
        seg3 = [mirror_y(p) for p in reversed(qtr_displaced)]
        # 4. bottom-center -> left-center (mirror-xy of quadrant)
        seg4 = [mirror_xy(p) for p in qtr_displaced]

        full_path = seg1 + seg2 + seg3 + seg4

        d = _points_to_svg_path(full_path)
        # Vary opacity slightly per curve for depth
        opacity = 0.7 + 0.25 * (ci % 2)
        paths_svg.append(
            f'  <path d="{d}" fill="none" stroke="{color}" '
            f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" '
            f'stroke-linejoin="round" opacity="{opacity:.2f}"/>'
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
    # Default green braided border
    cfg = LissajousConfig()
    svg = generate_lissajous(cfg)
    with open("lissajous_border.svg", "w") as f:
        f.write(svg)
    print("Wrote lissajous_border.svg")

    # Dense blue security variant — higher frequencies, more curves
    cfg2 = LissajousConfig(
        border_thickness=52.0,
        num_curves=20,
        samples=1200,
        freq_a=5.0,
        freq_b=3.0,
        phase_delta=0.3,
        amp=0.90,
        stroke_width=0.4,
        colors=["#1a3a6e", "#2a5090", "#163060", "#1a3a6e"],
        corner_radius=18.0,
    )
    svg2 = generate_lissajous(cfg2)
    with open("lissajous_border_blue.svg", "w") as f:
        f.write(svg2)
    print("Wrote lissajous_border_blue.svg")
