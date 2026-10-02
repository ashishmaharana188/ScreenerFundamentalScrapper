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
        "Optional. Leave empty to query all sectors/subsectors "
        "within the selected industries."
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

screener_groups = st.session_state.get("screener_groups", {})


def _screen_items(subgroup):
    """Return the actual Screener screens belonging to a subgroup."""
    return subgroup.get("items", subgroup.get("screens", []))


def _screen_description(screen):
    """Return the discovered description for an individual screen."""
    description = screen.get("description")
    return str(description).strip() if description else ""


def _item_label(screen):
    """Display the actual screen title together with its description."""
    return outerFlow.make_screen_label(screen)


def _group_items_by_description(selected_subgroups):
    """
    Group actual items from selected subgroups by their description.

    A description is a matching group only when every selected subgroup
    contains an item with that description. The items themselves remain
    independently selectable.
    """
    description_groups = {}

    for subgroup in selected_subgroups:
        subgroup_name = subgroup.get("name", "")

        for screen in _screen_items(subgroup):
            description = _screen_description(screen)

            # Keep items without a description independently grouped.
            group_key = description or "__NO_DESCRIPTION__"

            description_groups.setdefault(
                group_key,
                {
                    "description": description,
                    "items": [],
                    "subgroups": set(),
                },
            )

            description_groups[group_key]["items"].append(
                screen
            )
            description_groups[group_key]["subgroups"].add(
                subgroup_name
            )

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


if screener_groups:

    group_lookup = {
        key: group
        for key, group in screener_groups.items()
    }

    group_column, mode_column = st.columns([3, 2])

    with group_column:
        selected_group_key = st.selectbox(
            "Screener Group",
            options=list(group_lookup.keys()),
            format_func=lambda key: group_lookup[key]["name"].upper(),
        )

    selected_group = group_lookup[selected_group_key]
    group_type = selected_group["type"]

    # ========================================================
    # TOP-LEVEL PACK
    # ========================================================
    # A top-level PACK is already a complete executable unit.
    # No subgroup hierarchy is exposed here.
    # ========================================================

    if group_type == "pack":

        with mode_column:
            st.radio(
                "Mode",
                ["Single", "Merge"],
                index=1,
                disabled=True,
                key=f"mode_{selected_group_key}",
                help=(
                    "This group is a PACK because all screens have "
                    "the same description. The complete pack is merged."
                ),
            )

        st.info(
            "PACK detected: all screens in this group are selected."
        )

        for screen in selected_group["screens"]:
            st.write(f"☑ {_item_label(screen)}")

        run_pack = st.button(
            "Run Pack",
            type="primary",
            use_container_width=True,
            key=f"run_pack_{selected_group_key}",
        )

        if run_pack:
            try:
                with st.spinner("Running complete screen pack..."):
                    result = outerFlow.run_selection(
                        group=selected_group,
                        selected_screens=selected_group["screens"],
                        mode="merge",
                    )

                st.success(
                    f"Pack complete. "
                    f"{result['row_count']} unique companies saved."
                )
                st.caption(f"Saved to: {result['file']}")

            except Exception as exc:
                st.error(f"Pack failed: {exc}")

    # ========================================================
    # NORMAL GROUP
    # ========================================================
    # Group -> subgroup -> item.
    #
    # Single:
    #   Select one subgroup. Every item in that subgroup is run.
    #
    # Merge:
    #   Select two or more subgroups.
    #   Matching item descriptions are auto-selected.
    #   Non-matching item descriptions are manually selectable.
    # ========================================================

    elif group_type == "normal":

        with mode_column:
            mode = st.radio(
                "Mode",
                ["Single", "Merge"],
                horizontal=True,
                key=f"mode_{selected_group_key}",
            )

        subgroups = selected_group.get("subgroups", [])
        subgroup_lookup = {
            subgroup["key"]: subgroup
            for subgroup in subgroups
        }

        selected_screens = []
        selected_subgroup_keys = []

        if not subgroup_lookup:

            st.error("This group has no subgroups.")

        elif mode == "Single":

            selected_subgroup_key = st.selectbox(
                "Subgroup",
                options=list(subgroup_lookup.keys()),
                format_func=lambda key: (
                    outerFlow.make_subgroup_label(
                        subgroup_lookup[key]
                    )
                ),
                key=f"single_subgroup_{selected_group_key}",
            )

            selected_subgroup_keys = [selected_subgroup_key]
            selected_subgroup = subgroup_lookup[
                selected_subgroup_key
            ]

            subgroup_items = _screen_items(
                selected_subgroup
            )

            st.write("Items")

            selected_screens = []

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
                format_func=lambda key: (
                    outerFlow.make_subgroup_label(
                        subgroup_lookup[key]
                    )
                ),
                key=f"merge_subgroups_{selected_group_key}",
                help=(
                    "Select two or more subgroups. "
                    "Items with descriptions common to all selected "
                    "subgroups are selected automatically."
                ),
            )

            if selected_subgroup_keys:

                selected_subgroups = [
                    subgroup_lookup[key]
                    for key in selected_subgroup_keys
                ]

                if len(selected_subgroups) >= 2:

                    matching_groups, other_groups = (
                        _group_items_by_description(
                            selected_subgroups
                        )
                    )

                    # ------------------------------------------------
                    # DESCRIPTION GROUPS
                    # ------------------------------------------------
                    # One description becomes one item group when
                    # every selected subgroup contains that description.
                    # The actual screens inside the group stay editable.
                    # ------------------------------------------------

                    if matching_groups:
                        st.write("**Matching item groups**")

                        for description, group in matching_groups.items():

                            st.markdown(
                                f"**{description}**"
                            )

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

                    # ------------------------------------------------
                    # NON-MATCHING DESCRIPTION GROUPS
                    # ------------------------------------------------
                    # These descriptions do not exist in every selected
                    # subgroup, so they are available manually.
                    # ------------------------------------------------

                    if other_groups:
                        st.write("**Other item groups**")

                        for group_key, group in other_groups.items():

                            description = group["description"]

                            if description:
                                st.markdown(
                                    f"**{description}**"
                                )
                            else:
                                st.markdown(
                                    "**No description**"
                                )

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

                    if not matching_groups and not other_groups:
                        st.warning(
                            "The selected subgroups contain no items."
                        )

                else:
                    st.info(
                        "Select at least two subgroups to compare "
                        "their item descriptions."
                    )

        run_selection = st.button(
            "Run Selection",
            type="primary",
            use_container_width=True,
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
                        "Select one subgroup containing at least one item."
                    )
                else:
                    st.error(
                        "Select at least two subgroups and at least one item."
                    )

            else:

                try:
                    with st.spinner(
                        "Running Screener selection..."
                    ):
                        result = outerFlow.run_selection(
                            group=selected_group,
                            selected_screens=selected_screens,
                            mode=mode.lower(),
                        )

                    st.success(
                        f"{mode} complete. "
                        f"{result['row_count']} companies saved."
                    )
                    st.caption(
                        f"Saved to: {result['file']}"
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
                ["Single"],
                index=0,
                horizontal=True,
                disabled=True,
                key=f"mode_{selected_group_key}",
            )

        subgroups = selected_group.get("subgroups", [])

        if subgroups:

            subgroup = subgroups[0]
            items = _screen_items(subgroup)

            if not items:
                st.error("This subgroup contains no screens.")
                screen = None
            else:
                screen = items[0]
                st.write(_item_label(screen))

        else:

            screens = selected_group.get("screens", [])

            if not screens:
                st.error("This group contains no screens.")
                screen = None
            else:
                screen = screens[0]
                st.write(_item_label(screen))

        run_single = st.button(
            "Run Screen",
            type="primary",
            use_container_width=True,
            key=f"run_single_{selected_group_key}",
        )

        if run_single:

            if screen is None:
                st.error("No screen is available to run.")

            else:

                try:
                    with st.spinner(
                        "Running Screener screen..."
                    ):
                        result = outerFlow.run_selection(
                            group=selected_group,
                            selected_screens=[screen],
                            mode="single",
                        )

                    st.success(
                        f"Screen complete. "
                        f"{result['row_count']} companies saved."
                    )
                    st.caption(
                        f"Saved to: {result['file']}"
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