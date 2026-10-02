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

import os
import re
from pathlib import Path
from datetime import datetime

import pandas as pd


# ============================================================
# STORAGE RESOLUTION
# ============================================================
#
# Local:
#     APP_STORAGE_ROOT is normally unset.
#     Project root is used.
#
# Render:
#     APP_STORAGE_ROOT=/var/data
#     Persistent disk becomes the storage root.
#
# The fallback intentionally reads APP_STORAGE_ROOT itself so Render
# still works even if storage.py is not importable from Scripts/.
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_ENV_STORAGE_ROOT = os.getenv("APP_STORAGE_ROOT", "").strip()

if _ENV_STORAGE_ROOT:
    STORAGE_ROOT = Path(_ENV_STORAGE_ROOT).expanduser().resolve()
else:
    STORAGE_ROOT = PROJECT_ROOT.resolve()


try:
    from storage import (
        STORAGE_ROOT as _CENTRAL_STORAGE_ROOT,
        GROUPS_DIR as _CENTRAL_GROUPS_DIR,
        COMPARISON_DIR as _CENTRAL_COMPARISON_DIR,
        SCANX_DIR as _CENTRAL_SCANX_DIR,
    )

    # storage.py is the source of truth when it is importable and its
    # root matches the environment configuration.
    GROUPS_DIR = _CENTRAL_GROUPS_DIR
    COMPARISON_DIR = _CENTRAL_COMPARISON_DIR
    SCANX_DIR = _CENTRAL_SCANX_DIR

except ImportError:
    BASE_DATA_DIR = STORAGE_ROOT / "screener_data"
    GROUPS_DIR = BASE_DATA_DIR / "groups"
    COMPARISON_DIR = BASE_DATA_DIR / "comparison"
    SCANX_DIR = STORAGE_ROOT / "scanx_data"


# Preserve compatibility with files created by the older relative-path
# implementation during local development. Only enabled when Render
# storage has not explicitly been selected.
LEGACY_SCANX_DIR = (Path.cwd() / "scanx_data").resolve()
LEGACY_GROUPS_DIR = (
    Path.cwd() / "screener_data" / "groups"
).resolve()


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

def _unique_csv_files(
    directories: list[Path],
) -> list[Path]:
    """Return unique CSV files from the supplied directories."""
    files_by_path: dict[str, Path] = {}

    for directory in directories:
        if not directory.exists() or not directory.is_dir():
            continue

        for path in directory.glob("*.csv"):
            if not path.is_file():
                continue

            resolved = path.resolve()
            files_by_path[str(resolved).lower()] = resolved

    return sorted(
        files_by_path.values(),
        key=lambda path: (
            path.name.lower(),
            str(path).lower(),
        ),
    )


def get_scanx_files() -> list[Path]:
    """
    Return available ScanX CSV files.

    Local development also checks the legacy cwd-based directory so files
    created before storage.py was introduced remain visible.
    """
    directories = [SCANX_DIR]

    if not _ENV_STORAGE_ROOT:
        directories.append(LEGACY_SCANX_DIR)

    return _unique_csv_files(directories)


def get_screener_files() -> list[Path]:
    """
    Return available Screener CSV files.

    Local development also checks the legacy cwd-based directory so files
    created before storage.py was introduced remain visible.
    """
    directories = [GROUPS_DIR]

    if not _ENV_STORAGE_ROOT:
        directories.append(LEGACY_GROUPS_DIR)

    return _unique_csv_files(directories)


# ============================================================
# CSV LOADING
# ============================================================

def load_scanx_company_names(file_path: Path) -> pd.DataFrame:
    """
    Load one ScanX CSV.

    ScanX now stores:
        company_name
        industry
        sector

    Industry and sector are retained so they can be attached to
    the final comparison results.
    """

    df = pd.read_csv(file_path)

    # Strip accidental whitespace in CSV headers.
    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    # company_name is the only field required for comparison.
    # industry/sector are optional so older ScanX exports remain usable.
    if "company_name" not in df.columns:
        raise ValueError(
            f"ScanX file is missing 'company_name': {file_path}"
        )

    for column in ("industry", "sector"):
        if column not in df.columns:
            df[column] = ""

    df = df[
        [
            "company_name",
            "industry",
            "sector",
        ]
    ].copy()

    df["industry"] = (
        df["industry"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["sector"] = (
        df["sector"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["comparison_key"] = (
        df["company_name"]
        .map(normalize_company_name)
    )

    df = (
        df[df["comparison_key"] != ""]
        .drop_duplicates("comparison_key")
    )

    return df


def load_screener_file(file_path: Path) -> pd.DataFrame:
    """Load one saved Screener result CSV."""

    df = pd.read_csv(file_path)

    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

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


def _comparison_output_path(
    directory: Path,
    filename: str,
) -> Path:
    """
    Return a writable comparison filename.

    Windows can reject an overwrite when the previous CSV is open in
    Excel or another application. It can also reject excessively long
    paths. When the deterministic filename already exists, create a
    timestamped sibling instead of failing the entire comparison.
    """
    directory.mkdir(parents=True, exist_ok=True)

    candidate = directory / filename

    try:
        path_length = len(str(candidate.resolve()))
    except OSError:
        path_length = len(str(candidate))

    if not candidate.exists() and path_length < 230:
        return candidate

    stem = candidate.stem[:90].rstrip("_")
    suffix = candidate.suffix or ".csv"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fallback = directory / f"{stem}_{timestamp}{suffix}"

    counter = 1
    while fallback.exists():
        fallback = directory / (
            f"{stem}_{timestamp}_{counter}{suffix}"
        )
        counter += 1

    return fallback


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

    # Attach ScanX taxonomy to the matched Screener companies.
    scanx_metadata = (
        scanx_df[
            [
                "comparison_key",
                "industry",
                "sector",
            ]
        ]
        .rename(
            columns={
                "industry": "scanx_industry",
                "sector": "scanx_sector",
            }
        )
        .copy()
    )

    filtered = filtered.merge(
        scanx_metadata,
        on="comparison_key",
        how="left",
    )

    # ScanX is authoritative for these two taxonomy columns.
    if "industry" in filtered.columns:
        filtered["industry"] = (
            filtered["scanx_industry"]
            .where(
                filtered["scanx_industry"].ne(""),
                filtered["industry"].fillna(""),
            )
        )
    else:
        filtered["industry"] = (
            filtered["scanx_industry"].fillna("")
        )

    if "sector" in filtered.columns:
        filtered["sector"] = (
            filtered["scanx_sector"]
            .where(
                filtered["scanx_sector"].ne(""),
                filtered["sector"].fillna(""),
            )
        )
    else:
        filtered["sector"] = (
            filtered["scanx_sector"].fillna("")
        )

    filtered = filtered.drop(
        columns=[
            "comparison_key",
            "scanx_industry",
            "scanx_sector",
        ]
    )

    level_1_dir = COMPARISON_DIR / "level_1_scanx_vs_screener"
    level_1_dir.mkdir(parents=True, exist_ok=True)

    output_filename = (
        f"scanx_vs_{make_safe_filename(screener_file.name)}"
    )

    if not output_filename.lower().endswith(".csv"):
        output_filename += ".csv"

    output_file = _comparison_output_path(
        level_1_dir,
        output_filename,
    )

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

    output_file = _comparison_output_path(
        level_2_dir,
        "common_across_selected_screens.csv",
    )

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
        raise FileNotFoundError(
            f"ScanX file not found: {scanx_file}"
        )

    if not screener_files:
        raise ValueError("No Screener files selected.")

    # Ensure the active storage tree exists.
    GROUPS_DIR.mkdir(parents=True, exist_ok=True)
    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
    SCANX_DIR.mkdir(parents=True, exist_ok=True)

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
