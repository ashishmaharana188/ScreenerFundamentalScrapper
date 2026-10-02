"""ScanX company-name scraper.

Flow
----
1. Dashboard supplies the industries and sectors selected by the user.
2. This file converts those selections into ScanX's API query format.
3. The ScanX API is called page by page.
4. Company names are extracted and saved to scanx_data/.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

import requests


# ============================================================
# CONFIGURATION
# ============================================================

ENTRY_URL = "https://scanx.trade/create-custom-screener"
API_URL = "https://ow-scanx-analytics.dhan.co/customscan/v2/fetchdt"

PAGE_SIZE = 25
REQUEST_DELAY = 0.35
REQUEST_TIMEOUT = 30
MAX_RETRIES = 4
RETRY_DELAYS = (2, 5, 10, 20)

OUTPUT_DIR = Path("scanx_data")
OUTPUT_FILE = OUTPUT_DIR / "scanx_company_names.csv"


# ============================================================
# ALL INDUSTRIES
# ============================================================

ALL_INDUSTRIES = [
    "Aerospace & Defense",
    "Automobile & Auto Components",
    "Automobiles",
    "Aviation",
    "Banks",
    "Beverages",
    "Cables",
    "Capital Goods",
    "Capital Goods - Electrical Equipment",
    "Capital Markets",
    "Castings, Forgings & Fastners",
    "Chemicals",
    "Commercial Services",
    "Construction",
    "Consumer Durables",
    "Consumer Goods",
    "Consumer Services",
    "Diamond, Gems and Jewellery",
    "Diversified",
    "Education",
    "Energy",
    "Engineering Services",
    "Financial Services",
    "FMCG",
    "Food Products",
    "Forest Materials",
    "Healthcare",
    "Healthcare Services",
    "Industrial Products",
    "Information Technology",
    "Insurance",
    "Leisure Services",
    "Logistics & Cargo",
    "Media",
    "Media Entertainment & Publication",
    "Metals & Mining",
    "Oil & Gas",
    "Packaging",
    "Petroleum Products",
    "Power",
    "Printing & Stationery",
    "Realty",
    "Retail",
    "Services",
    "Steel",
    "Telecom",
    "Telecomm Equipment & Infra Services",
    "Textiles",
    "Trading",
    "Transport",
    "Transport Services",
    "Utilities",
]


# ============================================================
# ALL SECTORS
# ============================================================

ALL_SECTORS = [
    "2/3 Wheelers",
    "AMC Mutual Fund",
    "Abrasives & Bearings",
    "Advertising & Media Agencies",
    "Advertising Agencies",
    "Aerospace & Defense",
    "Agricultural Products",
    "Airline",
    "Airport & Airport Services",
    "Aluminium",
    "Aluminium Copper & Zinc",
    "Animal Feed",
    "Auto Components",
    "Auto Dealer",
    "BPO / KPO",
    "Bikes",
    "Biotechnology",
    "Breweries & Distilleries",
    "Cables - Electricals",
    "Cables - Power",
    "Carbon Black",
    "Cars & Utility Vehicles",
    "Castings & Forgings",
    "Cement",
    "Ceramics",
    "Cigarettes & Tobacco",
    "Civil Construction",
    "Coal",
    "Commercial Vehicles",
    "Commodity Chemicals",
    "Composite Textiles",
    "Compressors Pumps & Diesel Engines",
    "Computer Software & Consulting",
    "Construction",
    "Construction Materials",
    "Consulting Services",
    "Consumer Glass",
    "Copper",
    "Cotton/Blended",
    "Cycles",
    "Dairy Products",
    "Data Processing Services",
    "Dealers",
    "Depository",
    "Diamond Cutting / Jewellery",
    "Digital Entertainment",
    "Distributors",
    "Diversified - Large",
    "Diversified FMCG",
    "Diversified Group",
    "Diversified Metals",
    "Diversified Products",
    "Diversified Retail",
    "Diversified Services",
    "Dredging",
    "Dyes & Pigments",
    "E-Learning",
    "E-Retail/ E-Commerce",
    "E-Services",
    "Ecommerce",
    "Edible Oil",
    "Education",
    "Electric Equipment",
    "Electrical Equipment",
    "Electrodes & Refractories",
    "Electronic Media",
    "Electronics",
    "Engineering",
    "Equipment & Accessories",
    "Event Management",
    "Exchange",
    "Explosives",
    "FMCG Products",
    "Ferro & Silica Manganese",
    "Fertilizers",
    "Film Production Distribution",
    "Finance",
    "Financial Institution",
    "Fintech",
    "Food - Processing - Indian",
    "Food Products",
    "Footwear",
    "Forest Products",
    "Garments & Apparels",
    "Gas",
    "Gas Supplier",
    "Gems Jewellery & Watches",
    "General Insurance",
    "Glass - Industrial",
    "Granites & Marbles",
    "Healthcare Service Provider",
    "Healthcare Technology",
    "Heavy Electric Equipment",
    "Holding Company",
    "Home Furnishing",
    "Hospital",
    "Hospitals",
    "Hotels & Resorts",
    "Household Appliances",
    "Household Products",
    "Houseware",
    "Housing Finance",
    "IT - Hardware",
    "IT Enabled Services",
    "Industrial Gases",
    "Industrial Minerals",
    "Industrial Products",
    "Insurance Distribution",
    "Integrated Power Utilities",
    "Investment Company",
    "Iron & Steel",
    "Iron & Steel Products",
    "Jewellery & Watches",
    "Jute & Jute Products",
    "Jute/Yarn Products",
    "Leather & Leather Products",
    "Leather Products",
    "Leisure Products",
    "Life Insurance",
    "Logistics Solution Provider",
    "Lubricants",
    "Manmade Textiles",
    "Meat Products",
    "Media & Entertainment",
    "Media Entertainment & Publication",
    "Medical Equipment",
    "Microfinance",
    "Miscellaneous",
    "NBFC",
    "Non - Ferrous Metals",
    "Non Alcoholic Beverages",
    "Offshore Operations",
    "Oil Equipment & Services",
    "Oil Exploration & Production",
    "Oil Storage & Transportation",
    "Other Electrical Equipment",
    "Other Financial Services",
    "Other Industrial Products",
    "Other Utilities",
    "Packaged Foods",
    "Packaging",
    "Paints",
    "Paper & Paper Products",
    "Payment Bank",
    "Personal Care",
    "Pesticides & Agrochemicals",
    "Petrochemicals",
    "Pharmaceuticals",
    "Pharmacy Retail",
    "Pig Iron",
    "Plastic Products",
    "Plastic Products - Industrial",
    "Plastics Products",
    "Plywood Boards & Laminates",
    "Plywood Boards/ Laminates",
    "Port & Port Services",
    "Power Distribution",
    "Power Generation",
    "Power Trading",
    "Power Transmission",
    "Precious Metals",
    "Print Media",
    "Printing & Publication",
    "Printing & Stationery",
    "Printing Inks",
    "Private Bank",
    "Public Sector Bank",
    "Quick Service Restaurant",
    "REITs",
    "RTA",
    "Railway Wagons",
    "Rating Services",
    "Real Estate Investment Trusts (REITs)",
    "Real Estate Services",
    "Residential Commercial Projects",
    "Recreation",
    "Refineries & Marketing",
    "Restaurants",
    "Road Assets - Toll Annuity Hybrid-Annuity",
    "Road Transport",
    "Rubber",
    "Rubber Products",
    "Sanitary Ware",
    "Seafood",
    "Ship Building",
    "Shipping",
    "Small Finance Bank",
    "Software Products",
    "Speciality Retail",
    "Specialty Chemicals",
    "Spinning - Synthetic / Blended",
    "Sponge Iron",
    "Stationary",
    "Steel - Medium / Small",
    "Stock Broking",
    "Sugar",
    "TV Broadcasting & Media",
    "Tea & Coffee",
    "Telecom Infrastructure",
    "Telecom Service Provider",
    "Telecom Services",
    "Textile Processing",
    "Textile Products",
    "Textile Trading",
    "Textiles & Apparels",
    "Textiles - Products",
    "Toll Road Assets",
    "Tour & Travel",
    "Tractors",
    "Trading",
    "Trading & Distributors",
    "Trading Chemicals",
    "Trading Coal",
    "Trading Gas",
    "Trading Metals",
    "Trading Minerals",
    "Transmisson Line Towers / Equipment",
    "Transport Services",
    "Tyres",
    "Waste Management",
    "Water Supply & Management",
    "Wealth",
    "Wellness",
    "Zinc",
]


# ============================================================
# SESSION
# ============================================================

def create_session() -> requests.Session:
    """Create one HTTP session for the ScanX run."""

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://scanx.trade",
            "Referer": ENTRY_URL,
        }
    )

    return session


# ============================================================
# QUERY BUILDING
# ============================================================

def make_or_params(field: str, values: list[str]) -> dict[str, Any]:
    """Turn a list of selected values into ScanX OR conditions."""

    return {
        "logic_op": "OR",
        "params": [
            {
                "field": field,
                "op": "eq",
                "val": value,
            }
            for value in values
        ],
    }


def build_query(
    industries: list[str],
    sectors: list[str],
) -> dict[str, Any]:
    """Build the ScanX query from the user's dashboard selections."""

    industries = [value.strip() for value in industries if value.strip()]
    sectors = [value.strip() for value in sectors if value.strip()]

    if not industries:
        raise ValueError("Select at least one industry.")

    invalid_industries = [
        value for value in industries if value not in ALL_INDUSTRIES
    ]
    invalid_sectors = [
        value for value in sectors if value not in ALL_SECTORS
    ]

    if invalid_industries:
        raise ValueError(
            f"Unknown ScanX industries: {invalid_industries}"
        )

    if invalid_sectors:
        raise ValueError(
            f"Unknown ScanX sectors: {invalid_sectors}"
        )

    params = [
        {
            "field": "Exch",
            "op": "eq",
            "val": "NSE",
        },
        make_or_params("Sector", industries),
    ]

    # User-facing Sector maps to ScanX SubSector.
    # It is optional. When no sectors are selected, no SubSector
    # filter is sent, so all subsectors within the selected industries
    # are included.
    if sectors:
        params.append(
            make_or_params("SubSector", sectors)
        )

    params.extend(
        [
            {
                "field": "OgInst",
                "op": "eq",
                "val": "ES",
            },
            {
                "field": "Volume",
                "op": "gte",
                "val": "0",
            },
        ]
    )

    return {
        "logic_op": "AND",
        "params": params,
    }


def build_payload(
    page_number: int,
    industries: list[str],
    sectors: list[str],
) -> dict[str, Any]:
    """Build the request body for one ScanX page."""

    if page_number < 1:
        raise ValueError("page_number must be >= 1")

    return {
        "data": {
            "count": PAGE_SIZE,
            "pgno": page_number,
            "fields": [
                "DispSym",
                "Sector",
                "SubSector",
            ],
            "query": build_query(industries, sectors),
            "sorder": "desc",
            "sort": "Mcap",
        }
    }


# ============================================================
# API REQUEST
# ============================================================

def post_page(
    session: requests.Session,
    page_number: int,
    industries: list[str],
    sectors: list[str],
) -> dict[str, Any]:
    """POST one ScanX page with retry handling."""

    payload = build_payload(
        page_number=page_number,
        industries=industries,
        sectors=sectors,
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = session.post(
                API_URL,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == MAX_RETRIES - 1:
                    response.raise_for_status()

                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                print(
                    f"Page {page_number}: HTTP {response.status_code}; "
                    f"retrying in {delay}s..."
                )
                time.sleep(delay)
                continue

            response.raise_for_status()

            data = response.json()
            if not isinstance(data, dict):
                raise ValueError(
                    f"Unexpected API response type: {type(data).__name__}"
                )

            return data

        except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    f"ScanX page {page_number} failed after "
                    f"{MAX_RETRIES} attempts: {exc}"
                ) from exc

            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            print(
                f"Page {page_number}: {exc}; retrying in {delay}s..."
            )
            time.sleep(delay)

    raise RuntimeError(f"Unable to fetch ScanX page {page_number}")


# ============================================================
# RESPONSE EXTRACTION
# ============================================================

def extract_company_rows(
    response_json: dict[str, Any],
) -> tuple[list[dict[str, Any]], int | None, int | None]:
    """Extract rows and pagination metadata from a ScanX response."""

    if not isinstance(response_json, dict):
        raise ValueError(
            f"Unexpected ScanX response type: {type(response_json).__name__}"
        )

    code = response_json.get("code")
    if code not in (None, 0):
        raise RuntimeError(
            f"ScanX returned error code {code}: "
            f"{response_json.get('remarks', '')}"
        )

    fields = response_json.get("headers")
    rows = response_json.get("data")

    if not isinstance(fields, list) or not all(
        isinstance(field, str) for field in fields
    ):
        raise ValueError(
            "ScanX response does not contain a valid 'headers' list. "
            f"Keys: {list(response_json.keys())}"
        )

    if not isinstance(rows, list):
        raise ValueError(
            "ScanX response does not contain a valid 'data' row list. "
            f"Keys: {list(response_json.keys())}"
        )

    extracted: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, list):
            continue

        if len(row) != len(fields):
            print(
                "WARNING: Skipping ScanX row because the number of values "
                f"({len(row)}) does not match headers ({len(fields)})."
            )
            continue

        extracted.append(dict(zip(fields, row)))

    total_records = response_json.get("tot_rec")
    total_pages = response_json.get("tot_pg")

    try:
        total_records = int(total_records) if total_records is not None else None
    except (TypeError, ValueError):
        total_records = None

    try:
        total_pages = int(total_pages) if total_pages is not None else None
    except (TypeError, ValueError):
        total_pages = None

    return extracted, total_records, total_pages


def extract_company_record(
    row: dict[str, Any],
) -> dict[str, str] | None:
    """
    Extract the company and ScanX taxonomy values from one row.

    ScanX field mapping:
        Sector    -> user-facing industry
        SubSector -> user-facing sector
    """

    company_value = row.get("DispSym")

    if company_value is None:
        return None

    company_name = str(company_value).strip()

    if not company_name:
        return None

    industry = str(row.get("Sector") or "").strip()
    sector = str(row.get("SubSector") or "").strip()

    return {
        "company_name": company_name,
        "industry": industry,
        "sector": sector,
    }


def extract_company_name(row: dict[str, Any]) -> str | None:
    """Backward-compatible company-name extraction."""

    record = extract_company_record(row)

    if record is None:
        return None

    return record["company_name"]


# ============================================================
# PAGINATION
# ============================================================

def scrape_company_names(
    session: requests.Session,
    industries: list[str],
    sectors: list[str],
) -> list[dict[str, str]]:
    """
    Fetch every ScanX page and return distinct companies with taxonomy.

    Each record contains:
        company_name
        industry
        sector
    """

    page = 1
    records: list[dict[str, str]] = []
    record_index: dict[str, int] = {}
    expected_total: int | None = None
    expected_pages: int | None = None

    while True:
        response_json = post_page(
            session=session,
            page_number=page,
            industries=industries,
            sectors=sectors,
        )

        rows, total_records, total_pages = extract_company_rows(
            response_json
        )

        if expected_total is None:
            expected_total = total_records

        if expected_pages is None:
            expected_pages = total_pages

        if not rows:
            if expected_total in (0, None):
                print(f"Page {page}: 0 rows.")
                break

            raise RuntimeError(
                f"ScanX returned 0 rows on page {page} even though "
                f"total_records={expected_total}."
            )

        new_companies = 0

        for row in rows:
            record = extract_company_record(row)

            if record is None:
                continue

            company_name = record["company_name"]
            existing_index = record_index.get(company_name)

            if existing_index is None:
                record_index[company_name] = len(records)
                records.append(record)
                new_companies += 1
                continue

            # Preserve the first value, but fill blanks from a later
            # occurrence if ScanX returns incomplete metadata.
            existing = records[existing_index]

            if not existing["industry"] and record["industry"]:
                existing["industry"] = record["industry"]

            if not existing["sector"] and record["sector"]:
                existing["sector"] = record["sector"]

        page_text = (
            f"{page}/{expected_pages}"
            if expected_pages is not None
            else str(page)
        )

        total_text = (
            str(expected_total)
            if expected_total is not None
            else "?"
        )

        print(
            f"Page {page_text}: API rows={len(rows)} | "
            f"new companies={new_companies} | "
            f"distinct collected={len(records)}/{total_text}"
        )

        if expected_pages is not None and page >= expected_pages:
            break

        if expected_pages is None and len(rows) < PAGE_SIZE:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    if expected_total is not None and len(records) != expected_total:
        raise RuntimeError(
            "ScanX pagination validation failed: "
            f"expected {expected_total} records, "
            f"collected {len(records)} distinct companies."
        )

    return records


# ============================================================
# SAVE
# ============================================================

def save_company_names(
    records: list[dict[str, str]],
    file_path: Path = OUTPUT_FILE,
) -> Path:
    """
    Save the ScanX universe with taxonomy columns.

    Output columns:
        company_name
        industry
        sector
    """

    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "company_name",
                "industry",
                "sector",
            ],
        )

        writer.writeheader()

        for record in records:
            writer.writerow(
                {
                    "company_name": record.get("company_name", ""),
                    "industry": record.get("industry", ""),
                    "sector": record.get("sector", ""),
                }
            )

    print(f"Saved: {file_path.resolve()}")
    print(f"Rows written: {len(records)}")

    return file_path


# ============================================================
# PUBLIC RUN FUNCTION
# ============================================================

def run_scan(
    industries: list[str],
    sectors: list[str],
) -> list[str]:
    """Run one ScanX scrape using the dashboard's selections."""

    print("========================================")
    print("SCANX SCRAPER")
    print("========================================")
    print(f"Industries selected: {len(industries)}")
    print(f"Sectors selected:    {len(sectors)}")
    print(f"Page size:           {PAGE_SIZE}")
    print()

    session = create_session()

    try:
        entry_response = session.get(
            ENTRY_URL,
            timeout=REQUEST_TIMEOUT,
        )
        entry_response.raise_for_status()
        print(f"Entry page: HTTP {entry_response.status_code}")

        records = scrape_company_names(
            session=session,
            industries=industries,
            sectors=sectors,
        )

        if not records:
            raise RuntimeError("ScanX returned no company names.")

        save_company_names(records)

        names = [
            record["company_name"]
            for record in records
        ]

        print("\n========================================")
        print("SCANX SCRAPER COMPLETE")
        print("========================================")
        print(f"Distinct company names: {len(names)}")

        return names

    finally:
        session.close()


# ============================================================
# DIRECT SCRIPT ENTRY
# ============================================================

if __name__ == "__main__":
    raise RuntimeError(
        "Run ScanX from dashboard.py so industries and sectors can be selected."
    )
