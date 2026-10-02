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
import os
import re
import secrets
import time
from collections import Counter, defaultdict
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

# Use centralized storage when available. Fall back to APP_STORAGE_ROOT
# or the project root so this module also works when run directly.
try:
    from storage import GROUPS_DIR as STORAGE_GROUPS_DIR
    from storage import SESSION_DIR as STORAGE_SESSION_DIR
except ImportError:
    MODULE_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = (
        MODULE_DIR.parent
        if MODULE_DIR.name.casefold() == "scripts"
        else MODULE_DIR
    )
    STORAGE_ROOT = Path(
        os.getenv("APP_STORAGE_ROOT", str(PROJECT_ROOT))
    ).expanduser().resolve()
    STORAGE_SESSION_DIR = STORAGE_ROOT / "session"
    STORAGE_GROUPS_DIR = STORAGE_ROOT / "screener_data" / "groups"

SESSION_DIR = Path(STORAGE_SESSION_DIR)

GROUPS_DIR = Path(STORAGE_GROUPS_DIR)


# ============================================================
# SESSION
# ============================================================


def _utc_now() -> str:
    """Return a compact UTC timestamp for session metadata."""

    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def create_screener_session():
    """Create one HTTP session for the complete Screener operation."""

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
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    return session


# ============================================================
# SESSION PERSISTENCE
# ============================================================


def _normalize_identity(email: str | None) -> str:
    """Normalize a Screener login identity for stable session lookup."""

    return str(email or "").strip().casefold()


def _session_file_for_email(email: str | None) -> Path:
    """Return a user-scoped session path without exposing the email."""

    identity = _normalize_identity(email)
    if not identity:
        raise ValueError("A Screener email is required to access its session.")

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return SESSION_DIR / f"screener_{digest}.json"


def _read_session_payload(session_file: Path) -> dict:
    """Read one user's saved session payload."""

    if not session_file.exists():
        return {}

    try:
        with open(session_file, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception as exc:
        print(f"Could not read saved Screener session: {exc}")
        return {}

    return payload if isinstance(payload, dict) else {}


def save_session(session, email: str, session_id: str | None = None) -> str:
    """Persist authenticated cookies for exactly one Screener account."""

    session_file = _session_file_for_email(email)
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    existing = _read_session_payload(session_file)
    cookies = requests.utils.dict_from_cookiejar(session.cookies)
    stable_session_id = str(
        session_id
        or existing.get("session_id")
        or secrets.token_urlsafe(32)
    ).strip()

    payload = {
        "session_id": stable_session_id,
        "email": _normalize_identity(email),
        "saved_at": existing.get("saved_at") or _utc_now(),
        "last_validated_at": _utc_now(),
        "cookies": cookies,
    }

    temp_file = session_file.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    temp_file.replace(session_file)
    return stable_session_id


def load_saved_session(session, email: str) -> bool:
    """Load the saved cookies belonging to the supplied Screener account."""

    session_file = _session_file_for_email(email)
    payload = _read_session_payload(session_file)
    cookies = payload.get("cookies")

    if not isinstance(cookies, dict) or not cookies:
        return False

    try:
        session.cookies = requests.utils.cookiejar_from_dict(cookies)
        return True
    except Exception as exc:
        print(f"Could not load saved session cookies: {exc}")
        return False


def get_saved_session_info(email: str | None = None) -> dict:
    """Return safe metadata for one user's persisted session."""

    if not _normalize_identity(email):
        return {
            "exists": False,
            "saved_at": "",
            "last_validated_at": "",
            "file": "",
        }

    session_file = _session_file_for_email(email)
    payload = _read_session_payload(session_file)

    return {
        "exists": session_file.exists(),
        "saved_at": str(payload.get("saved_at") or "").strip(),
        "last_validated_at": str(
            payload.get("last_validated_at") or ""
        ).strip(),
        "file": str(session_file),
    }


def get_identity_for_session_id(session_id: str | None) -> dict:
    """Resolve an opaque browser session id to its saved Screener identity."""

    target = str(session_id or "").strip()
    if not target or not SESSION_DIR.exists():
        return {}

    for session_file in SESSION_DIR.glob("screener_*.json"):
        payload = _read_session_payload(session_file)
        if str(payload.get("session_id") or "").strip() != target:
            continue

        email = _normalize_identity(payload.get("email"))
        if not email:
            continue

        return {
            "email": email,
            "session_id": target,
            "file": str(session_file),
        }

    return {}


def clear_saved_session(email: str | None = None) -> None:
    """Remove only the persisted session for the supplied account."""

    session_file = _session_file_for_email(email)

    try:
        session_file.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Could not clear Screener session: {exc}"
        ) from exc


# ============================================================
# AUTHENTICATION
# ============================================================


def _resolve_email(
    email: str | None = None,
    session_id: str | None = None,
) -> str:
    """Resolve the Screener identity from email, session id, or environment."""

    resolved_email = str(email or "").strip()

    if not resolved_email and session_id:
        identity = get_identity_for_session_id(session_id)
        resolved_email = str(identity.get("email") or "").strip()

    if not resolved_email:
        resolved_email = os.getenv("SCREENER_EMAIL", "").strip()

    return resolved_email


def _resolve_credentials(
    email: str | None = None,
    password: str | None = None,
) -> tuple[str, str]:
    """Resolve credentials only when a fresh login is required."""

    resolved_email = _resolve_email(email)
    resolved_password = (
        password
        if password is not None
        else os.getenv("SCREENER_PASSWORD", "")
    )

    if not str(resolved_password):
        raise RuntimeError(
            "Screener credentials are required for a fresh login. "
            "Enter the email and password in the dashboard, or configure "
            "SCREENER_EMAIL and SCREENER_PASSWORD."
        )

    return resolved_email, str(resolved_password)


def is_authenticated(session) -> bool:
    """Check the authenticated Explore page."""

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

        for heading in soup.select("h2.h3"):
            text = heading.get_text(" ", strip=True)
            if text.casefold() == "your screens":
                return True

        return False

    except requests.RequestException:
        return False


def perform_login(
    session,
    email: str | None = None,
    password: str | None = None,
) -> None:
    """Perform a fresh Screener login using supplied or environment credentials."""

    resolved_email, resolved_password = _resolve_credentials(
        email=email,
        password=password,
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

    csrf_input = login_soup.select_one(
        'input[name="csrfmiddlewaretoken"]'
    )

    if csrf_input is None:
        raise RuntimeError(
            "Could not find csrfmiddlewaretoken on Screener login page."
        )

    csrf_token = csrf_input.get("value")

    if not csrf_token:
        raise RuntimeError(
            "Screener returned an empty CSRF token."
        )

    login_data = {
        "csrfmiddlewaretoken": csrf_token,
        "username": resolved_email,
        "password": resolved_password,
        "next": "/explore/",
    }

    login_headers = {
        "Referer": LOGIN_URL,
        "Origin": BASE_URL,
        "Content-Type": "application/x-www-form-urlencoded",
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
            "Login completed, but Screener did not return the authenticated "
            "'Your screens' section. Check the credentials and account access."
        )

    save_session(
        session,
        email=resolved_email,
    )


def authenticate_screener(
    session,
    email: str | None = None,
    password: str | None = None,
    session_id: str | None = None,
    force_login: bool = False,
) -> str:
    """Reuse a saved session by email or opaque session id."""

    resolved_email = _resolve_email(
        email=email,
        session_id=session_id,
    )

    if not force_login and resolved_email:
        if load_saved_session(session, resolved_email):
            if is_authenticated(session):
                save_session(session, resolved_email)
                return resolved_email

            session.cookies.clear()
            clear_saved_session(resolved_email)

    if not resolved_email:
        raise RuntimeError(
            "A Screener account is required for a fresh login. "
            "Enter the email in the dashboard."
        )

    perform_login(
        session,
        email=resolved_email,
        password=password,
    )

    return resolved_email


def get_screener_status(
    email: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Validate one account's persisted Screener session."""

    resolved_email = _normalize_identity(email)

    if not resolved_email and session_id:
        identity = get_identity_for_session_id(session_id)
        resolved_email = _normalize_identity(identity.get("email"))

    if not resolved_email:
        return {
            "connected": False,
            "saved_at": "",
            "last_validated_at": "",
            "session_id": "",
        }

    session = create_screener_session()

    try:
        info = get_saved_session_info(resolved_email)

        if not info["exists"] or not load_saved_session(session, resolved_email):
            return {
                "connected": False,
                "saved_at": info.get("saved_at", ""),
                "last_validated_at": info.get("last_validated_at", ""),
            }

        connected = is_authenticated(session)

        if connected:
            save_session(session, resolved_email)
        else:
            session.cookies.clear()
            clear_saved_session(resolved_email)

        refreshed = get_saved_session_info(resolved_email)

        payload = _read_session_payload(
            _session_file_for_email(resolved_email)
        )

        return {
            "connected": connected,
            "saved_at": refreshed.get("saved_at", ""),
            "last_validated_at": refreshed.get("last_validated_at", ""),
            "session_id": str(payload.get("session_id") or ""),
        }

    finally:
        session.close()


def connect_screener(
    email: str | None = None,
    password: str | None = None,
    session_id: str | None = None,
    force_login: bool = False,
) -> dict:
    """Connect one Screener account and persist only its session cookies."""

    session = create_screener_session()

    try:
        resolved_email = authenticate_screener(
            session,
            email=email,
            password=password,
            session_id=session_id,
            force_login=force_login,
        )

        payload = _read_session_payload(
            _session_file_for_email(resolved_email)
        )

        return {
            "connected": True,
            "session_file": str(_session_file_for_email(resolved_email)),
            "session_id": str(payload.get("session_id") or ""),
        }

    finally:
        session.close()


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


def discover_custom_screens(
    email: str | None = None,
    password: str | None = None,
    session_id: str | None = None,
) -> list[dict]:
    """Authenticate and return discovered custom screens."""

    session = create_screener_session()

    try:
        authenticate_screener(
            session,
            email=email,
            password=password,
            session_id=session_id,
        )

        return get_custom_screens(session)

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
    Automatically build the hierarchy:

        GROUP
            -> SUBGROUP
                -> ITEM

    GROUP:
        Determined from the shared leading title identity.

    SUBGROUP:
        Screens with the same complete normalized title.

    ITEM:
        The individual screen metadata belonging to that subgroup.
        The description is the item-level label shown to the user.

    PACK:
        A top-level group is a PACK when every screen in the
        group has the same non-empty description.

    NORMAL:
        A top-level group has differing descriptions.

    SINGLE:
        A top-level group contains only one screen.

    The original flat ``screens`` list is deliberately retained
    on every group and subgroup so existing execution code remains
    compatible while the dashboard can use the hierarchy.
    """

    grouped = defaultdict(list)

    # --------------------------------------------------------
    # TOP-LEVEL GROUP
    # --------------------------------------------------------
    # Keep the existing leading-title grouping logic.
    #
    # QUALITY CAPITAL AND INFRASTRUCTURE INTENSIVE -> quality
    # QUALITY FINANCE                              -> quality
    # QUALITY NON FINANCE                          -> quality
    #
    # VALUATION FINANCE                            -> valuation
    # VALUATION NON FINANCE                        -> valuation
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

        # ----------------------------------------------------
        # SUBGROUP
        # ----------------------------------------------------
        # A subgroup is the actual distinct screen title.
        #
        # Example:
        #
        # QUALITY
        #   ├── QUALITY CAPITAL AND INFRASTRUCTURE INTENSIVE
        #   ├── QUALITY FINANCE
        #   └── QUALITY NON FINANCE
        #
        # Each subgroup then contains its item(s).
        # ----------------------------------------------------

        subgrouped = defaultdict(list)

        for screen in group_screens:

            subgroup_key = normalize_text(
                screen["title"]
            )

            subgrouped[
                subgroup_key
            ].append(
                screen
            )

        subgroups = []

        for (
            subgroup_key,
            subgroup_screens,
        ) in subgrouped.items():

            subgroup_descriptions = [
                normalize_text(
                    screen["description"]
                )
                for screen in subgroup_screens
            ]

            non_empty_subgroup_descriptions = [
                description
                for description in subgroup_descriptions
                if description
            ]

            unique_subgroup_descriptions = set(
                non_empty_subgroup_descriptions
            )

            # A subgroup is a pack only when its own
            # items all carry the same non-empty description.
            if (
                len(subgroup_screens) > 1
                and
                len(non_empty_subgroup_descriptions)
                == len(subgroup_screens)
                and
                len(unique_subgroup_descriptions)
                == 1
            ):

                subgroup_type = "pack"

            elif len(subgroup_screens) == 1:

                subgroup_type = "single"

            else:

                subgroup_type = "normal"

            subgroups.append(
                {
                    "name": subgroup_screens[0]["title"],
                    "key": subgroup_key,
                    "type": subgroup_type,
                    "screens": subgroup_screens,
                    "items": subgroup_screens,
                }
            )

        subgroups.sort(
            key=lambda subgroup:
            subgroup["name"].casefold()
        )

        # ----------------------------------------------------
        # TOP-LEVEL GROUP TYPE
        # ----------------------------------------------------

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
            and
            len(unique_descriptions)
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

            # Existing execution compatibility.
            "screens": group_screens,

            # New hierarchy.
            "subgroups": subgroups,
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


def make_subgroup_label(
    subgroup,
):
    """
    Display the subgroup title.

    The subgroup is the actual distinct screen title.
    """

    return subgroup[
        "name"
    ]


def make_item_label(
    item,
):
    """
    Display one item belonging to a subgroup.

    Item display is:
        TITLE | DESCRIPTION

    This keeps the actual screen metadata visible rather than
    inventing another naming layer.
    """

    return make_screen_label(
        item
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
    email: str | None = None,
    password: str | None = None,
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
            session,
            email=email,
            password=password,
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