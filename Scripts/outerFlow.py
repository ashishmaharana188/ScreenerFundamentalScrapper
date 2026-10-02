# outerFlow.py

import json
import time
from getpass import getpass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from innerFlow import scrape_screen,save_group_csv
from logicFlow import run_logic_flow
# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://www.screener.in"

LOGIN_URL = f"{BASE_URL}/login/"
EXPLORE_URL = f"{BASE_URL}/explore/"

SESSION_FILE = Path("screener_session.json")

#TARGET_GROUPS = [
#    "Core Business Quality",
#    "Growth and Earnings Quality",
#    "Balance Sheet and Cash-Flow Strength",
#    "Valuation",
#    "Promoters and Shareholder Structure",
#]

TARGET_GROUPS = [
    "Quality Gate",
    "Under valued",
    "Over Valued",
    "Loose check"
]


# ============================================================
# SCREENER SESSION
# ============================================================

def create_screener_session():
    """
    Create one requests.Session() for the complete run.

    This SAME session is used for:
        - authentication
        - Explore
        - all five screens
        - every page handled by innerFlow
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
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    return session


# ============================================================
# SESSION PERSISTENCE
# ============================================================

def save_session(session):
    """
    Save the current Screener cookies.

    The password is NEVER stored.
    """

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
    """
    Load previously saved Screener cookies.

    Returns:
        True  -> session file loaded
        False -> no usable session file
    """

    if not SESSION_FILE.exists():

        print(
            "No saved Screener session found."
        )

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

        print(
            "Saved Screener session loaded."
        )

        return True

    except Exception as e:

        print(
            f"Could not load saved session: {e}"
        )

        return False


# ============================================================
# AUTHENTICATION CHECK
# ============================================================

def is_authenticated(session):
    """
    Verify that the current session is actually logged in.

    We use the account-specific 'Your screens' section as
    the authentication check.
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


# ============================================================
# FRESH LOGIN
# ============================================================

def perform_login(session):
    """
    Perform a fresh Screener login.

    Credentials are requested only when the saved session
    is missing or expired.
    """

    print("\n========================================")
    print("FRESH SCREENER LOGIN")
    print("========================================")

    # --------------------------------------------------------
    # GET LOGIN PAGE
    # --------------------------------------------------------

    print(
        "\nFetching Screener login page..."
    )

    login_response = session.get(
        LOGIN_URL,
        timeout=30,
    )

    login_response.raise_for_status()

    print(
        f"Login page response: "
        f"{login_response.status_code}"
    )

    login_soup = BeautifulSoup(
        login_response.text,
        "html.parser",
    )

    # --------------------------------------------------------
    # CSRF TOKEN
    # --------------------------------------------------------

    csrf_input = login_soup.select_one(
        'input[name="csrfmiddlewaretoken"]'
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

    # --------------------------------------------------------
    # CREDENTIALS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # LOGIN REQUEST
    # --------------------------------------------------------

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

    print(
        "\nAuthenticating with Screener..."
    )

    login_response = session.post(
        LOGIN_URL,
        data=login_data,
        headers=login_headers,
        timeout=30,
        allow_redirects=True,
    )

    login_response.raise_for_status()

    print(
        f"Login response: "
        f"{login_response.status_code}"
    )

    print(
        f"Login final URL: "
        f"{login_response.url}"
    )

    # --------------------------------------------------------
    # VERIFY
    # --------------------------------------------------------

    if not is_authenticated(session):

        raise RuntimeError(
            "Login request completed, but Screener did not "
            "return the authenticated 'Your screens' section."
        )

    print(
        "\nAuthentication successful."
    )

    print(
        "'Your screens' is visible."
    )


# ============================================================
# AUTHENTICATE SESSION
# ============================================================

def authenticate_screener(session):
    """
    Authentication strategy:

        1. Try saved session.
        2. Validate it.
        3. If valid -> reuse it.
        4. If invalid -> perform fresh login.
        5. Save new cookies.
    """

    print("\n========================================")
    print("SCREENER AUTHENTICATION")
    print("========================================")

    # --------------------------------------------------------
    # TRY SAVED SESSION
    # --------------------------------------------------------

    if load_saved_session(session):

        print(
            "Checking saved Screener session..."
        )

        if is_authenticated(session):

            print(
                "Saved Screener session is valid."
            )

            print(
                "Using saved authentication."
            )

            return

        print(
            "Saved session is expired or invalid."
        )

        session.cookies.clear()

    # --------------------------------------------------------
    # FRESH LOGIN
    # --------------------------------------------------------

    perform_login(
        session
    )

    # --------------------------------------------------------
    # SAVE NEW SESSION
    # --------------------------------------------------------

    save_session(
        session
    )


# ============================================================
# GET CUSTOM SCREENS
# ============================================================

def get_custom_screens(session):
    """
    Fetch authenticated Explore page and extract the
    custom screens under 'Your screens'.
    """

    print(
        "\nFetching authenticated Explore page..."
    )

    response = session.get(
        EXPLORE_URL,
        timeout=30,
    )

    response.raise_for_status()

    print(
        f"Explore response: "
        f"{response.status_code}"
    )

    print(
        f"Explore URL: "
        f"{response.url}"
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    # --------------------------------------------------------
    # Find "Your screens"
    # --------------------------------------------------------

    your_screens_card = None

    for heading in soup.select("h2.h3"):

        heading_text = heading.get_text(
            " ",
            strip=True,
        )

        if heading_text.lower() == "your screens":

            your_screens_card = heading.parent
            break

    if your_screens_card is None:

        raise RuntimeError(
            "Could not find the 'Your screens' card "
            "on authenticated Screener Explore."
        )

    # --------------------------------------------------------
    # Extract links
    # --------------------------------------------------------

    screens = {}

    screen_items = your_screens_card.select(
        "a.screen-item"
    )

    print(
        f"\nFound {len(screen_items)} screens "
        "inside 'Your screens'."
    )

    for item in screen_items:

        name_element = item.select_one(
            "div.font-weight-500"
        )

        if name_element is None:
            continue

        name = name_element.get_text(
            " ",
            strip=True,
        )

        href = item.get(
            "href"
        )

        if not name or not href:
            continue

        screens[name] = href

    if not screens:

        raise RuntimeError(
            "Found 'Your screens' but no screen links."
        )

    return screens


# ============================================================
# VALIDATE TARGET GROUPS
# ============================================================

def validate_target_groups(screens):
    """
    Ensure all five required screens exist.
    """

    missing_groups = [
        group
        for group in TARGET_GROUPS
        if group not in screens
    ]

    if missing_groups:

        print(
            "\n========================================"
        )
        print(
            "MISSING REQUIRED SCREENS"
        )
        print(
            "========================================"
        )

        for group in missing_groups:
            print(
                f"- {group}"
            )

        raise RuntimeError(
            "One or more required custom screens "
            "were not found."
        )


# ============================================================
# PROCESS ONE SCREEN
# ============================================================

def process_screen(
    session,
    group_name,
    screen_href,
):
    """
    Send the authenticated session and screen URL
    into innerFlow.
    """

    screen_url = urljoin(
        BASE_URL,
        screen_href,
    )

    print("\n")
    print("========================================")
    print(
        f"GROUP: {group_name}"
    )
    print("========================================")

    print(
        f"Screen URL: {screen_url}"
    )

    # --------------------------------------------------------
    # INNER FLOW
    # --------------------------------------------------------

    results = scrape_screen(
        session=session,
        screen_url=screen_url,
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n----------------------------------------")
    print(
        f"Completed: {group_name}"
    )

    print(
        f"Expected rows: "
        f"{results['total_results']}"
    )

    print(
        f"Collected rows: "
        f"{results['total_rows_collected']}"
    )

    print("----------------------------------------")

    return results


# ============================================================
# RETURN TO EXPLORE
# ============================================================

def return_to_explore(session):
    """
    Return to Explore after completing one screen.
    """

    print(
        "\nReturning to Screener Explore..."
    )

    response = session.get(
        EXPLORE_URL,
        timeout=30,
    )

    response.raise_for_status()

    print(
        f"Back to Explore: "
        f"{response.status_code}"
    )

    return response


# ============================================================
# MAIN OUTER FLOW
# ============================================================

def run_outer_flow():
    """
    Complete Screener workflow.

    Authentication happens once.

    The same authenticated session is then passed
    into innerFlow for every screen.
    """

    session = create_screener_session()

    all_results = {}

    try:

        # ====================================================
        # 1. AUTHENTICATION
        # ====================================================

        authenticate_screener(
            session
        )

        # ====================================================
        # 2. DISCOVER CUSTOM SCREENS
        # ====================================================

        screens = get_custom_screens(
            session
        )

        print("\n========================================")
        print("CUSTOM SCREENS FOUND")
        print("========================================")

        for name, href in screens.items():

            print(
                f"{name} -> {href}"
            )

        # ====================================================
        # 3. VALIDATE
        # ====================================================

        validate_target_groups(
            screens
        )

        # ====================================================
        # 4. PROCESS ALL FIVE GROUPS
        # ====================================================

        for index, group_name in enumerate(
            TARGET_GROUPS,
            start=1,
        ):

            print("\n\n")
            print("========================================")
            print(
                f"GROUP {index}/{len(TARGET_GROUPS)}"
            )
            print(
                group_name
            )
            print("========================================")

            # ------------------------------------------------
            # Inner flow
            # ------------------------------------------------

            results = process_screen(
                session=session,
                group_name=group_name,
                screen_href=screens[group_name],
            )
            
            save_group_csv(
                group_name=group_name,
                rows=results["rows"],
                group_number=index,
            )

            # ------------------------------------------------
            # Keep results in memory
            # ------------------------------------------------

            all_results[group_name] = results

            # ------------------------------------------------
            # Return to Explore
            # ------------------------------------------------

            return_to_explore(
                session
            )

            time.sleep(1)

        # ====================================================
        # 5. FINAL SUMMARY
        # ====================================================

        print("\n========================================")
        print("COMPLETE OUTER + INNER FLOW")
        print("========================================")

        for group_name, results in all_results.items():

            print(
                f"{group_name}: "
                f"{results['total_rows_collected']} / "
                f"{results['total_results']} rows"
            )

        print(
            "\nAll five screens processed."
        )
        
        
        
        # ====================================================
        # 6. RUN LOGIC FLOW
        # ====================================================

        print("\n")
        print("========================================")
        print("STARTING LOGIC FLOW")
        print("========================================")

        logic_results = run_logic_flow()

        print("\n")
        print("========================================")
        print("LOGIC FLOW COMPLETE")
        print("========================================")

        return all_results

    except requests.RequestException as e:

        print("\n========================================")
        print("SCREENER REQUEST ERROR")
        print("========================================")

        print(e)

        raise

    except Exception as e:

        print("\n========================================")
        print("OUTER FLOW ERROR")
        print("========================================")

        print(e)

        raise

    finally:

        session.close()

        print(
            "\nScreener session closed."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_outer_flow()