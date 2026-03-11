"""
Image augmentation pipeline for synthetic document images.

Simulates camera capture artifacts: noise, blur, perspective distortion,
barrel distortion (fisheye), JPEG compression, brightness/contrast shifts,
and resolution reduction.

All augmentations also transform bounding boxes so annotations stay aligned.
"""

import math
import random
from dataclasses import dataclass, field
from io import BytesIO

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


@dataclass
class AugmentationResult:
    """Result of augmenting an image."""
    image: Image.Image
    # Transformation matrix mapping original coords → augmented coords.
    # For simple augmentations (no spatial transform), this is identity.
    # For perspective/fisheye, use transform_point() instead.
    applied: list[str] = field(default_factory=list)
    # Callable to transform (x, y) from original to augmented coordinates.
    # Composed from all spatial transforms applied in order.
    _transforms: list = field(default_factory=list, repr=False)

    def transform_point(self, x: float, y: float) -> tuple[float, float]:
        """Transform a point from original image coords to augmented coords."""
        for fn in self._transforms:
            x, y = fn(x, y)
        return x, y

    def transform_bbox(
        self, x1: float, y1: float, x2: float, y2: float,
    ) -> tuple[float, float, float, float]:
        """Transform a bounding box. Uses corner mapping for accuracy."""
        corners = [
            (x1, y1), (x2, y1), (x1, y2), (x2, y2),
        ]
        tx = [self.transform_point(cx, cy) for cx, cy in corners]
        new_x1 = min(p[0] for p in tx)
        new_y1 = min(p[1] for p in tx)
        new_x2 = max(p[0] for p in tx)
        new_y2 = max(p[1] for p in tx)
        return new_x1, new_y1, new_x2, new_y2


# ---------------------------------------------------------------------------
# Individual augmentations
# ---------------------------------------------------------------------------

def _add_gaussian_noise(img: Image.Image, rng: random.Random,
                        sigma_range: tuple[float, float] = (3, 15)) -> Image.Image:
    """Add Gaussian noise to simulate camera sensor noise."""
    arr = np.array(img, dtype=np.float32)
    sigma = rng.uniform(*sigma_range)
    noise = np.random.RandomState(rng.randint(0, 2**31)).normal(0, sigma, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _adjust_brightness(img: Image.Image, rng: random.Random,
                       factor_range: tuple[float, float] = (0.8, 1.2)) -> Image.Image:
    """Random brightness adjustment."""
    factor = rng.uniform(*factor_range)
    return ImageEnhance.Brightness(img).enhance(factor)


def _adjust_contrast(img: Image.Image, rng: random.Random,
                     factor_range: tuple[float, float] = (0.8, 1.3)) -> Image.Image:
    """Random contrast adjustment."""
    factor = rng.uniform(*factor_range)
    return ImageEnhance.Contrast(img).enhance(factor)


def _gaussian_blur(img: Image.Image, rng: random.Random,
                   radius_range: tuple[float, float] = (0.5, 1.5)) -> Image.Image:
    """Slight Gaussian blur to simulate defocus."""
    radius = rng.uniform(*radius_range)
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def _jpeg_compress(img: Image.Image, rng: random.Random,
                   quality_range: tuple[int, int] = (40, 85)) -> Image.Image:
    """JPEG compression artifacts."""
    quality = rng.randint(*quality_range)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _downscale(img: Image.Image, rng: random.Random,
               factor_range: tuple[float, float] = (0.4, 0.8)) -> tuple[Image.Image, float]:
    """Downscale then upscale to simulate low-resolution capture.
    Returns (image, scale_factor)."""
    factor = rng.uniform(*factor_range)
    w, h = img.size
    small_w = max(1, int(w * factor))
    small_h = max(1, int(h * factor))
    small = img.resize((small_w, small_h), Image.BILINEAR)
    return small.resize((w, h), Image.BILINEAR), factor


def _perspective_transform(
    img: Image.Image, rng: random.Random,
    max_shift_frac: float = 0.03,
) -> tuple[Image.Image, callable]:
    """Random perspective distortion to simulate an angled camera.

    Returns (image, transform_function) where transform_function maps
    original (x,y) -> distorted (x,y).
    """
    w, h = img.size

    # Random shifts for each corner (fraction of image dimension)
    shifts = [
        (rng.uniform(-max_shift_frac, max_shift_frac) * w,
         rng.uniform(-max_shift_frac, max_shift_frac) * h)
        for _ in range(4)
    ]

    # Source corners (original)
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    # Destination corners (shifted)
    dst = [(s[0] + d[0], s[1] + d[1]) for s, d in zip(src, shifts)]

    # Compute perspective coefficients
    coeffs = _find_perspective_coeffs(dst, src)
    result = img.transform(
        (w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC,
        fillcolor=(245, 245, 245),
    )

    # Forward transform function: original coords -> distorted coords
    fwd_coeffs = _find_perspective_coeffs(src, dst)

    def transform_fn(x: float, y: float) -> tuple[float, float]:
        a, b, c, d, e, f, g, hh = fwd_coeffs
        denom = g * x + hh * y + 1.0
        if abs(denom) < 1e-10:
            return x, y
        nx = (a * x + b * y + c) / denom
        ny = (d * x + e * y + f) / denom
        return nx, ny

    return result, transform_fn


def _find_perspective_coeffs(
    src: list[tuple[float, float]],
    dst: list[tuple[float, float]],
) -> tuple:
    """Find 8 perspective transform coefficients.

    Maps src quadrilateral to dst quadrilateral.
    """
    # Set up the linear system: Ax = b
    A = []
    b = []
    for (sx, sy), (dx, dy) in zip(src, dst):
        A.append([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy])
        A.append([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy])
        b.append(dx)
        b.append(dy)
    A = np.array(A, dtype=np.float64)
    b = np.array(b, dtype=np.float64)
    try:
        x = np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return (1, 0, 0, 0, 1, 0, 0, 0)
    return tuple(x.tolist())


def _barrel_distortion(
    img: Image.Image, rng: random.Random,
    k_range: tuple[float, float] = (0.00, 0.10),
) -> tuple[Image.Image, callable]:
    """Barrel distortion (fisheye effect).

    Returns (image, transform_function).
    """
    w, h = img.size
    k = rng.uniform(*k_range)
    if k < 0.005:
        # Negligible distortion, skip
        return img, lambda x, y: (x, y)

    cx, cy = w / 2.0, h / 2.0
    max_r = math.sqrt(cx**2 + cy**2)

    arr = np.array(img)
    result = np.full_like(arr, 245)  # light gray fill

    # Build coordinate maps
    ys, xs = np.mgrid[0:h, 0:w]
    # Normalize to [-1, 1]
    xn = (xs - cx) / max_r
    yn = (ys - cy) / max_r
    r2 = xn**2 + yn**2
    # Inverse barrel: find source coords for each destination pixel
    factor = 1.0 / (1.0 + k * r2)
    src_x = (xn * factor * max_r + cx).astype(np.float32)
    src_y = (yn * factor * max_r + cy).astype(np.float32)

    # Clip to valid range
    src_x = np.clip(src_x, 0, w - 1).astype(int)
    src_y = np.clip(src_y, 0, h - 1).astype(int)

    result = arr[src_y, src_x]

    # Forward transform: original coords -> barrel distorted coords
    def transform_fn(x: float, y: float) -> tuple[float, float]:
        xn = (x - cx) / max_r
        yn = (y - cy) / max_r
        r2 = xn**2 + yn**2
        fwd_factor = 1.0 + k * r2
        nx = xn * fwd_factor * max_r + cx
        ny = yn * fwd_factor * max_r + cy
        return nx, ny

    return Image.fromarray(result), transform_fn


def _slight_rotation(
    img: Image.Image, rng: random.Random,
    max_degrees: float = 1.5,
) -> tuple[Image.Image, callable]:
    """Slight rotation to simulate imperfect document placement."""
    angle = rng.uniform(-max_degrees, max_degrees)
    if abs(angle) < 0.1:
        return img, lambda x, y: (x, y)

    w, h = img.size
    result = img.rotate(
        angle, resample=Image.BICUBIC, expand=False,
        fillcolor=(245, 245, 245),
    )

    # Forward transform: rotate point around center
    cx, cy = w / 2.0, h / 2.0
    rad = math.radians(-angle)  # negative because PIL rotates CCW
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def transform_fn(x: float, y: float) -> tuple[float, float]:
        dx, dy = x - cx, y - cy
        nx = cos_a * dx - sin_a * dy + cx
        ny = sin_a * dx + cos_a * dy + cy
        return nx, ny

    return result, transform_fn


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

@dataclass
class AugmentationConfig:
    """Configuration for the augmentation pipeline."""
    # Probability of applying each augmentation
    p_noise: float = 0.7
    p_brightness: float = 0.6
    p_contrast: float = 0.6
    p_blur: float = 0.5
    p_jpeg: float = 0.8
    p_downscale: float = 0.5
    p_perspective: float = 0.4
    p_barrel: float = 0.3
    p_rotation: float = 0.5

    # Intensity ranges
    noise_sigma: tuple[float, float] = (3, 15)
    brightness_range: tuple[float, float] = (0.8, 1.2)
    contrast_range: tuple[float, float] = (0.8, 1.3)
    blur_radius: tuple[float, float] = (0.5, 1.5)
    jpeg_quality: tuple[int, int] = (40, 85)
    downscale_factor: tuple[float, float] = (0.4, 0.8)
    perspective_shift: float = 0.03
    barrel_k: tuple[float, float] = (0.01, 0.10)
    rotation_degrees: float = 1.5


# No augmentation — for generating clean ground truth
CLEAN_CONFIG = AugmentationConfig(
    p_noise=0, p_brightness=0, p_contrast=0, p_blur=0,
    p_jpeg=0, p_downscale=0, p_perspective=0, p_barrel=0, p_rotation=0,
)

# Light augmentation — minor camera artifacts
LIGHT_CONFIG = AugmentationConfig(
    p_noise=0.5, p_brightness=0.5, p_contrast=0.4, p_blur=0.3,
    p_jpeg=0.6, p_downscale=0.3, p_perspective=0.2, p_barrel=0.1, p_rotation=0.3,
    noise_sigma=(2, 8), blur_radius=(0.3, 0.8), jpeg_quality=(65, 90),
    perspective_shift=0.015, barrel_k=(0.005, 0.04), rotation_degrees=0.8,
)

# Heavy augmentation — rough camera capture
HEAVY_CONFIG = AugmentationConfig(
    p_noise=0.9, p_brightness=0.8, p_contrast=0.8, p_blur=0.7,
    p_jpeg=0.9, p_downscale=0.7, p_perspective=0.6, p_barrel=0.5, p_rotation=0.7,
    noise_sigma=(8, 25), blur_radius=(0.8, 2.5), jpeg_quality=(25, 60),
    downscale_factor=(0.3, 0.6), perspective_shift=0.05,
    barrel_k=(0.03, 0.15), rotation_degrees=2.5,
)

PRESETS = {
    "clean": CLEAN_CONFIG,
    "light": LIGHT_CONFIG,
    "default": AugmentationConfig(),
    "heavy": HEAVY_CONFIG,
}


def augment_image(
    img: Image.Image,
    config: AugmentationConfig | None = None,
    rng: random.Random | None = None,
) -> AugmentationResult:
    """Apply a random set of augmentations to a document image.

    Returns an AugmentationResult with the augmented image and a
    transform function for mapping bounding boxes.

    Spatial transforms (perspective, barrel, rotation) are applied first,
    then pixel-level transforms (noise, blur, JPEG, etc.).
    """
    if config is None:
        config = AugmentationConfig()
    if rng is None:
        rng = random.Random()

    img = img.convert("RGB")
    applied = []
    transforms = []

    # --- Spatial transforms first (order matters for bbox mapping) ---

    if rng.random() < config.p_rotation:
        img, tfn = _slight_rotation(img, rng, config.rotation_degrees)
        transforms.append(tfn)
        applied.append("rotation")

    if rng.random() < config.p_perspective:
        img, tfn = _perspective_transform(img, rng, config.perspective_shift)
        transforms.append(tfn)
        applied.append("perspective")

    if rng.random() < config.p_barrel:
        img, tfn = _barrel_distortion(img, rng, config.barrel_k)
        transforms.append(tfn)
        applied.append("barrel_distortion")

    # --- Pixel-level transforms (no bbox change) ---

    if rng.random() < config.p_brightness:
        img = _adjust_brightness(img, rng, config.brightness_range)
        applied.append("brightness")

    if rng.random() < config.p_contrast:
        img = _adjust_contrast(img, rng, config.contrast_range)
        applied.append("contrast")

    if rng.random() < config.p_blur:
        img = _gaussian_blur(img, rng, config.blur_radius)
        applied.append("blur")

    if rng.random() < config.p_noise:
        img = _add_gaussian_noise(img, rng, config.noise_sigma)
        applied.append("noise")

    if rng.random() < config.p_downscale:
        img, _ = _downscale(img, rng, config.downscale_factor)
        applied.append("downscale")

    # JPEG compression last (common in real pipelines)
    if rng.random() < config.p_jpeg:
        img = _jpeg_compress(img, rng, config.jpeg_quality)
        applied.append("jpeg")

    return AugmentationResult(
        image=img,
        applied=applied,
        _transforms=transforms,
    )
