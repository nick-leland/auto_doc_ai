"""
Download vehicle registration and tax forms from state DMV websites.
Uses DuckDuckGo to find the PDF URLs, then downloads them.
"""

import os
import sys
import time
import re
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests
from ddgs import DDGS

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
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

FORM_TYPES = {
    "Registration": [
        '"{state}" vehicle registration application form pdf site:.gov',
        '"{state}" DMV vehicle registration form pdf',
        '"{state}" application for registration title pdf site:.gov',
        '"{state}" motor vehicle registration form pdf',
    ],
    "Tax Form": [
        '"{state}" vehicle sales tax form pdf site:.gov',
        '"{state}" motor vehicle use tax form pdf site:.gov',
        '"{state}" vehicle tax form pdf DMV',
        '"{state}" sales use tax motor vehicle pdf site:.gov',
        '"{state}" title ad valorem tax form pdf',
    ],
}


def search_for_pdf(queries: list[str], ddgs: DDGS) -> str | None:
    """Try multiple search queries to find a PDF URL."""
    for query in queries:
        time.sleep(2)
        try:
            results = list(ddgs.text(query, max_results=10))
        except Exception as e:
            if "ratelimit" in str(e).lower():
                print("    Rate limited, waiting 30s...")
                time.sleep(30)
                ddgs = DDGS()
                continue
            print(f"    Search error: {e}")
            continue

        for r in results:
            url = r.get("href", "")
            # Prefer .gov PDF links
            if url.lower().endswith(".pdf"):
                return url
            # Check for PDF in URL path
            parsed = urlparse(url)
            if ".pdf" in parsed.path.lower():
                return url

        # Second pass: accept non-.gov PDFs
        for r in results:
            url = r.get("href", "")
            if "pdf" in url.lower() and ("form" in url.lower() or "application" in url.lower()):
                return url

    return None


def download_pdf(url: str, filepath: Path, session: requests.Session) -> bool:
    """Download a PDF file."""
    try:
        resp = session.get(url, timeout=30, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").lower()

        # If we got HTML instead of PDF, the link might be a landing page
        if "html" in content_type and "pdf" not in content_type:
            print(f"    Got HTML instead of PDF, skipping: {url[:80]}")
            return False

        # Verify it's a reasonable size for a PDF
        if len(resp.content) < 1000:
            print(f"    File too small ({len(resp.content)} bytes), skipping")
            return False

        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(resp.content)
        size_kb = len(resp.content) / 1024
        print(f"    Saved: {filepath.name} ({size_kb:.0f} KB)")
        return True

    except requests.RequestException as e:
        print(f"    Download failed: {e}")
        return False


def main():
    base_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("scraped_vehicle_titles")

    session = requests.Session()
    session.headers.update(HEADERS)
    ddgs = DDGS()

    results = {"Registration": {"found": 0, "missing": []}, "Tax Form": {"found": 0, "missing": []}}

    for form_type, query_templates in FORM_TYPES.items():
        form_dir = base_dir / form_type
        form_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n{'='*60}")
        print(f"  Downloading: {form_type}")
        print(f"{'='*60}")

        for state in STATES:
            safe_name = state.replace(" ", "_")
            pdf_path = form_dir / f"{safe_name}.pdf"

            # Skip if already downloaded
            if pdf_path.exists() and pdf_path.stat().st_size > 1000:
                print(f"  [{state}] Already have {pdf_path.name}, skipping")
                results[form_type]["found"] += 1
                continue

            print(f"  [{state}] Searching for {form_type.lower()}...")
            queries = [q.format(state=state) for q in query_templates]
            pdf_url = search_for_pdf(queries, ddgs)

            if pdf_url:
                print(f"    Found: {pdf_url[:80]}")
                time.sleep(1)
                if download_pdf(pdf_url, pdf_path, session):
                    results[form_type]["found"] += 1
                else:
                    results[form_type]["missing"].append(state)
            else:
                print(f"    No PDF found for {state}")
                results[form_type]["missing"].append(state)

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for form_type, stats in results.items():
        print(f"\n  {form_type}: {stats['found']}/50 states")
        if stats["missing"]:
            print(f"    Missing: {', '.join(stats['missing'])}")


if __name__ == "__main__":
    main()
