# logicFlow.py

import json
import re
import time
from pathlib import Path

import pandas as pd
import yfinance as yf


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DATA_DIR = Path("screener_data")

GROUPS_DIR = BASE_DATA_DIR / "groups"

FINAL_DIR = BASE_DATA_DIR / "final"

INDUSTRY_CACHE_FILE = BASE_DATA_DIR / "industry_cache.json"


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


#GROUP_FILE_NAMES = {
#    "Core Business Quality":
#        "01_core_business_quality.csv",

#    "Growth and Earnings Quality":
#        "02_growth_and_earnings_quality.csv",

#    "Balance Sheet and Cash-Flow Strength":
#        "03_balance_sheet_and_cash_flow_strength.csv",

#    "Valuation":
#        "04_valuation.csv",

#    "Promoters and Shareholder Structure":
#        "05_promoters_and_shareholder_structure.csv",
#}

TARGET_GROUPS = [
    "Quality Gate",
    "Under valued",
    "Over Valued",
    "Loose check",
]

GROUP_FILE_NAMES = {
    "Quality Gate":
        "01_quality_gate.csv",

    "Under valued":
        "02_under_valued.csv",

    "Over Valued":
        "03_over_valued.csv",

    "Loose check":
        "04_loose_check.csv",
}

# ------------------------------------------------------------
# Final selection rule
#
# Currently:
# Company must appear in every one of the five groups.
#
# Later this can be changed without touching scraping code.
# ------------------------------------------------------------

FINAL_REQUIRED_GROUPS = [
    "Core Business Quality",
    "Growth and Earnings Quality",
    "Balance Sheet and Cash-Flow Strength",
    "Valuation",
    "Promoters and Shareholder Structure",
]


# ------------------------------------------------------------
# yfinance spacing
# ------------------------------------------------------------

YFINANCE_DELAY = 1.0


# ============================================================
# DIRECTORY SETUP
# ============================================================

def initialize_logic_directories():
    """
    Make sure the post-processing directories exist.
    """

    GROUPS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    FINAL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# INDUSTRY CACHE
# ============================================================

def load_industry_cache():
    """
    Load locally cached Yahoo Finance industry lookups.

    This prevents querying the same company repeatedly
    across multiple group files.
    """

    if not INDUSTRY_CACHE_FILE.exists():
        return {}

    try:

        with open(
            INDUSTRY_CACHE_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):
            return data

    except Exception as e:

        print(
            f"WARNING: Could not load industry cache: {e}"
        )

    return {}


def save_industry_cache(cache):
    """
    Save industry lookup cache.
    """

    initialize_logic_directories()

    with open(
        INDUSTRY_CACHE_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            cache,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# EXTRACT YAHOO SYMBOL
# ============================================================

def extract_screener_symbol(company_url):
    """
    Extract the Screener symbol from company_url.

    Example:

        https://www.screener.in/company/HDFCAMC/

    becomes:

        HDFCAMC
    """

    if not company_url:
        return None

    match = re.search(
        r"/company/([^/]+)/",
        str(company_url),
    )

    if not match:
        return None

    symbol = match.group(1).strip()

    if not symbol:
        return None

    return symbol


# ============================================================
# GET INDUSTRY FROM YFINANCE
# ============================================================

def get_yfinance_industry(
    screener_symbol,
    cache,
):
    """
    Get industry from Yahoo Finance.

    Tries:
        SYMBOL.NS
        SYMBOL.BO

    The first successful industry value is returned.

    Cache is checked before making a Yahoo Finance request.
    """

    if not screener_symbol:
        return None

    screener_symbol = str(
        screener_symbol
    ).strip()

    if not screener_symbol:
        return None

    # --------------------------------------------------------
    # Cached result
    # --------------------------------------------------------

    if screener_symbol in cache:

        cached_value = cache[
            screener_symbol
        ]

        if cached_value:
            return cached_value

    # --------------------------------------------------------
    # Candidate Yahoo symbols
    # --------------------------------------------------------

    candidates = []

    if screener_symbol.endswith(
        ".NS"
    ) or screener_symbol.endswith(
        ".BO"
    ):

        candidates.append(
            screener_symbol
        )

    else:

        candidates.extend(
            [
                f"{screener_symbol}.NS",
                f"{screener_symbol}.BO",
            ]
        )

    # --------------------------------------------------------
    # Query Yahoo Finance
    # --------------------------------------------------------

    for yahoo_symbol in candidates:

        try:

            print(
                f"    Yahoo Finance lookup: "
                f"{yahoo_symbol}"
            )

            ticker = yf.Ticker(
                yahoo_symbol
            )

            info = ticker.info

            industry = info.get(
                "industry"
            )

            if industry:

                industry = str(
                    industry
                ).strip()

                if industry:

                    cache[
                        screener_symbol
                    ] = industry

                    print(
                        f"    industry: "
                        f"{industry}"
                    )

                    time.sleep(
                        YFINANCE_DELAY
                    )

                    return industry

        except Exception as e:

            print(
                f"    Yahoo lookup failed for "
                f"{yahoo_symbol}: {e}"
            )

        time.sleep(
            YFINANCE_DELAY
        )

    # --------------------------------------------------------
    # No industry found
    # --------------------------------------------------------

    cache[
        screener_symbol
    ] = ""

    print(
        f"    industry not found for "
        f"{screener_symbol}"
    )

    return None


# ============================================================
# INDUSTRY ENRICHMENT: COMPANY-FIRST
# ============================================================

def normalize_company_name(value):
    """Normalize company names so the same company matches reliably."""

    if pd.isna(value):
        return ""

    value = str(value).strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def load_all_group_files():
    """Load all five group CSVs into memory."""

    group_dataframes = {}

    for group_name in TARGET_GROUPS:
        filename = GROUP_FILE_NAMES[group_name]
        file_path = GROUPS_DIR / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"Group CSV not found: {file_path}"
            )

        df = pd.read_csv(
            file_path,
            dtype={"company_id": "string"},
        )

        required_columns = [
            "company_id",
            "company_name",
            "company_url",
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            raise RuntimeError(
                f"{group_name} is missing required columns: "
                f"{missing_columns}"
            )

        group_dataframes[group_name] = df

        print(
            f"Loaded {group_name}: {len(df)} rows"
        )

    return group_dataframes


def build_distinct_company_map(group_dataframes):
    """
    Build ONE company list from all five group files.

    Distinctness is based on normalized company_name.
    The first available company_url is retained so Yahoo Finance
    only needs to be queried once for that company.
    """

    records = {}

    for group_name in TARGET_GROUPS:
        df = group_dataframes[group_name]

        for _, row in df.iterrows():
            company_name = row.get("company_name")
            company_key = normalize_company_name(company_name)

            if not company_key:
                continue

            if company_key not in records:
                records[company_key] = {
                    "company_name": str(company_name).strip(),
                    "company_url": str(row.get("company_url", "")).strip(),
                }
            else:
                # If the first occurrence had no usable URL,
                # use a later group's URL.
                existing_url = records[company_key]["company_url"]
                current_url = str(row.get("company_url", "")).strip()

                if not existing_url and current_url:
                    records[company_key]["company_url"] = current_url

    return records


def build_industry_mapping(group_dataframes, industry_cache):
    """
    Fetch industry ONCE per distinct company across all five groups.

    Flow:
        1. Read all five group files.
        2. Build one distinct company-name map.
        3. Resolve Yahoo Finance industry once per company.
        4. Return {normalized_company_name: industry}.
    """

    company_map = build_distinct_company_map(
        group_dataframes
    )

    print("\n========================================")
    print("BUILDING DISTINCT COMPANY INDUSTRY MAP")
    print("========================================")

    print(
        f"Rows across all groups: "
        f"{sum(len(df) for df in group_dataframes.values())}"
    )

    print(
        f"Distinct companies: {len(company_map)}"
    )

    industry_mapping = {}

    for index, (company_key, company) in enumerate(
        company_map.items(),
        start=1,
    ):

        company_name = company["company_name"]
        company_url = company["company_url"]

        print("\n----------------------------------------")
        print(
            f"Company {index}/{len(company_map)}: "
            f"{company_name}"
        )

        symbol = extract_screener_symbol(
            company_url
        )

        if not symbol:
            print(
                "  Could not extract Screener symbol."
            )
            industry_mapping[company_key] = ""
            continue

        industry = get_yfinance_industry(
            screener_symbol=symbol,
            cache=industry_cache,
        )

        industry_mapping[company_key] = (
            industry if industry else ""
        )

    return industry_mapping


def apply_industry_mapping_to_groups(
    group_dataframes,
    industry_mapping,
):
    """
    Insert the newly built industry mapping into each original group CSV.

    Matching is done by normalized company_name.
    The same company therefore receives the exact same industry value
    in every group where it appears.
    """

    updated_dataframes = {}

    for group_name in TARGET_GROUPS:
        df = group_dataframes[group_name].copy()

        df["industry"] = (
            df["company_name"]
            .map(normalize_company_name)
            .map(industry_mapping)
            .fillna("")
        )

        desired_order = []

        for column in [
            "company_id",
            "company_name",
            "company_url",
            "industry",
        ]:
            if column in df.columns:
                desired_order.append(column)

        remaining_columns = [
            column
            for column in df.columns
            if column not in desired_order
        ]

        df = df[
            desired_order + remaining_columns
        ]

        file_path = GROUPS_DIR / GROUP_FILE_NAMES[group_name]

        df.to_csv(
            file_path,
            index=False,
            encoding="utf-8-sig",
        )

        found_count = (
            df["industry"]
            .astype(str)
            .str.strip()
            .ne("")
            .sum()
        )

        print("\nSaved enriched group:")
        print(f"  {file_path}")
        print(f"  Rows: {len(df)}")
        print(
            f"  industry found: "
            f"{found_count}/{len(df)}"
        )

        updated_dataframes[group_name] = df

    return updated_dataframes


def run_industry_enrichment():
    """
    Company-first industry enrichment.

    IMPORTANT:
    Yahoo Finance is queried once per distinct company across ALL
    five group files, not once per group file.
    """

    initialize_logic_directories()

    print("\n")
    print("########################################")
    print("# INDUSTRY ENRICHMENT")
    print("########################################")

    group_dataframes = load_all_group_files()

    industry_cache = load_industry_cache()

    industry_mapping = build_industry_mapping(
        group_dataframes=group_dataframes,
        industry_cache=industry_cache,
    )

    save_industry_cache(
        industry_cache
    )

    updated_dataframes = apply_industry_mapping_to_groups(
        group_dataframes=group_dataframes,
        industry_mapping=industry_mapping,
    )

    found = sum(
        1
        for industry in industry_mapping.values()
        if str(industry).strip()
    )

    print("\n========================================")
    print("INDUSTRY ENRICHMENT COMPLETE")
    print("========================================")
    print(
        f"Distinct companies processed: "
        f"{len(industry_mapping)}"
    )
    print(
        f"Industries found: {found}"
    )
    print(
        f"industry cache entries: "
        f"{len(industry_cache)}"
    )

    return {
        "companies_processed": len(industry_mapping),
        "industries_found": found,
        "industry_mapping": industry_mapping,
        "group_dataframes": updated_dataframes,
    }


# ============================================================
# LOAD GROUP CSVs
# ============================================================

def load_group_csv(
    group_name,
):
    """
    Load a group CSV after industry enrichment.
    """

    file_path = (
        GROUPS_DIR
        / GROUP_FILE_NAMES[group_name]
    )

    if not file_path.exists():

        raise FileNotFoundError(
            f"Group CSV not found: {file_path}"
        )

    df = pd.read_csv(
        file_path,
        dtype={
            "company_id": "string"
        },
    )

    return df


# ============================================================
# PREPARE GROUP FOR MERGE
# ============================================================

def prepare_group_for_merge(
    group_name,
    df,
):
    """
    Prepare one group DataFrame for the final merge.

    Common identity columns remain unchanged.

    Group-specific metrics are prefixed with the group name
    so columns from different screens cannot collide.
    """

    df = df.copy()

    # --------------------------------------------------------
    # Ensure unique company per group
    # --------------------------------------------------------

    duplicate_count = (
        df["company_id"]
        .duplicated()
        .sum()
    )

    if duplicate_count:

        print(
            f"WARNING: {group_name} contains "
            f"{duplicate_count} duplicate company_id rows."
        )

        df = df.drop_duplicates(
            subset=["company_id"],
            keep="first",
        )

    # --------------------------------------------------------
    # Common columns
    # --------------------------------------------------------

    common_columns = [
        "company_id",
         "company_name",
        "company_url",
        "industry",
    ]

    existing_common = [
        column
        for column in common_columns
        if column in df.columns
    ]

    # --------------------------------------------------------
    # Group-specific columns
    # --------------------------------------------------------

    metric_columns = [
        column
        for column in df.columns
        if column not in existing_common
    ]

    safe_group_name = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        group_name,
    ).strip("_")

    rename_map = {
        column:
            f"{safe_group_name}__{column}"
        for column in metric_columns
    }

    df = df.rename(
        columns=rename_map
    )

    return df


# ============================================================
# COALESCE COMMON COLUMN
# ============================================================

def coalesce_column(
    df,
    column,
):
    """
    Ensure a common field has one consolidated value.

    For example, industry may exist in several group frames
    after the merge.
    """

    matching_columns = [
        col
        for col in df.columns
        if col == column
        or col.startswith(
            f"{column}_"
        )
    ]

    if not matching_columns:
        return df

    # If already only one column exists, nothing to do.
    if len(matching_columns) == 1:
        return df

    df[column] = ""

    for col in matching_columns:

        values = (
            df[col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        mask = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
            & values.ne("")
        )

        df.loc[
            mask,
            column,
        ] = values[mask]

    columns_to_drop = [
        col
        for col in matching_columns
        if col != column
    ]

    df = df.drop(
        columns=columns_to_drop
    )

    return df


# ============================================================
# MERGE ALL GROUPS
# ============================================================

def build_merged_candidates(
    group_dataframes,
):
    """
    Outer-merge all five groups using company_id.

    This preserves every company that appears in at least
    one screen.
    """

    print("\n========================================")
    print("BUILDING MERGED DATASET")
    print("========================================")

    merged_df = None

    for group_index, group_name in enumerate(
        TARGET_GROUPS,
        start=1,
    ):

        df = group_dataframes[
            group_name
        ]

        prepared = prepare_group_for_merge(
            group_name,
            df,
        )

        # ----------------------------------------------------
        # Add group membership flag
        # ----------------------------------------------------

        group_flag = (
            f"Group_{group_index}_Pass"
        )

        prepared[
            group_flag
        ] = True

        # ----------------------------------------------------
        # First group
        # ----------------------------------------------------

        if merged_df is None:

            merged_df = prepared

            continue

        # ----------------------------------------------------
        # Subsequent groups
        # ----------------------------------------------------

        merged_df = merged_df.merge(
            prepared,
            on="company_id",
            how="outer",
            suffixes=("", f"_group_{group_index}"),
        )

    # --------------------------------------------------------
    # Consolidate common columns
    # --------------------------------------------------------

    for column in [
        "company_name",
        "company_url",
        "industry",
    ]:

        merged_df = coalesce_column(
            merged_df,
            column,
        )

    # --------------------------------------------------------
    # Ensure all group flags exist
    # --------------------------------------------------------

    for group_index in range(
        1,
        len(TARGET_GROUPS) + 1,
    ):

        group_flag = (
            f"Group_{group_index}_Pass"
        )

        if group_flag not in merged_df.columns:

            merged_df[
                group_flag
            ] = False

        else:

            merged_df[
                group_flag
            ] = (
                merged_df[
                    group_flag
                ]
                .fillna(False)
                .astype(bool)
            )

    # --------------------------------------------------------
    # Number of groups passed
    # --------------------------------------------------------

    group_flags = [
        f"Group_{i}_Pass"
        for i in range(
            1,
            len(TARGET_GROUPS) + 1,
        )
    ]

    merged_df[
        "Groups_Passed"
    ] = merged_df[
        group_flags
    ].sum(axis=1)

    # --------------------------------------------------------
    # Group names passed
    # --------------------------------------------------------

    def get_groups_passed(row):

        passed = []

        for index, group_name in enumerate(
            TARGET_GROUPS,
            start=1,
        ):

            if row[
                f"Group_{index}_Pass"
            ]:

                passed.append(
                    group_name
                )

        return " | ".join(
            passed
        )

    merged_df[
        "Groups_Passed_Names"
    ] = merged_df.apply(
        get_groups_passed,
        axis=1,
    )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    merged_df = merged_df.sort_values(
        by=[
            "Groups_Passed",
            "company_name",
        ],
        ascending=[
            False,
            True,
        ],
        na_position="last",
    ).reset_index(
        drop=True
    )

    return merged_df


# ============================================================
# SAVE CSV
# ============================================================

def save_dataframe(
    df,
    file_path,
):
    """
    Save DataFrame to CSV.
    """

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        file_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"\nSaved:"
    )

    print(
        f"  {file_path.resolve()}"
    )

    print(
        f"  Rows: {len(df)}"
    )


# ============================================================
# APPLY FINAL LOGIC
# ============================================================

def build_final_candidates(
    merged_df,
):
    """
    Apply the configured final-selection rule.

    Current rule:
        company must appear in every group listed in
        FINAL_REQUIRED_GROUPS.
    """

    required_group_indexes = []

    for group_name in FINAL_REQUIRED_GROUPS:

        if group_name not in TARGET_GROUPS:

            raise ValueError(
                f"Unknown final-required group: "
                f"{group_name}"
            )

        index = (
            TARGET_GROUPS.index(
                group_name
            )
            + 1
        )

        required_group_indexes.append(
            index
        )

    required_flags = [
        f"Group_{index}_Pass"
        for index in required_group_indexes
    ]

    final_mask = merged_df[
        required_flags
    ].all(axis=1)

    final_df = merged_df[
        final_mask
    ].copy()

    # --------------------------------------------------------
    # Sort final candidates
    # --------------------------------------------------------

    final_df = final_df.sort_values(
        by=[
            "Groups_Passed",
            "company_name",
        ],
        ascending=[
            False,
            True,
        ],
        na_position="last",
    ).reset_index(
        drop=True
    )

    return final_df


# ============================================================
# CONTROLLED LOGIC STAGES
# ============================================================

def run_group_merge():
    """Merge the already-saved group CSVs. Does not fetch Industry."""

    initialize_logic_directories()

    group_dataframes = {}

    for group_name in TARGET_GROUPS:
        group_dataframes[group_name] = load_group_csv(
            group_name
        )

    print("\n")
    print("########################################")
    print("# STAGE: MERGING GROUPS")
    print("########################################")

    merged_df = build_merged_candidates(
        group_dataframes
    )

    merged_file = FINAL_DIR / "merged_candidates.csv"

    save_dataframe(
        merged_df,
        merged_file,
    )

    return merged_df


def run_final_logic(merged_df=None):
    """Apply final-selection logic. Does not fetch Industry."""

    if merged_df is None:
        merged_file = FINAL_DIR / "merged_candidates.csv"

        if not merged_file.exists():
            merged_df = run_group_merge()
        else:
            merged_df = pd.read_csv(
                merged_file,
            )

    print("\n")
    print("########################################")
    print("# STAGE: FINAL FILTER")
    print("########################################")

    final_df = build_final_candidates(
        merged_df
    )

    final_file = FINAL_DIR / "final_candidates.csv"

    save_dataframe(
        final_df,
        final_file,
    )

    print("\n========================================")
    print("FINAL LOGIC COMPLETE")
    print("========================================")
    print(
        f"Companies across any group: {len(merged_df)}"
    )
    print(
        f"Final candidates: {len(final_df)}"
    )

    return final_df


def run_logic_flow(include_industry=False):
    """
    Run post-processing with Industry OFF by default.

    include_industry=True explicitly performs:
        1. Distinct-company Industry enrichment
        2. Group merge
        3. Final logic
    """

    results = {}

    if include_industry:
        results["industry"] = run_industry_enrichment()

    results["merged"] = run_group_merge()
    results["final"] = run_final_logic(
        results["merged"]
    )

    return results


def run_complete_logic():
    """Explicit full logic run with Industry enrichment enabled."""

    return run_logic_flow(
        include_industry=True
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_complete_logic()