"""Comparison logic for ScanX and Screener CSV files.

New flow
--------
Level 1:
    ScanX company universe ∩ each selected Screener screen

Level 2:
    The Level-1 results from multiple Screener screens are intersected.

There is no hard-coded Screener screen name and no requirement that
companies appear in a fixed set of screens.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


# ============================================================
# DIRECTORIES
# ============================================================

BASE_DATA_DIR = Path("screener_data")
GROUPS_DIR = BASE_DATA_DIR / "groups"
COMPARISON_DIR = BASE_DATA_DIR / "comparison"
SCANX_DIR = Path("scanx_data")


# ============================================================
# NAME NORMALIZATION
# ============================================================

def normalize_company_name(value) -> str:
    """Create a comparison key from a company name."""

    if pd.isna(value):
        return ""

    value = str(value).strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


# ============================================================
# FILE DISCOVERY
# ============================================================

def get_scanx_files() -> list[Path]:
    """Return all CSV files currently available in scanx_data/."""

    if not SCANX_DIR.exists():
        return []

    return sorted(
        path
        for path in SCANX_DIR.glob("*.csv")
        if path.is_file()
    )


def get_screener_files() -> list[Path]:
    """Return all CSV files currently available in screener_data/groups/."""

    if not GROUPS_DIR.exists():
        return []

    return sorted(
        path
        for path in GROUPS_DIR.glob("*.csv")
        if path.is_file()
    )


# ============================================================
# CSV LOADING
# ============================================================

def load_scanx_company_names(file_path: Path) -> pd.DataFrame:
    """Load one ScanX CSV and validate its company_name column."""

    df = pd.read_csv(file_path)

    if "company_name" not in df.columns:
        raise ValueError(
            f"ScanX file is missing 'company_name': {file_path}"
        )

    df = df[["company_name"]].copy()
    df["comparison_key"] = df["company_name"].map(normalize_company_name)
    df = df[df["comparison_key"] != ""].drop_duplicates("comparison_key")

    return df


def load_screener_file(file_path: Path) -> pd.DataFrame:
    """Load one saved Screener result CSV."""

    df = pd.read_csv(file_path)

    if "company_name" not in df.columns:
        raise ValueError(
            f"Screener file is missing 'company_name': {file_path}"
        )

    df = df.copy()
    df["comparison_key"] = df["company_name"].map(normalize_company_name)
    df = df[df["comparison_key"] != ""].drop_duplicates("comparison_key")

    return df


# ============================================================
# SAFE OUTPUT NAME
# ============================================================

def make_safe_filename(name: str) -> str:
    """Convert a screen/file label to a safe filename."""

    filename = Path(name).stem.lower().strip()
    filename = re.sub(r"[^a-z0-9]+", "_", filename)
    filename = filename.strip("_")

    return filename or "comparison"


# ============================================================
# LEVEL 1: SCANX x SCREENER
# ============================================================

def compare_scanx_with_screener(
    scanx_file: Path,
    screener_file: Path,
) -> tuple[pd.DataFrame, Path]:
    """Keep Screener rows whose company also exists in ScanX."""

    scanx_df = load_scanx_company_names(scanx_file)
    screener_df = load_screener_file(screener_file)

    scanx_keys = set(scanx_df["comparison_key"])

    filtered = screener_df[
        screener_df["comparison_key"].isin(scanx_keys)
    ].copy()

    # comparison_key is internal only and should not appear in the result.
    filtered = filtered.drop(columns=["comparison_key"])

    level_1_dir = COMPARISON_DIR / "level_1_scanx_vs_screener"
    level_1_dir.mkdir(parents=True, exist_ok=True)

    output_file = level_1_dir / (
        f"scanx_vs_{make_safe_filename(screener_file.name)}"
    )

    if output_file.suffix.lower() != ".csv":
        output_file = output_file.with_suffix(".csv")

    filtered.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"Level 1 | {screener_file.name} | "
        f"ScanX companies={len(scanx_df)} | "
        f"Screener rows={len(screener_df)} | "
        f"Common={len(filtered)}"
    )

    return filtered, output_file


def run_level_1(
    scanx_file: Path,
    screener_files: list[Path],
) -> dict[str, dict]:
    """Run ScanX ∩ Screener for every selected Screener file."""

    if not screener_files:
        raise ValueError("Select at least one Screener file for comparison.")

    results = {}

    for screener_file in screener_files:
        filtered_df, output_file = compare_scanx_with_screener(
            scanx_file=scanx_file,
            screener_file=screener_file,
        )

        results[screener_file.name] = {
            "rows": len(filtered_df),
            "file": output_file,
            "dataframe": filtered_df,
        }

    return results


# ============================================================
# LEVEL 2: SCREENER x SCREENER
# ============================================================

def run_level_2(
    level_1_results: dict[str, dict],
) -> tuple[pd.DataFrame | None, Path | None]:
    """Find companies common to all selected Level-1 Screener results."""

    if len(level_1_results) < 2:
        print("Level 2 skipped: select at least two Screener files.")
        return None, None

    dataframes = [
        result["dataframe"]
        for result in level_1_results.values()
    ]

    common_keys = set(dataframes[0]["company_name"].map(normalize_company_name))

    for df in dataframes[1:]:
        current_keys = set(df["company_name"].map(normalize_company_name))
        common_keys &= current_keys

    # Use the first Level-1 dataframe as the source for all columns.
    first_df = dataframes[0].copy()
    first_df["comparison_key"] = first_df["company_name"].map(
        normalize_company_name
    )

    common_df = first_df[
        first_df["comparison_key"].isin(common_keys)
    ].copy()

    common_df = common_df.drop(columns=["comparison_key"])

    level_2_dir = COMPARISON_DIR / "level_2_screener_intersection"
    level_2_dir.mkdir(parents=True, exist_ok=True)

    output_file = level_2_dir / "common_across_selected_screens.csv"

    common_df.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"Level 2 | selected Screener files={len(dataframes)} | "
        f"Common companies={len(common_df)}"
    )

    return common_df, output_file


# ============================================================
# MAIN COMPARISON RUNNER
# ============================================================

def run_comparison(
    scanx_file: Path,
    screener_files: list[Path],
) -> dict:
    """Run Level 1 and, when possible, Level 2 comparison."""

    if not scanx_file.exists():
        raise FileNotFoundError(f"ScanX file not found: {scanx_file}")

    if not screener_files:
        raise ValueError("No Screener files selected.")

    for file_path in screener_files:
        if not file_path.exists():
            raise FileNotFoundError(f"Screener file not found: {file_path}")

    level_1 = run_level_1(
        scanx_file=scanx_file,
        screener_files=screener_files,
    )

    level_2_df, level_2_file = run_level_2(level_1)

    return {
        "scanx_file": scanx_file,
        "level_1": level_1,
        "level_2_dataframe": level_2_df,
        "level_2_file": level_2_file,
    }


if __name__ == "__main__":
    print("Comparison logic is run from dashboard.py.")
