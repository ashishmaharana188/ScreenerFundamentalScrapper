# dashboard.py

import streamlit as st

st.set_page_config(
    page_title="Screener Dashboard",
    layout="centered",
)

st.title("Screener Fundamental Dashboard")

st.divider()

run_industry = st.checkbox(
    "Run Industry Fetch after initial group saves",
    value=False,
)

st.caption(
    "Unchecked = Industry enrichment will not run."
)

run_process = st.button(
    "Run Whole Process",
    type="primary",
    use_container_width=True,
)

if run_process:
    try:
        import outerFlow
        import logicFlow

        st.info("Running initial Screener extraction and saves...")

        # outerFlow performs:
        # authentication -> screen discovery -> group extraction -> saves
        # and its normal post-processing. The updated logicFlow default
        # does NOT perform Industry enrichment.
        outerFlow.run_outer_flow()

        if run_industry:
            st.info("Industry Fetch enabled. Running Industry enrichment...")

            industry_result = logicFlow.run_industry_enrichment()

            st.success("Industry enrichment completed.")
            st.write(industry_result)

            # Rebuild downstream files so Industry is carried into them.
            st.info("Rebuilding merged and final files...")
            logicFlow.run_group_merge()
            logicFlow.run_final_logic()

            st.success("Whole process completed with Industry enrichment.")

        else:
            st.success(
                "Whole process completed. Industry enrichment was not run."
            )

    except Exception as exc:
        st.error(f"Process failed: {exc}")
