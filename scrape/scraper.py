"""
Vehicle Title Image Scraper

Scrapes vehicle title images from web searches, eBay, DMV sites,
auction sites, and title guides. Uses DuckDuckGo text search to find
pages, then scrapes those pages for images. Organizes results by US state.
"""

import csv
import hashlib
import io
import logging
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
from PIL import Image
from tqdm.auto import tqdm

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

JUNK_URL_PATTERNS = re.compile(
    r"(logo|icon|sprite|banner|avatar|badge|button|arrow|spacer|pixel"
    r"|tracking|analytics|ad[sx]?[\-_/]|doubleclick|facebook\.com/tr"
    r"|\.gif$|1x1|transparent|placeholder|loading|spinner"
    r"|gravatar|emoji|smil|thumb.*nail.*s?/|/feed/|\.svg)",
    re.IGNORECASE,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20MB cap
MIN_IMAGE_BYTES = 10_000  # 10KB floor — filters out most thumbnails/icons
MIN_IMAGE_DIM = 300  # pixels — reject images smaller than this in either dimension
MAX_ASPECT_RATIO = 4.0  # reject extremely tall/narrow images (full-page screenshots)
LIGHT_PIXEL_THRESHOLD = 0.4  # at least 40% of pixels should be light (document-like)
LIGHT_PIXEL_VALUE = 180  # RGB value above which a pixel counts as "light"

# Keywords that suggest an <img> tag is a document (checked against alt/title/src)
DOC_KEYWORDS = re.compile(
    r"(title|certificate|document|dmv|registration|salvage|rebuilt|pink.?slip"
    r"|transfer|lien|odometer|vin|vehicle.?id|dept.?of.?motor"
    r"|state.?of|form|application|notary|bill.?of.?sale)",
    re.IGNORECASE,
)

METADATA_COLUMNS = [
    "filename", "state", "source_url", "image_url", "source_type",
    "search_query", "content_hash", "downloaded_at", "file_size_bytes",
    "width", "height",
]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

class RateLimiter:
    """Enforces a minimum delay between calls."""

    def __init__(self, min_delay: float = 2.0):
        self.min_delay = min_delay
        self._last_call = 0.0

    def wait(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self._last_call = time.time()


class ImageDeduplicator:
    """Tracks images by SHA-256 to prevent duplicate saves."""

    def __init__(self):
        self._seen: set[str] = set()

    def is_duplicate(self, data: bytes) -> bool:
        h = hashlib.sha256(data).hexdigest()
        return h in self._seen

    def register(self, data: bytes) -> str:
        h = hashlib.sha256(data).hexdigest()
        self._seen.add(h)
        return h

    def add_known(self, hash_hex: str):
        self._seen.add(hash_hex)

    @property
    def seen_count(self) -> int:
        return len(self._seen)


class MetadataTracker:
    """Manages a CSV log of all downloaded images."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.csv_path = os.path.join(output_dir, "metadata.csv")
        self.records: list[dict] = []

    def load_existing(self) -> list[dict]:
        """Load records from a previous run for resumption."""
        if not os.path.exists(self.csv_path):
            return []
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.records = list(reader)
        log.info("Loaded %d existing records from %s", len(self.records), self.csv_path)
        return self.records

    def add_record(self, record: dict):
        self.records.append(record)

    def save(self):
        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=METADATA_COLUMNS)
            writer.writeheader()
            writer.writerows(self.records)

    @property
    def count(self) -> int:
        return len(self.records)


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

class TitleImageScraper:
    """Orchestrates searching, downloading, and organizing vehicle title images."""

    def __init__(
        self,
        output_dir: str = "vehicle_titles",
        rate_limit: float = 3.0,
        max_results_per_query: int = 10,
    ):
        self.output_dir = output_dir
        self.max_results_per_query = max_results_per_query
        self.rate_limiter = RateLimiter(min_delay=rate_limit)
        self.deduplicator = ImageDeduplicator()
        self.metadata = MetadataTracker(output_dir)
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._ddgs = DDGS()
        self._ddgs_backoff = 15  # initial backoff seconds
        self._consecutive_ratelimits = 0

    # ------------------------------------------------------------------
    # Query generation
    # ------------------------------------------------------------------

    def build_search_queries(
        self,
        states: list[str] | None = None,
        source_types: list[str] | None = None,
    ) -> list[dict]:
        """Build text search queries for each state and source type.

        Returns list of dicts: {"query", "state", "source_type"}
        All queries use text search — we then scrape the resulting pages for images.
        """
        target_states = states or US_STATES
        all_types = {"ebay", "dmv", "auction", "guide", "general"}
        active_types = set(source_types) if source_types else all_types

        queries = []

        for state in target_states:
            # General searches — find pages with title document images
            if "general" in active_types:
                for q in [
                    f'"{state} vehicle title" document photo',
                    f'"{state} car title" certificate image',
                    f'"{state} certificate of title" example',
                    f'"{state} salvage title" OR "{state} rebuilt title" photo',
                ]:
                    queries.append({
                        "query": q, "state": state, "source_type": "general",
                    })

            # DMV / government sources
            if "dmv" in active_types:
                for q in [
                    f'"{state}" "certificate of title" site:.gov',
                    f'"{state} DMV" vehicle title example',
                    f'"{state}" title application form sample',
                ]:
                    queries.append({
                        "query": q, "state": state, "source_type": "dmv",
                    })

            # eBay
            if "ebay" in active_types:
                queries.append({
                    "query": f'site:ebay.com "{state}" vehicle title document',
                    "state": state, "source_type": "ebay",
                })

            # Auction sites
            if "auction" in active_types:
                queries.append({
                    "query": f'"{state} title" site:copart.com OR site:iaai.com',
                    "state": state, "source_type": "auction",
                })

            # Guides / how-to / example posts
            if "guide" in active_types:
                for q in [
                    f'"how to fill out" "{state}" vehicle title',
                    f'"{state}" "pink slip" OR "title transfer" example photo',
                    f'"{state} title" site:reddit.com OR site:imgur.com',
                ]:
                    queries.append({
                        "query": q, "state": state, "source_type": "guide",
                    })

        return queries

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_text(self, query: str, max_results: int | None = None) -> list[dict]:
        """Use DuckDuckGo text search. Returns list of result dicts with 'href' key."""
        mr = max_results or self.max_results_per_query
        self.rate_limiter.wait()
        try:
            results = list(self._ddgs.text(query, max_results=mr))
            # Successful search — reset backoff
            self._consecutive_ratelimits = 0
            self._ddgs_backoff = 15
            return results
        except Exception as e:
            if "ratelimit" in str(e).lower() or "403" in str(e):
                self._handle_ddgs_ratelimit()
                return []
            log.warning("Text search failed for %r: %s", query, e)
            return []

    def _handle_ddgs_ratelimit(self):
        self._consecutive_ratelimits += 1
        wait = min(self._ddgs_backoff * (2 ** (self._consecutive_ratelimits - 1)), 300)
        log.warning(
            "DuckDuckGo rate limit hit (%d consecutive) — backing off %ds",
            self._consecutive_ratelimits, wait,
        )
        time.sleep(wait)
        # Recreate the DDGS client to get a fresh session
        self._ddgs = DDGS()

    # ------------------------------------------------------------------
    # Page scraping
    # ------------------------------------------------------------------

    def scrape_images_from_page(self, url: str) -> list[str]:
        """Fetch a web page and extract likely vehicle-title image URLs.

        Returns URLs sorted with document-keyword matches first.
        """
        self.rate_limiter.wait()
        try:
            resp = self._session.get(url, timeout=15, allow_redirects=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.debug("Failed to fetch page %s: %s", url, e)
            return []

        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        priority = []  # images with document keywords in alt/title/src
        other = []

        # <img> tags
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if not src:
                continue
            src = urljoin(url, src)
            if self._is_junk_url(src):
                continue
            # Skip small images (when dimensions are declared in HTML)
            w = _parse_dim(img.get("width"))
            h = _parse_dim(img.get("height"))
            if (w and w < 250) or (h and h < 250):
                continue
            # Check if alt text, title attr, or src path hints at a document
            text_blob = " ".join(filter(None, [
                img.get("alt", ""), img.get("title", ""), src,
            ]))
            if DOC_KEYWORDS.search(text_blob):
                priority.append(src)
            else:
                other.append(src)

        # <a> tags linking directly to images
        for a in soup.find_all("a", href=True):
            href = a["href"]
            parsed = urlparse(href)
            ext = os.path.splitext(parsed.path)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                full = urljoin(url, href)
                if not self._is_junk_url(full):
                    text_blob = " ".join(filter(None, [a.get_text(), full]))
                    if DOC_KEYWORDS.search(text_blob):
                        priority.append(full)
                    else:
                        other.append(full)

        # Only return keyword-matched images when we have them.
        # Fall back to other images only if no keyword matches found on the page,
        # capped at 3 to limit noise.
        pool = priority if priority else other[:3]

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for c in pool:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        return unique

    @staticmethod
    def _is_junk_url(url: str) -> bool:
        return bool(JUNK_URL_PATTERNS.search(url))

    # ------------------------------------------------------------------
    # Download & validate
    # ------------------------------------------------------------------

    def download_image(
        self,
        image_url: str,
        state: str,
        source_type: str,
        source_url: str,
        search_query: str,
    ) -> bool:
        """Download, validate, deduplicate, and save one image. Returns True if saved."""
        self.rate_limiter.wait()
        try:
            resp = self._session.get(image_url, timeout=15, stream=True)
            resp.raise_for_status()
        except requests.RequestException:
            return False

        ct = resp.headers.get("content-type", "")
        if not ct.startswith("image/"):
            return False

        data = resp.content
        if len(data) > MAX_IMAGE_BYTES:
            return False

        if not self.is_valid_image(data):
            return False

        if self.deduplicator.is_duplicate(data):
            return False

        content_hash = self.deduplicator.register(data)
        ext = self._guess_extension(ct, image_url)
        width, height = self._image_dimensions(data)

        state_dir = os.path.join(self.output_dir, _normalize_dirname(state))
        os.makedirs(state_dir, exist_ok=True)
        filename = f"{content_hash[:16]}.{ext}"
        filepath = os.path.join(state_dir, filename)

        with open(filepath, "wb") as f:
            f.write(data)

        self.metadata.add_record({
            "filename": filename,
            "state": state,
            "source_url": source_url,
            "image_url": image_url,
            "source_type": source_type,
            "search_query": search_query,
            "content_hash": content_hash,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "file_size_bytes": len(data),
            "width": width,
            "height": height,
        })
        return True

    @staticmethod
    def is_valid_image(data: bytes, min_size: int = MIN_IMAGE_BYTES) -> bool:
        """Check bytes are a real image with reasonable size, dimensions, and document-like colors."""
        if len(data) < min_size:
            return False
        try:
            img = Image.open(io.BytesIO(data))
            img.verify()
            # Re-open to get dimensions and pixel data (verify() consumes the stream)
            img = Image.open(io.BytesIO(data))
            w, h = img.size
            # Too small in either dimension
            if w < MIN_IMAGE_DIM or h < MIN_IMAGE_DIM:
                return False
            # Extreme aspect ratio — likely a full-page screenshot, not a title doc
            ratio = max(w, h) / max(min(w, h), 1)
            if ratio > MAX_ASPECT_RATIO:
                return False
            # Light-pixel check: documents have lots of white/cream/light-colored area.
            # Sample the image at reduced size for speed.
            thumb = img.convert("L").resize((100, 100))
            try:
                pixels = list(thumb.get_flattened_data())
            except AttributeError:
                pixels = list(thumb.getdata())
            light_count = sum(1 for p in pixels if p >= LIGHT_PIXEL_VALUE)
            if light_count / len(pixels) < LIGHT_PIXEL_THRESHOLD:
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def _image_dimensions(data: bytes) -> tuple[int | None, int | None]:
        try:
            img = Image.open(io.BytesIO(data))
            return img.size  # (width, height)
        except Exception:
            return (None, None)

    @staticmethod
    def _guess_extension(content_type: str, url: str) -> str:
        ct_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/bmp": "bmp",
            "image/tiff": "tiff",
        }
        for ct, ext in ct_map.items():
            if ct in content_type:
                return ext
        parsed = urlparse(url)
        ext = os.path.splitext(parsed.path)[1].lower().lstrip(".")
        return ext if ext in {"jpg", "jpeg", "png", "webp", "bmp", "tiff"} else "jpg"

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def resume(self):
        """Load existing metadata so we can skip already-downloaded images."""
        existing = self.metadata.load_existing()
        for record in existing:
            if "content_hash" in record and record["content_hash"]:
                self.deduplicator.add_known(record["content_hash"])

    def run(
        self,
        states: list[str] | None = None,
        source_types: list[str] | None = None,
        progress: bool = True,
    ) -> dict:
        """Run the full scraping pipeline. Returns summary stats."""
        self.resume()

        queries = self.build_search_queries(states=states, source_types=source_types)
        log.info("Generated %d search queries", len(queries))

        stats = {"queries_run": 0, "images_found": 0, "images_saved": 0, "errors": 0}
        pbar = tqdm(queries, desc="Scraping", disable=not progress)

        for qinfo in pbar:
            query = qinfo["query"]
            state = qinfo["state"]
            source_type = qinfo["source_type"]
            pbar.set_postfix_str(f"{state} / {source_type}")

            try:
                self._process_query(query, state, source_type, stats)
            except Exception as e:
                log.warning("Error processing query %r: %s", query, e)
                stats["errors"] += 1

            stats["queries_run"] += 1

            # Save metadata periodically
            if stats["queries_run"] % 10 == 0:
                self.metadata.save()

        self.metadata.save()

        stats["total_images"] = self.metadata.count
        stats["unique_hashes"] = self.deduplicator.seen_count
        log.info(
            "Done. %d images saved (%d found, %d queries, %d errors).",
            stats["images_saved"], stats["images_found"],
            stats["queries_run"], stats["errors"],
        )
        return stats

    def _process_query(self, query: str, state: str, source_type: str, stats: dict):
        """Run a text search query, scrape result pages for images, download them."""
        results = self.search_text(query)
        for r in results:
            page_url = r.get("href", "")
            if not page_url:
                continue
            image_urls = self.scrape_images_from_page(page_url)
            for img_url in image_urls[:15]:  # cap per page
                stats["images_found"] += 1
                if self.download_image(img_url, state, source_type, page_url, query):
                    stats["images_saved"] += 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_dirname(state: str) -> str:
    return state.strip().replace(" ", "_")


def _parse_dim(val) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).replace("px", "").strip())
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape vehicle title images")
    parser.add_argument("--output", "-o", default="vehicle_titles", help="Output directory")
    parser.add_argument("--states", nargs="*", default=None, help="States to scrape (default: all)")
    parser.add_argument("--sources", nargs="*", default=None,
                        help="Source types: general, ebay, dmv, auction, guide")
    parser.add_argument("--rate-limit", type=float, default=3.0, help="Seconds between requests")
    parser.add_argument("--max-results", type=int, default=10, help="Max results per search query")
    args = parser.parse_args()

    scraper = TitleImageScraper(
        output_dir=args.output,
        rate_limit=args.rate_limit,
        max_results_per_query=args.max_results,
    )
    result = scraper.run(states=args.states, source_types=args.sources)
    print(f"\nSummary: {result}")
