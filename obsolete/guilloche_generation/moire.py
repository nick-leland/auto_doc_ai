import math
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class MoireConfig:
    width: int = 800                          # outer SVG width (px)
    height: int = 1040                        # outer SVG height (px)
    margin: float = 20.0                      # offset from SVG edge to outer border edge
    border_thickness: float = 48.0            # thickness of the border band
    colors: list[str] = field(default_factory=lambda: ["#1a4a2e", "#2a6e3f", "#1a5c30"])
    stroke_width: float = 0.35               # thin lines produce better moire
    num_line_sets: int = 3                    # overlapping line sets
    lines_per_set: int = 120                  # lines in each set
    angle_offset: float = 3.0                # degrees between successive sets
    line_spacing: float = 2.4                # spacing between parallel lines (px)
    corner_radius: float = 12.0              # rounded corners on the border rect
    background_color: str = "none"


def _sample_quadrant(cfg: MoireConfig) -> list[Tuple[float, float, float, float]]:
    """
    Sample points for the top-right quadrant of the border centerline.
    Path: top-center -> top-right corner arc -> right-center.
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

    # Use enough samples for smooth curves
    n = 400
    points: list[Tuple[float, float, float, float]] = []

    for i in range(n):
        d = (i / max(n - 1, 1)) * total

        if d <= half_top:
            frac = d / half_top if half_top > 0 else 0
            x = mid_x + frac * half_top
            y = oy
            points.append((x, y, 0.0, 1.0))
            continue

        d2 = d - half_top

        if d2 <= corner_arc:
            angle = -math.pi / 2 + (d2 / corner_arc) * (math.pi / 2)
            ccx = ox + w - r
            ccy = oy + r
            x = ccx + r * math.cos(angle)
            y = ccy + r * math.sin(angle)
            points.append((x, y, -math.cos(angle), -math.sin(angle)))
            continue

        d3 = d2 - corner_arc
        frac = d3 / half_right if half_right > 0 else 0
        x = ox + w
        y = oy + r + frac * half_right
        points.append((x, y, -1.0, 0.0))

    return points


def _build_full_border_centerline(cfg: MoireConfig) -> list[Tuple[float, float, float, float]]:
    """
    Build the full closed border centerline by mirroring the quadrant.
    Returns list of (x, y, nx, ny) going clockwise around the full border.
    """
    cx = cfg.width / 2
    cy = cfg.height / 2
    qtr = _sample_quadrant(cfg)

    # seg1: left-center -> top-center (mirror-x of quadrant, reversed)
    seg1 = [(2 * cx - x, y, -nx, ny) for x, y, nx, ny in reversed(qtr)]
    # seg2: top-center -> right-center (quadrant as-is)
    seg2 = list(qtr)
    # seg3: right-center -> bottom-center (mirror-y of quadrant)
    seg3 = [(x, 2 * cy - y, nx, -ny) for x, y, nx, ny in qtr]
    # seg4: bottom-center -> left-center (mirror-xy of quadrant, reversed)
    seg4 = [(2 * cx - x, 2 * cy - y, -nx, -ny) for x, y, nx, ny in reversed(qtr)]

    return seg1 + seg2 + seg3 + seg4


def _generate_line_set(
    centerline: list[Tuple[float, float, float, float]],
    cfg: MoireConfig,
    set_idx: int,
) -> list[str]:
    """
    Generate one set of fine lines that follow the border band.
    Each line is offset perpendicular to the centerline. The angle_offset
    causes a slight angular oscillation along the path, creating the moire
    interference when overlapped with other sets.
    """
    n_pts = len(centerline)
    color = cfg.colors[set_idx % len(cfg.colors)]
    angle_rad = math.radians(cfg.angle_offset * set_idx)

    # The lines span from -border_thickness/2 to +border_thickness/2
    half = cfg.border_thickness / 2
    paths: list[str] = []

    for li in range(cfg.lines_per_set):
        # Base perpendicular offset for this line
        t_line = (li / max(cfg.lines_per_set - 1, 1)) - 0.5  # range [-0.5, 0.5]
        base_offset = t_line * cfg.border_thickness

        pts: list[Tuple[float, float]] = []
        for pi in range(0, n_pts, 2):  # skip every other point for performance
            bx, by, nx, ny = centerline[pi]
            # Parameter along the path
            s = pi / n_pts

            # Angular modulation: slight sinusoidal wobble whose frequency
            # differs per set (via angle_rad). This is what creates the moire.
            freq = 40.0 + set_idx * 7.0
            wobble = cfg.line_spacing * math.sin(
                2 * math.pi * freq * s + angle_rad * 15.0
            )

            offset = base_offset + wobble
            # Clamp to border band
            offset = max(-half, min(half, offset))

            # Also rotate the normal slightly per set to get crossing angles
            cos_a = math.cos(angle_rad * 0.3)
            sin_a = math.sin(angle_rad * 0.3)
            rnx = nx * cos_a - ny * sin_a
            rny = nx * sin_a + ny * cos_a

            x = bx + rnx * offset
            y = by + rny * offset
            pts.append((x, y))

        if len(pts) < 2:
            continue

        d_parts = [f"M {pts[0][0]:.2f},{pts[0][1]:.2f}"]
        for x, y in pts[1:]:
            d_parts.append(f"L {x:.2f},{y:.2f}")
        d_str = " ".join(d_parts)

        opacity = 0.55 + 0.25 * abs(t_line)
        paths.append(
            f'  <path d="{d_str}" fill="none" stroke="{color}" '
            f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" '
            f'opacity="{opacity:.2f}"/>'
        )

    return paths


def generate_moire(cfg: MoireConfig | None = None) -> str:
    """
    Generate an SVG string containing a rectangular moire interference
    pattern border. Produces horizontal and vertical symmetry by generating
    one quadrant of the border centerline and mirroring it, then overlaying
    multiple sets of fine lines at slightly different angles.
    """
    if cfg is None:
        cfg = MoireConfig()

    centerline = _build_full_border_centerline(cfg)

    # Build a clip path for the border band (rounded rect with hole)
    outer_r = cfg.corner_radius
    inner_margin = cfg.margin + cfg.border_thickness
    inner_w = cfg.width - 2 * inner_margin
    inner_h = cfg.height - 2 * inner_margin
    inner_r = max(0, cfg.corner_radius - cfg.border_thickness)

    clip_id = "moire-clip"

    all_paths: list[str] = []
    for si in range(cfg.num_line_sets):
        all_paths.extend(_generate_line_set(centerline, cfg, si))

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

    # Clip path: outer rect minus inner rect to restrict lines to the border band
    svg_parts.append("  <defs>")
    svg_parts.append(f'    <clipPath id="{clip_id}">')
    # Outer rounded rect (filled)
    svg_parts.append(
        f'      <rect x="{cfg.margin}" y="{cfg.margin}" '
        f'width="{cfg.width - 2 * cfg.margin}" height="{cfg.height - 2 * cfg.margin}" '
        f'rx="{outer_r}" ry="{outer_r}"/>'
    )
    svg_parts.append(f"    </clipPath>")
    svg_parts.append("  </defs>")

    # Group with clip, then punch out the inner area with a white rect on top
    svg_parts.append(f'  <g clip-path="url(#{clip_id})">')
    svg_parts.extend(all_paths)
    svg_parts.append("  </g>")

    # Punch out the interior so only the border band remains
    # Use a rect matching the inner area to cover the interior lines
    if inner_w > 0 and inner_h > 0:
        fill = cfg.background_color if cfg.background_color != "none" else "white"
        svg_parts.append(
            f'  <rect x="{inner_margin}" y="{inner_margin}" '
            f'width="{inner_w}" height="{inner_h}" '
            f'rx="{inner_r}" ry="{inner_r}" fill="{fill}"/>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


if __name__ == "__main__":
    cfg = MoireConfig()
    svg = generate_moire(cfg)
    with open("moire_border.svg", "w") as f:
        f.write(svg)
    print("Wrote moire_border.svg")
