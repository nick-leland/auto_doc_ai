"""
State insignia (seal) watermark renderer.

Loads a state seal SVG, recolors it, and places it as a low-opacity
watermark within the inner content area of a document.
"""

import random
import xml.etree.ElementTree as ET
from pathlib import Path

import svgwrite

INSIGNIAS_DIR = Path("src/data/insignias")

SVG_NS = "http://www.w3.org/2000/svg"


def _strip_ns(elem: ET.Element) -> None:
    """Recursively strip the SVG namespace from tag names and attributes."""
    if elem.tag.startswith(f"{{{SVG_NS}}}"):
        elem.tag = elem.tag[len(f"{{{SVG_NS}}}"):]
    # Strip namespace from attributes too
    new_attrib = {}
    for k, v in elem.attrib.items():
        if k.startswith(f"{{{SVG_NS}}}"):
            new_attrib[k[len(f"{{{SVG_NS}}}"):]] = v
        elif k == "xmlns" or k.startswith("xmlns:"):
            continue  # drop xmlns declarations
        else:
            new_attrib[k] = v
    elem.attrib = new_attrib
    for child in elem:
        _strip_ns(child)


def _load_seal_svg(state_name: str) -> tuple[ET.Element | None, float, float]:
    """Load a state seal SVG and return (root_g_element, orig_width_pt, orig_height_pt).

    Returns (None, 0, 0) if the seal file doesn't exist.
    """
    # Normalize: "Rhode Island" -> "rhode_island"
    filename = state_name.lower().replace(" ", "_") + ".svg"
    path = INSIGNIAS_DIR / filename
    if not path.exists():
        return None, 0, 0

    tree = ET.parse(path)
    root = tree.getroot()

    # Parse original dimensions from viewBox or width/height
    viewbox = root.get("viewBox", "")
    if viewbox:
        parts = viewbox.split()
        orig_w = float(parts[2])
        orig_h = float(parts[3])
    else:
        # Fall back to width/height attributes (strip "pt" suffix)
        w_str = root.get("width", "3000").replace("pt", "").strip()
        h_str = root.get("height", "3000").replace("pt", "").strip()
        orig_w = float(w_str)
        orig_h = float(h_str)

    # Find the main <g> element containing the paths
    g_elem = root.find(f"{{{SVG_NS}}}g")
    if g_elem is None:
        g_elem = root.find("g")
    if g_elem is None:
        return None, 0, 0

    # Strip SVG namespace so we don't get duplicate xmlns in output
    _strip_ns(g_elem)

    return g_elem, orig_w, orig_h


class _RawSVGElement:
    """Wrapper to inject raw SVG XML into an svgwrite container."""
    elementname = "g"

    def __init__(self, element: ET.Element):
        self._xml = element

    def get_xml(self):
        return self._xml


def add_state_insignia(
    drawing: svgwrite.Drawing,
    state_name: str,
    inner_rect: tuple[float, float, float, float],
    color: str = "#2C5C9A",
    bg_color: str = "#E0E8F0",
    opacity: float = 0.08,
    scale_fraction: float = 0.45,
    rng: random.Random | None = None,
) -> bool:
    """Add a state seal watermark to the drawing.

    The seal is placed at a random position within inner_rect, fully visible
    (not clipped by the border). A background-colored circle is drawn first
    to mask out the security pattern beneath, then the seal is rendered in a
    single color at low opacity — like on real government documents.

    Args:
        drawing: svgwrite Drawing to add the insignia to.
        state_name: State name (e.g. "California", "Rhode Island").
        inner_rect: (x, y, w, h) of the content area inside the border.
        color: Fill color for the seal (should match document's accent color).
        bg_color: Document background color (used to mask the security pattern).
        opacity: Opacity of the watermark (0.0-1.0). Default 0.08.
        scale_fraction: Seal diameter as fraction of min(inner_w, inner_h).
        rng: Random instance for position selection.

    Returns:
        True if the insignia was added, False if the seal file wasn't found.
    """
    if rng is None:
        rng = random.Random()

    g_elem, orig_w, orig_h = _load_seal_svg(state_name)
    if g_elem is None:
        return False

    ix, iy, iw, ih = inner_rect

    # Target size: fraction of the smaller inner dimension
    target_size = min(iw, ih) * scale_fraction
    # The <g> transform includes scale(0.1, -0.1) which maps raw potrace coords
    # (~30000) down to viewBox units (~3000). So the rendered seal occupies
    # orig_w x orig_h SVG units after the <g> transform runs.
    seal_scale = target_size / max(orig_w, orig_h)

    seal_w = orig_w * seal_scale
    seal_h = orig_h * seal_scale

    # Random position: seal must be fully within inner_rect
    x_min = ix
    x_max = ix + iw - seal_w
    y_min = iy
    y_max = iy + ih - seal_h

    if x_max < x_min:
        x_max = x_min
    if y_max < y_min:
        y_max = y_min

    seal_x = rng.uniform(x_min, x_max)
    seal_y = rng.uniform(y_min, y_max)

    # Center of the seal in document coordinates
    cx = seal_x + seal_w / 2
    cy = seal_y + seal_h / 2
    radius = max(seal_w, seal_h) / 2

    # Draw a background-colored circle to clear the security pattern
    # beneath the seal. Slightly larger than the seal for a clean edge.
    drawing.add(drawing.circle(
        center=(cx, cy),
        r=radius * 1.05,
        fill=bg_color,
    ))

    # Override the fill on the existing <g>
    g_elem.set("fill", color)

    # Wrap in an outer <g> that translates + scales, and sets opacity.
    # The inner <g> already has the potrace flip transform.
    wrapper = ET.Element("g", {
        "transform": f"translate({seal_x:.2f},{seal_y:.2f}) scale({seal_scale:.6f})",
        "opacity": f"{opacity:.3f}",
    })
    wrapper.append(g_elem)

    drawing.add(_RawSVGElement(wrapper))
    return True
