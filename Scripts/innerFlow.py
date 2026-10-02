# innerFlow.py

import re
import time
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs, urlencode
import csv
from pathlib import Path
from storage import GROUPS_DIR, FINAL_DIR, upload_file

from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://www.screener.in"

# Delay between normal page requests.
PAGE_DELAY = 1

# If Screener returns 429, wait progressively longer.
RETRY_DELAYS = [10, 20, 40]

# ============================================================
# PAGE INFORMATION
# ============================================================

def get_page_info(soup):
    """
    Extract Screener pagination information.

    Example:
        225 results found: Showing page 1 of 5
    """

    page_info_element = soup.select_one(
        "[data-page-info]"
    )

    if page_info_element is None:
        raise RuntimeError(
            "Could not find Screener page information."
        )

    page_info_text = page_info_element.get_text(
        " ",
        strip=True,
    )

    match = re.search(
        r"([\d,]+)\s+results\s+found:\s+"
        r"Showing\s+page\s+(\d+)\s+of\s+(\d+)",
        page_info_text,
        re.IGNORECASE,
    )

    if match is None:
        raise RuntimeError(
            f"Could not parse page information: "
            f"{page_info_text}"
        )

    return {
        "total_results": int(
            match.group(1).replace(",", "")
        ),
        "current_page": int(
            match.group(2)
        ),
        "total_pages": int(
            match.group(3)
        ),
    }


# ============================================================
# TABLE HEADERS
# ============================================================

def extract_headers(soup):
    """
    Extract column names from the Screener results table.
    """

    table = soup.select_one(
        'div[data-page-results] table.data-table'
    )

    if table is None:
        raise RuntimeError(
            "Could not find Screener results table."
        )

    header_row = table.find("tr")

    if header_row is None:
        raise RuntimeError(
            "Could not find table header row."
        )

    headers = []

    for th in header_row.find_all(
        "th",
        recursive=False,
    ):

        link = th.find("a")

        if link:

            aria_label = link.get(
                "aria-label"
            )

            if aria_label:

                header = re.sub(
                    r"^Sort on\s+",
                    "",
                    aria_label,
                    flags=re.IGNORECASE,
                ).strip().lower()
                
                header = re.sub(
                r"\s+",
                "_",
                header,
            )

                if header:
                    headers.append(header)
                    continue

        header = th.get_text(
            " ",
            strip=True,
        ).strip().lower()

        header = re.sub(
            r"\s+",
            "_",
            header,
        )

        headers.append(header)

    return headers


# ============================================================
# TABLE ROWS
# ============================================================

def extract_rows(soup, headers):
    """
    Extract company rows from the current Screener page.
    """

    table = soup.select_one(
        'div[data-page-results] table.data-table'
    )

    if table is None:
        raise RuntimeError(
            "Could not find Screener results table."
        )

    company_rows = table.select(
        "tr[data-row-company-id]"
    )

    rows = []

    for row in company_rows:

        company_id = row.get(
            "data-row-company-id"
        )

        cells = row.find_all(
            ["td", "th"],
            recursive=False,
        )

        values = [
            cell.get_text(
                " ",
                strip=True,
            )
            for cell in cells
        ]

        if len(values) != len(headers):

            print(
                f"WARNING: Skipping company ID "
                f"{company_id}. "
                f"Expected {len(headers)} values, "
                f"found {len(values)}."
            )

            continue

        row_data = {
            headers[i]: values[i]
            for i in range(len(headers))
        }

        row_data["company_id"] = company_id

        company_link = row.select_one(
            'td.text a[href*="/company/"]'
        )

        if company_link:

            href = company_link.get(
                "href"
            )

            if href:

                row_data["company_url"] = urljoin(
                    BASE_URL,
                    href,
                )

        rows.append(row_data)

    return rows


# ============================================================
# BUILD PAGE URL
# ============================================================

def build_page_url(
    base_url,
    page_number,
):
    """
    Preserve the existing URL and add/replace page=N.
    """

    parts = urlsplit(
        base_url
    )

    query = parse_qs(
        parts.query,
        keep_blank_values=True,
    )

    query["page"] = [
        str(page_number)
    ]

    new_query = urlencode(
        query,
        doseq=True,
    )

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            new_query,
            parts.fragment,
        )
    )


# ============================================================
# FIND NEXT PAGE
# ============================================================

def get_next_page_url(
    soup,
    current_url,
    current_page,
    total_pages,
):
    """
    Find Screener's Next pagination URL.

    Falls back to page=N when required.
    """

    if current_page >= total_pages:
        return None

    paging = soup.select_one(
        "div[data-paging]"
    )

    if paging is not None:

        links = paging.select(
            "a"
        )

        for link in links:

            link_text = link.get_text(
                " ",
                strip=True,
            ).lower()

            if "next" in link_text:

                href = link.get(
                    "href"
                )

                if href:

                    return urljoin(
                        current_url,
                        href,
                    )

    return build_page_url(
        current_url,
        current_page + 1,
    )


# ============================================================
# FETCH PAGE WITH RATE-LIMIT HANDLING
# ============================================================

def fetch_page(
    session,
    page_url,
):
    """
    Fetch one page.

    Normal request:
        wait PAGE_DELAY seconds before request.

    429:
        wait progressively longer and retry.
    """

    # --------------------------------------------------------
    # Normal spacing between requests
    # --------------------------------------------------------

    print(
        f"\nWaiting {PAGE_DELAY} seconds before request..."
    )

    time.sleep(
        PAGE_DELAY
    )

    # --------------------------------------------------------
    # Request + retry handling
    # --------------------------------------------------------

    for attempt, retry_delay in enumerate(
        RETRY_DELAYS,
        start=1,
    ):

        print(
            f"Fetching page: {page_url}"
        )

        response = session.get(
            page_url,
            timeout=30,
        )

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        if response.status_code == 200:

            return response

        # ----------------------------------------------------
        # Rate limited
        # ----------------------------------------------------

        if response.status_code == 429:

            print(
                f"429 Too Many Requests."
            )

            print(
                f"Retry {attempt}/{len(RETRY_DELAYS)} "
                f"in {retry_delay} seconds..."
            )

            time.sleep(
                retry_delay
            )

            continue

        # ----------------------------------------------------
        # Other HTTP error
        # ----------------------------------------------------

        response.raise_for_status()

    raise RuntimeError(
        f"Screener continued returning HTTP 429 "
        f"after {len(RETRY_DELAYS)} retries."
    )


# ============================================================
# SCRAPE ONE PAGE
# ============================================================

def scrape_page(
    session,
    page_url,
):
    """
    Fetch and parse one Screener page.
    """

    response = fetch_page(
        session=session,
        page_url=page_url,
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    page_info = get_page_info(
        soup
    )

    headers = extract_headers(
        soup
    )

    rows = extract_rows(
        soup,
        headers,
    )

    next_page_url = get_next_page_url(
        soup,
        page_url,
        page_info["current_page"],
        page_info["total_pages"],
    )

    return {
        "page_info": page_info,
        "headers": headers,
        "rows": rows,
        "next_page_url": next_page_url,
    }


# ============================================================
# SCRAPE COMPLETE SCREEN
# ============================================================

def scrape_screen(
    session,
    screen_url,
):
    """
    Scrape every page of one Screener screen.

    The authenticated session comes from outerFlow.py.
    """

    print("\n========================================")
    print("INNER FLOW START")
    print("========================================")

    print(
        f"Screen URL: {screen_url}"
    )

    all_rows = []

    all_headers = None

    page_results = []

    current_url = screen_url

    expected_total_results = None

    while current_url:

        page_data = scrape_page(
            session=session,
            page_url=current_url,
        )

        page_info = page_data[
            "page_info"
        ]

        headers = page_data[
            "headers"
        ]

        rows = page_data[
            "rows"
        ]

        next_page_url = page_data[
            "next_page_url"
        ]

        # ----------------------------------------------------
        # Capture first-page metadata
        # ----------------------------------------------------

        if all_headers is None:

            all_headers = headers

        if expected_total_results is None:

            expected_total_results = (
                page_info["total_results"]
            )

        # ----------------------------------------------------
        # Store page result
        # ----------------------------------------------------

        page_results.append(
            {
                "page": page_info[
                    "current_page"
                ],
                "rows": len(rows),
            }
        )

        # ----------------------------------------------------
        # Add rows
        # ----------------------------------------------------

        all_rows.extend(
            rows
        )

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        print(
            f"Page "
            f"{page_info['current_page']}/"
            f"{page_info['total_pages']} "
            f"| Rows this page: "
            f"{len(rows)} "
            f"| Collected: "
            f"{len(all_rows)}/"
            f"{expected_total_results}"
        )

        # ----------------------------------------------------
        # Final page
        # ----------------------------------------------------

        if (
            page_info["current_page"]
            >= page_info["total_pages"]
        ):

            print(
                "Final page reached."
            )

            break

        # ----------------------------------------------------
        # Next page
        # ----------------------------------------------------

        if not next_page_url:

            raise RuntimeError(
                f"Page "
                f"{page_info['current_page']} says "
                f"there are more pages, but no next "
                f"page URL was found."
            )

        current_url = next_page_url

    # ========================================================
    # VALIDATION
    # ========================================================

    print("\n========================================")
    print("INNER FLOW COMPLETE")
    print("========================================")

    print(
        f"Expected results: "
        f"{expected_total_results}"
    )

    print(
        f"Collected rows: "
        f"{len(all_rows)}"
    )

    if (
        expected_total_results is not None
        and len(all_rows) == expected_total_results
    ):

        print(
            "Row count validation: PASSED"
        )

    else:

        print(
            "WARNING: Row count validation FAILED"
        )

    return {
        "screen_url": screen_url,
        "total_results": expected_total_results,
        "total_rows_collected": len(all_rows),
        "headers": all_headers,
        "pages": page_results,
        "rows": all_rows,
    }
    
    
    
# dataFile.py


# ============================================================
# DIRECTORY STRUCTURE
# ============================================================

BASE_DATA_DIR = Path("screener_data")

GROUPS_DIR = BASE_DATA_DIR / "groups"

FINAL_DIR = BASE_DATA_DIR / "final"


# ============================================================
# CREATE DIRECTORY STRUCTURE
# ============================================================

def initialize_data_structure():
    """
    Create the required data directories.
    """

    GROUPS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    FINAL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"Data directory ready: "
        f"{BASE_DATA_DIR.resolve()}"
    )


# ============================================================
# FILE NAME HANDLING
# ============================================================

def make_safe_filename(name):
    """
    Convert a screen/group name into a safe filename.

    Example:
        Core Business Quality
        ->
        core_business_quality.csv
    """

    filename = name.lower().strip()

    filename = re.sub(
        r"[^a-z0-9]+",
        "_",
        filename,
    )

    filename = filename.strip("_")

    return filename


# ============================================================
# GROUP CSV PATH
# ============================================================

def get_group_file_path(
    group_name,
    group_number=None,
):
    """
    Return the CSV path for one group.

    Example:
        screener_data/groups/
        01_core_business_quality.csv
    """

    safe_name = make_safe_filename(
        group_name
    )

    if group_number is not None:

        filename = (
            f"{group_number:02d}_"
            f"{safe_name}.csv"
        )

    else:

        filename = (
            f"{safe_name}.csv"
        )

    return GROUPS_DIR / filename


# ============================================================
# SAVE GROUP DATA
# ============================================================

def save_group_csv(
    group_name,
    rows,
    group_number=None,
):
    """
    Save the extracted rows for one Screener group.

    Parameters:
        group_name:
            Name of the Screener group.

        rows:
            List of dictionaries returned by innerFlow.

        group_number:
            Optional group order number.
    """

    initialize_data_structure()

    file_path = get_group_file_path(
        group_name=group_name,
        group_number=group_number,
    )

    # --------------------------------------------------------
    # Handle empty result
    # --------------------------------------------------------

    if not rows:

        print(
            f"No data to save for: "
            f"{group_name}"
        )

        return file_path

    # --------------------------------------------------------
    # Build consistent column list
    # --------------------------------------------------------

    headers = []

    for row in rows:

        for key in row.keys():

            if key not in headers:
                headers.append(key)

    # --------------------------------------------------------
    # Write CSV
    # --------------------------------------------------------

    with open(
        file_path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=headers,
            extrasaction="ignore",
        )

        writer.writeheader()

        writer.writerows(
            rows
        )
    upload_file(file_path)
    print(
        f"Saved {len(rows)} rows:"
    )

    print(
        f"  {file_path.resolve()}"
    )

    return file_path


# ============================================================
# FINAL CSV PATH
# ============================================================

def get_final_file_path(
    filename="final_candidates.csv",
):
    """
    Return the path for a final output file.
    """

    initialize_data_structure()

    return FINAL_DIR / filename


# ============================================================
# SAVE FINAL DATA
# ============================================================

def save_final_csv(
    rows,
    filename="final_candidates.csv",
):
    """
    Save final/merged candidate data.

    This function does not perform filtering.
    Filtering logic belongs elsewhere.
    """

    initialize_data_structure()

    file_path = get_final_file_path(
        filename
    )

    if not rows:

        print(
            "No final data to save."
        )

        return file_path

    headers = []

    for row in rows:

        for key in row.keys():

            if key not in headers:
                headers.append(key)

    with open(
        file_path,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=headers,
            extrasaction="ignore",
        )

        writer.writeheader()

        writer.writerows(
            rows
        )
    upload_file(file_path)
    print(
        f"Saved final data: "
        f"{len(rows)} rows"
    )

    print(
        f"  {file_path.resolve()}"
    )

    return file_path


# ============================================================
# MAIN TEST
# ============================================================

if __name__ == "__main__":

    initialize_data_structure()

    print(
        "\nData structure initialized."
    )

    print(
        f"Groups directory: "
        f"{GROUPS_DIR.resolve()}"
    )

    print(
        f"Final directory: "
        f"{FINAL_DIR.resolve()}"
    )