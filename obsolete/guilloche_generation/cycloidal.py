import math
from dataclasses import dataclass, field
from typing import Tuple, List


@dataclass
class CycloidalConfig:
    width: int = 800                            # outer SVG width (px)
    height: int = 1040                          # outer SVG height (px)
    margin: float = 20.0                        # offset from SVG edge to border band outer edge
    border_thickness: float = 40.0              # thickness of the border band
    colors: list[str] = field(default_factory=lambda: ["#2a6e3f", "#1a5c30", "#3a7e4f"])
    stroke_width: float = 0.5
    num_tangent_lines: int = 200                # tangent lines per quadrant side-segment
    wave_frequency: float = 6.0                 # number of wave cycles along each side
    wave_amplitude: float = 0.85                # amplitude as fraction of border_thickness / 2
    tangent_length: float = 1.8                 # length of each tangent line relative to one wave period
    corner_radius: float = 12.0                 # rounded corners
    background_color: str = "none"


def _sample_quadrant_centerline(cfg: CycloidalConfig) -> List[Tuple[float, float, float, float]]:
    """
    Sample the centerline of the border band for the top-right quadrant.
    Path: top-center -> top-right corner arc -> right-edge midpoint.
    Returns list of (x, y, nx, ny) where (nx, ny) is the inward normal.
    """
    w = cfg.width - 2 * cfg.margin
    h = cfg.height - 2 * cfg.margin
    r = min(cfg.corner_radius, w / 2, h / 2)
    ox = cfg.margin
    oy = cfg.margin
    mid_x = cfg.width / 2

    # The centerline of the band sits at margin + border_thickness / 2
    # But we sample the geometric border path and use normals to place waves.
    half_top = w / 2 - r
    corner_arc = 0.5 * math.pi * r
    half_right = h / 2 - r
    total = half_top + corner_arc + half_right

    # We need fine sampling for the centerline to compute tangent directions
    n = 2000
    points: List[Tuple[float, float, float, float]] = []

    for i in range(n + 1):
        d = (i / n) * total

        if d <= half_top:
            frac = d / half_top if half_top > 0 else 0
            x = mid_x + frac * half_top
            y = oy
            points.append((x, y, 0.0, 1.0))
        elif d <= half_top + corner_arc:
            d2 = d - half_top
            angle = -math.pi / 2 + (d2 / corner_arc) * (math.pi / 2)
            ccx = ox + w - r
            ccy = oy + r
            x = ccx + r * math.cos(angle)
            y = ccy + r * math.sin(angle)
            points.append((x, y, -math.cos(angle), -math.sin(angle)))
        else:
            d3 = d - half_top - corner_arc
            frac = d3 / half_right if half_right > 0 else 0
            x = ox + w
            y = oy + r + frac * half_right
            points.append((x, y, -1.0, 0.0))

    return points


def _compute_arc_lengths(points: List[Tuple[float, float, float, float]]) -> List[float]:
    """Compute cumulative arc length for a list of centerline points."""
    lengths = [0.0]
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        lengths.append(lengths[-1] + math.sqrt(dx * dx + dy * dy))
    return lengths


def _lerp_on_centerline(
    t_param: float,
    points: List[Tuple[float, float, float, float]],
    arc_lengths: List[float],
) -> Tuple[float, float, float, float, float, float]:
    """
    Given a parameter t_param in [0, total_arc_length], interpolate position,
    normal, and tangent direction on the centerline.
    Returns (x, y, nx, ny, tx, ty).
    """
    total = arc_lengths[-1]
    t_param = max(0.0, min(t_param, total))

    # Binary search for segment
    lo, hi = 0, len(arc_lengths) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if arc_lengths[mid] <= t_param:
            lo = mid
        else:
            hi = mid

    seg_len = arc_lengths[hi] - arc_lengths[lo]
    frac = (t_param - arc_lengths[lo]) / seg_len if seg_len > 0 else 0.0

    x = points[lo][0] + frac * (points[hi][0] - points[lo][0])
    y = points[lo][1] + frac * (points[hi][1] - points[lo][1])
    nx = points[lo][2] + frac * (points[hi][2] - points[lo][2])
    ny = points[lo][3] + frac * (points[hi][3] - points[lo][3])

    # Tangent direction (along the centerline)
    tx = points[hi][0] - points[lo][0]
    ty = points[hi][1] - points[lo][1]
    tlen = math.sqrt(tx * tx + ty * ty)
    if tlen > 0:
        tx /= tlen
        ty /= tlen

    # Normalize normal
    nlen = math.sqrt(nx * nx + ny * ny)
    if nlen > 0:
        nx /= nlen
        ny /= nlen

    return x, y, nx, ny, tx, ty


def _generate_tangent_lines_quadrant(
    cfg: CycloidalConfig,
) -> List[Tuple[float, float, float, float, str]]:
    """
    Generate tangent-line segments for one quadrant.
    Each tangent line is tangent to a sinusoidal wave that runs along the
    border centerline. The envelope of these tangent lines produces the
    classic diamond/eye/spindle motifs.

    Returns list of (x1, y1, x2, y2, color).
    """
    centerline = _sample_quadrant_centerline(cfg)
    arc_lengths = _compute_arc_lengths(centerline)
    total_len = arc_lengths[-1]

    half_band = cfg.border_thickness / 2
    amp = half_band * cfg.wave_amplitude

    lines: List[Tuple[float, float, float, float, str]] = []

    # We generate multiple color layers with slight phase offsets
    num_colors = len(cfg.colors)

    for color_idx in range(num_colors):
        color = cfg.colors[color_idx]
        phase_offset = (color_idx / num_colors) * 2 * math.pi / cfg.wave_frequency

        for i in range(cfg.num_tangent_lines):
            # Parameter along the border centerline
            t = (i / cfg.num_tangent_lines) * total_len
            # Small dt for derivative
            dt = total_len / (cfg.num_tangent_lines * 100)

            # Position on the centerline at parameter t
            x, y, nx, ny, tx, ty = _lerp_on_centerline(t, centerline, arc_lengths)

            # The wave function: displacement perpendicular to centerline
            # w(t) = amp * sin(2*pi*freq * t / total_len + phase)
            wave_phase = 2 * math.pi * cfg.wave_frequency * t / total_len + phase_offset
            wave_val = amp * math.sin(wave_phase)

            # Derivative of wave w.r.t. arc-length parameter
            wave_deriv = amp * (2 * math.pi * cfg.wave_frequency / total_len) * math.cos(wave_phase)

            # Point on the wave curve (centerline + normal displacement)
            wx = x + nx * wave_val
            wy = y + ny * wave_val

            # Tangent direction of the wave curve:
            # The wave curve point = centerline(t) + normal(t) * w(t)
            # Its tangent = tangent_centerline + normal * w'(t)
            # (ignoring normal derivative for simplicity — valid for gentle curves)
            wave_tx = tx + nx * wave_deriv
            wave_ty = ty + ny * wave_deriv
            wt_len = math.sqrt(wave_tx * wave_tx + wave_ty * wave_ty)
            if wt_len > 0:
                wave_tx /= wt_len
                wave_ty /= wt_len

            # Tangent line extends in both directions from the wave point
            half_t = (total_len / cfg.wave_frequency) * cfg.tangent_length / 2
            # Scale tangent length to create good envelope coverage
            extent = half_t * 0.08

            x1 = wx - wave_tx * extent
            y1 = wy - wave_ty * extent
            x2 = wx + wave_tx * extent
            y2 = wy + wave_ty * extent

            lines.append((x1, y1, x2, y2, color))

    return lines


def generate_cycloidal(cfg: CycloidalConfig | None = None) -> str:
    """
    Generate an SVG string containing a cycloidal envelope border pattern.
    Produces perfect horizontal and vertical symmetry by generating tangent
    lines for one quadrant and mirroring them four ways.
    """
    if cfg is None:
        cfg = CycloidalConfig()

    cx = cfg.width / 2
    cy = cfg.height / 2

    quadrant_lines = _generate_tangent_lines_quadrant(cfg)

    def mirror_line(
        x1: float, y1: float, x2: float, y2: float
    ) -> List[Tuple[float, float, float, float]]:
        """Return the four mirrored versions of a line segment."""
        # Original (top-right quadrant)
        segments = [(x1, y1, x2, y2)]
        # Mirror horizontally (top-left)
        segments.append((2 * cx - x1, y1, 2 * cx - x2, y2))
        # Mirror vertically (bottom-right)
        segments.append((x1, 2 * cy - y1, x2, 2 * cy - y2))
        # Mirror both (bottom-left)
        segments.append((2 * cx - x1, 2 * cy - y1, 2 * cx - x2, 2 * cy - y2))
        return segments

    svg_lines: List[str] = []

    for x1, y1, x2, y2, color in quadrant_lines:
        for mx1, my1, mx2, my2 in mirror_line(x1, y1, x2, y2):
            svg_lines.append(
                f'  <line x1="{mx1:.2f}" y1="{my1:.2f}" '
                f'x2="{mx2:.2f}" y2="{my2:.2f}" '
                f'stroke="{color}" stroke-width="{cfg.stroke_width}" '
                f'stroke-linecap="round" opacity="0.8"/>'
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

    svg_parts.extend(svg_lines)
    svg_parts.append("</svg>")

    return "\n".join(svg_parts)


if __name__ == "__main__":
    # Default green currency-style pattern
    cfg = CycloidalConfig()
    svg = generate_cycloidal(cfg)
    with open("cycloidal_border.svg", "w") as f:
        f.write(svg)
    print("Wrote cycloidal_border.svg")
