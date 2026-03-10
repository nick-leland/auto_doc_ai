"""
Full-page SVG pattern generators.

Each generator fills an entire page (width x height) with elaborate ornate
line work — the kind you see on checks, currency, vehicle titles, and
certificates.  Every pattern should be intricate and detailed enough that:

  - At full opacity on a border, it's immediately recognizable as a
    security/ornamental pattern.
  - At very low opacity over a matching background, it's barely noticeable
    unless you're really focusing — the anti-copy watermark effect.

All patterns are pure SVG path strings (no external dependencies) and are
designed to be randomizable.
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple


class PatternType(str, Enum):
    GUILLOCHE_DIAMOND = "guilloche_diamond"
    SPIROGRAPH_LATTICE = "spirograph_lattice"
    LISSAJOUS_MESH = "lissajous_mesh"
    GUILLOCHE_ROSETTE = "guilloche_rosette"
    CROSSHATCH_WEAVE = "crosshatch_weave"
    EPITROCHOID_LATTICE = "epitrochoid_lattice"
    CONCENTRIC_LATHE = "concentric_lathe"
    MOIRE_RADIAL = "moire_radial"
    WOVEN_RIBBON = "woven_ribbon"
    WAVE_FIELD = "wave_field"
    HEX_ROSETTE_GRID = "hex_rosette_grid"
    CONTOUR_ENGRAVING = "contour_engraving"
    BASKET_WEAVE = "basket_weave"
    LATHE_RINGS = "lathe_rings"
    SCROLL_CHAIN = "scroll_chain"


@dataclass
class FullPageConfig:
    width: int = 2250
    height: int = 3000
    pattern_type: PatternType = PatternType.GUILLOCHE_DIAMOND
    colors: list[str] = field(default_factory=lambda: ["#2a6e3f", "#1a5c30"])
    stroke_width: float = 0.7
    seed: int | None = None

    # Guilloche diamond — interlocking wave sets at multiple angles
    guil_num_sets: int = 4
    guil_waves_per_set: int = 35
    guil_freq: float = 10.0
    guil_amplitude: float = 10.0
    guil_angle_spread: float = 45.0     # degrees between wave set angles

    # Spirograph lattice
    spiro_R: float = 5.0
    spiro_r: float = 3.0
    spiro_d: float = 5.0
    spiro_count_x: int = 4
    spiro_count_y: int = 5
    spiro_size: float = 180.0
    spiro_num_points: int = 300
    spiro_layers: int = 2
    spiro_layer_r_step: float = 0.15
    spiro_layer_phase: float = 0.4

    # Lissajous mesh (grid of Lissajous knots)
    liss_freq_a: float = 5.0
    liss_freq_b: float = 3.0
    liss_num_curves: int = 3          # curves per cell
    liss_amplitude: float = 0.46

    # Guilloche rosette — overlapping circular guilloche patterns
    rosette_count_x: int = 3
    rosette_count_y: int = 4
    rosette_radius: float = 200.0
    rosette_num_rings: int = 30
    rosette_wave_freq: int = 8
    rosette_wave_amp: float = 0.15

    # Crosshatch weave
    crosshatch_spacing: float = 14.0
    crosshatch_angles: list[float] = field(default_factory=lambda: [0.0, 60.0, 120.0])
    crosshatch_wave_amp: float = 5.0
    crosshatch_wave_freq: float = 6.0

    # Epitrochoid lattice — outer-rolling-circle curves on a grid
    epi_R: float = 3.0
    epi_r: float = 1.0
    epi_d: float = 2.5
    epi_count_x: int = 3
    epi_count_y: int = 4
    epi_size: float = 210.0
    epi_num_points: int = 400
    epi_layers: int = 2
    epi_layer_r_step: float = 0.4
    epi_layer_phase: float = 0.6

    # Concentric lathe — nested ellipse rings like engraved currency
    lathe_num_rings: int = 50
    lathe_centers: int = 3            # number of ellipse center points
    lathe_eccentricity: float = 0.6   # how elliptical (0=circle, 1=flat)
    lathe_wobble_amp: float = 3.0     # fine ripple on each ring
    lathe_wobble_freq: int = 20       # ripple frequency

    # Moiré radial — radial line bursts from offset centers
    moire_num_centers: int = 7
    moire_rays_per_center: int = 120
    moire_ray_length: float = 0.55    # fraction of page diagonal
    moire_curve_amp: float = 20.0     # subtle curve on each ray

    # Woven ribbon — interlocking sine bands
    ribbon_count_h: int = 20          # horizontal ribbons
    ribbon_count_v: int = 15          # vertical ribbons
    ribbon_amplitude: float = 18.0    # wave amplitude
    ribbon_freq: float = 5.0          # wave cycles across page
    ribbon_width: float = 1.5         # visual width of each ribbon (stroke)

    # Wave field — flowing field lines with varying density
    wfield_num_lines: int = 140
    wfield_num_sets: int = 3
    wfield_freq: float = 6.0
    wfield_amplitude: float = 15.0
    wfield_angle_spread: float = 20.0

    # Hex rosette grid — hexagonal tiling with small rosettes in each cell
    hex_cell_size: float = 60.0
    hex_rosette_petals: int = 6
    hex_rosette_rings: int = 3
    hex_border_weight: float = 0.5    # hex cell border stroke weight

    # Contour engraving — field-following tightly spaced curves like banknotes
    engrave_num_lines: int = 90
    engrave_num_sources: int = 5
    engrave_curve_amp: float = 30.0

    # Basket weave — two families of arcs at opposing angles
    basket_lines_per_set: int = 60
    basket_freq: float = 6.0
    basket_amplitude: float = 12.0
    basket_angle: float = 35.0

    # Lathe rings — nested deformed ellipses from offset centers
    lathe_ring_num_centers: int = 5
    lathe_ring_rings_per: int = 25
    lathe_ring_deform_freq: int = 6
    lathe_ring_deform_amp: float = 0.12

    # Scroll chain — interlocking sine-chain rows with varying phase
    scroll_num_h: int = 40
    scroll_num_v: int = 30
    scroll_freq: float = 8.0
    scroll_amplitude: float = 15.0
    scroll_phase_drift: float = 0.3


def _seeded_rng(seed: int | None) -> random.Random:
    return random.Random(seed)


# ---------------------------------------------------------------------------
# Pattern: Guilloche Diamond — interlocking wave sets creating diamonds
# ---------------------------------------------------------------------------

def _gen_guilloche_diamond(cfg: FullPageConfig) -> list[str]:
    """
    Multiple families of sinusoidal waves at different angles with paired
    envelope modulation. Where sets cross they create a dense diamond/moiré
    interference — the classic guilloche look on checks and currency.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)
    diagonal = math.sqrt(cfg.width ** 2 + cfg.height ** 2)
    num_samples = max(600, int(diagonal * 0.9))

    for set_idx in range(cfg.guil_num_sets):
        angle_deg = (set_idx - (cfg.guil_num_sets - 1) / 2) * cfg.guil_angle_spread
        angle_rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
        color = cfg.colors[set_idx % len(cfg.colors)]

        spacing = cfg.height / (cfg.guil_waves_per_set + 1)

        for wi in range(cfg.guil_waves_per_set):
            offset = spacing * (wi + 1) - cfg.height / 2
            freq = cfg.guil_freq + wi * 0.06
            amp = cfg.guil_amplitude * (0.9 + 0.2 * rng.random())
            phase = wi * 0.15 + rng.uniform(-0.15, 0.15)

            # Envelope that pinches the wave periodically → diamond lozenges
            env_freq = cfg.guil_freq * 0.3
            env_phase = set_idx * 1.2 + wi * 0.05

            # Two harmonics for richer line shape
            h2_amp = amp * 0.18
            h2_freq = freq * 2.0
            h3_amp = amp * 0.07
            h3_freq = freq * 3.0

            points = []
            for s in range(num_samples):
                t = (s / (num_samples - 1)) * diagonal - diagonal / 2
                # Envelope modulation creates the diamond pinch points
                envelope = 0.55 + 0.45 * math.cos(2 * math.pi * env_freq * t / diagonal + env_phase)
                wave = amp * math.sin(2 * math.pi * freq * t / diagonal + phase)
                wave += h2_amp * math.sin(2 * math.pi * h2_freq * t / diagonal + phase * 1.5)
                wave += h3_amp * math.sin(2 * math.pi * h3_freq * t / diagonal + phase * 2.3)
                wave *= envelope
                bx = cfg.width / 2 + t * cos_a - offset * sin_a + wave * (-sin_a)
                by = cfg.height / 2 + t * sin_a + offset * cos_a + wave * cos_a
                points.append(f"{bx:.1f},{by:.1f}")

            d = "M " + " L ".join(points)
            paths.append(
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="0.45"/>'
            )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Spirograph Lattice (grid of hypotrochoid rosettes)
# ---------------------------------------------------------------------------

def _hypotrochoid(R: float, r: float, d: float,
                  num_points: int, rotation: float = 0.0) -> list[Tuple[float, float]]:
    try:
        Ri, ri = round(R * 1000), round(r * 1000)
        g = math.gcd(Ri, ri)
        periods = ri // g
    except Exception:
        periods = 20
    periods = min(periods, 60)

    t_max = 2 * math.pi * periods
    diff = R - r
    ratio = diff / r if r != 0 else 0
    cos_rot, sin_rot = math.cos(rotation), math.sin(rotation)

    points = []
    for i in range(num_points):
        t = (i / num_points) * t_max
        x = diff * math.cos(t) + d * math.cos(ratio * t)
        y = diff * math.sin(t) - d * math.sin(ratio * t)
        rx = x * cos_rot - y * sin_rot
        ry = x * sin_rot + y * cos_rot
        points.append((rx, ry))
    return points


def _gen_spirograph_lattice(cfg: FullPageConfig) -> list[str]:
    """Large spirograph rosettes on an even grid lattice."""
    paths = []
    rng = _seeded_rng(cfg.seed)

    spacing_x = cfg.width / cfg.spiro_count_x
    spacing_y = cfg.height / cfg.spiro_count_y

    for row in range(cfg.spiro_count_y):
        for col in range(cfg.spiro_count_x):
            cx = spacing_x * (col + 0.5)
            cy = spacing_y * (row + 0.5)

            for layer in range(cfg.spiro_layers):
                color = cfg.colors[(row + col + layer) % len(cfg.colors)]
                layer_r = cfg.spiro_r + layer * cfg.spiro_layer_r_step
                rotation = layer * cfg.spiro_layer_phase + rng.uniform(-0.2, 0.2)

                pts = _hypotrochoid(cfg.spiro_R, layer_r, cfg.spiro_d,
                                    cfg.spiro_num_points, rotation)
                lmax = max(max(abs(x) for x, _ in pts), max(abs(y) for _, y in pts)) if pts else 1.0
                scale = cfg.spiro_size / lmax if lmax > 0 else 1.0

                coords = [f"{cx + x * scale:.1f},{cy + y * scale:.1f}" for x, y in pts]
                d = "M " + " L ".join(coords) + " Z"
                paths.append(
                    f'<path d="{d}" fill="none" stroke="{color}" '
                    f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="0.55"/>'
                )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Lissajous Mesh
# ---------------------------------------------------------------------------

def _gen_lissajous_mesh(cfg: FullPageConfig) -> list[str]:
    """
    Grid of Lissajous figures — each cell has a compact Lissajous knot with
    multiple frequency layers, giving uniform page coverage and intricate
    detail at every point.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)
    num_samples = 500

    # Grid layout for even coverage — radius overshoots cells for overlap
    cols, rows = 5, 6
    cell_w = cfg.width / cols
    cell_h = cfg.height / rows
    radius = min(cell_w, cell_h) * 0.58

    for row in range(rows):
        for col in range(cols):
            cx = cell_w * (col + 0.5)
            cy = cell_h * (row + 0.5)

            for curve_i in range(cfg.liss_num_curves):
                color = cfg.colors[(row + col + curve_i) % len(cfg.colors)]
                phase = curve_i * (2 * math.pi / cfg.liss_num_curves) + rng.uniform(-0.3, 0.3)
                freq_a = cfg.liss_freq_a + curve_i * 0.7 + rng.uniform(-0.2, 0.2)
                freq_b = cfg.liss_freq_b + curve_i * 0.5 + rng.uniform(-0.2, 0.2)

                points = []
                t_max = 2 * math.pi * max(int(freq_a), int(freq_b), 4)
                for s in range(num_samples):
                    t = (s / (num_samples - 1)) * t_max
                    x = cx + radius * math.sin(freq_a * t + phase)
                    y = cy + radius * math.sin(freq_b * t)
                    points.append(f"{x:.1f},{y:.1f}")

                d = "M " + " L ".join(points)
                opacity = 0.18 + 0.08 * (curve_i % 3)
                paths.append(
                    f'<path d="{d}" fill="none" stroke="{color}" '
                    f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
                )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Mandala Lattice — elaborate multi-ring rose patterns on a grid
# ---------------------------------------------------------------------------

def _gen_guilloche_rosette(cfg: FullPageConfig) -> list[str]:
    """
    Tiled grid of large circular guilloche rosettes — each is a family of
    concentric rings with sinusoidal radial deformation, like the large
    security rosettes on Euro banknotes. Overlapping rosettes create dense
    moiré interference in the gaps.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)

    spacing_x = cfg.width / cfg.rosette_count_x
    spacing_y = cfg.height / cfg.rosette_count_y
    num_samples = 360

    for row in range(-1, cfg.rosette_count_y + 1):
        for col in range(-1, cfg.rosette_count_x + 1):
            cx = spacing_x * (col + 0.5)
            cy = spacing_y * (row + 0.5)

            # Skip if too far off page
            if cx < -cfg.rosette_radius or cx > cfg.width + cfg.rosette_radius:
                continue
            if cy < -cfg.rosette_radius or cy > cfg.height + cfg.rosette_radius:
                continue

            wave_freq = cfg.rosette_wave_freq + rng.randint(-1, 1)
            phase_offset = rng.uniform(0, 2 * math.pi)

            for ring in range(cfg.rosette_num_rings):
                t = (ring + 1) / cfg.rosette_num_rings
                base_r = cfg.rosette_radius * t
                color = cfg.colors[(ring + row + col) % len(cfg.colors)]
                # Wave amplitude increases with radius for richer outer detail
                amp = cfg.rosette_wave_amp * base_r * (0.6 + 0.4 * t)
                freq = wave_freq + ring % 3
                phase = phase_offset + ring * 0.35

                points = []
                for s in range(num_samples):
                    theta = (s / num_samples) * 2 * math.pi
                    r = base_r + amp * math.sin(freq * theta + phase)
                    # Second harmonic for complexity
                    r += amp * 0.3 * math.sin((freq * 2 + 1) * theta + phase * 1.7)
                    x = cx + r * math.cos(theta)
                    y = cy + r * math.sin(theta)
                    points.append(f"{x:.1f},{y:.1f}")

                d = "M " + " L ".join(points) + " Z"
                opacity = 0.20 + 0.15 * t
                paths.append(
                    f'<path d="{d}" fill="none" stroke="{color}" '
                    f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
                )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Crosshatch Weave — angled wavy lines
# ---------------------------------------------------------------------------

def _gen_crosshatch_weave(cfg: FullPageConfig) -> list[str]:
    """Wavy lines at multiple angles creating a woven texture."""
    paths = []
    rng = _seeded_rng(cfg.seed)
    diagonal = math.sqrt(cfg.width ** 2 + cfg.height ** 2)
    num_samples = 300

    for angle_idx, angle_deg in enumerate(cfg.crosshatch_angles):
        angle_rad = math.radians(angle_deg)
        color = cfg.colors[angle_idx % len(cfg.colors)]
        cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)

        num_lines = int(diagonal / cfg.crosshatch_spacing)
        for li in range(num_lines):
            offset = (li - num_lines / 2) * cfg.crosshatch_spacing
            phase = rng.uniform(0, 2 * math.pi)
            freq = cfg.crosshatch_wave_freq + rng.uniform(-0.5, 0.5)

            points = []
            line_len = diagonal
            for s in range(num_samples):
                t = (s / (num_samples - 1)) * line_len - line_len / 2
                bx = cfg.width / 2 + t * cos_a - offset * sin_a
                by = cfg.height / 2 + t * sin_a + offset * cos_a
                wave = cfg.crosshatch_wave_amp * math.sin(
                    2 * math.pi * freq * t / diagonal + phase
                )
                wave += (cfg.crosshatch_wave_amp * 0.3) * math.sin(
                    2 * math.pi * freq * 2.7 * t / diagonal + phase * 1.3
                )
                bx += wave * (-sin_a)
                by += wave * cos_a
                points.append(f"{bx:.1f},{by:.1f}")

            d = "M " + " L ".join(points)
            paths.append(
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="0.55"/>'
            )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Epitrochoid Lattice — outer-rolling-circle curves on a grid
# ---------------------------------------------------------------------------

def _epitrochoid(R: float, r: float, d: float,
                 num_points: int, rotation: float = 0.0) -> list[Tuple[float, float]]:
    """
    Epitrochoid: point on a circle of radius r rolling OUTSIDE a circle of radius R.
      x(t) = (R + r) * cos(t) - d * cos((R + r) / r * t)
      y(t) = (R + r) * sin(t) - d * sin((R + r) / r * t)
    Produces star-like, gear-like curves — distinct from hypotrochoid spirographs.
    """
    try:
        Ri, ri = round(R * 1000), round(r * 1000)
        g = math.gcd(Ri, ri)
        periods = ri // g
    except Exception:
        periods = 20
    periods = min(periods, 60)

    t_max = 2 * math.pi * periods
    total = R + r
    ratio = total / r if r != 0 else 0
    cos_rot, sin_rot = math.cos(rotation), math.sin(rotation)

    points = []
    for i in range(num_points):
        t = (i / num_points) * t_max
        x = total * math.cos(t) - d * math.cos(ratio * t)
        y = total * math.sin(t) - d * math.sin(ratio * t)
        rx = x * cos_rot - y * sin_rot
        ry = x * sin_rot + y * cos_rot
        points.append((rx, ry))
    return points


def _gen_epitrochoid_lattice(cfg: FullPageConfig) -> list[str]:
    """
    Grid of epitrochoid curves — star/gear shapes that look distinct from
    the hypotrochoid spirographs. Multiple layers with different parameters
    create elaborate, ornate figures at each grid point.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)

    spacing_x = cfg.width / cfg.epi_count_x
    spacing_y = cfg.height / cfg.epi_count_y

    for row in range(cfg.epi_count_y):
        for col in range(cfg.epi_count_x):
            cx = spacing_x * (col + 0.5)
            cy = spacing_y * (row + 0.5)

            for layer in range(cfg.epi_layers):
                color = cfg.colors[(row + col + layer) % len(cfg.colors)]
                layer_r = cfg.epi_r + layer * cfg.epi_layer_r_step
                rotation = layer * cfg.epi_layer_phase + rng.uniform(-0.2, 0.2)

                pts = _epitrochoid(cfg.epi_R, layer_r, cfg.epi_d,
                                   cfg.epi_num_points, rotation)
                lmax = max(max(abs(x) for x, _ in pts), max(abs(y) for _, y in pts)) if pts else 1.0
                scale = cfg.epi_size / lmax if lmax > 0 else 1.0

                coords = [f"{cx + x * scale:.1f},{cy + y * scale:.1f}" for x, y in pts]
                d = "M " + " L ".join(coords) + " Z"
                paths.append(
                    f'<path d="{d}" fill="none" stroke="{color}" '
                    f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="0.22"/>'
                )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Concentric Lathe — nested ellipse rings like engraved currency
# ---------------------------------------------------------------------------

def _gen_concentric_lathe(cfg: FullPageConfig) -> list[str]:
    """
    Multiple sets of concentric elliptical rings emanating from offset center
    points. Each ring has fine sinusoidal wobble — like lathe-engraved patterns
    on banknotes and bonds. Where ring sets from different centers overlap they
    create subtle moiré interference.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)
    num_samples = 400

    # Place centers spread across the page
    centers = []
    for ci in range(cfg.lathe_centers):
        cx = cfg.width * (0.25 + 0.5 * rng.random())
        cy = cfg.height * (0.25 + 0.5 * rng.random())
        rotation = rng.uniform(0, math.pi)  # ellipse rotation
        centers.append((cx, cy, rotation))

    for ci, (cx, cy, rot) in enumerate(centers):
        cos_r, sin_r = math.cos(rot), math.sin(rot)
        color = cfg.colors[ci % len(cfg.colors)]
        max_radius = max(cfg.width, cfg.height) * 0.55

        for ri in range(cfg.lathe_num_rings):
            base_r = max_radius * (ri + 1) / cfg.lathe_num_rings
            # Eccentricity: different radii on x vs y axis
            rx = base_r
            ry = base_r * (1.0 - cfg.lathe_eccentricity * 0.5)
            wobble_phase = rng.uniform(0, 2 * math.pi)
            wobble_amp = cfg.lathe_wobble_amp * (0.8 + 0.4 * rng.random())

            points = []
            for s in range(num_samples):
                theta = (s / num_samples) * 2 * math.pi
                # Base ellipse
                ex = rx * math.cos(theta)
                ey = ry * math.sin(theta)
                # Add fine wobble
                wobble = wobble_amp * math.sin(cfg.lathe_wobble_freq * theta + wobble_phase)
                ex += wobble * math.cos(theta)
                ey += wobble * math.sin(theta)
                # Rotate and translate
                x = cx + ex * cos_r - ey * sin_r
                y = cy + ex * sin_r + ey * cos_r
                points.append(f"{x:.1f},{y:.1f}")

            d = "M " + " L ".join(points) + " Z"
            opacity = 0.30 + 0.10 * (ri % 3) / 2
            paths.append(
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.stroke_width * 0.8:.2f}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
            )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Moiré Radial — radial line bursts from multiple offset centers
# ---------------------------------------------------------------------------

def _gen_moire_radial(cfg: FullPageConfig) -> list[str]:
    """
    Multiple starburst centers emit curved radial lines. Where ray fields
    from different centers overlap, complex moiré interference forms — a
    classic anti-counterfeiting visual.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)
    diagonal = math.sqrt(cfg.width ** 2 + cfg.height ** 2)
    ray_len = diagonal * cfg.moire_ray_length
    num_samples = 200

    # Spread centers across the page
    centers = []
    grid_cols = max(2, int(math.sqrt(cfg.moire_num_centers * cfg.width / cfg.height)))
    grid_rows = max(2, (cfg.moire_num_centers + grid_cols - 1) // grid_cols)
    for ci in range(cfg.moire_num_centers):
        row = ci // grid_cols
        col = ci % grid_cols
        cx = cfg.width * (col + 0.5) / grid_cols + rng.uniform(-30, 30)
        cy = cfg.height * (row + 0.5) / grid_rows + rng.uniform(-30, 30)
        centers.append((cx, cy))

    for ci, (cx, cy) in enumerate(centers):
        color = cfg.colors[ci % len(cfg.colors)]

        for ri in range(cfg.moire_rays_per_center):
            base_angle = (ri / cfg.moire_rays_per_center) * 2 * math.pi
            # Subtle curve on each ray
            curve_dir = 1 if ri % 2 == 0 else -1
            curve_amp = cfg.moire_curve_amp * (0.7 + 0.6 * rng.random())

            points = []
            for s in range(num_samples):
                t = s / (num_samples - 1)
                dist = t * ray_len
                # Angle drifts slightly along the ray for curvature
                angle = base_angle + curve_dir * curve_amp * t * t / ray_len
                x = cx + dist * math.cos(angle)
                y = cy + dist * math.sin(angle)
                points.append(f"{x:.1f},{y:.1f}")

            d = "M " + " L ".join(points)
            opacity = 0.22 + 0.08 * (ri % 3)
            paths.append(
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.stroke_width * 0.7:.2f}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
            )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Woven Ribbon — interlocking sine wave bands
# ---------------------------------------------------------------------------

def _gen_woven_ribbon(cfg: FullPageConfig) -> list[str]:
    """
    Horizontal and vertical families of sine-wave ribbons that weave over and
    under each other. Each ribbon is drawn as a pair of parallel wavy lines
    giving it visual width — like a basket-weave security pattern.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)
    num_samples = 400

    def _ribbon_wave(base_pos: float, t_frac: float, amplitude: float,
                     freq: float, phase: float, offset: float) -> float:
        """Compute wave displacement for a ribbon edge."""
        return base_pos + (amplitude + offset) * math.sin(
            2 * math.pi * freq * t_frac + phase
        )

    half_w = cfg.ribbon_width / 2

    # Horizontal ribbons
    h_spacing = cfg.height / (cfg.ribbon_count_h + 1)
    for hi in range(cfg.ribbon_count_h):
        color = cfg.colors[hi % len(cfg.colors)]
        base_y = h_spacing * (hi + 1)
        phase = rng.uniform(0, 2 * math.pi)
        freq = cfg.ribbon_freq + rng.uniform(-0.3, 0.3)
        amp = cfg.ribbon_amplitude * (0.85 + 0.3 * rng.random())

        # Draw two edges of the ribbon
        for edge in [-1, 1]:
            points = []
            for s in range(num_samples):
                t = s / (num_samples - 1)
                x = t * cfg.width
                y = _ribbon_wave(base_y, t, amp, freq, phase, edge * half_w)
                points.append(f"{x:.1f},{y:.1f}")
            d = "M " + " L ".join(points)
            paths.append(
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="0.40"/>'
            )

        # Fill line between edges for ribbon body
        points = []
        for s in range(num_samples):
            t = s / (num_samples - 1)
            x = t * cfg.width
            y = _ribbon_wave(base_y, t, amp, freq, phase, 0)
            points.append(f"{x:.1f},{y:.1f}")
        d = "M " + " L ".join(points)
        paths.append(
            f'<path d="{d}" fill="none" stroke="{color}" '
            f'stroke-width="{cfg.ribbon_width:.1f}" stroke-linecap="round" opacity="0.12"/>'
        )

    # Vertical ribbons
    v_spacing = cfg.width / (cfg.ribbon_count_v + 1)
    for vi in range(cfg.ribbon_count_v):
        color = cfg.colors[(vi + 1) % len(cfg.colors)]
        base_x = v_spacing * (vi + 1)
        phase = rng.uniform(0, 2 * math.pi)
        freq = cfg.ribbon_freq * (cfg.height / cfg.width) + rng.uniform(-0.3, 0.3)
        amp = cfg.ribbon_amplitude * (0.85 + 0.3 * rng.random())

        for edge in [-1, 1]:
            points = []
            for s in range(num_samples):
                t = s / (num_samples - 1)
                y = t * cfg.height
                x = _ribbon_wave(base_x, t, amp, freq, phase, edge * half_w)
                points.append(f"{x:.1f},{y:.1f}")
            d = "M " + " L ".join(points)
            paths.append(
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="0.40"/>'
            )

        points = []
        for s in range(num_samples):
            t = s / (num_samples - 1)
            y = t * cfg.height
            x = _ribbon_wave(base_x, t, amp, freq, phase, 0)
            points.append(f"{x:.1f},{y:.1f}")
        d = "M " + " L ".join(points)
        paths.append(
            f'<path d="{d}" fill="none" stroke="{color}" '
            f'stroke-width="{cfg.ribbon_width:.1f}" stroke-linecap="round" opacity="0.12"/>'
        )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Microline Waves — dense parallel undulating lines
# ---------------------------------------------------------------------------

def _gen_wave_field(cfg: FullPageConfig) -> list[str]:
    """
    Multiple families of flowing sinusoidal curves at slightly different angles,
    each family containing many tightly-spaced lines. Where families cross they
    create dense moiré interference. Like the background field on currency and
    stock certificates — organic flowing lines with full page coverage.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)
    diagonal = math.sqrt(cfg.width ** 2 + cfg.height ** 2)
    num_samples = max(500, int(diagonal * 0.7))
    lines_per_set = cfg.wfield_num_lines // cfg.wfield_num_sets

    for set_idx in range(cfg.wfield_num_sets):
        angle_deg = (set_idx - (cfg.wfield_num_sets - 1) / 2) * cfg.wfield_angle_spread
        angle_rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
        color = cfg.colors[set_idx % len(cfg.colors)]

        # Per-set frequency variation
        base_freq = cfg.wfield_freq + rng.uniform(-0.3, 0.3)
        base_phase = rng.uniform(0, 2 * math.pi)

        # Compute offset range to fully cover the page rectangle
        corners = [(0, 0), (cfg.width, 0), (0, cfg.height), (cfg.width, cfg.height)]
        perp_dists = [-cx * sin_a + cy * cos_a for cx, cy in corners]
        min_perp, max_perp = min(perp_dists), max(perp_dists)
        margin = (max_perp - min_perp) * 0.05
        spacing = (max_perp - min_perp + 2 * margin) / (lines_per_set + 1)

        for li in range(lines_per_set):
            offset = min_perp - margin + spacing * (li + 1)
            phase = base_phase + li * 0.12 + rng.uniform(-0.08, 0.08)
            freq = base_freq + li * 0.02
            amp = cfg.wfield_amplitude * (0.85 + 0.3 * rng.random())

            # Second harmonic for complexity
            h2_freq = freq * 2.3
            h2_amp = amp * 0.25
            h2_phase = phase * 1.6 + set_idx * 0.9

            points = []
            line_extent = diagonal * 1.6
            for s in range(num_samples):
                t = (s / (num_samples - 1)) * line_extent - line_extent * 0.3
                # Base position along angled line
                bx = t * cos_a - offset * sin_a
                by = t * sin_a + offset * cos_a
                # Perpendicular displacement
                wave = amp * math.sin(2 * math.pi * freq * t / cfg.width + phase)
                wave += h2_amp * math.sin(2 * math.pi * h2_freq * t / cfg.width + h2_phase)
                x = bx - wave * sin_a
                y = by + wave * cos_a
                points.append(f"{x:.1f},{y:.1f}")

            d = "M " + " L ".join(points)
            opacity = 0.25 + 0.12 * (li % 3) / 2
            paths.append(
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
            )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Hex Rosette Grid — hexagonal tiles with rosettes inside
# ---------------------------------------------------------------------------

def _gen_hex_rosette_grid(cfg: FullPageConfig) -> list[str]:
    """
    Hexagonal grid tiling the page. Each hex cell contains a small multi-ring
    rosette (like passport background pages). The hex borders plus interior
    rosettes create a dense, intricate repeating pattern.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)

    s = cfg.hex_cell_size  # hex side length
    h = s * math.sqrt(3) / 2  # hex half-height

    # How many columns/rows to cover the page
    cols = int(cfg.width / (1.5 * s)) + 2
    rows = int(cfg.height / (2 * h)) + 2

    for row in range(-1, rows + 1):
        for col in range(-1, cols + 1):
            # Hex center
            cx = col * 1.5 * s
            cy = row * 2 * h + (h if col % 2 else 0)

            if cx < -s or cx > cfg.width + s or cy < -s or cy > cfg.height + s:
                continue

            color = cfg.colors[(row + col) % len(cfg.colors)]

            # Draw hex border
            hex_pts = []
            for i in range(6):
                angle = math.pi / 3 * i + math.pi / 6
                hx = cx + s * math.cos(angle)
                hy = cy + s * math.sin(angle)
                hex_pts.append(f"{hx:.1f},{hy:.1f}")
            d = "M " + " L ".join(hex_pts) + " Z"
            paths.append(
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.hex_border_weight:.2f}" stroke-linecap="round" opacity="0.30"/>'
            )

            # Draw rosette inside the hex
            for ring in range(cfg.hex_rosette_rings):
                radius = s * 0.35 * (ring + 1) / cfg.hex_rosette_rings
                petals = cfg.hex_rosette_petals + ring * 2
                phase = ring * 0.5 + rng.uniform(-0.2, 0.2)
                num_samples = max(120, petals * 16)

                rose_pts = []
                for si in range(num_samples):
                    theta = (si / num_samples) * 2 * math.pi
                    rose = math.cos(petals / 2 * (theta + phase))
                    r = radius * (0.35 + 0.65 * rose * rose)
                    x = cx + r * math.cos(theta)
                    y = cy + r * math.sin(theta)
                    rose_pts.append(f"{x:.1f},{y:.1f}")

                d = "M " + " L ".join(rose_pts) + " Z"
                opacity = 0.25 + 0.10 * (ring / cfg.hex_rosette_rings)
                paths.append(
                    f'<path d="{d}" fill="none" stroke="{color}" '
                    f'stroke-width="{cfg.stroke_width * 0.8:.2f}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
                )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Contour Engraving — field-following curves like banknote portraits
# ---------------------------------------------------------------------------

def _gen_contour_engraving(cfg: FullPageConfig) -> list[str]:
    """
    Tightly spaced parallel curves displaced by a smooth potential field from
    multiple source points. Lines bunch and spread as they follow the field,
    creating natural light/dark density variation like banknote portrait
    engraving. Each line has multi-harmonic wobble for complexity.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)
    num_samples = 500

    # Potential field sources with per-source frequency for variety
    sources = []
    for ci in range(cfg.engrave_num_sources):
        sx = cfg.width * rng.uniform(0.1, 0.9)
        sy = cfg.height * rng.uniform(0.1, 0.9)
        strength = rng.uniform(0.6, 1.4)
        freq = rng.uniform(1.5, 3.5)
        sources.append((sx, sy, strength, freq))

    def _field_displacement(x: float, y: float) -> float:
        """Compute smooth displacement from all field sources."""
        total = 0.0
        for sx, sy, strength, freq in sources:
            dx, dy = x - sx, y - sy
            dist = math.sqrt(dx * dx + dy * dy) + 100.0
            angle = math.atan2(dy, dx)
            # Smooth sine displacement modulated by distance
            total += strength * math.sin(freq * angle + dist * 0.005) / (1.0 + dist * 0.003)
        return total

    for li in range(cfg.engrave_num_lines):
        color = cfg.colors[li % len(cfg.colors)]
        base_y = cfg.height * (li + 0.5) / cfg.engrave_num_lines

        points = []
        for s in range(num_samples):
            t = s / (num_samples - 1)
            x = t * cfg.width
            displacement = cfg.engrave_curve_amp * _field_displacement(x, base_y)
            # Add fine ripple for engraved texture
            ripple = 1.5 * math.sin(2 * math.pi * 15 * t + li * 0.4)
            y = base_y + displacement + ripple
            points.append(f"{x:.1f},{y:.1f}")

        d = "M " + " L ".join(points)
        opacity = 0.30 + 0.10 * (li % 3) / 2
        paths.append(
            f'<path d="{d}" fill="none" stroke="{color}" '
            f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
        )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Basket Weave — two families of arcs at opposing angles
# ---------------------------------------------------------------------------

def _gen_basket_weave(cfg: FullPageConfig) -> list[str]:
    """
    Two families of sinusoidal curves running at opposing angles (~+40° and
    ~-40°) creating a tight woven/basket texture. Each family has tightly
    spaced lines with multi-harmonic wave shapes. The crossing creates dense
    diamond-shaped interference cells across the entire page.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)
    diagonal = math.sqrt(cfg.width ** 2 + cfg.height ** 2)
    num_samples = max(500, int(diagonal * 0.7))

    for family in range(2):
        angle_deg = cfg.basket_angle if family == 0 else -cfg.basket_angle
        angle_rad = math.radians(angle_deg)
        cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
        color = cfg.colors[family % len(cfg.colors)]

        # Compute offset range to fully cover the page rectangle
        corners = [(0, 0), (cfg.width, 0), (0, cfg.height), (cfg.width, cfg.height)]
        perp_dists = [-cx * sin_a + cy * cos_a for cx, cy in corners]
        min_perp, max_perp = min(perp_dists), max(perp_dists)
        margin = (max_perp - min_perp) * 0.05
        spacing = (max_perp - min_perp + 2 * margin) / (cfg.basket_lines_per_set + 1)
        base_freq = cfg.basket_freq + rng.uniform(-0.2, 0.2)
        base_phase = rng.uniform(0, 2 * math.pi)

        for li in range(cfg.basket_lines_per_set):
            offset = min_perp - margin + spacing * (li + 1)
            phase = base_phase + li * 0.1
            freq = base_freq + li * 0.015
            amp = cfg.basket_amplitude * (0.85 + 0.3 * rng.random())

            # Second and third harmonics
            h2_amp = amp * 0.2
            h2_freq = freq * 2.0 + 0.3
            h3_amp = amp * 0.08
            h3_freq = freq * 3.2

            points = []
            line_extent = diagonal * 1.6
            for s in range(num_samples):
                t = (s / (num_samples - 1)) * line_extent - line_extent * 0.3
                bx = t * cos_a - offset * sin_a
                by = t * sin_a + offset * cos_a
                wave = amp * math.sin(2 * math.pi * freq * t / cfg.width + phase)
                wave += h2_amp * math.sin(2 * math.pi * h2_freq * t / cfg.width + phase * 1.5)
                wave += h3_amp * math.sin(2 * math.pi * h3_freq * t / cfg.width + phase * 2.1)
                x = bx - wave * sin_a
                y = by + wave * cos_a
                points.append(f"{x:.1f},{y:.1f}")

            d = "M " + " L ".join(points)
            opacity = 0.25 + 0.10 * (li % 3) / 2
            paths.append(
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
            )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Lathe Rings — nested deformed ellipses from offset centers
# ---------------------------------------------------------------------------

def _gen_lathe_rings(cfg: FullPageConfig) -> list[str]:
    """
    Multiple center points, each emitting many concentric rings with sinusoidal
    radial deformation. The rings from different centers overlap and create
    complex moiré interference — like engine-turned (guilloché) watch cases
    or the lathe patterns on banknote backgrounds.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)
    num_samples = 360

    # Generate offset centers spread across the page
    centers = []
    for ci in range(cfg.lathe_ring_num_centers):
        cx = cfg.width * rng.uniform(0.15, 0.85)
        cy = cfg.height * rng.uniform(0.15, 0.85)
        deform_phase = rng.uniform(0, 2 * math.pi)
        eccentricity = rng.uniform(0.7, 1.3)  # stretch ratio
        centers.append((cx, cy, deform_phase, eccentricity))

    max_radius = math.sqrt(cfg.width ** 2 + cfg.height ** 2) * 0.55

    for ci, (cx, cy, deform_phase, ecc) in enumerate(centers):
        color = cfg.colors[ci % len(cfg.colors)]
        freq = cfg.lathe_ring_deform_freq + (ci % 3)

        for ring in range(cfg.lathe_ring_rings_per):
            t = (ring + 1) / cfg.lathe_ring_rings_per
            base_r = max_radius * t
            amp = cfg.lathe_ring_deform_amp * base_r
            ring_phase = deform_phase + ring * 0.2

            points = []
            for s in range(num_samples):
                theta = (s / num_samples) * 2 * math.pi
                r = base_r + amp * math.sin(freq * theta + ring_phase)
                r += amp * 0.4 * math.sin((freq * 2 + 1) * theta + ring_phase * 1.5)
                x = cx + r * math.cos(theta) * ecc
                y = cy + r * math.sin(theta) / ecc
                points.append(f"{x:.1f},{y:.1f}")

            d = "M " + " L ".join(points) + " Z"
            opacity = 0.18 + 0.12 * t
            paths.append(
                f'<path d="{d}" fill="none" stroke="{color}" '
                f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
            )

    return paths


# ---------------------------------------------------------------------------
# Pattern: Scroll Chain — continuous S-curve chains across the page
# ---------------------------------------------------------------------------

def _gen_scroll_chain(cfg: FullPageConfig) -> list[str]:
    """
    Two families of tightly-spaced sinusoidal lines (horizontal and vertical)
    where each line's phase drifts gradually, creating a scrolling chain-link
    interference pattern. Similar to guilloche_diamond but with perpendicular
    families and phase-based modulation instead of angle-based, producing a
    different texture — more like interlocking chain mail.
    """
    paths = []
    rng = _seeded_rng(cfg.seed)
    num_samples = 500

    # Horizontal family
    h_spacing = cfg.height / (cfg.scroll_num_h + 1)
    h_base_phase = rng.uniform(0, 2 * math.pi)
    for li in range(cfg.scroll_num_h):
        color = cfg.colors[li % len(cfg.colors)]
        base_y = h_spacing * (li + 1)
        phase = h_base_phase + li * cfg.scroll_phase_drift
        freq = cfg.scroll_freq + li * 0.03
        amp = cfg.scroll_amplitude * (0.85 + 0.3 * rng.random())

        # Envelope modulation creates chain-link bulges
        env_freq = cfg.scroll_freq * 0.5
        env_phase = li * 0.25

        points = []
        for s in range(num_samples):
            t = s / (num_samples - 1)
            x = t * cfg.width
            envelope = 0.6 + 0.4 * abs(math.sin(2 * math.pi * env_freq * t + env_phase))
            y = base_y + amp * envelope * math.sin(2 * math.pi * freq * t + phase)
            y += amp * 0.2 * math.sin(2 * math.pi * freq * 2.3 * t + phase * 1.7)
            points.append(f"{x:.1f},{y:.1f}")

        d = "M " + " L ".join(points)
        opacity = 0.25 + 0.10 * (li % 3) / 2
        paths.append(
            f'<path d="{d}" fill="none" stroke="{color}" '
            f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
        )

    # Vertical family
    v_spacing = cfg.width / (cfg.scroll_num_v + 1)
    v_base_phase = rng.uniform(0, 2 * math.pi)
    for li in range(cfg.scroll_num_v):
        color = cfg.colors[(li + 1) % len(cfg.colors)]
        base_x = v_spacing * (li + 1)
        phase = v_base_phase + li * cfg.scroll_phase_drift
        freq = cfg.scroll_freq + li * 0.03
        amp = cfg.scroll_amplitude * (0.85 + 0.3 * rng.random())

        env_freq = cfg.scroll_freq * 0.5
        env_phase = li * 0.25

        points = []
        for s in range(num_samples):
            t = s / (num_samples - 1)
            y = t * cfg.height
            envelope = 0.6 + 0.4 * abs(math.sin(2 * math.pi * env_freq * t + env_phase))
            x = base_x + amp * envelope * math.sin(2 * math.pi * freq * t + phase)
            x += amp * 0.2 * math.sin(2 * math.pi * freq * 2.3 * t + phase * 1.7)
            points.append(f"{x:.1f},{y:.1f}")

        d = "M " + " L ".join(points)
        opacity = 0.25 + 0.10 * (li % 3) / 2
        paths.append(
            f'<path d="{d}" fill="none" stroke="{color}" '
            f'stroke-width="{cfg.stroke_width}" stroke-linecap="round" opacity="{opacity:.2f}"/>'
        )

    return paths


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_GENERATORS = {
    PatternType.GUILLOCHE_DIAMOND: _gen_guilloche_diamond,
    PatternType.SPIROGRAPH_LATTICE: _gen_spirograph_lattice,
    PatternType.LISSAJOUS_MESH: _gen_lissajous_mesh,
    PatternType.GUILLOCHE_ROSETTE: _gen_guilloche_rosette,
    PatternType.CROSSHATCH_WEAVE: _gen_crosshatch_weave,
    PatternType.EPITROCHOID_LATTICE: _gen_epitrochoid_lattice,
    PatternType.CONCENTRIC_LATHE: _gen_concentric_lathe,
    PatternType.MOIRE_RADIAL: _gen_moire_radial,
    PatternType.WOVEN_RIBBON: _gen_woven_ribbon,
    PatternType.WAVE_FIELD: _gen_wave_field,
    PatternType.HEX_ROSETTE_GRID: _gen_hex_rosette_grid,
    PatternType.CONTOUR_ENGRAVING: _gen_contour_engraving,
    PatternType.BASKET_WEAVE: _gen_basket_weave,
    PatternType.LATHE_RINGS: _gen_lathe_rings,
    PatternType.SCROLL_CHAIN: _gen_scroll_chain,
}


def generate_full_page_pattern(cfg: FullPageConfig) -> str:
    """Generate a complete SVG string with the specified full-page pattern."""
    gen = _GENERATORS[cfg.pattern_type]
    svg_paths = gen(cfg)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{cfg.width}" height="{cfg.height}" '
        f'viewBox="0 0 {cfg.width} {cfg.height}">',
    ]
    parts.extend(f"  {p}" for p in svg_paths)
    parts.append("</svg>")
    return "\n".join(parts)


def generate_pattern_elements(cfg: FullPageConfig) -> list[str]:
    """Generate just the SVG path elements (no wrapper) for embedding."""
    gen = _GENERATORS[cfg.pattern_type]
    return gen(cfg)


# ---------------------------------------------------------------------------
# Random config generator
# ---------------------------------------------------------------------------

def random_full_page_config(
    width: int = 2250,
    height: int = 3000,
    colors: list[str] | None = None,
    pattern_type: PatternType | None = None,
    seed: int | None = None,
) -> FullPageConfig:
    """Generate a randomized FullPageConfig."""
    rng = random.Random(seed)

    if pattern_type is None:
        pattern_type = rng.choice(list(PatternType))

    if colors is None:
        colors = ["#2a6e3f", "#1a5c30"]

    # Scale factor: all parameters were tuned at 800x1040 reference size.
    # Scale grid counts, element sizes, line counts, and amplitudes proportionally.
    _REF_W, _REF_H = 800, 1040
    sx = width / _REF_W      # horizontal scale
    sy = height / _REF_H     # vertical scale
    s = math.sqrt(sx * sy)   # area-based scale (geometric mean)

    cfg = FullPageConfig(
        width=width,
        height=height,
        pattern_type=pattern_type,
        colors=colors,
        stroke_width=rng.uniform(0.5, 0.9),
        seed=seed,
    )

    if pattern_type == PatternType.GUILLOCHE_DIAMOND:
        cfg.guil_num_sets = rng.choice([3, 4, 5])
        cfg.guil_waves_per_set = int(rng.randint(25, 40) * sy)
        cfg.guil_freq = rng.uniform(8.0, 14.0)
        cfg.guil_amplitude = rng.uniform(6.0, 14.0) * s
        cfg.guil_angle_spread = rng.uniform(30.0, 60.0)

    elif pattern_type == PatternType.SPIROGRAPH_LATTICE:
        cfg.spiro_R = rng.uniform(4.0, 7.0)
        cfg.spiro_r = rng.uniform(1.5, cfg.spiro_R - 0.5)
        cfg.spiro_d = rng.uniform(1.0, cfg.spiro_r + 1)
        cfg.spiro_count_x = int(rng.randint(3, 5) * sx)
        cfg.spiro_count_y = int(rng.randint(4, 6) * sy)
        cfg.spiro_size = rng.uniform(140.0, 220.0) * s
        cfg.spiro_layers = rng.randint(2, 3)

    elif pattern_type == PatternType.LISSAJOUS_MESH:
        cfg.liss_freq_a = rng.uniform(3.0, 7.0)
        cfg.liss_freq_b = rng.uniform(2.0, 5.0)
        cfg.liss_num_curves = rng.randint(2, 4)
        cfg.liss_amplitude = rng.uniform(0.42, 0.48)

    elif pattern_type == PatternType.GUILLOCHE_ROSETTE:
        cfg.rosette_count_x = max(2, int(rng.randint(2, 4) * sx))
        cfg.rosette_count_y = max(2, int(rng.randint(3, 5) * sy))
        cfg.rosette_radius = rng.uniform(160.0, 260.0) * s
        cfg.rosette_num_rings = int(rng.randint(20, 40) * s)
        cfg.rosette_wave_freq = rng.randint(6, 12)
        cfg.rosette_wave_amp = rng.uniform(0.10, 0.22)

    elif pattern_type == PatternType.CROSSHATCH_WEAVE:
        cfg.crosshatch_spacing = rng.uniform(10.0, 18.0)
        num_angles = rng.choice([2, 3])
        base_spread = 180.0 / num_angles
        cfg.crosshatch_angles = [
            i * base_spread + rng.uniform(-10, 10) for i in range(num_angles)
        ]
        cfg.crosshatch_wave_amp = rng.uniform(3.0, 7.0) * s
        cfg.crosshatch_wave_freq = rng.uniform(4.0, 8.0)

    elif pattern_type == PatternType.EPITROCHOID_LATTICE:
        cfg.epi_R = rng.uniform(2.0, 5.0)
        cfg.epi_r = rng.uniform(0.5, cfg.epi_R * 0.6)
        cfg.epi_d = rng.uniform(1.0, cfg.epi_r + 2)
        cfg.epi_count_x = max(2, int(rng.randint(3, 4) * sx))
        cfg.epi_count_y = max(2, int(rng.randint(3, 5) * sy))
        cfg.epi_size = rng.uniform(180.0, 250.0) * s
        cfg.epi_layers = rng.randint(1, 2)
        cfg.epi_layer_r_step = rng.uniform(0.1, 0.3)
        cfg.epi_layer_phase = rng.uniform(0.2, 0.5)

    elif pattern_type == PatternType.CONCENTRIC_LATHE:
        cfg.lathe_num_rings = int(rng.randint(35, 65) * s)
        cfg.lathe_centers = rng.randint(2, 4)
        cfg.lathe_eccentricity = rng.uniform(0.3, 0.8)
        cfg.lathe_wobble_amp = rng.uniform(1.5, 5.0) * s
        cfg.lathe_wobble_freq = rng.randint(12, 30)

    elif pattern_type == PatternType.MOIRE_RADIAL:
        cfg.moire_num_centers = rng.randint(5, 9)
        cfg.moire_rays_per_center = rng.randint(90, 150)
        cfg.moire_ray_length = rng.uniform(0.4, 0.65)
        cfg.moire_curve_amp = rng.uniform(12.0, 30.0) * s

    elif pattern_type == PatternType.WOVEN_RIBBON:
        cfg.ribbon_count_h = int(rng.randint(16, 28) * sy)
        cfg.ribbon_count_v = int(rng.randint(12, 20) * sx)
        cfg.ribbon_amplitude = rng.uniform(12.0, 25.0) * s
        cfg.ribbon_freq = rng.uniform(3.0, 7.0)
        cfg.ribbon_width = rng.uniform(1.0, 2.5)

    elif pattern_type == PatternType.WAVE_FIELD:
        cfg.wfield_num_lines = int(rng.randint(100, 180) * s)
        cfg.wfield_num_sets = rng.choice([2, 3, 4])
        cfg.wfield_freq = rng.uniform(4.0, 9.0)
        cfg.wfield_amplitude = rng.uniform(8.0, 22.0) * s
        cfg.wfield_angle_spread = rng.uniform(12.0, 30.0)

    elif pattern_type == PatternType.HEX_ROSETTE_GRID:
        cfg.hex_cell_size = rng.uniform(40.0, 80.0) * s
        cfg.hex_rosette_petals = rng.choice([4, 6, 8, 10])
        cfg.hex_rosette_rings = rng.randint(2, 4)
        cfg.hex_border_weight = rng.uniform(0.3, 0.8)

    elif pattern_type == PatternType.CONTOUR_ENGRAVING:
        cfg.engrave_num_lines = int(rng.randint(70, 110) * sy)
        cfg.engrave_num_sources = rng.randint(3, 7)
        cfg.engrave_curve_amp = rng.uniform(20.0, 45.0) * s

    elif pattern_type == PatternType.BASKET_WEAVE:
        cfg.basket_lines_per_set = int(rng.randint(45, 75) * s)
        cfg.basket_freq = rng.uniform(4.0, 9.0)
        cfg.basket_amplitude = rng.uniform(8.0, 18.0) * s
        cfg.basket_angle = rng.uniform(25.0, 50.0)

    elif pattern_type == PatternType.LATHE_RINGS:
        cfg.lathe_ring_num_centers = rng.randint(3, 7)
        cfg.lathe_ring_rings_per = int(rng.randint(18, 35) * s)
        cfg.lathe_ring_deform_freq = rng.randint(4, 10)
        cfg.lathe_ring_deform_amp = rng.uniform(0.08, 0.18)

    elif pattern_type == PatternType.SCROLL_CHAIN:
        cfg.scroll_num_h = int(rng.randint(30, 55) * sy)
        cfg.scroll_num_v = int(rng.randint(20, 40) * sx)
        cfg.scroll_freq = rng.uniform(5.0, 11.0)
        cfg.scroll_amplitude = rng.uniform(8.0, 22.0) * s
        cfg.scroll_phase_drift = rng.uniform(0.15, 0.5)

    return cfg
