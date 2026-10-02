"""Primary Streamlit UI for the ScanX + Screener workflow."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import scanx


st.set_page_config(
    page_title="Screener Fundamental Dashboard",
    layout="wide",
)

st.title("Screener Fundamental Dashboard")
st.caption(
    "ScanX builds the company universe. Screener supplies the selected screens. "
    "Comparisons use the CSV files created by those steps."
)

st.divider()

# ============================================================
# STEP 1: SCANX SELECTION
# ============================================================

st.subheader("1. Select ScanX universe")

selected_industries = st.multiselect(
    "Industries",
    options=scanx.ALL_INDUSTRIES,
    help="Select the ScanX industries to include in the company universe.",
)

selected_sectors = st.multiselect(
    "Sectors",
    options=scanx.ALL_SECTORS,
    help="Select the ScanX sectors to include in the company universe.",
)

scanx_run = st.button(
    "Run ScanX Scraper",
    type="primary",
    use_container_width=True,
)

if scanx_run:
    if not selected_industries:
        st.error("Select at least one industry.")
    elif not selected_sectors:
        st.error("Select at least one sector.")
    else:
        try:
            with st.spinner("Running ScanX scraper..."):
                scanx_names = scanx.run_scan(
                    industries=selected_industries,
                    sectors=selected_sectors,
                )

            st.success(
                f"ScanX complete. {len(scanx_names)} distinct company names saved."
            )

        except Exception as exc:
            st.error(f"ScanX failed: {exc}")

st.divider()

# ============================================================
# STEP 2: SCREENER SELECTION
# ============================================================

st.subheader("2. Select Screener screens")

st.write(
    "Type the exact custom Screener screen names. Enter one screen name per line."
)

screen_names_text = st.text_area(
    "Custom Screener screen names",
    height=150,
    placeholder="Quality Gate\nUndervalued\nOvervalued",
)

screener_run = st.button(
    "Run Screener Scraper",
    use_container_width=True,
)

if screener_run:
    requested_screens = [
        line.strip()
        for line in screen_names_text.splitlines()
        if line.strip()
    ]

    if not requested_screens:
        st.error("Enter at least one Screener screen name.")
    else:
        try:
            import outerFlow

            with st.spinner("Scraping selected Screener screens..."):
                results = outerFlow.run_outer_flow(requested_screens)

            st.success(
                f"Screener scraping complete. {len(results)} screen(s) saved."
            )

            for screen_name, result in results.items():
                st.write(
                    f"**{screen_name}**: "
                    f"{result['total_rows_collected']} / "
                    f"{result['total_results']} rows"
                )

        except Exception as exc:
            st.error(f"Screener scraping failed: {exc}")

st.divider()

# ============================================================
# STEP 3: COMPARISON TOGGLE
# ============================================================

st.subheader("3. Compare saved data")

compare_enabled = st.toggle(
    "Enable comparison",
    value=False,
    help="Use CSV files already available in scanx_data/ and screener_data/groups/.",
)

if compare_enabled:
    import logicFlow

    scanx_files = logicFlow.get_scanx_files()
    screener_files = logicFlow.get_screener_files()

    if not scanx_files:
        st.warning("No ScanX CSV files found in scanx_data/ yet.")

    if not screener_files:
        st.warning("No Screener CSV files found in screener_data/groups/ yet.")

    if scanx_files and screener_files:
        scanx_labels = {
            str(path): path.name
            for path in scanx_files
        }

        selected_scanx_key = st.selectbox(
            "ScanX data file",
            options=list(scanx_labels.keys()),
            format_func=lambda key: scanx_labels[key],
        )

        screener_labels = {
            str(path): path.name
            for path in screener_files
        }

        selected_screener_keys = st.multiselect(
            "Screener data files",
            options=list(screener_labels.keys()),
            format_func=lambda key: screener_labels[key],
            help=(
                "Level 1 compares each selected Screener file with the ScanX file. "
                "Level 2 finds companies common to all selected Screener files."
            ),
        )

        compare_run = st.button(
            "Run Comparison",
            type="primary",
            use_container_width=True,
        )

        if compare_run:
            if not selected_screener_keys:
                st.error("Select at least one Screener data file.")
            else:
                try:
                    result = logicFlow.run_comparison(
                        scanx_file=Path(selected_scanx_key),
                        screener_files=[
                            Path(key)
                            for key in selected_screener_keys
                        ],
                    )

                    st.success("Comparison complete.")

                    st.write("**Level 1: ScanX × Screener**")
                    for screen_file, data in result["level_1"].items():
                        st.write(
                            f"{screen_file}: {data['rows']} common companies"
                        )

                    if result["level_2_dataframe"] is not None:
                        st.write("**Level 2: Screener screen intersection**")
                        st.write(
                            f"{len(result['level_2_dataframe'])} companies are present "
                            "in all selected Screener results after ScanX filtering."
                        )

                    st.caption(
                        "Comparison files are saved under screener_data/comparison/."
                    )

                except Exception as exc:
                    st.error(f"Comparison failed: {exc}")
