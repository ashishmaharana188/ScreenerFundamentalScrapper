"""
Primary Streamlit UI for the ScanX + Screener workflow.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import scanx
import outerFlow


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Screener Fundamental Dashboard",
    layout="wide",
)

st.title(
    "Screener Fundamental Dashboard"
)

st.caption(
    "ScanX builds the company universe. "
    "Screener provides the discovered custom screens. "
    "Comparison operates on saved datasets."
)

st.divider()


# ============================================================
# STEP 1: SCANX
# ============================================================

st.subheader(
    "1. Select ScanX universe"
)

selected_industries = st.multiselect(
    "Industries",
    options=scanx.ALL_INDUSTRIES,
    help=(
        "Select the ScanX industries to include."
    ),
)

selected_sectors = st.multiselect(
    "Sectors",
    options=scanx.ALL_SECTORS,
    help=(
        "Select the ScanX sectors to include."
    ),
)

scanx_run = st.button(
    "Run ScanX Scraper",
    type="primary",
    use_container_width=True,
)

if scanx_run:

    if not selected_industries:

        st.error(
            "Select at least one industry."
        )

    elif not selected_sectors:

        st.error(
            "Select at least one sector."
        )

    else:

        try:

            with st.spinner(
                "Running ScanX scraper..."
            ):

                scanx_names = (
                    scanx.run_scan(
                        industries=(
                            selected_industries
                        ),
                        sectors=(
                            selected_sectors
                        ),
                    )
                )

            st.success(
                f"ScanX complete. "
                f"{len(scanx_names)} distinct "
                f"company names saved."
            )

        except Exception as exc:

            st.error(
                f"ScanX failed: {exc}"
            )


st.divider()


# ============================================================
# STEP 2: SCREENER GROUP SELECTION
# ============================================================

st.subheader(
    "2. Screener Screen Groups"
)

st.write(
    "Screens are discovered automatically from "
    "**Your screens**. Groups are formed from the "
    "shared leading title identity."
)

load_screens = st.button(
    "Load Screener Screens",
    use_container_width=True,
)

if load_screens:

    try:

        with st.spinner(
            "Discovering Screener screens..."
        ):

            discovered_screens = (
                outerFlow
                .discover_custom_screens()
            )

        discovered_groups = (
            outerFlow
            .build_screen_groups(
                discovered_screens
            )
        )

        st.session_state[
            "screener_screens"
        ] = discovered_screens

        st.session_state[
            "screener_groups"
        ] = discovered_groups

        st.success(
            f"Discovered "
            f"{len(discovered_screens)} screens "
            f"across "
            f"{len(discovered_groups)} groups."
        )

    except Exception as exc:

        st.error(
            f"Could not load Screener screens: {exc}"
        )


# ============================================================
# GROUP UI
# ============================================================

screener_groups = (
    st.session_state.get(
        "screener_groups",
        {},
    )
)


if screener_groups:

    group_lookup = {
        key: group
        for key, group in (
            screener_groups.items()
        )
    }

    # --------------------------------------------------------
    # Group dropdown + mode beside it
    # --------------------------------------------------------

    group_column, mode_column = (
        st.columns(
            [3, 2]
        )
    )

    with group_column:

        selected_group_key = (
            st.selectbox(
                "Screener Group",
                options=list(
                    group_lookup.keys()
                ),
                format_func=lambda key: (
                    group_lookup[key][
                        "name"
                    ].upper()
                ),
            )
        )

    selected_group = (
        group_lookup[
            selected_group_key
        ]
    )

    # ========================================================
    # PACK
    # ========================================================

    if selected_group[
        "type"
    ] == "pack":

        with mode_column:

            st.radio(
                "Mode",
                options=[
                    "Single",
                    "Merge",
                ],
                index=1,
                disabled=True,
                key=(
                    f"mode_{selected_group_key}"
                ),
                help=(
                    "This group is a PACK because all "
                    "screens have the same description. "
                    "The complete pack is always merged."
                ),
            )

        st.info(
            "PACK detected: all screens below are "
            "automatically selected and will run together."
        )

        for screen in (
            selected_group["screens"]
        ):

            st.write(
                f"☑ "
                f"{outerFlow.make_screen_label(screen)}"
            )

        run_pack = st.button(
            "Run Pack",
            type="primary",
            use_container_width=True,
            key=(
                f"run_pack_{selected_group_key}"
            ),
        )

        if run_pack:

            try:

                with st.spinner(
                    "Running complete screen pack..."
                ):

                    result = (
                        outerFlow.run_selection(
                            group=selected_group,
                            selected_screens=(
                                selected_group[
                                    "screens"
                                ]
                            ),
                            mode="merge",
                        )
                    )

                st.success(
                    f"Pack complete. "
                    f"{result['row_count']} "
                    f"unique companies saved."
                )

                st.caption(
                    f"Saved to: "
                    f"{result['file']}"
                )

            except Exception as exc:

                st.error(
                    f"Pack failed: {exc}"
                )

    # ========================================================
    # NORMAL GROUP
    # ========================================================

    elif selected_group[
        "type"
    ] == "normal":

        with mode_column:

            mode = st.radio(
                "Mode",
                options=[
                    "Single",
                    "Merge",
                ],
                horizontal=True,
                key=(
                    f"mode_{selected_group_key}"
                ),
            )

        screen_lookup = {}

        for screen in (
            selected_group[
                "screens"
            ]
        ):

            screen_lookup[
                outerFlow.make_screen_key(
                    screen
                )
            ] = screen

        # ----------------------------------------------------
        # SINGLE
        # ----------------------------------------------------

        if mode == "Single":

            selected_screen_key = (
                st.selectbox(
                    "Screen",
                    options=list(
                        screen_lookup.keys()
                    ),
                    format_func=lambda key: (
                        outerFlow.make_screen_label(
                            screen_lookup[key]
                        )
                    ),
                    key=(
                        f"single_{selected_group_key}"
                    ),
                )
            )

            selected_screens = [
                screen_lookup[
                    selected_screen_key
                ]
            ]

        # ----------------------------------------------------
        # MERGE
        # ----------------------------------------------------

        else:

            selected_screen_keys = (
                st.multiselect(
                    "Screens to merge",
                    options=list(
                        screen_lookup.keys()
                    ),
                    format_func=lambda key: (
                        outerFlow.make_screen_label(
                            screen_lookup[key]
                        )
                    ),
                    key=(
                        f"merge_{selected_group_key}"
                    ),
                )
            )

            selected_screens = [
                screen_lookup[
                    key
                ]
                for key in selected_screen_keys
            ]

        # ----------------------------------------------------
        # RUN
        # ----------------------------------------------------

        run_selection = st.button(
            "Run Selection",
            type="primary",
            use_container_width=True,
            key=(
                f"run_{selected_group_key}"
            ),
        )

        if run_selection:

            if mode == "Single":

                valid = (
                    len(selected_screens)
                    == 1
                )

            else:

                valid = (
                    len(selected_screens)
                    >= 2
                )

            if not valid:

                if mode == "Single":

                    st.error(
                        "Select exactly one screen."
                    )

                else:

                    st.error(
                        "Select at least two screens "
                        "for Merge."
                    )

            else:

                try:

                    with st.spinner(
                        "Running Screener selection..."
                    ):

                        result = (
                            outerFlow.run_selection(
                                group=selected_group,
                                selected_screens=(
                                    selected_screens
                                ),
                                mode=(
                                    mode.lower()
                                ),
                            )
                        )

                    st.success(
                        f"{mode} complete. "
                        f"{result['row_count']} "
                        f"companies saved."
                    )

                    st.caption(
                        f"Saved to: "
                        f"{result['file']}"
                    )

                except Exception as exc:

                    st.error(
                        f"Screener run failed: {exc}"
                    )

    # ========================================================
    # SINGLE-SCREEN GROUP
    # ========================================================

    else:

        with mode_column:

            st.radio(
                "Mode",
                options=[
                    "Single"
                ],
                index=0,
                horizontal=True,
                disabled=True,
                key=(
                    f"mode_{selected_group_key}"
                ),
            )

        screen = (
            selected_group[
                "screens"
            ][0]
        )

        st.write(
            outerFlow.make_screen_label(
                screen
            )
        )

        run_single = st.button(
            "Run Screen",
            type="primary",
            use_container_width=True,
            key=(
                f"run_single_{selected_group_key}"
            ),
        )

        if run_single:

            try:

                with st.spinner(
                    "Running Screener screen..."
                ):

                    result = (
                        outerFlow.run_selection(
                            group=selected_group,
                            selected_screens=[
                                screen
                            ],
                            mode="single",
                        )
                    )

                st.success(
                    f"Screen complete. "
                    f"{result['row_count']} "
                    f"companies saved."
                )

                st.caption(
                    f"Saved to: "
                    f"{result['file']}"
                )

            except Exception as exc:

                st.error(
                    f"Screen failed: {exc}"
                )


st.divider()


# ============================================================
# STEP 3: COMPARISON
# ============================================================

st.subheader(
    "3. Compare saved data"
)

compare_enabled = st.toggle(
    "Enable comparison",
    value=False,
    help=(
        "Use the saved ScanX and Screener datasets."
    ),
)

if compare_enabled:

    import logicFlow

    scanx_files = (
        logicFlow.get_scanx_files()
    )

    screener_files = (
        logicFlow.get_screener_files()
    )

    if not scanx_files:

        st.warning(
            "No ScanX CSV files found."
        )

    if not screener_files:

        st.warning(
            "No Screener CSV files found."
        )

    if scanx_files and screener_files:

        # ----------------------------------------------------
        # ScanX
        # ----------------------------------------------------

        scanx_labels = {
            str(path): path.name
            for path in scanx_files
        }

        selected_scanx_key = (
            st.selectbox(
                "ScanX data file",
                options=list(
                    scanx_labels.keys()
                ),
                format_func=lambda key: (
                    scanx_labels[key]
                ),
            )
        )

        # ----------------------------------------------------
        # Screener
        # ----------------------------------------------------

        screener_labels = {
            str(path): path.name
            for path in screener_files
        }

        selected_screener_keys = (
            st.multiselect(
                "Screener data files",
                options=list(
                    screener_labels.keys()
                ),
                format_func=lambda key: (
                    screener_labels[key]
                ),
                help=(
                    "Level 1 compares each selected "
                    "Screener dataset with ScanX. "
                    "Level 2 finds companies common "
                    "to all selected datasets."
                ),
            )
        )

        compare_run = st.button(
            "Run Comparison",
            type="primary",
            use_container_width=True,
        )

        if compare_run:

            if not selected_screener_keys:

                st.error(
                    "Select at least one "
                    "Screener dataset."
                )

            else:

                try:

                    result = (
                        logicFlow.run_comparison(
                            scanx_file=Path(
                                selected_scanx_key
                            ),
                            screener_files=[
                                Path(key)
                                for key in (
                                    selected_screener_keys
                                )
                            ],
                        )
                    )

                    st.success(
                        "Comparison complete."
                    )

                    st.write(
                        "**Level 1: "
                        "ScanX × Screener**"
                    )

                    for (
                        screen_file,
                        data,
                    ) in result[
                        "level_1"
                    ].items():

                        st.write(
                            f"{screen_file}: "
                            f"{data['rows']} "
                            f"common companies"
                        )

                    if (
                        result[
                            "level_2_dataframe"
                        ]
                        is not None
                    ):

                        st.write(
                            "**Level 2: "
                            "Screener intersection**"
                        )

                        st.write(
                            f"{len(result['level_2_dataframe'])} "
                            "companies are common across "
                            "all selected datasets."
                        )

                    st.caption(
                        "Comparison files are saved under "
                        "screener_data/comparison/."
                    )

                except Exception as exc:

                    st.error(
                        f"Comparison failed: {exc}"
                    )