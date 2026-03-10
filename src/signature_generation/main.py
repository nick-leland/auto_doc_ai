import math
import random
import hashlib
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


# ----------------------------
# Tiny stroke-based signature generator (no training)
# ----------------------------

@dataclass
class SigConfig:
    canvas: Tuple[int, int] = (900, 260)   # (W, H)
    margin: int = 30
    strokes: int = 5                        # number of pen-down segments
    points_per_stroke: int = 120
    baseline_y_frac: float = 0.62           # baseline position in canvas
    slant_deg: float = -12                  # negative = forward slant
    jitter: float = 0.9                     # positional noise (px)
    wobble: float = 2.0                     # slow sinusoidal drift (px)
    wobble_freq: float = 1.1                # cycles across signature
    min_width: float = 1.4                  # px
    max_width: float = 4.2                  # px
    pressure_noise: float = 0.10
    pen_color: Tuple[int, int, int, int] = (10, 10, 10, 255)
    fade_alpha: int = 230                   # simulate ink not perfectly opaque
    blur: float = 0.35                      # slight blur
    add_scan_noise: bool = True
    scan_noise_strength: float = 7.0        # 0..20 typical


def _stable_seed(text: str) -> int:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:16], 16)


def _bezier(p0, p1, p2, p3, t):
    # Cubic bezier point at t
    u = 1 - t
    return (u**3) * p0 + 3*(u**2)*t*p1 + 3*u*(t**2)*p2 + (t**3)*p3


def _pressure_profile(n: int, rng: random.Random, cfg: SigConfig, np_rng: np.random.Generator | None = None) -> np.ndarray:
    """
    Make a plausible pressure curve for a single stroke:
    low at ends, peak mid-stroke, with some noise.
    """
    if np_rng is None:
        np_rng = np.random.default_rng()
    t = np.linspace(0, 1, n)
    base = np.sin(np.pi * t)  # 0..1..0
    # bias so pressure doesn't drop to zero (signatures often keep contact)
    base = 0.25 + 0.85 * base
    # per-point noise
    pn = np.clip(base + np_rng.normal(0, cfg.pressure_noise, size=n), 0.15, 1.2)
    return pn.astype(np.float32)


def generate_signature(name: str, cfg: SigConfig | None = None, seed: int | None = None) -> Image.Image:
    """
    Returns an RGBA PIL Image with transparent background containing a synthetic signature.
    """
    if cfg is None:
        cfg = SigConfig()
    W, H = cfg.canvas
    img = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    rng = random.Random(_stable_seed(name) if seed is None else seed)
    np_rng = np.random.default_rng(_stable_seed(name) if seed is None else seed)

    # baseline + overall signature length
    baseline_y = int(H * cfg.baseline_y_frac)
    usable_w = W - 2 * cfg.margin

    # "name complexity" influences flourish & segmentation a bit
    complexity = max(4, min(16, len(name.replace(" ", ""))))

    # global slant transform
    slant = math.tan(math.radians(cfg.slant_deg))

    # Decide stroke start X positions spaced across canvas
    # but with randomness to look organic
    x_positions = np.linspace(cfg.margin, cfg.margin + usable_w, cfg.strokes + 1)
    x_positions += np.array([rng.uniform(-20, 20) for _ in range(cfg.strokes + 1)])
    x_positions = np.clip(x_positions, cfg.margin, W - cfg.margin)
    x_positions.sort()

    # Build each pen-down stroke as 1–2 bezier "chunks" chained
    for s in range(cfg.strokes):
        x0 = x_positions[s]
        x1 = x_positions[s + 1]
        stroke_w = max(80, (x1 - x0))

        # stroke height + baseline wiggle
        amp = rng.uniform(18, 40) + 1.5 * complexity
        y0 = baseline_y + rng.uniform(-10, 10)

        # control points: create forward moving signature-like loops
        # Use two chained beziers (p0->p3 then p3->p6) for richer shape
        p0 = np.array([x0, y0], dtype=np.float32)

        # First bezier end
        p3 = np.array([x0 + stroke_w * rng.uniform(0.35, 0.55),
                       y0 + rng.uniform(-amp, amp)], dtype=np.float32)

        # Second bezier end (finish near x1, baseline-ish)
        p6 = np.array([x1,
                       baseline_y + rng.uniform(-12, 12)], dtype=np.float32)

        # Controls for first bezier
        p1 = p0 + np.array([stroke_w * rng.uniform(0.10, 0.22),
                            rng.uniform(-amp, amp)], dtype=np.float32)
        p2 = p3 - np.array([stroke_w * rng.uniform(0.12, 0.28),
                            rng.uniform(-amp, amp)], dtype=np.float32)

        # Controls for second bezier
        p4 = p3 + np.array([stroke_w * rng.uniform(0.10, 0.22),
                            rng.uniform(-amp, amp)], dtype=np.float32)
        p5 = p6 - np.array([stroke_w * rng.uniform(0.10, 0.26),
                            rng.uniform(-amp, amp)], dtype=np.float32)

        # Sample points along the chained curve
        n = cfg.points_per_stroke
        t = np.linspace(0, 1, n, dtype=np.float32)

        # split sampling between the two beziers
        split = int(n * rng.uniform(0.45, 0.60))
        pts1 = np.array([_bezier(p0, p1, p2, p3, ti) for ti in t[:split]])
        pts2 = np.array([_bezier(p3, p4, p5, p6, ti) for ti in t[:(n - split)]])
        pts = np.vstack([pts1, pts2])

        # Add wobble + jitter
        phase = rng.uniform(0, 2 * math.pi)
        wob = cfg.wobble * np.sin(2 * math.pi * cfg.wobble_freq * (pts[:, 0] - cfg.margin) / usable_w + phase)
        pts[:, 1] += wob

        pts += np_rng.normal(0, cfg.jitter, size=pts.shape).astype(np.float32)

        # Apply slant: x' = x + slant*(y - baseline)
        pts[:, 0] = pts[:, 0] + slant * (pts[:, 1] - baseline_y)

        # Pressure -> width per segment
        pressure = _pressure_profile(len(pts), rng, cfg, np_rng)
        widths = cfg.min_width + (cfg.max_width - cfg.min_width) * pressure
        widths = np.clip(widths, cfg.min_width, cfg.max_width)

        # Occasionally simulate a micro pen-lift by skipping a small section
        if rng.random() < 0.45:
            gap_center = rng.randrange(len(pts)//4, 3*len(pts)//4)
            gap_len = rng.randrange(6, 16)
            mask = np.ones(len(pts), dtype=bool)
            mask[gap_center:gap_center+gap_len] = False
        else:
            mask = np.ones(len(pts), dtype=bool)

        # Draw as short line segments with varying width
        for i in range(len(pts) - 1):
            if not (mask[i] and mask[i+1]):
                continue
            xA, yA = pts[i]
            xB, yB = pts[i + 1]
            w = float(widths[i])

            # ink alpha slightly variable (fading)
            a = int(cfg.fade_alpha * (0.88 + 0.24 * rng.random()))
            color = (cfg.pen_color[0], cfg.pen_color[1], cfg.pen_color[2], a)

            draw.line((xA, yA, xB, yB), fill=color, width=max(1, int(round(w))))

        # Add a small terminal flourish sometimes
        if rng.random() < 0.65:
            tail = pts[-1].copy()
            angle = rng.uniform(-0.9, 0.2)
            length = rng.uniform(25, 60)
            end = tail + np.array([math.cos(angle)*length, math.sin(angle)*length], dtype=np.float32)
            draw.line((tail[0], tail[1], end[0], end[1]),
                      fill=(cfg.pen_color[0], cfg.pen_color[1], cfg.pen_color[2], int(cfg.fade_alpha*0.85)),
                      width=max(1, int(cfg.min_width)))

    # Slight blur to mimic scan/ink bleed
    if cfg.blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(cfg.blur))

    # Optional scan noise (subtle)
    if cfg.add_scan_noise:
        arr = np.array(img).astype(np.int16)
        noise = np_rng.normal(0, cfg.scan_noise_strength, size=arr.shape[:2]).astype(np.int16)
        # apply noise to RGB where alpha > 0
        alpha = arr[:, :, 3]
        m = alpha > 0
        for c in range(3):
            channel = arr[:, :, c]
            channel[m] = np.clip(channel[m] + noise[m], 0, 255)
            arr[:, :, c] = channel
        img = Image.fromarray(arr.astype(np.uint8), mode="RGBA")

    return img


if __name__ == "__main__":
    cfg = SigConfig()
    sig = generate_signature("John A. Smith", cfg=cfg)  # change name to change style deterministically
    sig.save("signature.png")
    print("Wrote signature.png")
