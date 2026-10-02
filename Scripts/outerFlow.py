"""Screener outer flow.

The dashboard supplies the Screener screen names to scrape.
There are no hard-coded screen/group names in this module.
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

    cookies = requests.utils.dict_from_cookiejar(session.cookies)

    with open(SESSION_FILE, "w", encoding="utf-8") as file:
        json.dump(cookies, file, indent=2)

    print(f"Screener session saved to: {SESSION_FILE.resolve()}")


def load_saved_session(session):
    """Load the saved Screener cookies when available."""

    if not SESSION_FILE.exists():
        print("No saved Screener session found.")
        return False

    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as file:
            cookies = json.load(file)

        session.cookies = requests.utils.cookiejar_from_dict(cookies)
        print("Saved Screener session loaded.")
        return True

    except Exception as exc:
        print(f"Could not load saved session: {exc}")
        return False


# ============================================================
# AUTHENTICATION
# ============================================================

def is_authenticated(session):
    """Check whether the current session exposes 'Your screens'."""

    try:
        response = session.get(EXPLORE_URL, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for heading in soup.select("h2.h3"):
            heading_text = heading.get_text(" ", strip=True)
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

    login_response = session.get(LOGIN_URL, timeout=30)
    login_response.raise_for_status()

    login_soup = BeautifulSoup(login_response.text, "html.parser")

    csrf_input = login_soup.select_one(
        'input[name="csrfmiddlewaretoken"]'
    )

    if csrf_input is None:
        raise RuntimeError(
            "Could not find csrfmiddlewaretoken on Screener login page."
        )

    csrf_token = csrf_input.get("value")
    if not csrf_token:
        raise RuntimeError("Screener returned an empty CSRF token.")

    email = input("\nScreener email: ").strip()
    password = getpass("Screener password: ")

    if not email or not password:
        raise RuntimeError("Email and password are required.")

    login_data = {
        "csrfmiddlewaretoken": csrf_token,
        "username": email,
        "password": password,
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
            "'Your screens' section."
        )

    print("Authentication successful.")


def authenticate_screener(session):
    """Reuse the saved session or perform a fresh login."""

    if load_saved_session(session):
        print("Checking saved Screener session...")
        if is_authenticated(session):
            print("Saved Screener session is valid.")
            return

        print("Saved session is expired or invalid.")
        session.cookies.clear()

    perform_login(session)
    save_session(session)


# ============================================================
# SCREEN DISCOVERY
# ============================================================

def get_custom_screens(session):
    """Return the user's custom Screener screens as {name: href}."""

    response = session.get(EXPLORE_URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    your_screens_card = None

    for heading in soup.select("h2.h3"):
        heading_text = heading.get_text(" ", strip=True)
        if heading_text.lower() == "your screens":
            your_screens_card = heading.parent
            break

    if your_screens_card is None:
        raise RuntimeError(
            "Could not find the 'Your screens' card on authenticated Screener Explore."
        )

    screens = {}

    for item in your_screens_card.select("a.screen-item"):
        name_element = item.select_one("div.font-weight-500")
        if name_element is None:
            continue

        name = name_element.get_text(" ", strip=True)
        href = item.get("href")

        if name and href:
            screens[name] = href

    if not screens:
        raise RuntimeError("Found 'Your screens' but no screen links.")

    return screens


# ============================================================
# SCREEN NAME VALIDATION
# ============================================================

def validate_requested_screens(screens, requested_screen_names):
    """Validate the screen names typed in the dashboard."""

    requested = [
        name.strip()
        for name in requested_screen_names
        if name.strip()
    ]

    if not requested:
        raise ValueError("Enter at least one Screener screen name.")

    duplicates = []
    seen = set()

    for name in requested:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)

    if duplicates:
        raise ValueError(f"Duplicate screen names entered: {duplicates}")

    missing = [name for name in requested if name not in screens]

    if missing:
        available_preview = list(screens.keys())[:20]
        raise ValueError(
            "These requested Screener screens were not found: "
            f"{missing}. Available screen names include: {available_preview}"
        )

    return requested


# ============================================================
# PROCESS ONE SCREEN
# ============================================================

def process_screen(session, screen_name, screen_href):
    """Send one selected screen into innerFlow."""

    screen_url = urljoin(BASE_URL, screen_href)

    print("\n========================================")
    print(f"SCREEN: {screen_name}")
    print("========================================")
    print(f"Screen URL: {screen_url}")

    results = scrape_screen(
        session=session,
        screen_url=screen_url,
    )

    return results


# ============================================================
# RETURN TO EXPLORE
# ============================================================

def return_to_explore(session):
    """Return to Explore after one screen."""

    response = session.get(EXPLORE_URL, timeout=30)
    response.raise_for_status()
    return response


# ============================================================
# MAIN OUTER FLOW
# ============================================================

def run_outer_flow(requested_screen_names):
    """Scrape only the Screener screens selected by the dashboard."""

    session = create_screener_session()
    all_results = {}

    try:
        print("\n========================================")
        print("SCREENER OUTER FLOW")
        print("========================================")

        # 1. Login once.
        authenticate_screener(session)

        # 2. Find every custom screen in the account.
        screens = get_custom_screens(session)

        print("\nCUSTOM SCREENS FOUND")
        for name, href in screens.items():
            print(f"{name} -> {href}")

        # 3. Keep only the screen names the user typed.
        selected_screens = validate_requested_screens(
            screens,
            requested_screen_names,
        )

        print("\nSELECTED SCREENS")
        for index, screen_name in enumerate(selected_screens, start=1):
            print(f"{index}. {screen_name}")

        # 4. Scrape selected screens only.
        for index, screen_name in enumerate(selected_screens, start=1):
            results = process_screen(
                session=session,
                screen_name=screen_name,
                screen_href=screens[screen_name],
            )

            save_group_csv(
                group_name=screen_name,
                rows=results["rows"],
                group_number=index,
            )

            all_results[screen_name] = results

            if index < len(selected_screens):
                return_to_explore(session)
                time.sleep(1)

        print("\n========================================")
        print("SCREENER OUTER FLOW COMPLETE")
        print("========================================")

        for screen_name, results in all_results.items():
            print(
                f"{screen_name}: "
                f"{results['total_rows_collected']} / "
                f"{results['total_results']} rows"
            )

        return all_results

    except requests.RequestException as exc:
        print(f"\nSCREENER REQUEST ERROR: {exc}")
        raise

    except Exception as exc:
        print(f"\nSCREENER OUTER FLOW ERROR: {exc}")
        raise

    finally:
        session.close()
        print("\nScreener session closed.")


if __name__ == "__main__":
    names_text = input(
        "Enter Screener screen names, one per line. Finish with an empty line:\n"
    )

    # Simple command-line fallback for running this file directly.
    requested = [name.strip() for name in names_text.split(",") if name.strip()]
    run_outer_flow(requested)
