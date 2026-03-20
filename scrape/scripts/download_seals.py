"""
Download US state seals/insignias from Wikimedia Commons as SVGs.
State seals are public domain (US government works).
"""

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request

STATES = [
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
    "User-Agent": "VehicleTitleScraper/1.0 (educational project; polite bot)"
}

# Wikimedia Commons API endpoint
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def search_commons(query: str, limit: int = 5) -> list[dict]:
    """Search Wikimedia Commons for files matching a query."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": "6",  # File namespace
        "srlimit": str(limit),
        "format": "json",
    }
    url = COMMONS_API + "?" + "&".join(f"{k}={quote(v)}" for k, v in params.items())
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return data.get("query", {}).get("search", [])


def get_file_url(filename: str) -> str | None:
    """Get the direct download URL for a Wikimedia Commons file."""
    params = {
        "action": "query",
        "titles": filename,
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "format": "json",
    }
    url = COMMONS_API + "?" + "&".join(f"{k}={quote(v)}" for k, v in params.items())
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        imageinfo = page.get("imageinfo", [{}])
        if imageinfo:
            return imageinfo[0].get("url")
    return None


def download_file(url: str, filepath: Path) -> bool:
    """Download a file from a URL."""
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=30) as resp:
            data = resp.read()

        if len(data) < 500:
            return False

        filepath.write_bytes(data)
        size_kb = len(data) / 1024
        print(f"    Saved: {filepath.name} ({size_kb:.0f} KB)")
        return True
    except Exception as e:
        print(f"    Download failed: {e}")
        return False


def find_and_download_seal(state: str, output_dir: Path) -> bool:
    """Search for a state seal SVG on Wikimedia Commons and download it."""
    safe_name = state.replace(" ", "_")
    svg_path = output_dir / f"{safe_name}.svg"
    png_path = output_dir / f"{safe_name}.png"

    if svg_path.exists() and svg_path.stat().st_size > 500:
        print(f"  [{state}] Already have SVG, skipping")
        return True
    if png_path.exists() and png_path.stat().st_size > 500:
        print(f"  [{state}] Already have PNG, skipping")
        return True

    print(f"  [{state}] Searching...")

    # Try multiple search queries
    search_queries = [
        f"Seal of {state}",
        f"Great Seal of the State of {state}",
        f"{state} state seal",
    ]

    for query in search_queries:
        time.sleep(1)
        try:
            results = search_commons(query)
        except Exception as e:
            print(f"    Search error: {e}")
            continue

        for r in results:
            title = r.get("title", "")
            title_lower = title.lower()

            # Filter: must mention seal and state name
            if "seal" not in title_lower:
                continue
            if state.lower() not in title_lower and safe_name.lower() not in title_lower:
                continue

            # Prefer SVG files
            is_svg = title_lower.endswith(".svg")
            is_png = title_lower.endswith(".png")

            if not (is_svg or is_png):
                continue

            time.sleep(0.5)
            file_url = get_file_url(title)
            if not file_url:
                continue

            target = svg_path if is_svg else png_path
            if download_file(file_url, target):
                return True

    print(f"    No seal found for {state}")
    return False


def main():
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("insignias")
    output_dir.mkdir(parents=True, exist_ok=True)

    found = 0
    missing = []

    for state in STATES:
        if find_and_download_seal(state, output_dir):
            found += 1
        else:
            missing.append(state)

    print(f"\n{'='*60}")
    print(f"  Downloaded {found}/50 state seals to {output_dir}/")
    if missing:
        print(f"  Missing: {', '.join(missing)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
