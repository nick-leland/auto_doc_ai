import math
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class SpirographConfig:
    width: int = 800                          # outer SVG width (px)
    height: int = 1040                        # outer SVG height (px)
    margin: float = 20.0                      # offset from SVG edge to border band center
    colors: list[str] = field(default_factory=lambda: ["#2a6e3f", "#1a5c30", "#3a8e55"])
    stroke_width: float = 0.5
    rosettes_per_side: int = 6                # rosettes along top/bottom (long sides)
    rosette_size: float = 28.0                # scaling factor applied to the hypotrochoid
    R: float = 5.0                            # fixed (outer) circle radius
    r: float = 3.0                            # rolling (inner) circle radius
    d: float = 5.0                            # tracing point distance from inner center
    num_points: int = 600                     # sample points per rosette curve
    corner_radius: float = 12.0              # rounded corners on the border rectangle
    background_color: str = "none"
    num_layers: int = 3                       # number of overlaid rosette layers (varied params)
    layer_r_step: float = 0.15                # r increment per layer for visual complexity
    layer_phase_step: float = 0.4             # rotation offset per layer (radians)


def _hypotrochoid(
    R: float, r: float, d: float,
    num_points: int, rotation: float = 0.0,
) -> list[Tuple[float, float]]:
    """
    Compute a hypotrochoid curve:
      x(t) = (R - r) * cos(t) + d * cos((R - r) / r * t)
      y(t) = (R - r) * sin(t) - d * sin((R - r) / r * t)
    Returns points centered at (0, 0).

    The curve closes after t goes from 0 to 2*pi*lcm_periods.  For simplicity
    we always trace 0..2*pi * (r / gcd(R_int, r_int)) when R, r are close to
    integers, but we fall back to 0..2*pi*20 for arbitrary floats.
    """
    # Determine how many full turns to close the curve
    try:
        Ri = round(R * 1000)
        ri = round(r * 1000)
        g = math.gcd(Ri, ri)
        periods = ri // g
    except Exception:
        periods = 20
    periods = min(periods, 60)  # cap to keep point count sane

    t_max = 2 * math.pi * periods
    diff = R - r
    ratio = diff / r

    points: list[Tuple[float, float]] = []
    cos_rot = math.cos(rotation)
    sin_rot = math.sin(rotation)

    for i in range(num_points):
        t = (i / num_points) * t_max
        x = diff * math.cos(t) + d * math.cos(ratio * t)
        y = diff * math.sin(t) - d * math.sin(ratio * t)
        # apply rotation
        rx = x * cos_rot - y * sin_rot
        ry = x * sin_rot + y * cos_rot
        points.append((rx, ry))

    return points


def _points_to_svg_path(points: list[Tuple[float, float]], close: bool = True) -> str:
    """Convert a list of (x, y) points into an SVG path d-attribute string."""
    if not points:
        return ""
    parts = [f"M {points[0][0]:.2f},{points[0][1]:.2f}"]
    for x, y in points[1:]:
        parts.append(f"L {x:.2f},{y:.2f}")
    if close:
        parts.append("Z")
    return " ".join(parts)


def _sample_border_positions_quadrant(
    cfg: SpirographConfig,
) -> list[Tuple[float, float, float]]:
    """
    Compute rosette center positions for the top-right quadrant of the border.

    Returns list of (cx, cy, angle) where angle is the rotation of the rosette
    to align with the border direction.

    Layout: rosettes are evenly spaced along the top edge (center to right corner)
    and right edge (top corner to center).  Corner rosettes sit on the arc.
    """
    w = cfg.width - 2 * cfg.margin
    h = cfg.height - 2 * cfg.margin
    r = min(cfg.corner_radius, w / 2, h / 2)
    ox = cfg.margin
    oy = cfg.margin
    mid_x = cfg.width / 2
    mid_y = cfg.height / 2

    half_top = w / 2 - r
    corner_arc = 0.5 * math.pi * r
    half_right = h / 2 - r
    total = half_top + corner_arc + half_right

    # Determine how many rosettes go in this quadrant.
    # rosettes_per_side covers the full top edge; half belong to this quadrant
    # plus we add half the short-side rosettes for the right edge.
    # For simplicity: distribute N rosettes evenly along the quadrant path.
    aspect = cfg.width / cfg.height
    n_top_half = max(1, cfg.rosettes_per_side // 2)
    n_right_half = max(1, round(n_top_half / aspect))
    n_total = n_top_half + n_right_half + 1  # +1 for corner

    positions: list[Tuple[float, float, float]] = []

    for i in range(n_total):
        d = (i / max(n_total - 1, 1)) * total

        # Top edge segment
        if d <= half_top:
            frac = d / half_top if half_top > 0 else 0
            x = mid_x + frac * half_top
            y = oy
            angle = 0.0
            positions.append((x, y, angle))
            continue

        d2 = d - half_top

        # Corner arc segment
        if d2 <= corner_arc:
            arc_angle = -math.pi / 2 + (d2 / corner_arc) * (math.pi / 2)
            ccx = ox + w - r
            ccy = oy + r
            x = ccx + r * math.cos(arc_angle)
            y = ccy + r * math.sin(arc_angle)
            angle = arc_angle + math.pi / 2
            positions.append((x, y, angle))
            continue

        d3 = d2 - corner_arc

        # Right edge segment
        frac = d3 / half_right if half_right > 0 else 0
        x = ox + w
        y = oy + r + frac * half_right
        angle = math.pi / 2
        positions.append((x, y, angle))

    return positions


def generate_spirograph(cfg: SpirographConfig | None = None) -> str:
    """
    Generate an SVG string containing a rectangular border decorated with
    hypotrochoid (spirograph) rosette motifs.

    Produces perfect horizontal and vertical symmetry by generating rosette
    positions for one quadrant and mirroring them four ways.
    """
    if cfg is None:
        cfg = SpirographConfig()

    cx = cfg.width / 2
    cy = cfg.height / 2

    qtr_positions = _sample_border_positions_quadrant(cfg)

    def mirror_x(pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
        return (2 * cx - pos[0], pos[1], math.pi - pos[2])

    def mirror_y(pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
        return (pos[0], 2 * cy - pos[1], -pos[2])

    def mirror_xy(pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
        return (2 * cx - pos[0], 2 * cy - pos[1], math.pi + pos[2])

    # Build full set of rosette positions from quadrant via mirroring.
    # Quadrant covers top-center -> right-center (clockwise).
    # seg1 (top-left half):  mirror-x of quadrant, reversed
    # seg2 (top-right half): quadrant as-is
    # seg3 (bottom-right):   mirror-y of quadrant, reversed
    # seg4 (bottom-left):    mirror-xy of quadrant
    all_positions: list[Tuple[float, float, float]] = []

    seg1 = [mirror_x(p) for p in reversed(qtr_positions)]
    seg2 = list(qtr_positions)
    seg3 = [mirror_y(p) for p in reversed(qtr_positions)]
    seg4 = [mirror_xy(p) for p in qtr_positions]

    all_positions = seg1 + seg2 + seg3 + seg4

    # De-duplicate positions that are very close (at symmetry meeting points)
    deduped: list[Tuple[float, float, float]] = []
    for pos in all_positions:
        duplicate = False
        for existing in deduped:
            if (abs(pos[0] - existing[0]) < 0.5 and
                    abs(pos[1] - existing[1]) < 0.5):
                duplicate = True
                break
        if not duplicate:
            deduped.append(pos)

    # Generate SVG paths for each rosette at each position
    paths_svg: list[str] = []

    # Normalisation: compute the raw hypotrochoid extent to scale to rosette_size
    raw_points = _hypotrochoid(cfg.R, cfg.r, cfg.d, cfg.num_points)
    max_extent = max(
        max(abs(x) for x, _ in raw_points),
        max(abs(y) for _, y in raw_points),
    ) if raw_points else 1.0
    scale = cfg.rosette_size / max_extent if max_extent > 0 else 1.0

    for layer_idx in range(cfg.num_layers):
        color = cfg.colors[layer_idx % len(cfg.colors)]
        layer_r = cfg.r + layer_idx * cfg.layer_r_step
        layer_rotation = layer_idx * cfg.layer_phase_step

        for px, py, border_angle in deduped:
            pts = _hypotrochoid(
                cfg.R, layer_r, cfg.d,
                cfg.num_points,
                rotation=border_angle + layer_rotation,
            )

            # Recompute scale for this layer variant
            layer_max = max(
                max(abs(x) for x, _ in pts),
                max(abs(y) for _, y in pts),
            ) if pts else 1.0
            layer_scale = cfg.rosette_size / layer_max if layer_max > 0 else 1.0

            translated = [
                (px + x * layer_scale, py + y * layer_scale)
                for x, y in pts
            ]

            d_attr = _points_to_svg_path(translated)
            paths_svg.append(
                f'  <path d="{d_attr}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" '
                f'stroke-linejoin="round" opacity="0.80"/>'
            )

    # Assemble SVG
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
    # Default green rosette border
    cfg = SpirographConfig()
    svg = generate_spirograph(cfg)
    with open("spirograph_border.svg", "w") as f:
        f.write(svg)
    print("Wrote spirograph_border.svg")

    # Alternate: dense blue security rosette border
    cfg2 = SpirographConfig(
        rosettes_per_side=8,
        rosette_size=22.0,
        R=7.0,
        r=4.0,
        d=6.0,
        num_points=800,
        num_layers=4,
        layer_r_step=0.2,
        layer_phase_step=0.3,
        stroke_width=0.35,
        colors=["#1a3a6e", "#2a5090", "#1a3a6e", "#2a5090"],
        corner_radius=16.0,
    )
    svg2 = generate_spirograph(cfg2)
    with open("spirograph_border_blue.svg", "w") as f:
        f.write(svg2)
    print("Wrote spirograph_border_blue.svg")
