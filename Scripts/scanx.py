"""ScanX company-name scraper.

Purpose
-------
Build the ScanX custom-screener request for the selected industries/sectors,
paginate through the ScanX API (25 rows per request), extract company names,
deduplicate them, validate the pagination, and save a one-column CSV.

No browser automation is required. ScanX's custom screener uses:
    POST https://ow-scanx-analytics.dhan.co/customscan/v2/fetchdt

Our taxonomy:
    Industry -> ScanX field: Sector
    Sector   -> ScanX field: SubSector
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
# SELECTED ECONOMIC UNIVERSE
# ============================================================
# These are the 10 industries + 20 sectors selected for the project.
# ScanX terminology is different, so the request builder maps:
#     our industry -> ScanX Sector
#     our sector   -> ScanX SubSector

INDUSTRIES = [
    "Aerospace & Defense",
    "Capital Goods",
    "Power",
    "Information Technology",
    "Consumer Goods",
    "Healthcare",
    "Financial Services",
    "Automobile & Auto Components",
    "Logistics & Cargo",
    "Telecom",
]

SECTORS = [
    "Aerospace & Defense",
    "Ship Building",
    "Heavy Electric Equipment",
    "Compressors Pumps & Diesel Engines",
    "Power Generation",
    "Power Transmission",
    "Computer Software & Consulting",
    "Data Processing Services",
    "Electronics",
    "Household Appliances",
    "Pharmaceuticals",
    "Medical Equipment",
    "Private Bank",
    "NBFC",
    "Auto Components",
    "2/3 Wheelers",
    "Logistics Solution Provider",
    "Port & Port Services",
    "Telecom Infrastructure",
    "Telecom Services",
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
    """Create ScanX OR conditions for one field."""

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


def build_query() -> dict[str, Any]:
    """Build the exact query structure observed in ScanX."""

    if len(INDUSTRIES) != 10:
        raise ValueError(
            f"Expected 10 industries, found {len(INDUSTRIES)}"
        )

    if len(SECTORS) != 20:
        raise ValueError(
            f"Expected 20 sectors, found {len(SECTORS)}"
        )

    return {
        "logic_op": "AND",
        "params": [
            {
                "field": "Exch",
                "op": "eq",
                "val": "NSE",
            },
            make_or_params("Sector", INDUSTRIES),
            make_or_params("SubSector", SECTORS),
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
        ],
    }


def build_payload(page_number: int) -> dict[str, Any]:
    """Build one paginated ScanX POST body."""

    if page_number < 1:
        raise ValueError("page_number must be >= 1")

    return {
        "data": {
            "count": PAGE_SIZE,
            "pgno": page_number,
            "query": build_query(),
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
) -> dict[str, Any]:
    """POST one ScanX page with retry handling."""

    payload = build_payload(page_number)

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

def extract_company_rows(response_json: dict[str, Any]) -> tuple[list[dict[str, Any]], int | None, int | None]:
    """Extract rows and pagination metadata from ScanX fetchdt response.

    Captured ScanX response schema:

        {
            "code": 0,
            "remarks": "",
            "tot_rec": 439,
            "tot_pg": 18,
            "data": [[...], [...]],
            "headers": ["Exch", "Sid", ...]
        }

    Returns:
        rows, total_records, total_pages
    """

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


def extract_company_name(row: dict[str, Any]) -> str | None:
    """Extract the ScanX displayed company name from a normalized row."""

    value = row.get("DispSym")

    if value is None:
        return None

    name = str(value).strip()
    return name or None


# ============================================================
# PAGINATION
# ============================================================

def scrape_company_names(
    session: requests.Session,
) -> list[str]:
    """Fetch every ScanX page and return distinct company names."""

    page = 1
    names: list[str] = []
    seen_names: set[str] = set()
    expected_total: int | None = None
    expected_pages: int | None = None

    while True:
        response_json = post_page(session, page)
        rows, total_records, total_pages = extract_company_rows(response_json)

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

        new_names = 0

        for row in rows:
            name = extract_company_name(row)
            if not name:
                continue

            if name not in seen_names:
                seen_names.add(name)
                names.append(name)
                new_names += 1

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
            f"new companies={new_names} | "
            f"distinct collected={len(names)}/{total_text}"
        )

        # Prefer the API's explicit total-page metadata.
        if expected_pages is not None and page >= expected_pages:
            break

        # Fallback if total-page metadata is absent.
        if expected_pages is None and len(rows) < PAGE_SIZE:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    if expected_total is not None and len(names) != expected_total:
        raise RuntimeError(
            "ScanX pagination validation failed: "
            f"expected {expected_total} records, "
            f"collected {len(names)} distinct company names."
        )

    return names


# ============================================================
# SAVE
# ============================================================

def save_company_names(names: list[str], file_path: Path = OUTPUT_FILE) -> None:
    """Save one company_name column to CSV."""

    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(["company_name"])
        for name in names:
            writer.writerow([name])

    print(f"Saved: {file_path.resolve()}")
    print(f"Rows written: {len(names)}")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("========================================")
    print("SCANX SCRAPER")
    print("========================================")
    print(f"Industries: {len(INDUSTRIES)}")
    print(f"Sectors:    {len(SECTORS)}")
    print(f"Page size:  {PAGE_SIZE}")
    print()

    session = create_session()

    # A GET is not required for the data call, but doing one first gives the
    # session normal ScanX cookies if the site sets any on the entry page.
    try:
        entry_response = session.get(
            ENTRY_URL,
            timeout=REQUEST_TIMEOUT,
        )
        entry_response.raise_for_status()
        print(f"Entry page: HTTP {entry_response.status_code}")
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not open ScanX entry page: {exc}"
        ) from exc

    names = scrape_company_names(session)

    if not names:
        raise RuntimeError("ScanX returned no company names.")

    save_company_names(names)

    print("\n========================================")
    print("SCANX SCRAPER COMPLETE")
    print("========================================")
    print(f"Distinct company names: {len(names)}")


if __name__ == "__main__":
    main()
