import random
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from PIL import Image, ImageDraw


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WaveformType(str, Enum):
    SINE_ADDITIVE = "sine_additive"
    SPIROGRAPH = "spirograph"
    LISSAJOUS = "lissajous"
    ENVELOPE_SINE = "envelope_sine"
    CROSSHATCH = "crosshatch"


class CornerStyle(str, Enum):
    MITER = "miter"
    ROUNDED = "rounded"
    ROSETTE = "rosette"
    NONE = "none"


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

@dataclass
class BorderParams:
    width: int = 1600
    height: int = 1000
    margin: int = 60
    band_thickness: int = 54
    samples: int = 3200
    bg: str = "white"
    fg: str = "black"
    line_width: int = 1
    stroke_width: float = 0.5

    waveform_type: WaveformType = WaveformType.SINE_ADDITIVE
    waveform_config: dict = field(default_factory=lambda: {
        "cycles_main": 18,
        "cycles_secondary": 36,
        "cycles_fine": 72,
        "amp_main": 0.22,
        "amp_secondary": 0.06,
        "amp_fine": 0.015,
        "phase_secondary": 0.8,
        "phase_fine": 1.7,
    })

    num_strands: int = 9
    strand_spread: float = 0.65
    strand_phase_step: float = 0.18

    corner_style: CornerStyle = CornerStyle.MITER
    corner_trim: int = 22
    show_frame: bool = True

    strand_offsets: tuple = field(default=None, repr=False)

    def __post_init__(self):
        if self.strand_offsets is None:
            if self.num_strands == 1:
                self.strand_offsets = (0.0,)
            else:
                half = self.strand_spread / 2
                self.strand_offsets = tuple(
                    np.linspace(-half, half, self.num_strands).tolist()
                )


# ---------------------------------------------------------------------------
# Waveform generators
# ---------------------------------------------------------------------------

def waveform_sine_additive(
    xn: np.ndarray, config: dict, strand_index: int
) -> np.ndarray:
    y = (
        config.get("amp_main", 0.22)
        * np.sin(2 * np.pi * config.get("cycles_main", 18) * xn)
        + config.get("amp_secondary", 0.06)
        * np.sin(
            2 * np.pi * config.get("cycles_secondary", 36) * xn
            + config.get("phase_secondary", 0.8)
        )
        + config.get("amp_fine", 0.015)
        * np.sin(
            2 * np.pi * config.get("cycles_fine", 72) * xn
            + config.get("phase_fine", 1.7)
        )
    )
    return y


def waveform_spirograph(
    xn: np.ndarray, config: dict, strand_index: int
) -> np.ndarray:
    R = config.get("R", 5.0)
    r = config.get("r", 3.0)
    d = config.get("d", 2.0)
    cycles = config.get("cycles", 15)
    t = 2 * np.pi * cycles * xn
    y = (R - r) * np.sin(t) - d * np.sin(((R - r) / r) * t)
    y_max = abs(R - r) + abs(d)
    if y_max > 0:
        y = y / y_max
    return y * config.get("amp", 0.22)


def waveform_lissajous(
    xn: np.ndarray, config: dict, strand_index: int
) -> np.ndarray:
    fx = config.get("freq_x", 11)
    fy = config.get("freq_y", 17)
    phi = config.get("phase_offset", 0.7)
    sec_amp = config.get("secondary_amp", 0.15)
    t = 2 * np.pi * xn
    y = np.sin(fy * t + phi)
    y += sec_amp * np.sin(fx * t)
    y /= 1 + sec_amp
    return y * config.get("amp", 0.22)


def waveform_envelope_sine(
    xn: np.ndarray, config: dict, strand_index: int
) -> np.ndarray:
    carrier = config.get("carrier_cycles", 24)
    env_cycles = config.get("envelope_cycles", 3.0)
    env_depth = config.get("envelope_depth", 0.6)
    envelope = 1 - env_depth * 0.5 * (1 - np.cos(2 * np.pi * env_cycles * xn))
    y = envelope * np.sin(2 * np.pi * carrier * xn)
    fine = config.get("fine_cycles", None)
    if fine is not None:
        y += 0.08 * np.sin(2 * np.pi * fine * xn)
    return y * config.get("amp", 0.22)


def waveform_crosshatch(
    xn: np.ndarray, config: dict, strand_index: int
) -> np.ndarray:
    cycles = config.get("cycles", 16)
    direction = 1 if strand_index % 2 == 0 else -1
    t = 2 * np.pi * cycles * xn
    y = np.sin(t * direction)
    sec = config.get("secondary_cycles", None)
    if sec is not None:
        y += 0.15 * np.sin(2 * np.pi * sec * xn * direction)
        y /= 1.15
    return y * config.get("amp", 0.22)


WAVEFORM_GENERATORS = {
    WaveformType.SINE_ADDITIVE: waveform_sine_additive,
    WaveformType.SPIROGRAPH: waveform_spirograph,
    WaveformType.LISSAJOUS: waveform_lissajous,
    WaveformType.ENVELOPE_SINE: waveform_envelope_sine,
    WaveformType.CROSSHATCH: waveform_crosshatch,
}


def generate_waveform(
    xn: np.ndarray, p: BorderParams, strand_index: int = 0
) -> np.ndarray:
    gen = WAVEFORM_GENERATORS[p.waveform_type]
    return gen(xn, p.waveform_config, strand_index)


# ---------------------------------------------------------------------------
# Strand / side generation
# ---------------------------------------------------------------------------

def make_side_family(length: int, p: BorderParams, extra_outer: int = 0):
    """Generate wave strands for one side.

    *extra_outer*: number of additional strands to add on the outer side of the
    band (toward the document edge and past it).  These use the same offset
    spacing so the pattern density stays identical.
    """
    x = np.linspace(0, length, p.samples)
    xn = x / length

    curves = []
    center_y = p.band_thickness / 2
    amp_px = p.band_thickness * 0.48

    # Offset step between strands
    if p.num_strands > 1:
        off_step = p.strand_spread / (p.num_strands - 1)
    else:
        off_step = 0.1

    # Original + extra outer offsets (more negative = further from center)
    all_offsets = list(p.strand_offsets)
    if extra_outer > 0:
        outermost = min(p.strand_offsets)
        all_offsets += [outermost - (k + 1) * off_step for k in range(extra_outer)]

    for i, off in enumerate(all_offsets):
        strand_phase = i * p.strand_phase_step
        xn_shifted = xn + strand_phase / (2 * np.pi)

        base = generate_waveform(xn_shifted, p, strand_index=i)

        strand_mod = 0.012 * np.sin(
            2 * np.pi * 30 * xn + strand_phase
        ) + 0.006 * np.sin(
            2 * np.pi * 60 * xn + 1.7 * strand_phase
        )

        y = center_y + p.band_thickness * off + amp_px * (base + strand_mod)
        curves.append(np.stack([x, y], axis=1))

    return curves


# ---------------------------------------------------------------------------
# Coordinate transforms (one per side)
# ---------------------------------------------------------------------------

def transform_top(curve, x0, y0):
    out = curve.copy()
    out[:, 0] += x0
    out[:, 1] += y0
    return out


def transform_bottom(curve, x0, y0, band_thickness):
    out = curve.copy()
    out[:, 1] = band_thickness - out[:, 1]
    out[:, 0] += x0
    out[:, 1] += y0
    return out


def transform_left(curve, x0, y0):
    out = np.zeros_like(curve)
    out[:, 0] = curve[:, 1] + x0
    out[:, 1] = curve[:, 0] + y0
    return out


def transform_right(curve, x0, y0, band_thickness):
    out = np.zeros_like(curve)
    out[:, 0] = (band_thickness - curve[:, 1]) + x0
    out[:, 1] = curve[:, 0] + y0
    return out


# ---------------------------------------------------------------------------
# Clipping / splitting utilities
# ---------------------------------------------------------------------------

def clip_points_to_rect(points, xmin, ymin, xmax, ymax):
    mask = (
        (points[:, 0] >= xmin)
        & (points[:, 0] <= xmax)
        & (points[:, 1] >= ymin)
        & (points[:, 1] <= ymax)
    )
    return points[mask]


def split_runs(points, max_jump=6.0):
    if len(points) < 2:
        return []
    runs = []
    start = 0
    for i in range(1, len(points)):
        jump = np.linalg.norm(points[i] - points[i - 1])
        if jump > max_jump:
            if i - start >= 2:
                runs.append(points[start:i])
            start = i
    if len(points) - start >= 2:
        runs.append(points[start:])
    return runs


# ---------------------------------------------------------------------------
# Shared curve pipeline (used by both PIL and SVG renderers)
# ---------------------------------------------------------------------------

def _clip_miter_corners(points, side, x0, y0, x1, y1, b):
    """Clip points to the correct side of diagonal miter lines in corners.

    Each corner has a 45-degree diagonal from the outer corner to the inner
    corner.  Top-side waves stay above the diagonal, left-side waves stay
    below it, etc.  This produces clean mitered corners like a picture frame.
    """
    if len(points) == 0:
        return points

    px, py = points[:, 0], points[:, 1]
    mask = np.ones(len(points), dtype=bool)

    if side == "top":
        # TL corner: keep where (py - y0) <= (px - x0)
        in_tl = (px < x0 + b) & (py < y0 + b)
        mask &= ~in_tl | ((py - y0) <= (px - x0))
        # TR corner: keep where (py - y0) <= (x1 - px)
        in_tr = (px > x1 - b) & (py < y0 + b)
        mask &= ~in_tr | ((py - y0) <= (x1 - px))

    elif side == "bottom":
        # BL corner: keep where (y1 - py) <= (px - x0)
        in_bl = (px < x0 + b) & (py > y1 - b)
        mask &= ~in_bl | ((y1 - py) <= (px - x0))
        # BR corner: keep where (y1 - py) <= (x1 - px)
        in_br = (px > x1 - b) & (py > y1 - b)
        mask &= ~in_br | ((y1 - py) <= (x1 - px))

    elif side == "left":
        # TL corner: keep where (px - x0) <= (py - y0)
        in_tl = (px < x0 + b) & (py < y0 + b)
        mask &= ~in_tl | ((px - x0) <= (py - y0))
        # BL corner: keep where (px - x0) <= (y1 - py)
        in_bl = (px < x0 + b) & (py > y1 - b)
        mask &= ~in_bl | ((px - x0) <= (y1 - py))

    elif side == "right":
        # TR corner: keep where (x1 - px) <= (py - y0)
        in_tr = (px > x1 - b) & (py < y0 + b)
        mask &= ~in_tr | ((x1 - px) <= (py - y0))
        # BR corner: keep where (x1 - px) <= (y1 - py)
        in_br = (px > x1 - b) & (py > y1 - b)
        mask &= ~in_br | ((x1 - px) <= (y1 - py))

    return points[mask]


def _side_configs(p: BorderParams):
    x0, y0 = p.margin, p.margin
    x1, y1 = p.width - p.margin, p.height - p.margin
    b = p.band_thickness

    # --- Extension past document edges ---
    # Lengthwise overflow: extend waves past each end
    ovr_len = b

    # Perpendicular overflow: extra outer strands to fill from band edge to
    # past the document edge.  Compute how many extra strands are needed.
    if p.num_strands > 1:
        off_step = p.strand_spread / (p.num_strands - 1)
    else:
        off_step = 0.1
    px_step = off_step * b  # pixel step between strands
    # Distance from outermost original strand to outer edge of band
    outermost_y = b / 2 + b * min(p.strand_offsets)
    # Total distance to cover: from outermost strand to past the document edge
    # (margin is the gap between band outer edge and document edge)
    target_dist = outermost_y + p.margin + b
    extra_outer = int(np.ceil(target_dist / max(px_step, 1.0)))
    extra_outer = max(extra_outer, 0)

    top_len = (x1 - x0) + 2 * ovr_len
    side_len = (y1 - y0) + 2 * ovr_len
    top_curves = make_side_family(top_len, p, extra_outer=extra_outer)
    side_curves = make_side_family(side_len, p, extra_outer=extra_outer)

    # Clip rects: inner boundary is precise, outer extends past document edges.
    # Length direction also extends past edges.
    BIG = 9999
    use_miter = p.corner_style in (CornerStyle.MITER, CornerStyle.ROSETTE)
    if use_miter:
        clip_rects = {
            "top": (-BIG, -BIG, p.width + BIG, y0 + b),
            "bottom": (-BIG, y1 - b, p.width + BIG, p.height + BIG),
            "left": (-BIG, -BIG, x0 + b, p.height + BIG),
            "right": (x1 - b, -BIG, p.width + BIG, p.height + BIG),
        }
    else:
        ct = max(p.corner_trim, b)
        clip_rects = {
            "top": (x0 + ct - ovr_len, -BIG, x1 - ct + ovr_len, y0 + b),
            "bottom": (x0 + ct - ovr_len, y1 - b, x1 - ct + ovr_len, p.height + BIG),
            "left": (-BIG, y0 + ct - ovr_len, x0 + b, y1 - ct + ovr_len),
            "right": (x1 - b, y0 + ct - ovr_len, p.width + BIG, y1 - ct + ovr_len),
        }

    return [
        ("top", top_curves, transform_top, (x0 - ovr_len, y0), clip_rects["top"]),
        ("bottom", top_curves, transform_bottom, (x0 - ovr_len, y1 - b, b), clip_rects["bottom"]),
        ("left", side_curves, transform_left, (x0, y0 - ovr_len), clip_rects["left"]),
        ("right", side_curves, transform_right, (x1 - b, y0 - ovr_len, b), clip_rects["right"]),
    ]


def _clean_runs(runs, min_length=4.0, band_thickness=54.0, corner_boxes=None):
    """Remove debris and directly bridge dangling endpoints across corners.

    For each corner, collect all dangling endpoints (run start/end that sits
    inside the corner box), pair them by proximity, and concatenate the paired
    runs — the merge itself adds a short straight connector between them.
    """
    # 1. Filter out tiny debris
    filtered = []
    for run in runs:
        if len(run) < 2:
            continue
        total_len = np.sum(np.linalg.norm(np.diff(run, axis=0), axis=1))
        if total_len >= min_length:
            filtered.append(run)

    if not filtered or not corner_boxes:
        return filtered

    def _in_any_corner(pt):
        for box in corner_boxes:
            xmin, ymin, xmax, ymax = box[:4]
            if xmin <= pt[0] <= xmax and ymin <= pt[1] <= ymax:
                return True
        return False

    # 2. Greedy nearest-endpoint merging — only bridge endpoints that are
    #    both inside a corner zone (cross-side connections).  Use a generous
    #    distance since endpoints sit on opposite sides of the diagonal.
    merge_dist = max(12.0, band_thickness * 1.2)
    runs_list = [np.array(r) for r in filtered]
    active = list(range(len(runs_list)))

    changed = True
    while changed:
        changed = False
        best_dist = merge_dist
        best_pair = None

        for ai in range(len(active)):
            for aj in range(ai + 1, len(active)):
                ri, rj = runs_list[active[ai]], runs_list[active[aj]]
                # Only consider pairs where both touching endpoints are in
                # a corner zone — avoids merging mid-side runs.
                candidates = []
                if _in_any_corner(ri[-1]) and _in_any_corner(rj[0]):
                    candidates.append((np.linalg.norm(ri[-1] - rj[0]), "ei_sj"))
                if _in_any_corner(rj[-1]) and _in_any_corner(ri[0]):
                    candidates.append((np.linalg.norm(rj[-1] - ri[0]), "ej_si"))
                if _in_any_corner(ri[-1]) and _in_any_corner(rj[-1]):
                    candidates.append((np.linalg.norm(ri[-1] - rj[-1]), "ee"))
                if _in_any_corner(ri[0]) and _in_any_corner(rj[0]):
                    candidates.append((np.linalg.norm(ri[0] - rj[0]), "ss"))
                for d, mode in candidates:
                    if d < best_dist:
                        best_dist = d
                        best_pair = (ai, aj, mode)

        if best_pair is not None:
            ai, aj, mode = best_pair
            ri, rj = runs_list[active[ai]], runs_list[active[aj]]
            if mode == "ei_sj":
                merged = np.concatenate([ri, rj])
            elif mode == "ej_si":
                merged = np.concatenate([rj, ri])
            elif mode == "ee":
                merged = np.concatenate([ri, rj[::-1]])
            else:
                merged = np.concatenate([ri[::-1], rj])

            runs_list[active[ai]] = merged
            active.pop(aj)
            changed = True

    result = [runs_list[i] for i in active]

    # 3. Remove remaining stubs trapped entirely in a corner.
    stub_limit = band_thickness * 1.5
    cleaned = []
    for run in result:
        total_len = np.sum(np.linalg.norm(np.diff(run, axis=0), axis=1))
        s_in = _in_any_corner(run[0])
        e_in = _in_any_corner(run[-1])
        if total_len < stub_limit and s_in and e_in:
            continue
        cleaned.append(run)

    return cleaned


def _compute_all_runs(p: BorderParams):
    x0, y0 = p.margin, p.margin
    x1, y1 = p.width - p.margin, p.height - p.margin
    b = p.band_thickness
    use_miter = p.corner_style in (CornerStyle.MITER, CornerStyle.ROSETTE)

    all_runs = []
    for side_name, curves, tfn, targs, clip_rect in _side_configs(p):
        for curve in curves:
            pts = tfn(curve, *targs)
            pts = clip_points_to_rect(pts, *clip_rect)
            if use_miter and len(pts) > 0:
                pts = _clip_miter_corners(pts, side_name, x0, y0, x1, y1, b)
            runs = split_runs(pts)
            all_runs.extend(runs)

    if use_miter:
        # (xmin, ymin, xmax, ymax, diag_inner_x, diag_inner_y)
        corner_boxes = [
            (x0, y0, x0 + b, y0 + b, x0 + b, y0 + b),      # TL
            (x1 - b, y0, x1, y0 + b, x1 - b, y0 + b),       # TR
            (x0, y1 - b, x0 + b, y1, x0 + b, y1 - b),       # BL
            (x1 - b, y1 - b, x1, y1, x1 - b, y1 - b),       # BR
        ]
        all_runs = _clean_runs(
            all_runs, min_length=4.0, band_thickness=b,
            corner_boxes=corner_boxes,
        )

    return all_runs


# ---------------------------------------------------------------------------
# PIL rendering
# ---------------------------------------------------------------------------

def _draw_runs(draw, runs, color, width):
    for run in runs:
        xy = [tuple(map(float, pt)) for pt in run]
        draw.line(xy, fill=color, width=width)


def _draw_frame(draw, p: BorderParams):
    x0, y0 = p.margin, p.margin
    x1, y1 = p.width - p.margin, p.height - p.margin
    draw.rectangle([x0, y0, x1, y1], outline=p.fg, width=1)
    draw.rectangle(
        [
            x0 + p.band_thickness,
            y0 + p.band_thickness,
            x1 - p.band_thickness,
            y1 - p.band_thickness,
        ],
        outline=p.fg,
        width=1,
    )


def _draw_corner_masks_pil(draw, p: BorderParams):
    if p.corner_style == CornerStyle.NONE or not p.show_frame:
        return

    x0, y0 = p.margin, p.margin
    x1, y1 = p.width - p.margin, p.height - p.margin
    b = p.band_thickness

    if p.corner_style == CornerStyle.MITER:
        # Diagonal clipping already handled at data level — just draw miter lines
        miter_lines = [
            [(x0, y0), (x0 + b, y0 + b)],
            [(x1, y0), (x1 - b, y0 + b)],
            [(x0, y1), (x0 + b, y1 - b)],
            [(x1, y1), (x1 - b, y1 - b)],
        ]
        for line in miter_lines:
            draw.line(line, fill=p.fg, width=1)

    elif p.corner_style == CornerStyle.ROUNDED:
        r = b
        corners = [
            (x0, y0, x0 + 2 * r, y0 + 2 * r, 180, 270),
            (x1 - 2 * r, y0, x1, y0 + 2 * r, 270, 360),
            (x0, y1 - 2 * r, x0 + 2 * r, y1, 90, 180),
            (x1 - 2 * r, y1 - 2 * r, x1, y1, 0, 90),
        ]
        for cx0, cy0, cx1, cy1, start, end in corners:
            draw.rectangle([cx0, cy0, cx1, cy1], fill=p.bg)
            draw.arc([cx0, cy0, cx1, cy1], start, end, fill=p.fg, width=1)

    elif p.corner_style == CornerStyle.ROSETTE:
        # Diagonal clipping already handled at data level
        r = int(b * 0.45)
        rosette_centers = [
            (x0 + b // 2, y0 + b // 2),
            (x1 - b // 2, y0 + b // 2),
            (x0 + b // 2, y1 - b // 2),
            (x1 - b // 2, y1 - b // 2),
        ]
        for cx, cy in rosette_centers:
            for ri in range(3, r + 1, max(1, r // 4)):
                draw.ellipse(
                    [cx - ri, cy - ri, cx + ri, cy + ri],
                    outline=p.fg,
                    width=1,
                )


def render_border(p: BorderParams) -> Image.Image:
    img = Image.new("RGB", (p.width, p.height), p.bg)
    draw = ImageDraw.Draw(img)

    all_runs = _compute_all_runs(p)
    _draw_runs(draw, all_runs, p.fg, p.line_width)
    _draw_corner_masks_pil(draw, p)
    if p.show_frame:
        _draw_frame(draw, p)
    return img


# ---------------------------------------------------------------------------
# SVG rendering
# ---------------------------------------------------------------------------

def _runs_to_svg_path_d(runs) -> str:
    segments = []
    for run in runs:
        if len(run) < 2:
            continue
        parts = [f"M {run[0][0]:.2f},{run[0][1]:.2f}"]
        parts.extend(f"L {pt[0]:.2f},{pt[1]:.2f}" for pt in run[1:])
        segments.append(" ".join(parts))
    return " ".join(segments)


def add_border_to_drawing(drawing, p: BorderParams, group_id="guilloche-border"):
    g = drawing.g(id=group_id)

    x0, y0 = p.margin, p.margin
    x1, y1 = p.width - p.margin, p.height - p.margin
    b = p.band_thickness

    # Wave paths in a sub-group so clip-path applies cleanly
    waves_g = drawing.g(id=f"{group_id}-waves")
    all_runs = _compute_all_runs(p)
    if all_runs:
        path_d = _runs_to_svg_path_d(all_runs)
        waves_g.add(
            drawing.path(
                d=path_d,
                fill="none",
                stroke=p.fg,
                stroke_width=p.stroke_width,
            )
        )
    g.add(waves_g)

    if p.show_frame:
        g.add(
            drawing.rect(
                insert=(x0, y0),
                size=(x1 - x0, y1 - y0),
                fill="none",
                stroke=p.fg,
                stroke_width=0.5,
            )
        )
        g.add(
            drawing.rect(
                insert=(x0 + b, y0 + b),
                size=(x1 - x0 - 2 * b, y1 - y0 - 2 * b),
                fill="none",
                stroke=p.fg,
                stroke_width=0.5,
            )
        )

    _add_svg_corner_treatment(drawing, g, waves_g, p)
    drawing.add(g)
    return g


def _add_svg_corner_treatment(drawing, group, waves_group, p: BorderParams):
    if p.corner_style == CornerStyle.NONE or not p.show_frame:
        return

    x0, y0 = p.margin, p.margin
    x1, y1 = p.width - p.margin, p.height - p.margin
    b = p.band_thickness

    if p.corner_style == CornerStyle.MITER:
        # Diagonal miter lines at each corner
        miter_lines = [
            ((x0, y0), (x0 + b, y0 + b)),
            ((x1, y0), (x1 - b, y0 + b)),
            ((x0, y1), (x0 + b, y1 - b)),
            ((x1, y1), (x1 - b, y1 - b)),
        ]
        for (sx, sy), (ex, ey) in miter_lines:
            group.add(
                drawing.line(
                    start=(sx, sy), end=(ex, ey),
                    stroke=p.fg, stroke_width=0.5,
                )
            )

    elif p.corner_style == CornerStyle.ROSETTE:
        r = b * 0.45
        for cx, cy in [
            (x0 + b / 2, y0 + b / 2),
            (x1 - b / 2, y0 + b / 2),
            (x0 + b / 2, y1 - b / 2),
            (x1 - b / 2, y1 - b / 2),
        ]:
            for ri_frac in [0.3, 0.55, 0.8, 1.0]:
                ri = r * ri_frac
                group.add(
                    drawing.circle(
                        center=(cx, cy),
                        r=ri,
                        fill="none",
                        stroke=p.fg,
                        stroke_width=p.stroke_width,
                    )
                )

    elif p.corner_style == CornerStyle.ROUNDED:
        import math

        r = b
        arc_corners = [
            (x0, y0, r, 180, 270),
            (x1, y0, r, 270, 360),
            (x0, y1, r, 90, 180),
            (x1, y1, r, 0, 90),
        ]
        for cx, cy, rad, start_deg, end_deg in arc_corners:
            start_rad = math.radians(start_deg)
            end_rad = math.radians(end_deg)
            sx = cx + rad * math.cos(start_rad)
            sy = cy + rad * math.sin(start_rad)
            ex = cx + rad * math.cos(end_rad)
            ey = cy + rad * math.sin(end_rad)
            arc_d = (
                f"M {sx:.2f},{sy:.2f} "
                f"A {rad:.2f},{rad:.2f} 0 0,1 {ex:.2f},{ey:.2f}"
            )
            group.add(
                drawing.path(
                    d=arc_d,
                    fill="none",
                    stroke=p.fg,
                    stroke_width=0.5,
                )
            )


def render_border_svg(p: BorderParams):
    import svgwrite

    drawing = svgwrite.Drawing(size=(p.width, p.height))
    if p.bg and p.bg != "none":
        drawing.add(
            drawing.rect(
                insert=(0, 0), size=(p.width, p.height), fill=p.bg
            )
        )
    add_border_to_drawing(drawing, p)
    return drawing


# ---------------------------------------------------------------------------
# Random parameter generation
# ---------------------------------------------------------------------------

def random_params(
    width: int = 1600,
    height: int = 1000,
    margin: int | None = None,
    band_thickness: int | None = None,
    num_strands: int | None = None,
    strand_spread: float | None = None,
    strand_phase_step: float | None = None,
    fg: str | None = None,
    bg: str = "white",
    show_frame: bool = True,
    rng: random.Random | None = None,
) -> BorderParams:
    rng = rng or random.Random()

    waveform_type = rng.choice(list(WaveformType))
    corner_style = rng.choice(list(CornerStyle))

    band_thickness = band_thickness if band_thickness is not None else rng.randint(30, 80)
    num_strands = num_strands if num_strands is not None else rng.randint(5, 14)
    strand_spread = strand_spread if strand_spread is not None else rng.uniform(0.4, 0.8)
    strand_phase_step = strand_phase_step if strand_phase_step is not None else rng.uniform(0.05, 0.4)
    corner_trim = rng.randint(10, 35)
    margin = margin if margin is not None else rng.randint(30, 80)
    fg = fg or "black"
    stroke_width = rng.uniform(0.2, 1.0)
    line_width = rng.choice([1, 1, 1, 2])
    samples = rng.choice([2400, 3200, 4000])

    TWO_PI = 2 * np.pi

    if waveform_type == WaveformType.SINE_ADDITIVE:
        base_cycles = rng.randint(8, 25)
        waveform_config = {
            "cycles_main": base_cycles,
            "cycles_secondary": base_cycles * rng.choice([2, 3]),
            "cycles_fine": base_cycles * rng.choice([4, 5, 6]),
            "amp_main": rng.uniform(0.18, 0.35),
            "amp_secondary": rng.uniform(0.03, 0.12),
            "amp_fine": rng.uniform(0.005, 0.03),
            "phase_secondary": rng.uniform(0, TWO_PI),
            "phase_fine": rng.uniform(0, TWO_PI),
        }

    elif waveform_type == WaveformType.SPIROGRAPH:
        R = rng.uniform(3.0, 8.0)
        r = rng.uniform(1.0, R - 0.5)
        waveform_config = {
            "R": R,
            "r": r,
            "d": rng.uniform(0.5, r + 1),
            "cycles": rng.randint(8, 30),
            "amp": rng.uniform(0.22, 0.38),
        }

    elif waveform_type == WaveformType.LISSAJOUS:
        waveform_config = {
            "freq_x": rng.randint(5, 20),
            "freq_y": rng.randint(7, 25),
            "phase_offset": rng.uniform(0, TWO_PI),
            "secondary_amp": rng.uniform(0.05, 0.25),
            "amp": rng.uniform(0.22, 0.36),
        }

    elif waveform_type == WaveformType.ENVELOPE_SINE:
        config = {
            "carrier_cycles": rng.randint(15, 40),
            "envelope_cycles": rng.uniform(2.0, 6.0),
            "envelope_depth": rng.uniform(0.3, 0.9),
            "amp": rng.uniform(0.22, 0.36),
        }
        if rng.random() > 0.4:
            config["fine_cycles"] = rng.randint(40, 80)
        waveform_config = config

    elif waveform_type == WaveformType.CROSSHATCH:
        base = rng.randint(10, 25)
        config = {
            "cycles": base,
            "amp": rng.uniform(0.22, 0.36),
        }
        if rng.random() > 0.5:
            config["secondary_cycles"] = base * 2
        waveform_config = config

    else:
        waveform_config = {}

    return BorderParams(
        width=width,
        height=height,
        margin=margin,
        band_thickness=band_thickness,
        samples=samples,
        bg=bg,
        fg=fg,
        line_width=line_width,
        stroke_width=stroke_width,
        waveform_type=waveform_type,
        waveform_config=waveform_config,
        num_strands=num_strands,
        strand_spread=strand_spread,
        strand_phase_step=strand_phase_step,
        corner_style=corner_style,
        corner_trim=corner_trim,
        show_frame=show_frame,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    params = random_params()
    img = render_border(params)
    img.save("guilloche_border.png")
    print(
        f"Generated {params.waveform_type.value} border "
        f"with {params.num_strands} strands, "
        f"corner style: {params.corner_style.value}"
    )
