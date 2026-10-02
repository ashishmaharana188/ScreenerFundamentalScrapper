"""
Centralized application storage.

LOCAL
-----
STORAGE_BACKEND=local
or no STORAGE_BACKEND set.

Files are stored directly in the project filesystem.

SUPABASE
--------
STORAGE_BACKEND=supabase

Files are stored in a private Supabase Storage bucket.
A small local cache is used because the existing application
expects Path objects.

The rest of the application therefore continues to work with
normal Path objects while storage.py handles persistence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

from supabase import create_client


# ============================================================
# PROJECT / STORAGE CONFIGURATION
# ============================================================

MODULE_DIR = Path(__file__).resolve().parent

if MODULE_DIR.name.lower() == "scripts":
    PROJECT_ROOT = MODULE_DIR.parent
else:
    PROJECT_ROOT = MODULE_DIR


STORAGE_BACKEND = (
    os.getenv("STORAGE_BACKEND", "local")
    .strip()
    .casefold()
)


# ============================================================
# LOCAL ROOT
# ============================================================

_env_root = os.getenv("APP_STORAGE_ROOT", "").strip()

if _env_root:
    STORAGE_ROOT = Path(_env_root).expanduser().resolve()
else:
    STORAGE_ROOT = PROJECT_ROOT.resolve()


BASE_DATA_DIR = STORAGE_ROOT / "screener_data"

GROUPS_DIR = BASE_DATA_DIR / "groups"
FINAL_DIR = BASE_DATA_DIR / "final"
COMPARISON_DIR = BASE_DATA_DIR / "comparison"

SCANX_DIR = STORAGE_ROOT / "scanx_data"
SESSION_DIR = STORAGE_ROOT / "session"


STORAGE_DIRECTORIES = (
    BASE_DATA_DIR,
    GROUPS_DIR,
    FINAL_DIR,
    COMPARISON_DIR,
    SCANX_DIR,
    SESSION_DIR,
)


# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()

SUPABASE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY",
    "",
).strip()

SUPABASE_BUCKET = os.getenv(
    "SUPABASE_BUCKET",
    "screener-data",
).strip()


_supabase = None


def _get_supabase():
    """
    Create the Supabase client only when Supabase storage is used.
    """

    global _supabase

    if STORAGE_BACKEND != "supabase":
        return None

    if _supabase is not None:
        return _supabase

    if not SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL is required when "
            "STORAGE_BACKEND=supabase."
        )

    if not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is required when "
            "STORAGE_BACKEND=supabase."
        )

    _supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
    )

    return _supabase


# ============================================================
# DIRECTORY INITIALIZATION
# ============================================================

def ensure_storage_dirs() -> None:
    """
    Create the local directories used by the application.

    Even in Supabase mode these directories are used as a
    temporary/local cache so existing code can continue using Path.
    """

    for directory in STORAGE_DIRECTORIES:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


# ============================================================
# PATH HELPERS
# ============================================================

def storage_path(
    *parts: str | os.PathLike[str],
) -> Path:
    return STORAGE_ROOT.joinpath(*parts)


def data_path(
    *parts: str | os.PathLike[str],
) -> Path:
    return BASE_DATA_DIR.joinpath(*parts)


def scanx_path(
    *parts: str | os.PathLike[str],
) -> Path:
    return SCANX_DIR.joinpath(*parts)


def session_path(
    *parts: str | os.PathLike[str],
) -> Path:
    return SESSION_DIR.joinpath(*parts)


def ensure_parent(
    path: str | os.PathLike[str],
) -> Path:

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


# ============================================================
# SUPABASE PATH MAPPING
# ============================================================

def _remote_key(
    path: str | os.PathLike[str],
) -> str:
    """
    Convert a local application path into a Supabase object path.

    Example:

        local:
            /project/screener_data/groups/value.csv

        remote:
            screener_data/groups/value.csv
    """

    path = Path(path).resolve()

    try:
        relative = path.relative_to(
            STORAGE_ROOT.resolve()
        )
    except ValueError as exc:
        raise ValueError(
            f"Path is outside storage root: {path}"
        ) from exc

    return relative.as_posix()


# ============================================================
# SUPABASE DOWNLOAD
# ============================================================

def _download_remote_file(
    path: Path,
) -> Path:

    if STORAGE_BACKEND != "supabase":
        return path

    remote_key = _remote_key(path)

    client = _get_supabase()

    try:
        content = (
            client.storage
            .from_(SUPABASE_BUCKET)
            .download(remote_key)
        )
    except Exception as exc:
        raise RuntimeError(
            f"Could not download Supabase file: "
            f"{remote_key}"
        ) from exc

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(content)

    return path


# ============================================================
# SUPABASE UPLOAD
# ============================================================

def upload_file(
    path: str | os.PathLike[str],
) -> Path:
    """
    Upload a local file to Supabase Storage.

    LOCAL
        Does nothing and returns the local Path.

    SUPABASE
        Uploads the file to the configured private bucket and
        uses the path relative to STORAGE_ROOT as the object key.
    """

    path = Path(path)

    if STORAGE_BACKEND != "supabase":
        return path

    if not path.is_file():
        raise FileNotFoundError(
            f"Cannot upload missing file: {path}"
        )

    remote_key = _remote_key(path)
    client = _get_supabase()

    try:
        with path.open("rb") as file:
            client.storage.from_(SUPABASE_BUCKET).upload(
                remote_key,
                file,
                file_options={"upsert": "true"},
            )
    except Exception as exc:
        raise RuntimeError(
            f"Could not upload file to Supabase: {remote_key}"
        ) from exc

    return path


# ============================================================
# DELETE FILE
# ============================================================

def delete_file(
    path: str | os.PathLike[str],
) -> None:
    """
    Delete a file from the active storage backend.

    LOCAL
        Removes the local file.

    SUPABASE
        Removes the remote object and the local cached copy.
    """

    path = Path(path)

    # Local backend
    if STORAGE_BACKEND != "supabase":
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Could not delete local file: {path}"
            ) from exc

        return

    # Supabase backend
    remote_key = _remote_key(path)
    client = _get_supabase()

    try:
        client.storage.from_(SUPABASE_BUCKET).remove(
            [remote_key]
        )
    except Exception as exc:
        raise RuntimeError(
            f"Could not delete Supabase file: {remote_key}"
        ) from exc

    # Remove local cache after remote deletion succeeds.
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Supabase file was deleted, but local cache could not "
            f"be removed: {path}"
        ) from exc


# ============================================================
# FILE EXISTENCE
# ============================================================

def file_exists(
    path: str | os.PathLike[str],
) -> bool:

    path = Path(path)

    if path.is_file():
        return True

    if STORAGE_BACKEND != "supabase":
        return False

    remote_key = _remote_key(path)

    client = _get_supabase()

    parent = str(
        Path(remote_key).parent
    ).replace("\\", "/")

    filename = Path(remote_key).name

    try:
        files = (
            client.storage
            .from_(SUPABASE_BUCKET)
            .list(parent)
        )
    except Exception:
        return False

    return any(
        item.get("name") == filename
        for item in files
        if isinstance(item, dict)
    )


# ============================================================
# LIST FILES
# ============================================================

def list_files(
    directory: str | os.PathLike[str],
    pattern: str = "*",
) -> list[Path]:

    directory = Path(directory)

    if STORAGE_BACKEND != "supabase":

        if not directory.exists():
            return []

        return sorted(
            (
                path
                for path in directory.glob(pattern)
                if path.is_file()
            ),
            key=lambda path: path.name.lower(),
        )

    # --------------------------------------------------------
    # Supabase mode
    # --------------------------------------------------------

    client = _get_supabase()

    remote_directory = _remote_key(directory)

    try:
        items = (
            client.storage
            .from_(SUPABASE_BUCKET)
            .list(remote_directory)
        )
    except Exception as exc:
        raise RuntimeError(
            f"Could not list Supabase directory: "
            f"{remote_directory}"
        ) from exc

    results = []

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    for item in items:

        if not isinstance(item, dict):
            continue

        name = str(
            item.get("name") or ""
        ).strip()

        if not name:
            continue

        # Supabase list() can contain folders.
        if item.get("id") is None:
            continue

        local_path = directory / name

        if not local_path.match(pattern):
            continue

        _download_remote_file(
            local_path
        )

        results.append(
            local_path
        )

    return sorted(
        results,
        key=lambda path: path.name.lower(),
    )


# ============================================================
# TEXT
# ============================================================

def read_text(
    path: str | os.PathLike[str],
    encoding: str = "utf-8",
) -> str:

    path = Path(path)

    if STORAGE_BACKEND == "supabase":
        _download_remote_file(path)

    return path.read_text(
        encoding=encoding,
    )


def write_text(
    path: str | os.PathLike[str],
    content: str,
    encoding: str = "utf-8",
) -> Path:

    path = ensure_parent(path)

    path.write_text(
        content,
        encoding=encoding,
    )

    upload_file(path)

    return path


# ============================================================
# BYTES
# ============================================================

def read_bytes(
    path: str | os.PathLike[str],
) -> bytes:

    path = Path(path)

    if STORAGE_BACKEND == "supabase":
        _download_remote_file(path)

    return path.read_bytes()


def write_bytes(
    path: str | os.PathLike[str],
    content: bytes,
) -> Path:

    path = ensure_parent(path)

    path.write_bytes(content)

    upload_file(path)

    return path


# ============================================================
# OPEN FILE
# ============================================================

def open_file(
    path: str | os.PathLike[str],
    mode: str = "r",
    *args,
    **kwargs,
) -> BinaryIO:

    path = ensure_parent(path)

    return path.open(
        mode,
        *args,
        **kwargs,
    )


# ============================================================
# STARTUP
# ============================================================

ensure_storage_dirs()


__all__ = [
    "STORAGE_BACKEND",
    "STORAGE_ROOT",
    "BASE_DATA_DIR",
    "GROUPS_DIR",
    "FINAL_DIR",
    "COMPARISON_DIR",
    "SCANX_DIR",
    "SESSION_DIR",
    "ensure_storage_dirs",
    "storage_path",
    "data_path",
    "scanx_path",
    "session_path",
    "ensure_parent",
    "file_exists",
    "list_files",
    "read_text",
    "write_text",
    "read_bytes",
    "write_bytes",
    "open_file",
    "upload_file",
    "delete_file",
]