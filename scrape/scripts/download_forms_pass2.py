"""
Second pass — targeted searches for missing state DMV forms.
Uses broader queries and alternative search strategies.
"""

import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from ddgs import DDGS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

MISSING_REGISTRATION = [
    "Arkansas", "Colorado", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Kentucky", "Maryland", "Massachusetts",
    "Minnesota", "Mississippi", "Nebraska", "Oklahoma", "South Dakota", "Wyoming",
]

MISSING_TAX = [
    "Colorado", "Connecticut", "Iowa", "Kentucky", "Montana",
    "New Hampshire", "North Carolina", "Ohio", "Oklahoma", "Tennessee",
    "Vermont", "West Virginia",
]

# Broader and more varied query templates
REG_QUERIES = [
    '"{state}" application for certificate of title registration pdf',
    '"{state}" DMV registration application form filetype:pdf',
    '"{state}" motor vehicle title registration form download',
    '"{state}" department of motor vehicles registration application',
    '"{state}" vehicle registration form pdf',
    '"{state}" title and registration application pdf',
    '"{state}" MVD registration form pdf',
    '"{state}" secretary of state vehicle registration form pdf',
]

TAX_QUERIES = [
    '"{state}" motor vehicle excise tax form pdf',
    '"{state}" vehicle purchase tax form pdf',
    '"{state}" sales tax exemption vehicle form pdf',
    '"{state}" use tax return motor vehicle pdf',
    '"{state}" department of revenue vehicle tax form pdf',
    '"{state}" vehicle tax declaration form pdf',
    '"{state}" title tax form pdf',
    '"{state}" motor vehicle tax pdf site:.gov',
]


def search_for_pdf(queries: list[str], ddgs: DDGS) -> list[str]:
    """Try multiple search queries, return all unique PDF URLs found."""
    found_urls = []
    seen = set()

    for query in queries:
        time.sleep(2.5)
        try:
            results = list(ddgs.text(query, max_results=10))
        except Exception as e:
            if "ratelimit" in str(e).lower():
                print("    Rate limited, waiting 45s...")
                time.sleep(45)
                continue
            continue

        for r in results:
            url = r.get("href", "")
            if url in seen:
                continue
            seen.add(url)

            lower = url.lower()
            # Direct PDF link
            if lower.endswith(".pdf") or ".pdf" in urlparse(url).path.lower():
                found_urls.append(url)

    return found_urls


def download_pdf(url: str, filepath: Path, session: requests.Session) -> bool:
    """Download a PDF file."""
    try:
        resp = session.get(url, timeout=30, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").lower()

        if "html" in content_type and "pdf" not in content_type:
            return False

        data = resp.content

        # Check PDF magic bytes
        if not data[:5].startswith(b"%PDF"):
            return False

        if len(data) < 2000:
            return False

        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(data)
        size_kb = len(data) / 1024
        print(f"    Saved: {filepath.name} ({size_kb:.0f} KB) from {url[:80]}")
        return True

    except requests.RequestException:
        return False


def try_download_form(state: str, form_type: str, query_templates: list[str],
                      form_dir: Path, session: requests.Session, ddgs: DDGS) -> bool:
    safe_name = state.replace(" ", "_")
    pdf_path = form_dir / f"{safe_name}.pdf"

    if pdf_path.exists() and pdf_path.stat().st_size > 2000:
        print(f"  [{state}] Already have {form_type}, skipping")
        return True

    print(f"  [{state}] Searching for {form_type}...")
    queries = [q.format(state=state) for q in query_templates]
    pdf_urls = search_for_pdf(queries, ddgs)

    if not pdf_urls:
        print(f"    No PDF URLs found for {state}")
        return False

    print(f"    Found {len(pdf_urls)} candidate PDFs, trying downloads...")
    for url in pdf_urls[:5]:  # Try up to 5 candidates
        time.sleep(1)
        if download_pdf(url, pdf_path, session):
            return True

    print(f"    All download attempts failed for {state}")
    return False


def main():
    base_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("scraped_vehicle_titles")

    session = requests.Session()
    session.headers.update(HEADERS)
    ddgs = DDGS()

    reg_dir = base_dir / "Registration"
    tax_dir = base_dir / "Tax Form"

    still_missing_reg = []
    still_missing_tax = []

    print("=" * 60)
    print("  PASS 2: Missing Registration Forms")
    print("=" * 60)
    for state in MISSING_REGISTRATION:
        if not try_download_form(state, "registration", REG_QUERIES, reg_dir, session, ddgs):
            still_missing_reg.append(state)

    print("\n" + "=" * 60)
    print("  PASS 2: Missing Tax Forms")
    print("=" * 60)
    for state in MISSING_TAX:
        if not try_download_form(state, "tax form", TAX_QUERIES, tax_dir, session, ddgs):
            still_missing_tax.append(state)

    # Summary
    reg_count = len(list(reg_dir.glob("*.pdf")))
    tax_count = len(list(tax_dir.glob("*.pdf")))

    print(f"\n{'='*60}")
    print("  FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"\n  Registration: {reg_count}/50 states")
    if still_missing_reg:
        print(f"    Still missing: {', '.join(still_missing_reg)}")
    print(f"\n  Tax Forms: {tax_count}/50 states")
    if still_missing_tax:
        print(f"    Still missing: {', '.join(still_missing_tax)}")


if __name__ == "__main__":
    main()
