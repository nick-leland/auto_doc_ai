"""
Generate a synthetic vehicle title dataset.

Uses Faker for people/company info, NHTSA VIN Decoder for vehicle data,
and the document layout engine to produce SVG + PNG + metadata files.

Usage:
    python generate_dataset.py --count 100 --output dataset/
    python generate_dataset.py --count 10 --output dataset/ --size small
"""

import argparse
import importlib.util
import json
import random
import shutil
import string
import time
from datetime import date, timedelta
from pathlib import Path

import subprocess

import requests
import svgwrite
from faker import Faker
from PIL import Image

from src.data.static import STATES
from src.document_layout import (
    build_random_layout,
    build_random_back_layout,
    solve_layout,
    render_layout,
    fill_values,
)
from src.utils.augmentation import (
    AugmentationConfig,
    AugmentationResult,
    augment_image,
    PRESETS as AUG_PRESETS,
)
from src.utils.annotation import build_annotations, to_layoutlmv3, to_ocr, to_key_value
from src.utils.background_generation import (
    BackgroundParams,
    add_background_to_drawing,
    add_background_no_border,
)
from src.utils.border_text import render_border_text
from src.utils.state_insignia import add_state_insignia

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Common WMI (World Manufacturer Identifier) prefixes → manufacturer name
# Position 10 encodes model year: A=2010, B=2011, ..., J=2018, K=2019,
# L=2020, M=2021, N=2022, P=2023, R=2024, S=2025
WMIS = [
    "1FA",  # Ford USA
    "1FT",  # Ford Truck
    "1G1",  # Chevrolet
    "1GC",  # Chevrolet Truck
    "1GT",  # GMC Truck
    "1HG",  # Honda
    "1J4",  # Jeep
    "1N4",  # Nissan
    "2HG",  # Honda Canada
    "2T1",  # Toyota Canada
    "3FA",  # Ford Mexico
    "3VW",  # Volkswagen Mexico
    "4T1",  # Toyota USA
    "4T3",  # Toyota Truck
    "5YJ",  # Tesla
    "JH4",  # Acura
    "JN1",  # Nissan Japan
    "JTD",  # Toyota Japan
    "KM8",  # Hyundai Korea
    "KNA",  # Kia
    "WBA",  # BMW
    "WDB",  # Mercedes-Benz
    "WVW",  # Volkswagen
    "YV1",  # Volvo
    "ZFF",  # Ferrari
]

YEAR_CODES = {
    2010: "A", 2011: "B", 2012: "C", 2013: "D", 2014: "E",
    2015: "F", 2016: "G", 2017: "H", 2018: "J", 2019: "K",
    2020: "L", 2021: "M", 2022: "N", 2023: "P", 2024: "R",
    2025: "S",
}

VIN_CHARS = "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"  # no I, O, Q

VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
VIN_TRANSLITERATION = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}

STATE_ABBREVS = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}

COLORS = [
    "BLACK", "WHITE", "SILVER", "GRAY", "RED", "BLUE", "GREEN",
    "BROWN", "BEIGE", "GOLD", "MAROON", "NAVY", "TAN", "ORANGE",
]

TITLE_TYPES = ["ORIGINAL", "ORIGINAL", "ORIGINAL", "DUPLICATE", "CORRECTED"]
TITLE_BRANDS = [
    "NONE", "NONE", "NONE", "NONE", "NONE", "NONE", "NONE",  # most are clean
    "SALVAGE", "REBUILT", "FLOOD", "LEMON LAW BUYBACK",
]

OWNERSHIP_TYPES = ["AND", "OR", "JTWROS", "AND", "OR"]

BG_PALETTES = [
    ("#E0E8F0", "#2C5C9A"),  # Blue
    ("#E4F0E0", "#2F6F3E"),  # Green
    ("#F0E8E0", "#8B4513"),  # Brown
    ("#E8E0F0", "#5B2C8A"),  # Purple
    ("#F0E0E0", "#8B1A1A"),  # Red
    ("#E0F0F0", "#1A6B6B"),  # Teal
    ("#F0F0E0", "#6B6B1A"),  # Olive
    ("#E8E8E8", "#333333"),  # Gray
]

# NHTSA API endpoint
NHTSA_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin/{}?format=json"

# Fallback models by manufacturer when NHTSA can't decode the VDS
MODELS_BY_MAKE = {
    "FORD": ["F-150", "ESCAPE", "EXPLORER", "FUSION", "MUSTANG", "EDGE", "RANGER"],
    "CHEVROLET": ["SILVERADO", "EQUINOX", "MALIBU", "TRAVERSE", "CAMARO", "TAHOE"],
    "GMC": ["SIERRA", "TERRAIN", "ACADIA", "CANYON", "YUKON"],
    "HONDA": ["CIVIC", "ACCORD", "CR-V", "PILOT", "HR-V", "ODYSSEY"],
    "TOYOTA": ["CAMRY", "COROLLA", "RAV4", "HIGHLANDER", "TACOMA", "4RUNNER"],
    "NISSAN": ["ALTIMA", "ROGUE", "SENTRA", "PATHFINDER", "FRONTIER", "MAXIMA"],
    "HYUNDAI": ["ELANTRA", "TUCSON", "SONATA", "SANTA FE", "KONA", "PALISADE"],
    "KIA": ["FORTE", "SPORTAGE", "SORENTO", "SELTOS", "TELLURIDE", "K5"],
    "BMW": ["3 SERIES", "5 SERIES", "X3", "X5", "4 SERIES", "X1"],
    "MERCEDES-BENZ": ["C-CLASS", "E-CLASS", "GLC", "GLE", "A-CLASS", "CLA"],
    "VOLKSWAGEN": ["JETTA", "TIGUAN", "ATLAS", "PASSAT", "GOLF", "TAOS"],
    "TESLA": ["MODEL 3", "MODEL Y", "MODEL S", "MODEL X"],
    "ACURA": ["TLX", "MDX", "RDX", "ILX", "INTEGRA"],
    "VOLVO": ["XC60", "XC90", "S60", "V60", "XC40"],
    "JEEP": ["WRANGLER", "GRAND CHEROKEE", "CHEROKEE", "COMPASS", "GLADIATOR"],
    "SUBARU": ["OUTBACK", "FORESTER", "CROSSTREK", "IMPREZA", "ASCENT"],
}

# Cache decoded VINs to avoid redundant API calls
_vin_cache: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# VIN generation + decoding
# ---------------------------------------------------------------------------

def _compute_check_digit(vin_no_check: str) -> str:
    """Compute the VIN check digit (position 9)."""
    total = 0
    for i, ch in enumerate(vin_no_check):
        if i == 8:
            continue  # skip position 9 (the check digit itself)
        if ch.isdigit():
            val = int(ch)
        else:
            val = VIN_TRANSLITERATION.get(ch, 0)
        total += val * VIN_WEIGHTS[i]
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def generate_vin(rng: random.Random, year: int | None = None) -> str:
    """Generate a VIN with valid structure and check digit."""
    wmi = rng.choice(WMIS)

    if year is None:
        year = rng.randint(2010, 2024)
    year_code = YEAR_CODES.get(year, "R")

    # Positions 4-8: vehicle descriptor (random valid chars)
    vds = "".join(rng.choices(VIN_CHARS, k=5))

    # Position 9: placeholder for check digit
    # Position 10: year code
    # Position 11: plant code (random letter)
    plant = rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ")

    # Positions 12-17: sequential number
    seq = "".join(rng.choices("0123456789", k=6))

    vin_no_check = wmi + vds + "0" + year_code + plant + seq
    check = _compute_check_digit(vin_no_check)
    vin = wmi + vds + check + year_code + plant + seq

    return vin


def decode_vin(vin: str) -> dict:
    """Decode a VIN via NHTSA API. Returns dict of useful fields."""
    if vin in _vin_cache:
        return _vin_cache[vin]

    try:
        resp = requests.get(NHTSA_URL.format(vin), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = {
            r["Variable"]: r["Value"]
            for r in data["Results"]
            if r["Value"] and r["Value"].strip()
        }
        decoded = {
            "make": (results.get("Make") or "").upper(),
            "model": (results.get("Model") or "").upper(),
            "year": results.get("Model Year", ""),
            "body": results.get("Body Class", ""),
            "cylinders": results.get("Engine Number of Cylinders", ""),
            "fuel": (results.get("Fuel Type - Primary") or "").upper(),
            "weight": "",  # NHTSA doesn't give curb weight directly
        }
        # Extract weight from GVWR if available
        gvwr = results.get("Gross Vehicle Weight Rating From", "")
        if gvwr and "lb" in gvwr.lower():
            # Extract first number
            import re
            nums = re.findall(r"[\d,]+", gvwr)
            if nums:
                decoded["weight"] = nums[0].replace(",", "")

        # Fill in model from fallback if NHTSA couldn't decode it
        if not decoded["model"] or decoded["model"] == "UNKNOWN":
            make = decoded.get("make", "").upper()
            models = MODELS_BY_MAKE.get(make, ["SEDAN"])
            decoded["model"] = random.choice(models)

        _vin_cache[vin] = decoded
        return decoded
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Person / document data generation
# ---------------------------------------------------------------------------

def generate_person(fake: Faker, rng: random.Random, state: str) -> dict:
    """Generate a realistic person with address in a specific state."""
    first = fake.first_name().upper()
    mi = rng.choice(string.ascii_uppercase)
    last = fake.last_name().upper()
    name = f"{first} {mi} {last}"

    abbr = STATE_ABBREVS[state]
    street = fake.street_address().upper()
    city = fake.city().upper()
    zipcode = fake.zipcode()

    return {
        "name": name,
        "first": first,
        "mi": mi,
        "last": last,
        "street": street,
        "city": city,
        "state_abbr": abbr,
        "zip": zipcode,
        "address": f"{street}, {city} {abbr} {zipcode}",
        "dl": f"{abbr}-{rng.randint(1000000, 9999999)}",
    }


def generate_company(fake: Faker, rng: random.Random, state: str) -> dict:
    """Generate a lien holder or dealership."""
    abbr = STATE_ABBREVS[state]
    name = fake.company().upper()
    street = fake.street_address().upper()
    city = fake.city().upper()
    zipcode = fake.zipcode()

    return {
        "name": name,
        "street": street,
        "city": city,
        "state_abbr": abbr,
        "zip": zipcode,
        "address": f"{street}, {city} {abbr} {zipcode}",
        "license": f"DLR-{rng.randint(1000, 9999)}",
    }


def generate_document_values(
    fake: Faker,
    rng: random.Random,
    state: str,
    vin_info: dict,
    vin: str,
) -> dict:
    """Generate all field values for a complete title document."""
    abbr = STATE_ABBREVS[state]
    today = date.today()

    # --- Vehicle info ---
    model_year = int(vin_info.get("year") or rng.randint(2010, 2024))
    vehicle_age = today.year - model_year
    # ~12,000 miles/year average, with some randomness
    base_miles = max(0, vehicle_age * 12000 + rng.randint(-5000, 5000))
    odometer = str(base_miles)

    color = rng.choice(COLORS)
    weight = vin_info.get("weight") or str(rng.randint(2800, 5500))

    # Dates
    first_sold_date = date(model_year, rng.randint(1, 12), rng.randint(1, 28))
    issue_date = first_sold_date + timedelta(days=rng.randint(30, 365))
    if issue_date > today:
        issue_date = today - timedelta(days=rng.randint(30, 365))

    # Title metadata
    title_no = f"{abbr}-{issue_date.year}-{rng.randint(100000, 9999999):07d}"
    title_type = rng.choice(TITLE_TYPES)
    title_brand = rng.choice(TITLE_BRANDS)
    county = fake.city().upper() + " COUNTY"

    # Previous title (30% chance of out-of-state transfer)
    prev_title_state = ""
    prev_title_no = ""
    if rng.random() < 0.3:
        prev_state = rng.choice([s for s in STATES if s != state])
        prev_abbr = STATE_ABBREVS[prev_state]
        prev_title_state = prev_state.upper()
        prev_title_no = f"{prev_abbr}-{rng.randint(2015, 2023)}-{rng.randint(100000, 9999999):07d}"

    # --- Owner ---
    owner = generate_person(fake, rng, state)
    # Co-owner (60% chance)
    has_co_owner = rng.random() < 0.6
    co_owner = generate_person(fake, rng, state) if has_co_owner else None

    ownership_type = rng.choice(OWNERSHIP_TYPES) if has_co_owner else ""

    # TOD beneficiary (15% chance)
    tod = ""
    if rng.random() < 0.15:
        tod_person = generate_person(fake, rng, state)
        tod = tod_person["name"]

    # --- Liens ---
    lien1 = generate_company(fake, rng, state)
    lien1_date = first_sold_date + timedelta(days=rng.randint(0, 30))
    lien1_release_date = issue_date - timedelta(days=rng.randint(10, 180))
    lien1_releaser = generate_person(fake, rng, state)

    lien2 = generate_company(fake, rng, state)
    lien2_date = lien1_date + timedelta(days=rng.randint(180, 900))
    lien2_release_date = issue_date - timedelta(days=rng.randint(5, 90))
    lien2_releaser = generate_person(fake, rng, state)

    # --- Transfer (back side) ---
    buyer = generate_person(fake, rng, state)
    transfer_date = issue_date + timedelta(days=rng.randint(30, 730))
    if transfer_date > today:
        transfer_date = today - timedelta(days=rng.randint(5, 60))
    sale_price = str(rng.randint(2000, 55000))
    transfer_miles = base_miles + rng.randint(500, 8000)

    # New lien on transfer (40% chance)
    has_new_lien = rng.random() < 0.4
    new_lien = generate_company(fake, rng, state) if has_new_lien else None
    new_lien_date = transfer_date + timedelta(days=rng.randint(0, 7)) if has_new_lien else None

    # --- Dealer reassignments ---
    dealer1 = generate_company(fake, rng, state)
    dealer1_buyer = generate_person(fake, rng, state)
    dealer1_agent = generate_person(fake, rng, state)
    dealer1_date = transfer_date + timedelta(days=rng.randint(5, 60))
    dealer1_miles = transfer_miles + rng.randint(100, 3000)

    dealer1_has_lien = rng.random() < 0.5
    dealer1_lien = generate_company(fake, rng, state) if dealer1_has_lien else None

    dealer2 = generate_company(fake, rng, state)
    dealer2_buyer = generate_person(fake, rng, state)
    dealer2_agent = generate_person(fake, rng, state)
    dealer2_date = dealer1_date + timedelta(days=rng.randint(30, 180))
    dealer2_miles = dealer1_miles + rng.randint(100, 5000)

    dealer2_has_lien = rng.random() < 0.3
    dealer2_lien = generate_company(fake, rng, state) if dealer2_has_lien else None

    # --- Notary ---
    notary_person = generate_person(fake, rng, state)
    witness1 = generate_person(fake, rng, state)
    witness2 = generate_person(fake, rng, state)

    # --- VIN verification ---
    inspector = generate_person(fake, rng, state)
    agencies = [
        f"{fake.city().upper()} POLICE DEPT",
        f"{state.upper()} STATE PATROL",
        f"{fake.city().upper()} SHERIFF OFFICE",
        f"{abbr} DMV INSPECTION STATION",
    ]

    # --- POA ---
    poa_attorney = generate_person(fake, rng, state)

    # --- Tax / fee ---
    price_int = int(sale_price)
    tax_rate = round(rng.uniform(4.0, 10.0), 1)
    trade_in = rng.choice([0, 0, 0, rng.randint(1000, 15000)])
    net_price = max(0, price_int - trade_in)
    sales_tax = round(net_price * tax_rate / 100, 2)
    local_tax = round(rng.uniform(0, net_price * 0.02), 2) if rng.random() < 0.4 else 0
    total_tax = round(sales_tax + local_tax, 2)
    title_fee = round(rng.uniform(15, 75), 2)
    reg_fee = round(rng.uniform(20, 120), 2)
    total_fees = round(total_tax + title_fee + reg_fee, 2)

    def _fmt_date(d: date) -> str:
        return d.strftime("%m/%d/%Y")

    def _sig_name(person: dict) -> str:
        """Title-case name for signature style."""
        return person["name"].title()

    # --- Build the complete values dict ---
    values = {
        # Vehicle info
        "vin": vin,
        "year": str(model_year),
        "make": vin_info.get("make") or "UNKNOWN",
        "model": vin_info.get("model") or "UNKNOWN",
        "body": vin_info.get("body", "").upper() or "SEDAN",
        "weight": weight,
        "cylinders": vin_info.get("cylinders") or str(rng.choice([4, 6, 8])),
        "fuel": vin_info.get("fuel") or "GASOLINE",
        "color": color,
        "plate_no": f"{abbr}-{rng.randint(1000, 9999)}",
        "prev_title_state": prev_title_state,

        # Title meta
        "title_no": title_no,
        "date_issued": _fmt_date(issue_date),
        "date_first_sold": _fmt_date(first_sold_date),
        "odometer": odometer,
        "title_type": title_type,
        "title_brand": title_brand,
        "county": county,
        "prev_title_no": prev_title_no,

        # Owner
        "owner_name": owner["name"],
        "owner_name_1": owner["name"],
        "owner_name_2": co_owner["name"] if co_owner else "",
        "owner_first": owner["first"],
        "owner_mi": owner["mi"],
        "owner_last": owner["last"],
        "owner_first_2": co_owner["first"] if co_owner else "",
        "owner_last_2": co_owner["last"] if co_owner else "",
        "owner_address": owner["address"],
        "owner_street": owner["street"],
        "owner_city": owner["city"],
        "owner_state": owner["state_abbr"],
        "owner_zip": owner["zip"],
        "owner_dl": owner["dl"],
        "owner_dl_2": co_owner["dl"] if co_owner else "",
        "ownership_type": ownership_type,
        "owner_tod": tod,

        # First lien
        "first_lien_name": lien1["name"],
        "first_lien_address": lien1["address"],
        "first_lien_date": _fmt_date(lien1_date),
        "first_lien_elt": f"ELT-{rng.randint(10000, 99999):05d}",
        "first_lien_id": f"LN-{lien1_date.year}-{rng.randint(100000, 999999)}",
        "first_release_sig": _sig_name(lien1_releaser),
        "first_release_date": _fmt_date(lien1_release_date),
        "first_release_title": rng.choice([
            "VP, Loan Servicing", "Title Release Agent", "Authorized Agent",
            "Lien Release Officer", "Assistant VP",
        ]),

        # Second lien
        "second_lien_name": lien2["name"],
        "second_lien_address": lien2["address"],
        "second_lien_date": _fmt_date(lien2_date),
        "second_lien_elt": f"ELT-{rng.randint(10000, 99999):05d}",
        "second_lien_id": f"LN-{lien2_date.year}-{rng.randint(100000, 999999)}",
        "second_release_sig": _sig_name(lien2_releaser),
        "second_release_date": _fmt_date(lien2_release_date),
        "second_release_title": rng.choice([
            "VP, Loan Servicing", "Title Release Agent", "Authorized Agent",
            "Lien Release Officer", "Assistant VP",
        ]),

        # Transfer
        "transfer_buyer_name": buyer["name"],
        "transfer_buyer_address": buyer["address"],
        "transfer_new_lien": new_lien["name"] if new_lien else "NONE",
        "transfer_new_lien_date": _fmt_date(new_lien_date) if new_lien_date else "",
        "transfer_new_lien_address": new_lien["address"] if new_lien else "",
        "transfer_odometer": str(transfer_miles),
        "transfer_seller_sig": _sig_name(owner),
        "transfer_buyer_sig": _sig_name(buyer),
        "transfer_seller_print": owner["name"],
        "transfer_buyer_print": buyer["name"],
        "transfer_seller_dl": owner["dl"],
        "transfer_buyer_dl": buyer["dl"],
        "transfer_date": _fmt_date(transfer_date),
        "transfer_sale_price": sale_price,

        # Dealer first
        "dealer_first_buyer_name": dealer1_buyer["name"],
        "dealer_first_buyer_address": dealer1_buyer["address"],
        "dealer_first_new_lien": dealer1_lien["name"] if dealer1_lien else "NONE",
        "dealer_first_new_lien_date": _fmt_date(dealer1_date) if dealer1_lien else "",
        "dealer_first_new_lien_address": dealer1_lien["address"] if dealer1_lien else "",
        "dealer_first_odometer": str(dealer1_miles),
        "dealer_first_dealer_name": dealer1["name"],
        "dealer_first_dealer_license": dealer1["license"],
        "dealer_first_dealer_address": dealer1["street"],
        "dealer_first_dealer_city": dealer1["city"],
        "dealer_first_dealer_state": abbr,
        "dealer_first_date": _fmt_date(dealer1_date),
        "dealer_first_agent_sig": _sig_name(dealer1_agent),
        "dealer_first_buyer_sig": _sig_name(dealer1_buyer),
        "dealer_first_agent_print": dealer1_agent["name"],
        "dealer_first_buyer_print": dealer1_buyer["name"],

        # Dealer second
        "dealer_second_buyer_name": dealer2_buyer["name"],
        "dealer_second_buyer_address": dealer2_buyer["address"],
        "dealer_second_new_lien": dealer2_lien["name"] if dealer2_lien else "NONE",
        "dealer_second_new_lien_date": _fmt_date(dealer2_date) if dealer2_lien else "",
        "dealer_second_new_lien_address": dealer2_lien["address"] if dealer2_lien else "",
        "dealer_second_odometer": str(dealer2_miles),
        "dealer_second_dealer_name": dealer2["name"],
        "dealer_second_dealer_license": dealer2["license"],
        "dealer_second_dealer_address": dealer2["street"],
        "dealer_second_dealer_city": dealer2["city"],
        "dealer_second_dealer_state": abbr,
        "dealer_second_date": _fmt_date(dealer2_date),
        "dealer_second_agent_sig": _sig_name(dealer2_agent),
        "dealer_second_buyer_sig": _sig_name(dealer2_buyer),
        "dealer_second_agent_print": dealer2_agent["name"],
        "dealer_second_buyer_print": dealer2_buyer["name"],

        # Notary
        "notary_sig": _sig_name(notary_person),
        "notary_date": _fmt_date(transfer_date),
        "notary_name": notary_person["name"],
        "notary_commission_exp": _fmt_date(
            transfer_date + timedelta(days=rng.randint(365, 1460))
        ),
        "notary_commission_no": f"NP-{rng.randint(2020, 2025)}-{rng.randint(1000, 9999)}",
        "notary_witness1_sig": _sig_name(witness1),
        "notary_witness1_print": witness1["name"],
        "notary_witness2_sig": _sig_name(witness2),
        "notary_witness2_print": witness2["name"],

        # Damage disclosure
        "damage_seller_sig": _sig_name(owner),
        "damage_buyer_sig": _sig_name(buyer),
        "damage_date": _fmt_date(transfer_date),
        "damage_description": rng.choice([
            "", "", "", "",  # most have no damage
            "PRIOR FRONT-END COLLISION REPAIRED",
            "HAIL DAMAGE — COSMETIC ONLY",
            "REAR BUMPER REPLACED AFTER COLLISION",
        ]),

        # VIN verification
        "vin_verify_vin": vin,
        "vin_verify_location": rng.choice([
            "DRIVER DOOR JAMB", "DASHBOARD", "DRIVER DOOR JAMB AND DASHBOARD",
            "DRIVER SIDE A-PILLAR", "ENGINE COMPARTMENT",
        ]),
        "vin_verify_date": _fmt_date(
            transfer_date - timedelta(days=rng.randint(1, 14))
        ),
        "vin_verify_inspector_sig": _sig_name(inspector),
        "vin_verify_badge": f"B-{rng.randint(1000, 9999)}",
        "vin_verify_inspector_name": inspector["name"],
        "vin_verify_agency": rng.choice(agencies),

        # Power of attorney
        "poa_attorney_name": poa_attorney["name"],
        "poa_attorney_address": poa_attorney["address"],
        "poa_attorney_dl": poa_attorney["dl"],
        "poa_grantor_sig": _sig_name(owner),
        "poa_grantor_print": owner["name"],
        "poa_grantor_dl": owner["dl"],
        "poa_co_grantor_sig": _sig_name(co_owner) if co_owner else "",
        "poa_co_grantor_print": co_owner["name"] if co_owner else "",
        "poa_date": _fmt_date(transfer_date - timedelta(days=rng.randint(1, 30))),

        # Tax / fee
        "tax_purchase_price": sale_price,
        "tax_trade_in": str(trade_in),
        "tax_net_price": str(net_price),
        "tax_rate": str(tax_rate),
        "tax_sales_tax": f"{sales_tax:.2f}",
        "tax_local_tax": f"{local_tax:.2f}",
        "tax_total_tax": f"{total_tax:.2f}",
        "tax_title_fee": f"{title_fee:.2f}",
        "tax_registration_fee": f"{reg_fee:.2f}",
        "tax_total": f"{total_fees:.2f}",
        "tax_receipt_no": f"RCT-{transfer_date.year}-{rng.randint(100000, 999999)}",
        "tax_date_paid": _fmt_date(
            transfer_date + timedelta(days=rng.randint(1, 30))
        ),
    }

    return values


# ---------------------------------------------------------------------------
# Document rendering
# ---------------------------------------------------------------------------

def _available_svg_rasterizer() -> str | None:
    """Return the first supported SVG rasterizer available in the environment."""
    if shutil.which("rsvg-convert"):
        return "rsvg-convert"
    if importlib.util.find_spec("cairosvg") is not None:
        return "cairosvg"
    if shutil.which("magick"):
        return "magick"
    if shutil.which("convert"):
        return "convert"
    return None


def _require_svg_rasterizer() -> str:
    """Ensure SVG rasterization is available before generating the dataset."""
    rasterizer = _available_svg_rasterizer()
    if rasterizer is None:
        raise RuntimeError(
            "No SVG rasterizer available. Install `rsvg-convert` (recommended), "
            "install the Python package `cairosvg`, or make ImageMagick "
            "(`magick`/`convert`) available in PATH."
        )
    return rasterizer


def _svg_to_png(svg_path: Path, png_path: Path) -> None:
    """Convert SVG to PNG, raising a clear error when rasterization fails."""
    rasterizer = _require_svg_rasterizer()

    if rasterizer == "rsvg-convert":
        try:
            subprocess.run(
                ["rsvg-convert", str(svg_path), "-o", str(png_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            return
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip() or str(exc)
            raise RuntimeError(
                f"SVG rasterization failed via rsvg-convert for {svg_path.name}: {stderr}"
            ) from exc

    if rasterizer == "cairosvg":
        try:
            import cairosvg

            cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
            return
        except Exception as exc:
            raise RuntimeError(
                f"SVG rasterization failed via CairoSVG for {svg_path.name}: {exc}"
            ) from exc

    command = [rasterizer, str(svg_path), str(png_path)]
    if rasterizer == "magick":
        command = ["magick", str(svg_path), str(png_path)]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise RuntimeError(
            f"SVG rasterization failed via {rasterizer} for {svg_path.name}: {stderr}"
        ) from exc


def _synthetic_vehicle_info(rng: random.Random) -> dict:
    """Generate synthetic vehicle info when API is unavailable."""
    make = rng.choice(list(MODELS_BY_MAKE.keys()))
    model = rng.choice(MODELS_BY_MAKE[make])
    return {
        "make": make,
        "model": model,
        "year": str(rng.randint(2010, 2024)),
        "body": rng.choice(["SEDAN", "SUV", "TRUCK", "COUPE", "HATCHBACK"]),
        "cylinders": str(rng.choice([4, 6, 8])),
        "fuel": "GASOLINE",
        "weight": str(rng.randint(2800, 5500)),
    }


def render_document(
    doc_id: str,
    state: str,
    values: dict,
    size: tuple[int, int],
    seed: int,
    out_dir: Path,
    aug_config: AugmentationConfig | None = None,
) -> dict:
    """Render front + back, convert to PNG, augment, and annotate.

    Produces per-side:
      - SVG (clean vector source)
      - PNG clean (rasterized, no augmentation)
      - PNG augmented (with camera-like artifacts)
      - Annotations JSON (words, fields, blocks for all tasks)

    Returns combined metadata dict.
    """
    w, h = size
    rng = random.Random(seed)
    border_size = 0.06 * w
    bg_col, border_col = rng.choice(BG_PALETTES)

    sides_meta = {}

    for side in ("front", "back"):
        side_seed = seed if side == "front" else seed + 1
        side_rng = random.Random(side_seed)

        # --- Build layout ---
        if side == "front":
            layout = build_random_layout(state_name=state.upper(), rng=side_rng)
        else:
            layout = build_random_back_layout(state_name=state.upper(), rng=side_rng)

        # --- Create SVG drawing ---
        svg_path = out_dir / f"{doc_id}_{side}.svg"
        drawing = svgwrite.Drawing(filename=str(svg_path), size=(w, h))

        if side == "front":
            bg_params = BackgroundParams(
                width=w, height=h, border_size=border_size,
                bg_color=bg_col, border_color=border_col, seed=side_seed,
            )
            add_background_to_drawing(drawing, bg_params)

            inner_rect = (border_size, border_size,
                          w - 2 * border_size, h - 2 * border_size)
            add_state_insignia(
                drawing, state, inner_rect,
                color=border_col, bg_color=bg_col,
                opacity=0.07, scale_fraction=0.45, rng=random.Random(side_seed),
            )

            border_rng = random.Random(side_seed)
            render_border_text(
                drawing, layout.border_text, w, h, border_size,
                orientation="Top", fg_color=bg_col, bg_color=border_col, rng=border_rng,
            )
            render_border_text(
                drawing, layout.side_border_text, w, h, border_size,
                orientation="Sides", fg_color=bg_col, bg_color=border_col, rng=border_rng,
            )
            render_border_text(
                drawing, layout.bottom_border_text, w, h, border_size,
                orientation="Bottom", fg_color=bg_col, bg_color=border_col, rng=border_rng,
            )

            content_rect = (
                border_size + 10, border_size + 10,
                w - 2 * (border_size + 10), h - 2 * (border_size + 10),
            )
        else:
            bg_params = BackgroundParams(
                width=w, height=h, border_size=0,
                bg_color=bg_col, border_color=border_col, seed=side_seed,
            )
            add_background_no_border(drawing, bg_params)

            content_rect = (
                border_size + 10, border_size + 10,
                w - 2 * (border_size + 10), h - 2 * (border_size + 10),
            )

        result = solve_layout(layout, content_rect, compact=(side == "back"))
        layout_meta = render_layout(drawing, result, font_family=layout.font_family)
        fill_values(drawing, layout_meta, values, rng=random.Random(side_seed))
        drawing.save()

        # --- SVG → clean PNG ---
        clean_png_path = out_dir / "images_clean" / f"{doc_id}_{side}.png"
        clean_png_path.parent.mkdir(exist_ok=True)
        _svg_to_png(svg_path, clean_png_path)

        # --- Augment ---
        clean_img = Image.open(clean_png_path)
        aug_rng = random.Random(side_seed + 50)

        if aug_config is not None:
            aug_result = augment_image(clean_img, config=aug_config, rng=aug_rng)
        else:
            aug_result = AugmentationResult(image=clean_img)

        aug_png_path = out_dir / "images" / f"{doc_id}_{side}.png"
        aug_png_path.parent.mkdir(exist_ok=True)
        aug_result.image.save(str(aug_png_path))

        # --- Build annotations (mapped to augmented coordinates) ---
        aug_w, aug_h = aug_result.image.size
        annotations = build_annotations(
            layout_meta, values, aug_w, aug_h,
            transform_bbox=aug_result.transform_bbox,
        )

        # Save all annotation formats
        ann_dir = out_dir / "annotations"
        ann_dir.mkdir(exist_ok=True)

        # Base annotations (everything)
        ann_path = ann_dir / f"{doc_id}_{side}.json"
        with open(ann_path, "w") as f:
            json.dump({
                "doc_id": doc_id,
                "side": side,
                "state": state,
                "image_file": f"images/{doc_id}_{side}.png",
                "clean_image_file": f"images_clean/{doc_id}_{side}.png",
                "original_size": [w, h],
                "augmented_size": [aug_w, aug_h],
                "augmentations": aug_result.applied,
                "annotations": annotations,
            }, f, indent=2)

        # LayoutLMv3 format
        lm_dir = out_dir / "layoutlm"
        lm_dir.mkdir(exist_ok=True)
        lm_data = to_layoutlmv3(
            annotations, f"images/{doc_id}_{side}.png", aug_w, aug_h,
        )
        with open(lm_dir / f"{doc_id}_{side}.json", "w") as f:
            json.dump(lm_data, f, indent=2)

        sides_meta[side] = {
            "font_size": round(result.font_size, 2),
            "augmentations": aug_result.applied,
            "word_count": len(annotations["words"]),
            "field_count": len(annotations["fields"]),
        }

    # Save combined doc metadata (compact — no full layout dump)
    doc_meta = {
        "doc_id": doc_id,
        "state": state,
        "size": {"w": w, "h": h},
        "seed": seed,
        "bg_color": bg_col,
        "border_color": border_col,
        "values": values,
        **{f"{side}_info": info for side, info in sides_meta.items()},
    }
    with open(out_dir / f"{doc_id}_meta.json", "w") as f:
        json.dump(doc_meta, f, indent=2)

    return doc_meta


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SIZE_PRESETS = {
    "small": (800, 1040),
    "large": (2250, 3000),
    "medium": (1200, 1560),
    "random": None,
}

RANDOM_SIZES = [
    (800, 1040), (1000, 1300), (1200, 1560),
    (1500, 1950), (1800, 2340), (2250, 3000),
]


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic vehicle title dataset")
    parser.add_argument("--count", type=int, default=10, help="Number of documents to generate")
    parser.add_argument("--output", type=str, default="dataset", help="Output directory")
    parser.add_argument("--size", type=str, default="random",
                        choices=list(SIZE_PRESETS.keys()),
                        help="Document size preset (default: random)")
    parser.add_argument("--seed", type=int, default=42, help="Base random seed")
    parser.add_argument("--augment", type=str, default="default",
                        choices=list(AUG_PRESETS.keys()),
                        help="Augmentation intensity (clean/light/default/heavy)")
    parser.add_argument("--no-api", action="store_true",
                        help="Skip NHTSA API calls (use synthetic vehicle data)")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    rasterizer = _require_svg_rasterizer()
    aug_config = AUG_PRESETS[args.augment]

    rng = random.Random(args.seed)
    fake = Faker()
    Faker.seed(args.seed)

    print(f"Generating {args.count} documents in {out_dir}/")
    print(f"Size: {args.size}, Seed: {args.seed}, Augment: {args.augment}")
    print(f"NHTSA API: {'disabled' if args.no_api else 'enabled'}")
    print(f"SVG rasterizer: {rasterizer}")
    print("-" * 60)

    errors = []
    api_failures = 0

    for i in range(args.count):
        doc_seed = args.seed + i * 100
        doc_rng = random.Random(doc_seed)

        state = doc_rng.choice(STATES)

        if args.size == "random":
            size = doc_rng.choice(RANDOM_SIZES)
        else:
            size = SIZE_PRESETS[args.size]

        # Generate VIN and decode
        vin = generate_vin(doc_rng)

        if not args.no_api:
            vin_info = decode_vin(vin)
            if not vin_info.get("make"):
                api_failures += 1
                vin_info = _synthetic_vehicle_info(doc_rng)
            if i < args.count - 1:
                time.sleep(0.3)
        else:
            vin_info = _synthetic_vehicle_info(doc_rng)

        values = generate_document_values(fake, doc_rng, state, vin_info, vin)

        doc_id = f"title_{i:04d}"
        try:
            render_document(
                doc_id, state, values, size, doc_seed, out_dir,
                aug_config=aug_config,
            )
            vehicle = f"{values['year']} {values['make']} {values['model']}"
            print(f"  [{i+1:>{len(str(args.count))}}/{args.count}] {doc_id}  "
                  f"{state:<20} {size[0]}x{size[1]}  {vehicle}")
        except Exception as e:
            errors.append((doc_id, str(e)))
            print(f"  [{i+1:>{len(str(args.count))}}/{args.count}] {doc_id}  FAILED: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Generated: {args.count - len(errors)}/{args.count} documents")
    if api_failures:
        print(f"API fallbacks: {api_failures} (used synthetic vehicle data)")
    if errors:
        print(f"Errors: {len(errors)}")
        for doc_id, err in errors:
            print(f"  {doc_id}: {err}")

    # Count output files
    img_count = len(list((out_dir / "images").glob("*.png"))) if (out_dir / "images").exists() else 0
    ann_count = len(list((out_dir / "annotations").glob("*.json"))) if (out_dir / "annotations").exists() else 0
    print(f"\nOutput structure:")
    print(f"  {out_dir}/images/          — {img_count} augmented PNGs")
    print(f"  {out_dir}/images_clean/    — clean PNGs (no augmentation)")
    print(f"  {out_dir}/annotations/     — {ann_count} full annotation JSONs")
    print(f"  {out_dir}/layoutlm/        — LayoutLMv3-format JSONs")
    print(f"  {out_dir}/*.svg            — source SVGs")
    print(f"  {out_dir}/*_meta.json      — per-document metadata + values")


if __name__ == "__main__":
    main()
