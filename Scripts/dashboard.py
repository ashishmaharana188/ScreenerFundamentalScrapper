"""
Modern responsive Streamlit UI for the ScanX + Screener workflow.

Workflow:
    1. Build ScanX company universe.
    2. Discover and run Screener screens.
    3. Compare saved datasets.
    4. Render resulting CSV data directly in the UI.

The backend modules remain responsible for scraping, grouping, comparison,
authentication, and file creation. This module is the presentation layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

import scanx
import outerFlow
import logicFlow


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Fundamental Scanner",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# RESPONSIVE / MODERN UI
# ============================================================

st.markdown(
    """
    <style>
    /* ============================================================
       MONOCHROME THEME
       Light:  black button / white text
       Hover:  white button / black text
       Dark:   white button / black text
       Hover:  black button / white text
       ============================================================ */

    :root {
        color-scheme: light;
        --bg: white;
        --fg: black;
        --button-bg: black;
        --button-fg: white;
        --line: black;
    }

    html,
    body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {
        background: var(--bg) !important;
        color: var(--fg) !important;
    }

    header[data-testid="stHeader"] {
        background: var(--bg) !important;
        border-bottom: 1px solid var(--line) !important;
    }

    #MainMenu,
    footer {
        display: none !important;
    }

    .block-container {
        max-width: 1380px;
        padding-top: 0.65rem;
        padding-bottom: 1.5rem;
        padding-left: clamp(0.55rem, 1.15vw, 1rem);
        padding-right: clamp(0.55rem, 1.15vw, 1rem);
    }

    /* ============================================================
       HEADER
       ============================================================ */

    .app-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        margin-bottom: 0.55rem;
        padding: 0.8rem 0.9rem;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--bg);
    }

    .app-header-left {
        min-width: 0;
    }

    .app-eyebrow {
        margin: 0 0 0.15rem 0;
        color: var(--fg) !important;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .app-title {
        margin: 0;
        color: var(--fg) !important;
        font-size: clamp(1.55rem, 2.45vw, 2.05rem);
        font-weight: 800;
        letter-spacing: -0.04em;
        line-height: 1.03;
    }

    .app-subtitle {
        margin: 0.32rem 0 0 0;
        color: var(--fg) !important;
        font-size: 0.84rem;
        line-height: 1.4;
        max-width: 820px;
    }

    .app-badge {
        flex: 0 0 auto;
        padding: 0.3rem 0.46rem;
        border: 1px solid var(--button-bg);
        border-radius: 5px;
        background: var(--button-bg);
        color: var(--button-fg) !important;
        font-size: 0.64rem;
        font-weight: 800;
    }

    /* ============================================================
       SECTION FLAG LINE
       ============================================================ */

    .section-heading {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 0.75rem;
        width: 100%;
        margin: 1rem 0 0.7rem 0;
        padding: 0 0 0.5rem 0;
        border-bottom: 1px solid var(--line);
        background: transparent !important;
    }

    .section-heading-main {
        display: flex;
        align-items: flex-start;
        gap: 0.62rem;
        min-width: 0;
    }

    .section-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.65rem;
        height: 1.65rem;
        flex: 0 0 1.65rem;
        border: 1px solid var(--button-bg);
        border-radius: 4px;
        background: var(--button-bg);
        color: var(--button-fg) !important;
        font-size: 0.68rem;
        font-weight: 800;
    }

    .section-title {
        margin: 0;
        color: var(--fg) !important;
        font-size: 1.04rem;
        font-weight: 800;
        line-height: 1.2;
    }

    .section-description {
        margin: 0.18rem 0 0 0;
        color: var(--fg) !important;
        font-size: 0.78rem;
        line-height: 1.35;
    }

    .section-state {
        flex: 0 0 auto;
        padding: 0.28rem 0.46rem;
        border: 1px solid var(--line);
        border-radius: 4px;
        background: var(--bg);
        color: var(--fg) !important;
        font-size: 0.66rem;
        font-weight: 700;
        white-space: nowrap;
    }

    /* ============================================================
       METRICS
       ============================================================ */

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.5rem;
        margin: 0.55rem 0 0.75rem 0;
    }

    .metric-card {
        min-width: 0;
        padding: 0.58rem 0.66rem;
        border: 1px solid var(--line);
        border-radius: 6px;
        background: var(--bg);
        color: var(--fg);
    }

    .metric-label {
        color: var(--fg) !important;
        font-size: 0.64rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .metric-value {
        margin-top: 0.12rem;
        color: var(--fg) !important;
        font-size: 1.04rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* ============================================================
       RESULTS
       ============================================================ */

    .result-banner {
        margin: 0.4rem 0;
        padding: 0.58rem 0.68rem;
        border: 1px solid var(--line);
        border-radius: 6px;
        background: var(--bg);
    }

    .result-title,
    .result-meta,
    .empty-state {
        color: var(--fg) !important;
    }

    .result-title {
        margin: 0;
        font-weight: 800;
        font-size: 0.88rem;
    }

    .result-meta {
        margin-top: 0.08rem;
        font-size: 0.72rem;
    }

    .screen-chip {
        display: inline-block;
        margin: 0.08rem 0.16rem 0.08rem 0;
        padding: 0.2rem 0.34rem;
        border: 1px solid var(--line);
        border-radius: 4px;
        background: var(--bg);
        color: var(--fg) !important;
        font-size: 0.66rem;
        line-height: 1.15;
    }

    .empty-state {
        padding: 0.74rem;
        text-align: center;
        border: 1px dashed var(--line);
        border-radius: 6px;
        background: var(--bg);
        font-size: 0.76rem;
    }

    /* ============================================================
       TEXT
       ============================================================ */

    label,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] *,
    [data-testid="stMarkdownContainer"] *,
    .stCaption,
    .stMarkdown,
    p,
    span {
        color: var(--fg);
    }

    /* ============================================================
       BUTTONS
       ============================================================ */

    div[data-testid="stButton"],
    div[data-testid="stDownloadButton"] {
        width: fit-content !important;
    }

    div[data-testid="stButton"] > button,
    div[data-testid="stDownloadButton"] > button {
        width: auto !important;
        min-width: 92px !important;
        min-height: 1.72rem !important;
        height: 1.72rem !important;
        padding: 0.16rem 0.56rem !important;
        margin: 0 !important;
        border: 1px solid var(--button-bg) !important;
        border-radius: 5px !important;
        background: var(--button-bg) !important;
        color: var(--button-fg) !important;
        box-shadow: none !important;
        font-size: 0.70rem !important;
        font-weight: 800 !important;
        line-height: 1 !important;
        transition: none !important;
        transform: none !important;
    }

    div[data-testid="stButton"] > button *,
    div[data-testid="stDownloadButton"] > button * {
        color: inherit !important;
        fill: currentColor !important;
        stroke: currentColor !important;
    }

    /* Hover/focus/active always flips the monochrome pair. */
    div[data-testid="stButton"] > button:hover,
    div[data-testid="stButton"] > button:focus,
    div[data-testid="stButton"] > button:focus-visible,
    div[data-testid="stButton"] > button:active,
    div[data-testid="stDownloadButton"] > button:hover,
    div[data-testid="stDownloadButton"] > button:focus,
    div[data-testid="stDownloadButton"] > button:focus-visible,
    div[data-testid="stDownloadButton"] > button:active {
        background: var(--bg) !important;
        color: var(--fg) !important;
        border-color: var(--line) !important;
        box-shadow: none !important;
        transform: none !important;
    }

    /* ============================================================
       DROPDOWNS
       ============================================================ */

    div[data-testid="stSelectbox"] [data-baseweb="select"],
    div[data-testid="stMultiSelect"] [data-baseweb="select"] {
        min-height: 2.65rem !important;
        border: 1px solid var(--line) !important;
        border-radius: 6px !important;
        background: var(--bg) !important;
        color: var(--fg) !important;
        box-shadow: none !important;
    }

    div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
    div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        min-height: 2.63rem !important;
        background: var(--bg) !important;
        color: var(--fg) !important;
    }

    div[data-testid="stSelectbox"] input,
    div[data-testid="stMultiSelect"] input,
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {
        color: var(--fg) !important;
        background: var(--bg) !important;
        font-size: 0.88rem !important;
    }

    /* Kill BaseWeb's red tags. */
    div[data-testid="stMultiSelect"] [data-baseweb="tag"],
    div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
        margin: 0.15rem 0.16rem 0.15rem 0 !important;
        padding: 0.22rem 0.36rem !important;
        border: 1px solid var(--button-bg) !important;
        border-radius: 4px !important;
        background: var(--button-bg) !important;
        color: var(--button-fg) !important;
        font-size: 0.70rem !important;
    }

    div[data-testid="stMultiSelect"] [data-baseweb="tag"] *,
    div[data-testid="stMultiSelect"] [data-baseweb="tag"] svg {
        color: var(--button-fg) !important;
        fill: var(--button-fg) !important;
        stroke: var(--button-fg) !important;
    }

    /* Dropdown menu surfaces. */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[data-baseweb="menu"],
    div[data-baseweb="menu"] > div,
    div[role="listbox"],
    div[role="option"] {
        background: var(--bg) !important;
        color: var(--fg) !important;
    }

    div[data-baseweb="option"]:hover,
    div[data-baseweb="option"][aria-selected="true"],
    div[data-baseweb="option"][data-highlighted="true"],
    div[role="option"]:hover,
    div[role="option"][aria-selected="true"] {
        background: var(--button-bg) !important;
        color: var(--button-fg) !important;
    }

    /* ============================================================
       OTHER WIDGETS
       ============================================================ */

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {
        min-height: 2.5rem !important;
        border: 1px solid var(--line) !important;
        border-radius: 6px !important;
        box-shadow: none !important;
    }

    div[data-testid="stCheckbox"] label,
    div[data-testid="stRadio"] label,
    div[data-testid="stToggle"] label {
        color: var(--fg) !important;
        font-size: 0.82rem !important;
    }

    input,
    textarea,
    select,
    button {
        accent-color: var(--button-bg) !important;
    }

    div[data-testid="stAlert"],
    div[data-testid="stExpander"] {
        border: 1px solid var(--line) !important;
        border-radius: 6px !important;
        background: var(--bg) !important;
        color: var(--fg) !important;
        box-shadow: none !important;
    }

    div[data-testid="stAlert"] *,
    div[data-testid="stExpander"] *,
    div[data-testid="stAlert"] svg {
        color: var(--fg) !important;
        fill: currentColor !important;
        stroke: currentColor !important;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--line) !important;
        border-radius: 6px !important;
        overflow: hidden;
    }

    /* ============================================================
       DARK THEME
       ============================================================ */

    @media (prefers-color-scheme: dark) {
        :root {
            color-scheme: dark;
            --bg: black;
            --fg: white;
            --button-bg: white;
            --button-fg: black;
            --line: white;
        }
    }

    html[data-theme="dark"],
    body[data-theme="dark"],
    .stApp[data-theme="dark"],
    [data-theme="dark"] {
        --bg: black;
        --fg: white;
        --button-bg: white;
        --button-fg: black;
        --line: white;
        color-scheme: dark;
    }

    /* ============================================================
       SCREENER CONNECTION STATUS
       ============================================================ */

    .connection-row {
        display: flex;
        align-items: center;
        gap: 0.52rem;
        min-height: 2.2rem;
        margin: 0.35rem 0 0.65rem 0;
    }

    .connection-dot {
        width: 0.62rem;
        height: 0.62rem;
        flex: 0 0 0.62rem;
        border-radius: 50%;
        border: 1px solid var(--fg);
        background: var(--fg);
    }

    .connection-dot.offline {
        background: transparent;
    }

    .connection-main {
        display: flex;
        align-items: baseline;
        flex-wrap: wrap;
        gap: 0.42rem;
        color: var(--fg);
        font-size: 0.78rem;
        font-weight: 800;
    }

    /* ============================================================
       RESPONSIVE
       ============================================================ */

    @media (max-width: 900px) {
        .app-badge {
            display: none;
        }

        .metric-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }

        .section-heading {
            align-items: flex-start;
        }
    }

    @media (max-width: 600px) {
        .block-container {
            padding-top: 0.4rem;
            padding-left: 0.35rem;
            padding-right: 0.35rem;
        }

        .app-title {
            font-size: 1.38rem;
        }

        .app-subtitle {
            font-size: 0.74rem;
        }

        .section-heading {
            margin-top: 0.78rem;
            padding-bottom: 0.42rem;
        }

        .section-title {
            font-size: 0.94rem;
        }

        .section-description {
            font-size: 0.70rem;
        }

        .section-state {
            font-size: 0.60rem;
        }

        .metric-grid {
            grid-template-columns: 1fr 1fr;
            gap: 0.35rem;
        }

        .metric-card {
            padding: 0.48rem 0.52rem;
        }

        .metric-value {
            font-size: 0.90rem;
        }

        div[data-testid="stButton"],
        div[data-testid="stDownloadButton"] {
            width: 100% !important;
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button {
            width: 100% !important;
            min-width: 0 !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "screener_screens": [],
    "screener_groups": {},
    "screener_connected": False,
    "screener_active_email": "",
    "screener_session_id": "",
    "screener_show_login": False,
    "last_scanx_names": [],
    "last_result_file": None,
    "last_result_title": None,
    "last_result_dataframe": None,
    "last_comparison_result": None,
}

for key, value in DEFAULT_STATE.items():
    st.session_state.setdefault(key, value)


def _clear_screener_query_session() -> None:
    """Remove the browser-persisted Screener session identifier."""

    if "screener_session" in st.query_params:
        del st.query_params["screener_session"]


# Restore the active account after a browser reload. Only an opaque
# session id is kept in the browser URL, never the email or password.
if not st.session_state.get("screener_session_id"):
    persisted_session_id = str(
        st.query_params.get("screener_session", "")
    ).strip()

    if persisted_session_id:
        try:
            identity = outerFlow.get_identity_for_session_id(
                persisted_session_id
            )
            restored_email = str(identity.get("email") or "").strip()

            if restored_email:
                status = outerFlow.get_screener_status(
                    email=restored_email,
                    session_id=persisted_session_id,
                )

                if status.get("connected"):
                    st.session_state["screener_email"] = restored_email
                    st.session_state["screener_active_email"] = restored_email
                    st.session_state["screener_session_id"] = str(
                        status.get("session_id") or persisted_session_id
                    )
                    st.session_state["screener_connected"] = True
                    st.session_state["screener_show_login"] = False
                else:
                    _clear_screener_query_session()
        except Exception:
            _clear_screener_query_session()


# ============================================================
# HELPERS
# ============================================================

def _section_header(
    number: str,
    title: str,
    description: str,
    state: str | None = None,
) -> None:
    state_html = (
        f'<div class="section-state">{state}</div>'
        if state
        else ""
    )

    st.markdown(
        f"""
        <div class="section-heading">
            <div class="section-heading-main">
                <div class="section-number">{number}</div>
                <div>
                    <div class="section-title">{title}</div>
                    <div class="section-description">{description}</div>
                </div>
            </div>
            {state_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _metric_grid(metrics: list[tuple[str, str]]) -> None:
    """Render compact metric cards without markdown indentation issues."""
    cards = "".join(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div></div>'
        for label, value in metrics
    )

    st.markdown(
        f'<div class="metric-grid">{cards}</div>',
        unsafe_allow_html=True,
    )


def _screen_items(subgroup: dict[str, Any]) -> list[dict[str, Any]]:
    return subgroup.get("items", subgroup.get("screens", []))


def _screen_description(screen: dict[str, Any]) -> str:
    description = screen.get("description")
    return str(description).strip() if description else ""


def _item_label(screen: dict[str, Any]) -> str:
    return outerFlow.make_screen_label(screen)


def _group_items_by_description(
    selected_subgroups: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    description_groups: dict[str, dict[str, Any]] = {}

    for subgroup in selected_subgroups:
        subgroup_name = subgroup.get("name", "")

        for screen in _screen_items(subgroup):
            description = _screen_description(screen)
            group_key = description or "__NO_DESCRIPTION__"

            description_groups.setdefault(
                group_key,
                {
                    "description": description,
                    "items": [],
                    "subgroups": set(),
                },
            )

            description_groups[group_key]["items"].append(screen)
            description_groups[group_key]["subgroups"].add(subgroup_name)

    subgroup_count = len(selected_subgroups)
    matching_groups = {}
    other_groups = {}

    for group_key, group in description_groups.items():
        if (
            group_key != "__NO_DESCRIPTION__"
            and len(group["subgroups"]) == subgroup_count
        ):
            matching_groups[group_key] = group
        else:
            other_groups[group_key] = group

    return matching_groups, other_groups


def _read_csv(path_value: str | Path | None) -> pd.DataFrame | None:
    if not path_value:
        return None

    path = Path(path_value)

    if not path.exists() or not path.is_file():
        return None

    try:
        return pd.read_csv(path)
    except Exception:
        return None


def _render_csv_result(
    dataframe: pd.DataFrame | None,
    title: str,
    source_file: str | Path | None = None,
    key_prefix: str = "result",
) -> None:
    """Render a CSV result directly in the dashboard."""
    if dataframe is None:
        return

    st.markdown(
        f"""
        <div class="result-banner">
            <p class="result-title">{title}</p>
            <div class="result-meta">
                {len(dataframe):,} rows · {len(dataframe.columns):,} columns
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if source_file:
        st.caption(f"Source: {Path(source_file).name}")

    search = st.text_input(
        "Filter results",
        placeholder="Search company name or any visible value...",
        key=f"{key_prefix}_search",
    )

    view_df = dataframe.copy()

    if search.strip():
        needle = search.strip().lower()
        mask = view_df.astype(str).apply(
            lambda column: column.str.lower().str.contains(
                needle,
                regex=False,
                na=False,
            )
        ).any(axis=1)
        view_df = view_df[mask]

    st.caption(
        f"Showing {len(view_df):,} of {len(dataframe):,} rows"
    )

    st.dataframe(
        view_df,
        use_container_width=True,
        hide_index=True,
        height=min(620, max(280, 92 + len(view_df.head(12)) * 35)),
    )

    csv_bytes = dataframe.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name=Path(source_file).name if source_file else "result.csv",
        mime="text/csv",
        use_container_width=False,
        key=f"{key_prefix}_download",
    )


def _remember_file_result(
    result: dict[str, Any],
    title: str,
    key_prefix: str,
) -> None:
    file_value = result.get("file")

    st.session_state["last_result_file"] = file_value
    st.session_state["last_result_title"] = title

    dataframe = _read_csv(file_value)
    st.session_state["last_result_dataframe"] = dataframe

    if dataframe is not None:
        _render_csv_result(
            dataframe,
            title=title,
            source_file=file_value,
            key_prefix=key_prefix,
        )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="app-header">
        <div class="app-header-left">
            <p class="app-eyebrow">Research Workspace</p>
            <h1 class="app-title">Fundamental Scanner</h1>
            <p class="app-subtitle">
                Build a market universe with ScanX, run your discovered
                Screener screens, and inspect the resulting datasets here.
            </p>
        </div>
        <div class="app-badge">SCANX · SCREENER</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# TOP STATUS
# ============================================================

scanx_count = len(st.session_state["last_scanx_names"])
screen_count = len(st.session_state["screener_screens"])
group_count = len(st.session_state["screener_groups"])

_metric_grid(
    [
        ("ScanX companies", f"{scanx_count:,}"),
        ("Discovered screens", f"{screen_count:,}"),
        ("Screen groups", f"{group_count:,}"),
        (
            "Last result",
            (
                "Ready"
                if st.session_state["last_result_dataframe"] is not None
                else "None"
            ),
        ),
    ]
)


# ============================================================
# STEP 1: SCANX
# ============================================================
_section_header(
    "1",
    "Build ScanX universe",
    "Select one or more industries. Sector is optional and can be left empty.",
    (
        f"{scanx_count:,} companies loaded"
        if scanx_count
        else "No universe loaded"
    ),
)

scanx_col1, scanx_col2 = st.columns(2, gap="large")

with scanx_col1:
    selected_industries = st.multiselect(
        "Industries",
        options=scanx.ALL_INDUSTRIES,
        help="At least one industry is required.",
        key="scanx_industries",
    )

with scanx_col2:
    selected_sectors = st.multiselect(
        "Sectors",
        options=scanx.ALL_SECTORS,
        help=(
            "Optional. Leave empty to include all sectors/subsectors "
            "within the selected industries."
        ),
        key="scanx_sectors",
    )

scanx_action_col, scanx_info_col = st.columns(
    [1, 2],
    gap="large",
)

with scanx_action_col:
    scanx_run = st.button(
        "Run ScanX",
        type="primary",
        use_container_width=False,
        key="run_scanx",
    )

with scanx_info_col:
    if selected_industries:
        st.caption(
            f"{len(selected_industries)} industries selected"
            + (
                f" · {len(selected_sectors)} sectors selected"
                if selected_sectors
                else " · all sectors within those industries"
            )
        )
    else:
        st.caption("Select at least one industry to continue.")

if scanx_run:
    if not selected_industries:
        st.error("Select at least one industry.")
    else:
        try:
            with st.spinner("Running ScanX..."):
                scanx_names = scanx.run_scan(
                    industries=selected_industries,
                    sectors=selected_sectors,
                )

            st.session_state["last_scanx_names"] = scanx_names or []

            st.success(
                f"ScanX complete: {len(scanx_names):,} distinct companies."
            )

            # Show the most recent ScanX CSV when available.
            try:
                scanx_files = logicFlow.get_scanx_files()
            except Exception:
                scanx_files = []

            if scanx_files:
                latest_scanx = max(
                    scanx_files,
                    key=lambda path: path.stat().st_mtime,
                )
                scanx_df = _read_csv(latest_scanx)

                if scanx_df is not None:
                    with st.expander("Preview ScanX CSV", expanded=False):
                        _render_csv_result(
                            scanx_df,
                            title="ScanX universe",
                            source_file=latest_scanx,
                            key_prefix="scanx_preview",
                        )

        except Exception as exc:
            st.error(f"ScanX failed: {exc}")
# ============================================================
# STEP 2: SCREENER
# ============================================================

current_screener_email = str(
    st.session_state.get("screener_active_email", "")
).strip().casefold()

connection_active = bool(
    st.session_state.get("screener_connected")
    and current_screener_email
    and st.session_state.get("screener_session_id")
)

screener_state_label = (
    "● CONNECTED"
    if connection_active
    else "○ OFFLINE"
)

_section_header(
    "2",
    "Run Screener screens",
    "Connect with your own Screener account. Each account gets its own saved session.",
    screener_state_label,
)

# --------------------------------------------------------
# SCREENER CONNECTION
# --------------------------------------------------------

connection_col1, connection_col2 = st.columns([1, 2], gap="large")

with connection_col1:
    status_class = (
        "connection-dot"
        if connection_active
        else "connection-dot offline"
    )
    status_text = "Connected" if connection_active else "Offline"

    st.markdown(
        f"""<div class=\"connection-row\">
            <span class=\"{status_class}\"></span>
            <span class=\"connection-main\">
                <span>{status_text}</span>
            </span>
        </div>""",
        unsafe_allow_html=True,
    )

with connection_col2:
    st.caption(
        "Saved sessions are reused automatically. Passwords are never written to disk."
    )

if connection_active and not st.session_state.get("screener_show_login"):
    action_col1, action_col2 = st.columns([0.8, 0.8], gap="large")

    with action_col1:
        change_account = st.button(
            "Change Account",
            use_container_width=False,
            key="change_screener_account",
        )

    with action_col2:
        clear_session = st.button(
            "Clear Session",
            use_container_width=False,
            key="clear_screener_session_connected",
        )

    if change_account:
        st.session_state["screener_show_login"] = True
        st.rerun()

    if clear_session:
        try:
            outerFlow.clear_saved_session(
                email=st.session_state.get("screener_active_email")
            )
            st.session_state["screener_connected"] = False
            st.session_state["screener_active_email"] = ""
            st.session_state["screener_session_id"] = ""
            st.session_state["screener_show_login"] = False
            st.session_state["screener_screens"] = []
            st.session_state["screener_groups"] = {}
            _clear_screener_query_session()
            st.success("Saved Screener session cleared.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not clear Screener session: {exc}")

else:
    login_col1, login_col2, login_col3 = st.columns([1.15, 1.15, 0.8], gap="large")

    with login_col1:
        screener_email = st.text_input(
            "Screener email",
            key="screener_email",
            placeholder="name@example.com",
        )

    with login_col2:
        screener_password = st.text_input(
            "Screener password",
            type="password",
            key="screener_password",
            placeholder="Password",
        )

    with login_col3:
        connect_button_label = (
            "Reconnect"
            if st.session_state.get("screener_show_login")
            else "Connect Screener"
        )
        connect_screener = st.button(
            connect_button_label,
            type="primary",
            use_container_width=False,
            key="connect_screener",
        )

    if connect_screener:
        try:
            with st.spinner("Connecting to Screener..."):
                connection_result = outerFlow.connect_screener(
                    email=screener_email,
                    password=screener_password,
                    force_login=True,
                )

            session_id = str(connection_result.get("session_id") or "").strip()
            active_email = screener_email.strip().casefold()

            if not session_id:
                raise RuntimeError(
                    "Screener connected but no session identifier was created."
                )

            st.session_state["screener_connected"] = True
            st.session_state["screener_active_email"] = active_email
            st.session_state["screener_session_id"] = session_id
            st.session_state["screener_show_login"] = False
            st.query_params["screener_session"] = session_id
            st.success("Screener connected.")
            st.rerun()
        except Exception as exc:
            st.session_state["screener_connected"] = False
            st.error(f"Screener connection failed: {exc}")

load_col, status_col = st.columns([1, 2], gap="large")

with load_col:
    load_screens = st.button(
        "Discover Screener Screens",
        use_container_width=False,
        disabled=not connection_active,
        key="discover_screener",
    )

with status_col:
    if screen_count:
        st.caption(
            f"{screen_count:,} screens discovered across "
            f"{group_count:,} groups."
        )
    elif not connection_active:
        st.caption("Connect to Screener before discovering screens.")
    else:
        st.caption("Discovery uses the saved authenticated session for this account.")

if load_screens:
    try:
        with st.spinner("Discovering Screener screens..."):
            discovered_screens = outerFlow.discover_custom_screens(
                email=st.session_state.get("screener_active_email"),
                session_id=st.session_state.get("screener_session_id"),
            )

        discovered_groups = outerFlow.build_screen_groups(
            discovered_screens
        )

        st.session_state["screener_screens"] = discovered_screens
        st.session_state["screener_groups"] = discovered_groups

        screen_count = len(discovered_screens)
        group_count = len(discovered_groups)

        st.success(
            f"Discovered {screen_count:,} screens across "
            f"{group_count:,} groups."
        )
    except Exception as exc:
        st.error(f"Could not load Screener screens: {exc}")


screener_groups = st.session_state.get("screener_groups", {})

if screener_groups:
    group_lookup = {
        key: group
        for key, group in screener_groups.items()
    }

    group_keys = list(group_lookup.keys())

    selected_group_key = st.selectbox(
        "Screen group",
        options=group_keys,
        format_func=lambda key: group_lookup[key]["name"].upper(),
        key="selected_screen_group",
    )

    selected_group = group_lookup[selected_group_key]
    group_type = selected_group["type"]

    group_meta = (
        "PACK"
        if group_type == "pack"
        else "NORMAL"
        if group_type == "normal"
        else "SINGLE"
    )

    st.caption(
        f"Group type: {group_meta} · "
        f"{len(selected_group.get('screens', [])):,} screen(s)"
    )

    # --------------------------------------------------------
    # PACK
    # --------------------------------------------------------

    if group_type == "pack":
        st.info(
            "This PACK is already a complete executable unit. "
            "All screens are selected."
        )

        chips = "".join(
            f'<span class="screen-chip">{_item_label(screen)}</span>'
            for screen in selected_group.get("screens", [])
        )
        st.markdown(chips, unsafe_allow_html=True)

        run_pack = st.button(
            "Run Pack",
            type="primary",
            use_container_width=False,
            key=f"run_pack_{selected_group_key}",
        )

        if run_pack:
            try:
                with st.spinner("Running complete screen pack..."):
                    result = outerFlow.run_selection(
                        group=selected_group,
                        selected_screens=selected_group["screens"],
                        mode="merge",
                        email=st.session_state.get("screener_active_email"),
                    )

                st.success(
                    f"Pack complete: {result['row_count']:,} unique companies."
                )

                _remember_file_result(
                    result,
                    title="Pack result",
                    key_prefix=f"pack_{selected_group_key}",
                )

            except Exception as exc:
                st.error(f"Pack failed: {exc}")

    # --------------------------------------------------------
    # NORMAL GROUP
    # --------------------------------------------------------

    elif group_type == "normal":
        mode = st.radio(
            "Execution mode",
            ["Single", "Merge"],
            horizontal=True,
            key=f"mode_{selected_group_key}",
        )

        subgroups = selected_group.get("subgroups", [])
        subgroup_lookup = {
            subgroup["key"]: subgroup
            for subgroup in subgroups
        }

        selected_screens: list[dict[str, Any]] = []
        selected_subgroup_keys: list[str] = []

        if not subgroup_lookup:
            st.error("This group has no subgroups.")

        elif mode == "Single":
            selected_subgroup_key = st.selectbox(
                "Subgroup",
                options=list(subgroup_lookup.keys()),
                format_func=lambda key: outerFlow.make_subgroup_label(
                    subgroup_lookup[key]
                ),
                key=f"single_subgroup_{selected_group_key}",
            )

            selected_subgroup_keys = [selected_subgroup_key]
            selected_subgroup = subgroup_lookup[selected_subgroup_key]
            subgroup_items = _screen_items(selected_subgroup)

            st.markdown("**Screens in this subgroup**")

            for screen in subgroup_items:
                item_key = (
                    f"single_item_{selected_group_key}_"
                    f"{outerFlow.make_screen_key(screen)}"
                )

                if st.checkbox(
                    _item_label(screen),
                    value=True,
                    key=item_key,
                ):
                    selected_screens.append(screen)

        else:
            selected_subgroup_keys = st.multiselect(
                "Subgroups",
                options=list(subgroup_lookup.keys()),
                format_func=lambda key: outerFlow.make_subgroup_label(
                    subgroup_lookup[key]
                ),
                key=f"merge_subgroups_{selected_group_key}",
                help=(
                    "Select two or more subgroups. Items with descriptions "
                    "common to all selected subgroups start selected."
                ),
            )

            if selected_subgroup_keys:
                selected_subgroups = [
                    subgroup_lookup[key]
                    for key in selected_subgroup_keys
                ]

                if len(selected_subgroups) >= 2:
                    matching_groups, other_groups = (
                        _group_items_by_description(selected_subgroups)
                    )

                    if matching_groups:
                        st.markdown("**Matching item groups**")

                        for description, group in matching_groups.items():
                            with st.container(border=True):
                                st.markdown(f"**{description}**")

                                for screen in group["items"]:
                                    item_key = (
                                        f"match_{selected_group_key}_"
                                        f"{outerFlow.make_screen_key(screen)}"
                                    )

                                    if st.checkbox(
                                        outerFlow.make_screen_label(screen),
                                        value=True,
                                        key=item_key,
                                    ):
                                        selected_screens.append(screen)

                    if other_groups:
                        st.markdown("**Other item groups**")

                        for group_key, group in other_groups.items():
                            description = group["description"]
                            heading = description or "No description"

                            with st.container(border=True):
                                st.markdown(f"**{heading}**")

                                for screen in group["items"]:
                                    item_key = (
                                        f"other_{selected_group_key}_"
                                        f"{outerFlow.make_screen_key(screen)}"
                                    )

                                    if st.checkbox(
                                        outerFlow.make_screen_label(screen),
                                        value=False,
                                        key=item_key,
                                    ):
                                        selected_screens.append(screen)
                else:
                    st.info(
                        "Select at least two subgroups to compare their items."
                    )

        run_selection = st.button(
            "Run Selection",
            type="primary",
            use_container_width=False,
            key=f"run_{selected_group_key}",
        )

        if run_selection:
            if mode == "Single":
                valid = (
                    len(selected_subgroup_keys) == 1
                    and len(selected_screens) >= 1
                )
            else:
                valid = (
                    len(selected_subgroup_keys) >= 2
                    and len(selected_screens) >= 1
                )

            if not valid:
                if mode == "Single":
                    st.error(
                        "Select one subgroup containing at least one screen."
                    )
                else:
                    st.error(
                        "Select at least two subgroups and one screen."
                    )
            else:
                try:
                    with st.spinner("Running Screener selection..."):
                        result = outerFlow.run_selection(
                            group=selected_group,
                            selected_screens=selected_screens,
                            mode=mode.lower(),
                            email=st.session_state.get("screener_active_email"),
                        )

                    st.success(
                        f"{mode} complete: "
                        f"{result['row_count']:,} companies."
                    )

                    _remember_file_result(
                        result,
                        title=f"Screener {mode} result",
                        key_prefix=f"screener_{selected_group_key}",
                    )

                except Exception as exc:
                    st.error(f"Screener run failed: {exc}")

    # --------------------------------------------------------
    # SINGLE-SCREEN GROUP
    # --------------------------------------------------------

    else:
        subgroups = selected_group.get("subgroups", [])
        screen = None

        if subgroups:
            items = _screen_items(subgroups[0])
            if items:
                screen = items[0]
        else:
            screens = selected_group.get("screens", [])
            if screens:
                screen = screens[0]

        if screen:
            with st.container(border=True):
                st.markdown("**Screen**")
                st.write(_item_label(screen))

        run_single = st.button(
            "Run Screen",
            type="primary",
            use_container_width=False,
            key=f"run_single_{selected_group_key}",
        )

        if run_single:
            if screen is None:
                st.error("No screen is available to run.")
            else:
                try:
                    with st.spinner("Running Screener screen..."):
                        result = outerFlow.run_selection(
                            group=selected_group,
                            selected_screens=[screen],
                            mode="single",
                            email=st.session_state.get("screener_active_email"),
                        )

                    st.success(
                        f"Screen complete: "
                        f"{result['row_count']:,} companies."
                    )

                    _remember_file_result(
                        result,
                        title="Screener result",
                        key_prefix=f"screen_{selected_group_key}",
                    )

                except Exception as exc:
                    st.error(f"Screen failed: {exc}")
# ============================================================
# STEP 3: COMPARISON
# ============================================================
_section_header(
    "3",
    "Compare saved datasets",
    "Intersect the ScanX universe with selected Screener datasets and inspect the final CSV.",
)

scanx_files = logicFlow.get_scanx_files()
screener_files = logicFlow.get_screener_files()

if not scanx_files and not screener_files:
    st.markdown(
        '<div class="empty-state">No saved datasets yet. Run ScanX or Screener first.</div>',
        unsafe_allow_html=True,
    )

elif not scanx_files:
    st.warning("No ScanX CSV files found.")

elif not screener_files:
    st.warning("No Screener CSV files found.")

else:
    scanx_labels = {
        str(path): path.name
        for path in scanx_files
    }

    screener_labels = {
        str(path): path.name
        for path in screener_files
    }

    compare_col1, compare_col2 = st.columns(2, gap="large")

    with compare_col1:
        selected_scanx_key = st.selectbox(
            "ScanX dataset",
            options=list(scanx_labels.keys()),
            format_func=lambda key: scanx_labels[key],
            key="comparison_scanx_file",
        )

    with compare_col2:
        selected_screener_keys = st.multiselect(
            "Screener datasets",
            options=list(screener_labels.keys()),
            format_func=lambda key: screener_labels[key],
            help=(
                "Level 1 compares each selected Screener dataset against "
                "ScanX. Level 2 intersects the selected Screener datasets."
            ),
            key="comparison_screener_files",
        )

    compare_run = st.button(
        "Run Comparison",
        type="primary",
        use_container_width=False,
        key="run_comparison",
    )

    if compare_run:
        if not selected_screener_keys:
            st.error("Select at least one Screener dataset.")
        else:
            try:
                with st.spinner("Running comparison..."):
                    comparison_result = logicFlow.run_comparison(
                        scanx_file=Path(selected_scanx_key),
                        screener_files=[
                            Path(key)
                            for key in selected_screener_keys
                        ],
                    )

                st.session_state["last_comparison_result"] = comparison_result

                level_1 = comparison_result.get("level_1", {})

                total_level_1_rows = sum(
                    item.get("rows", 0)
                    for item in level_1.values()
                )

                level_2_df = comparison_result.get(
                    "level_2_dataframe"
                )

                _metric_grid(
                    [
                        ("Level 1 datasets", f"{len(level_1):,}"),
                        ("Level 1 matches", f"{total_level_1_rows:,}"),
                        (
                            "Final intersection",
                            (
                                f"{len(level_2_df):,}"
                                if level_2_df is not None
                                else "0"
                            ),
                        ),
                        ("ScanX source", Path(selected_scanx_key).name),
                    ]
                )

                st.success("Comparison complete.")

                # Level 1 result summaries and tables.
                if level_1:
                    st.markdown("**Level 1 · ScanX × Screener**")

                    for screen_file, data in level_1.items():
                        screen_path = Path(screen_file)

                        rows = data.get("rows", 0)
                        output_file = data.get("file")

                        with st.expander(
                            f"{screen_path.name} · {rows:,} common companies",
                            expanded=False,
                        ):
                            level_1_df = _read_csv(output_file)

                            if level_1_df is not None:
                                _render_csv_result(
                                    level_1_df,
                                    title=screen_path.stem,
                                    source_file=output_file,
                                    key_prefix=(
                                        "level1_"
                                        + screen_path.stem.replace(
                                            " ",
                                            "_",
                                        )
                                    ),
                                )
                            else:
                                st.caption(
                                    f"Saved to: {output_file}"
                                )

                # Level 2 is the final output.
                if level_2_df is not None:
                    st.markdown("**Final · Screener intersection**")

                    output_file = comparison_result.get(
                        "level_2_file"
                    )

                    _render_csv_result(
                        level_2_df,
                        title="Final comparison CSV",
                        source_file=output_file,
                        key_prefix="final_intersection",
                    )
                else:
                    st.info(
                        "No Level 2 intersection was produced for the selected datasets."
                    )

            except Exception as exc:
                st.error(f"Comparison failed: {exc}")
# ============================================================
# PERSISTED LAST RESULT
# ============================================================

last_df = st.session_state.get("last_result_dataframe")
last_title = st.session_state.get("last_result_title")
last_file = st.session_state.get("last_result_file")

if last_df is not None and last_title:
    _section_header(
        "4",
        "Latest CSV result",
        "The most recent completed Screener or pack run remains available here after Streamlit reruns.",
        f"{len(last_df):,} rows",
    )

    _render_csv_result(
        last_df,
        title=last_title,
        source_file=last_file,
        key_prefix="latest_result",
    )
