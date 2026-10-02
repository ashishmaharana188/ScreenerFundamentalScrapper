"""
Screener outer flow.

Flow
----
1. Authenticate with Screener.
2. Open /explore/.
3. Discover every screen under "Your screens".
4. Extract:
      - title
      - description
      - href
5. Dashboard selects screens from this discovered metadata.
6. Scrape only the selected screens.

No hard-coded Screener screen names.
"""

from __future__ import annotations

import json
import time
from getpass import getpass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from innerFlow import scrape_screen, save_group_csv


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://www.screener.in"
LOGIN_URL = f"{BASE_URL}/login/"
EXPLORE_URL = f"{BASE_URL}/explore/"

SESSION_FILE = Path("screener_session.json")


# ============================================================
# SESSION
# ============================================================

def create_screener_session():
    """Create one HTTP session for the complete Screener run."""

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

def save_session(session):
    """Save Screener cookies. The password is never stored."""

    cookies = requests.utils.dict_from_cookiejar(
        session.cookies
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

    print(
        f"Screener session saved to: "
        f"{SESSION_FILE.resolve()}"
    )


def load_saved_session(session):
    """Load the saved Screener cookies when available."""

    if not SESSION_FILE.exists():
        print("No saved Screener session found.")
        return False

    try:
        with open(
            SESSION_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            cookies = json.load(file)

        session.cookies = (
            requests.utils.cookiejar_from_dict(
                cookies
            )
        )

        print("Saved Screener session loaded.")
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
    Check whether the current session exposes
    the authenticated 'Your screens' section.
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

        for heading in soup.select("h2.h3"):

            heading_text = heading.get_text(
                " ",
                strip=True,
            )

            if heading_text.lower() == "your screens":
                return True

        return False

    except requests.RequestException:
        return False


def perform_login(session):
    """Perform a fresh Screener login."""

    print("\n========================================")
    print("FRESH SCREENER LOGIN")
    print("========================================")

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
            "Could not find csrfmiddlewaretoken "
            "on Screener login page."
        )

    csrf_token = csrf_input.get("value")

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
            "Login completed, but Screener did not return "
            "the authenticated 'Your screens' section."
        )

    print("Authentication successful.")


def authenticate_screener(session):
    """Reuse saved session or perform a fresh login."""

    if load_saved_session(session):

        print(
            "Checking saved Screener session..."
        )

        if is_authenticated(session):

            print(
                "Saved Screener session is valid."
            )

            return

        print(
            "Saved session is expired or invalid."
        )

        session.cookies.clear()

    perform_login(session)

    save_session(session)


# ============================================================
# SCREEN DISCOVERY
# ============================================================

# ============================================================
# SCREEN DISCOVERY
# ============================================================

def get_custom_screens(session):
    """
    Discover all custom screens under Screener's
    authenticated 'Your screens' section.

    Returns:
        [
            {
                "title": "...",
                "description": "...",
                "href": "..."
            }
        ]

    The href is the unique identifier.
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
    # Find "Your screens"
    # --------------------------------------------------------

    heading = None

    for element in soup.select("h2.h3"):

        text = element.get_text(
            " ",
            strip=True,
        )

        if text.lower() == "your screens":
            heading = element
            break

    if heading is None:
        raise RuntimeError(
            "Could not find the 'Your screens' section "
            "on Screener Explore."
        )

    your_screens_card = heading.parent

    if your_screens_card is None:
        raise RuntimeError(
            "Could not identify the 'Your screens' card."
        )

    # --------------------------------------------------------
    # Extract screens
    # --------------------------------------------------------

    screens = []

    screen_items = your_screens_card.select(
        "a.screen-item"
    )

    for item in screen_items:

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        title_element = item.select_one(
            "div.font-weight-500"
        )

        if title_element is None:
            continue

        title = title_element.get_text(
            " ",
            strip=True,
        )

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------
        #
        # Actual Screener HTML:
        #
        # <p class="sub font-size-12 margin-0 show-from-desktop">
        #     Deeply Undervalued
        # </p>
        #

        description_element = item.select_one(
            "p.sub"
        )

        if description_element is None:

            # Fallback in case Screener changes
            # the class structure slightly.
            description_element = item.find(
                "p"
            )

        description = ""

        if description_element is not None:
            description = description_element.get_text(
                " ",
                strip=True,
            )

        # ----------------------------------------------------
        # HREF
        # ----------------------------------------------------

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
            "Found 'Your screens' but no screen links."
        )

    print(
        f"\nFound {len(screens)} custom Screener screens."
    )

    # --------------------------------------------------------
    # Debug output
    # --------------------------------------------------------

    for screen in screens:

        print(
            f"\nTitle: {screen['title']}"
        )

        print(
            f"Description: {screen['description']}"
        )

        print(
            f"URL: {screen['href']}"
        )

    return screens
# ============================================================
# DISCOVER SCREENS FOR DASHBOARD
# ============================================================

def discover_custom_screens():
    """
    Authenticate and return discovered screens.

    Used by dashboard.py to populate the UI.
    """

    session = create_screener_session()

    try:

        authenticate_screener(
            session
        )

        screens = get_custom_screens(
            session
        )

        return screens

    finally:

        session.close()

        print(
            "Discovery session closed."
        )


# ============================================================
# SCREEN DISPLAY LABEL
# ============================================================

def make_screen_label(screen):
    """
    Create the UI label for one screen.

    Example:
        VALUATION NON FINANCE | Deeply Undervalued
    """

    title = screen["title"]
    description = screen["description"]

    if description:
        return (
            f"{title} | {description}"
        )

    return title


# ============================================================
# UNIQUE SCREEN KEY
# ============================================================

def make_screen_key(screen):
    """
    Create a unique internal key.

    Title alone is NOT sufficient because multiple screens
    may share the same title.
    """

    return (
        f"{screen['title']}||"
        f"{screen['description']}||"
        f"{screen['href']}"
    )


# ============================================================
# PROCESS ONE SCREEN
# ============================================================

def process_screen(
    session,
    screen,
):
    """Send one selected screen into innerFlow."""

    title = screen["title"]
    description = screen["description"]
    href = screen["href"]

    screen_url = urljoin(
        BASE_URL,
        href,
    )

    print(
        "\n========================================"
    )

    print(
        f"SCREEN TITLE: {title}"
    )

    print(
        f"DESCRIPTION: {description}"
    )

    print(
        f"SCREEN URL: {screen_url}"
    )

    print(
        "========================================"
    )

    results = scrape_screen(
        session=session,
        screen_url=screen_url,
    )

    return results


# ============================================================
# RETURN TO EXPLORE
# ============================================================

def return_to_explore(session):

    response = session.get(
        EXPLORE_URL,
        timeout=30,
    )

    response.raise_for_status()

    return response


# ============================================================
# MAIN OUTER FLOW
# ============================================================

def run_outer_flow(selected_screens):
    """
    Scrape only the screens selected in the dashboard.

    selected_screens is a list of dictionaries:

        {
            "title": "...",
            "description": "...",
            "href": "..."
        }
    """

    if not selected_screens:
        raise ValueError(
            "No Screener screens selected."
        )

    session = create_screener_session()

    all_results = {}

    try:

        print(
            "\n========================================"
        )

        print(
            "SCREENER OUTER FLOW"
        )

        print(
            "========================================"
        )

        # ----------------------------------------------------
        # 1. Authenticate
        # ----------------------------------------------------

        authenticate_screener(
            session
        )

        # ----------------------------------------------------
        # 2. Process selected screens
        # ----------------------------------------------------

        for index, screen in enumerate(
            selected_screens,
            start=1,
        ):

            results = process_screen(
                session=session,
                screen=screen,
            )

            title = screen["title"]
            description = screen["description"]

            # ------------------------------------------------
            # Build UNIQUE CSV label
            # ------------------------------------------------
            #
            # Example:
            # valuation_non_finance__deeply_undervalued.csv
            #
            # Existing innerFlow handles the safe filename
            # conversion.
            #

            if description:

                group_name = (
                    f"{title}__{description}"
                )

            else:

                group_name = title

            output_file = save_group_csv(
                group_name=group_name,
                rows=results["rows"],
                group_number=None,
            )

            result_key = make_screen_key(
                screen
            )

            all_results[result_key] = {
                "title": title,
                "description": description,
                "href": screen["href"],
                "file": output_file,
                **results,
            }

            # ------------------------------------------------
            # Return to Explore
            # ------------------------------------------------

            if index < len(selected_screens):

                return_to_explore(
                    session
                )

                time.sleep(1)

        print(
            "\n========================================"
        )

        print(
            "SCREENER OUTER FLOW COMPLETE"
        )

        print(
            "========================================"
        )

        return all_results

    except requests.RequestException as exc:

        print(
            f"\nSCREENER REQUEST ERROR: {exc}"
        )

        raise

    except Exception as exc:

        print(
            f"\nSCREENER OUTER FLOW ERROR: {exc}"
        )

        raise

    finally:

        session.close()

        print(
            "\nScreener session closed."
        )


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    print(
        "Discovering Screener custom screens..."
    )

    screens = discover_custom_screens()

    print(
        "\nCUSTOM SCREENS FOUND"
    )

    for index, screen in enumerate(
        screens,
        start=1,
    ):

        print(
            f"{index}. "
            f"{make_screen_label(screen)}"
        )