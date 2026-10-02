"""
Screener outer flow.

Responsibilities
----------------
1. Authenticate with Screener.
2. Discover the user's custom screens from /explore/.
3. Extract title, description and href.
4. Automatically group screens using the shared leading
   title identity.
5. Detect PACK groups when all screens in a group have the
   same description.
6. Let the dashboard run:
      - SINGLE -> exactly one screen
      - MERGE  -> multiple screens
      - PACK   -> automatic merge of the complete pack
7. Save one output CSV for the selected operation.

No Screener screen names are hard-coded.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from getpass import getpass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from innerFlow import scrape_screen


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://www.screener.in"

LOGIN_URL = f"{BASE_URL}/login/"

EXPLORE_URL = f"{BASE_URL}/explore/"

SESSION_FILE = Path(
    "screener_session.json"
)

BASE_DATA_DIR = Path(
    "screener_data"
)

GROUPS_DIR = (
    BASE_DATA_DIR / "groups"
)


# ============================================================
# SESSION
# ============================================================

def create_screener_session():
    """
    Create one HTTP session for the complete Screener run.
    """

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,image/avif,image/webp,"
                "*/*;q=0.8"
            ),
            "Accept-Language": (
                "en-US,en;q=0.9"
            ),
        }
    )

    return session


# ============================================================
# SESSION PERSISTENCE
# ============================================================

def save_session(session):
    """
    Save Screener cookies.

    Password is never stored.
    """

    cookies = (
        requests.utils
        .dict_from_cookiejar(
            session.cookies
        )
    )

    with open(
        SESSION_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            cookies,
            file,
            indent=2,
        )


def load_saved_session(session):
    """
    Load saved Screener cookies.

    Returns:
        True  -> loaded
        False -> unavailable/invalid file
    """

    if not SESSION_FILE.exists():

        return False

    try:

        with open(
            SESSION_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            cookies = json.load(
                file
            )

        session.cookies = (
            requests.utils
            .cookiejar_from_dict(
                cookies
            )
        )

        return True

    except Exception as exc:

        print(
            f"Could not load saved session: {exc}"
        )

        return False


# ============================================================
# AUTHENTICATION
# ============================================================

def is_authenticated(session):
    """
    Check the authenticated Explore page.
    """

    try:

        response = session.get(
            EXPLORE_URL,
            timeout=30,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        for heading in soup.select(
            "h2.h3"
        ):

            text = heading.get_text(
                " ",
                strip=True,
            )

            if (
                text.casefold()
                == "your screens"
            ):

                return True

        return False

    except requests.RequestException:

        return False


def perform_login(session):
    """
    Perform fresh Screener login.
    """

    print(
        "\n========================================"
    )

    print(
        "FRESH SCREENER LOGIN"
    )

    print(
        "========================================"
    )

    login_response = session.get(
        LOGIN_URL,
        timeout=30,
    )

    login_response.raise_for_status()

    login_soup = BeautifulSoup(
        login_response.text,
        "html.parser",
    )

    csrf_input = (
        login_soup.select_one(
            'input[name="csrfmiddlewaretoken"]'
        )
    )

    if csrf_input is None:

        raise RuntimeError(
            "Could not find csrfmiddlewaretoken "
            "on Screener login page."
        )

    csrf_token = csrf_input.get(
        "value"
    )

    if not csrf_token:

        raise RuntimeError(
            "Screener returned an empty CSRF token."
        )

    email = input(
        "\nScreener email: "
    ).strip()

    password = getpass(
        "Screener password: "
    )

    if not email or not password:

        raise RuntimeError(
            "Email and password are required."
        )

    login_data = {
        "csrfmiddlewaretoken": csrf_token,
        "username": email,
        "password": password,
        "next": "/explore/",
    }

    login_headers = {
        "Referer": LOGIN_URL,
        "Origin": BASE_URL,
        "Content-Type": (
            "application/x-www-form-urlencoded"
        ),
    }

    login_response = session.post(
        LOGIN_URL,
        data=login_data,
        headers=login_headers,
        timeout=30,
        allow_redirects=True,
    )

    login_response.raise_for_status()

    if not is_authenticated(session):

        raise RuntimeError(
            "Login completed, but Screener did not "
            "return the authenticated 'Your screens' section."
        )

    save_session(
        session
    )

    print(
        "Authentication successful."
    )


def authenticate_screener(session):
    """
    Reuse saved session when possible.
    """

    if load_saved_session(
        session
    ):

        if is_authenticated(
            session
        ):

            print(
                "Saved Screener session is valid."
            )

            return

        session.cookies.clear()

    perform_login(
        session
    )


# ============================================================
# SCREEN DISCOVERY
# ============================================================

def get_custom_screens(session):
    """
    Discover all screens under 'Your screens'.

    Every screen is represented as:

        {
            "title": "...",
            "description": "...",
            "href": "..."
        }
    """

    response = session.get(
        EXPLORE_URL,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    # --------------------------------------------------------
    # Locate "Your screens"
    # --------------------------------------------------------

    heading = None

    for element in soup.select(
        "h2.h3"
    ):

        text = element.get_text(
            " ",
            strip=True,
        )

        if text.casefold() == "your screens":

            heading = element
            break

    if heading is None:

        raise RuntimeError(
            "Could not find 'Your screens' "
            "on Screener Explore."
        )

    your_screens_card = heading.parent

    if your_screens_card is None:

        raise RuntimeError(
            "Could not identify the "
            "'Your screens' card."
        )

    # --------------------------------------------------------
    # Extract screens
    # --------------------------------------------------------

    screens = []

    for item in your_screens_card.select(
        "a.screen-item"
    ):

        title_element = (
            item.select_one(
                "div.font-weight-500"
            )
        )

        if title_element is None:
            continue

        title = title_element.get_text(
            " ",
            strip=True,
        )

        description_element = (
            item.select_one(
                "p.sub"
            )
        )

        if description_element is None:

            description_element = (
                item.find("p")
            )

        description = ""

        if description_element is not None:

            description = (
                description_element
                .get_text(
                    " ",
                    strip=True,
                )
            )

        href = item.get(
            "href"
        )

        if not title or not href:
            continue

        screens.append(
            {
                "title": title,
                "description": description,
                "href": href,
            }
        )

    if not screens:

        raise RuntimeError(
            "Found 'Your screens' but no "
            "screen links were discovered."
        )

    print(
        f"Discovered {len(screens)} custom screens."
    )

    return screens


def discover_custom_screens():
    """
    Authenticate and return discovered screens.
    """

    session = (
        create_screener_session()
    )

    try:

        authenticate_screener(
            session
        )

        return get_custom_screens(
            session
        )

    finally:

        session.close()


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(
    value,
):
    """
    Normalize text for comparisons.
    """

    if value is None:

        return ""

    value = str(
        value
    ).strip().casefold()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value


def title_tokens(
    title,
):
    """
    Convert title to normalized tokens.
    """

    return re.findall(
        r"[a-z0-9]+",
        normalize_text(
            title
        ),
    )


# ============================================================
# GROUP DETECTION
# ============================================================

def get_leading_title_identity(
    title,
):
    """
    Return the first meaningful title token.

    Examples:

        QUALITY CAPITAL AND INFRASTRUCTURE INTENSIVE
            -> quality

        QUALITY FINANCE
            -> quality

        QUALITY NON FINANCE
            -> quality

        VALUATION NON FINANCE
            -> valuation

        VALUATION FINANCE
            -> valuation

    This prevents words such as:
        and
        infrastructure
        intensive
    from becoming accidental group names.
    """

    tokens = title_tokens(
        title
    )

    stopwords = {
        "and",
        "or",
        "the",
        "of",
        "for",
        "in",
        "on",
        "to",
        "with",
        "a",
        "an",
    }

    for token in tokens:

        if token not in stopwords:

            return token

    return normalize_text(
        title
    )


def build_screen_groups(
    screens,
):
    """
    Automatically build screen groups.

    Grouping:
        Screens whose leading title identity is the same
        belong to the same group.

    PACK:
        All screens in a group have the same description.

    NORMAL:
        Descriptions differ.

    SINGLE:
        Only one screen has that title identity.
    """

    grouped = defaultdict(
        list
    )

    # --------------------------------------------------------
    # Group by leading title identity
    # --------------------------------------------------------

    for screen in screens:

        group_key = (
            get_leading_title_identity(
                screen["title"]
            )
        )

        grouped[
            group_key
        ].append(
            screen
        )

    result = {}

    for group_key, group_screens in (
        grouped.items()
    ):

        descriptions = [
            normalize_text(
                screen["description"]
            )
            for screen in group_screens
        ]

        non_empty_descriptions = [
            description
            for description in descriptions
            if description
        ]

        unique_descriptions = set(
            non_empty_descriptions
        )

        if len(group_screens) == 1:

            group_type = "single"

        elif (
            len(non_empty_descriptions)
            == len(group_screens)
            and len(unique_descriptions)
            == 1
        ):

            group_type = "pack"

        else:

            group_type = "normal"

        result[
            group_key
        ] = {
            "name": group_key,
            "type": group_type,
            "screens": group_screens,
        }

    return dict(
        sorted(
            result.items(),
            key=lambda item:
            item[0].casefold(),
        )
    )


# ============================================================
# DISPLAY LABELS
# ============================================================

def make_screen_label(
    screen,
):
    """
    Display title + description.
    """

    title = screen[
        "title"
    ]

    description = screen[
        "description"
    ]

    if description:

        return (
            f"{title} | "
            f"{description}"
        )

    return title


def make_group_label(
    group,
):
    """
    Display group label.
    """

    return (
        f"{group['name'].upper()} "
        f"({group['type'].upper()})"
    )


def make_screen_key(
    screen,
):
    """
    href is the stable unique identity.
    """

    return screen[
        "href"
    ]


# ============================================================
# SCREEN EXECUTION
# ============================================================

def process_screen(
    session,
    screen,
):
    """
    Run one screen through innerFlow.
    """

    screen_url = urljoin(
        BASE_URL,
        screen["href"],
    )

    print(
        "\n========================================"
    )

    print(
        f"TITLE: {screen['title']}"
    )

    print(
        f"DESCRIPTION: "
        f"{screen['description']}"
    )

    print(
        f"URL: {screen_url}"
    )

    print(
        "========================================"
    )

    return scrape_screen(
        session=session,
        screen_url=screen_url,
    )


# ============================================================
# MERGE
# ============================================================

def merge_screen_results(
    screen_results,
):
    """
    Union rows from multiple screens.

    Company identity:
        company_id

    If the same company appears in more than one screen,
    one row is retained and the screen sources are recorded.
    """

    if not screen_results:

        raise ValueError(
            "No screen results supplied."
        )

    merged_rows = {}

    source_map = defaultdict(
        set
    )

    for screen, result in (
        screen_results
    ):

        screen_label = (
            make_screen_label(
                screen
            )
        )

        for row in result[
            "rows"
        ]:

            company_id = row.get(
                "company_id"
            )

            if company_id is None:

                company_id = row.get(
                    "company_name"
                )

            if company_id is None:

                continue

            company_id = str(
                company_id
            )

            if company_id not in merged_rows:

                merged_rows[
                    company_id
                ] = dict(
                    row
                )

            else:

                existing = merged_rows[
                    company_id
                ]

                for key, value in (
                    row.items()
                ):

                    if key not in existing:

                        existing[
                            key
                        ] = value

            source_map[
                company_id
            ].add(
                screen_label
            )

    rows = []

    for company_id, row in (
        merged_rows.items()
    ):

        row[
            "screen_sources"
        ] = " | ".join(
            sorted(
                source_map[
                    company_id
                ]
            )
        )

        rows.append(
            row
        )

    return rows


# ============================================================
# OUTPUT NAME
# ============================================================

def make_safe_filename(
    value,
):
    """
    Make a filesystem-safe filename.
    """

    value = normalize_text(
        value
    )

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    return value.strip(
        "_"
    )


def make_selection_output_name(
    group,
    selected_screens,
    mode,
):
    """
    Create a readable but unique output filename.
    """

    group_name = make_safe_filename(
        group["name"]
    )

    mode_name = make_safe_filename(
        mode
    )

    screen_part = "__".join(
        make_safe_filename(
            screen["title"]
        )
        for screen in selected_screens
    )

    if len(
        screen_part
    ) > 120:

        href_string = "|".join(
            screen["href"]
            for screen in selected_screens
        )

        digest = hashlib.sha1(
            href_string.encode(
                "utf-8"
            )
        ).hexdigest()[:10]

        screen_part = (
            f"{len(selected_screens)}"
            f"_screens_{digest}"
        )

    return (
        f"{group_name}__"
        f"{mode_name}__"
        f"{screen_part}"
    )


# ============================================================
# SAVE
# ============================================================

def save_results_csv(
    rows,
    output_name,
):
    """
    Save one Single/Merge result CSV.
    """

    GROUPS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_name = (
        make_safe_filename(
            output_name
        )
    )

    output_file = (
        GROUPS_DIR
        / f"{safe_name}.csv"
    )

    if not rows:

        with open(
            output_file,
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            writer = csv.writer(
                file
            )

            writer.writerow(
                ["company_id"]
            )

        return output_file

    headers = []

    for row in rows:

        for key in row.keys():

            if key not in headers:

                headers.append(
                    key
                )

    with open(
        output_file,
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

    print(
        f"Saved {len(rows)} rows:"
    )

    print(
        output_file.resolve()
    )

    return output_file


# ============================================================
# RUN SELECTION
# ============================================================

def run_selection(
    group,
    selected_screens,
    mode,
):
    """
    Run the selected screens.

    SINGLE:
        exactly one screen

    MERGE:
        two or more screens

    PACK:
        dashboard sends all screens as MERGE
    """

    if not group:

        raise ValueError(
            "No group supplied."
        )

    if not selected_screens:

        raise ValueError(
            "No screens selected."
        )

    mode = normalize_text(
        mode
    )

    if group["type"] == "pack":

        mode = "merge"

        selected_screens = (
            group["screens"]
        )

    elif group["type"] == "single":

        mode = "single"

    if mode == "single":

        if len(
            selected_screens
        ) != 1:

            raise ValueError(
                "Single mode requires "
                "exactly one screen."
            )

    elif mode == "merge":

        if len(
            selected_screens
        ) < 2:

            raise ValueError(
                "Merge mode requires at least "
                "two screens."
            )

    else:

        raise ValueError(
            "Mode must be Single or Merge."
        )

    session = (
        create_screener_session()
    )

    screen_results = []

    try:

        authenticate_screener(
            session
        )

        for screen in selected_screens:

            result = process_screen(
                session=session,
                screen=screen,
            )

            screen_results.append(
                (
                    screen,
                    result,
                )
            )

            if (
                screen
                != selected_screens[-1]
            ):

                time.sleep(
                    1
                )

        # ----------------------------------------------------
        # SINGLE
        # ----------------------------------------------------

        if mode == "single":

            rows = (
                screen_results[0][1][
                    "rows"
                ]
            )

        # ----------------------------------------------------
        # MERGE
        # ----------------------------------------------------

        else:

            rows = merge_screen_results(
                screen_results
            )

        output_name = (
            make_selection_output_name(
                group=group,
                selected_screens=selected_screens,
                mode=mode,
            )
        )

        output_file = (
            save_results_csv(
                rows=rows,
                output_name=output_name,
            )
        )

        return {
            "group": group,
            "mode": mode,
            "screens": selected_screens,
            "rows": rows,
            "row_count": len(rows),
            "file": output_file,
        }

    finally:

        session.close()

        print(
            "Screener selection session closed."
        )


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    screens = (
        discover_custom_screens()
    )

    groups = (
        build_screen_groups(
            screens
        )
    )

    print(
        "\n========================================"
    )

    print(
        "DISCOVERED GROUPS"
    )

    print(
        "========================================"
    )

    for group in groups.values():

        print(
            f"\n{make_group_label(group)}"
        )

        for screen in (
            group["screens"]
        ):

            print(
                f"  - "
                f"{make_screen_label(screen)}"
            )