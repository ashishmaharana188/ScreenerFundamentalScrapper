"""
Centralized application storage.

LOCAL
-----
STORAGE_BACKEND=local

Files remain on the local filesystem:
    scanx_data/
    screener_data/
    session/

SUPABASE
--------
STORAGE_BACKEND=supabase

Files are persisted in a private Supabase Storage bucket.
A small local cache is used because the existing application expects
normal pathlib.Path objects.

IMPORTANT
---------
The current Supabase API uses opaque `sb_secret_...` keys for server-side
access. Those keys are NOT JWTs. This module therefore talks directly to
the Supabase Storage HTTP API and sends the secret key in the `apikey`
header only. It deliberately does NOT send:

    Authorization: Bearer sb_secret_...

because Supabase documents that opaque publishable/secret keys are not JWTs
and should not be sent as Bearer tokens.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

import requests


# ============================================================
# PROJECT / STORAGE CONFIGURATION
# ============================================================

MODULE_DIR = Path(__file__).resolve().parent

if MODULE_DIR.name.casefold() == "scripts":
    PROJECT_ROOT = MODULE_DIR.parent
else:
    PROJECT_ROOT = MODULE_DIR


STORAGE_BACKEND = (
    os.getenv("STORAGE_BACKEND", "local")
    .strip()
    .casefold()
)


# ============================================================
# STORAGE ROOT
# ============================================================

# Local mode keeps the existing project-root directory structure.
# Supabase mode may use a temporary cache directory. This is ephemeral
# by design because the persistent copy lives in Supabase.

if STORAGE_BACKEND == "supabase":
    _supabase_cache = os.getenv(
        "SUPABASE_CACHE_DIR",
        "/tmp/screener_storage",
    ).strip()

    STORAGE_ROOT = (
        Path(_supabase_cache).expanduser().resolve()
        if _supabase_cache
        else Path("/tmp/screener_storage").resolve()
    )
else:
    _env_root = os.getenv("APP_STORAGE_ROOT", "").strip()

    if _env_root:
        STORAGE_ROOT = (
            Path(_env_root)
            .expanduser()
            .resolve()
        )
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

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    "",
).strip().rstrip("/")

SUPABASE_SECRET_KEY = os.getenv(
    "SUPABASE_SECRET_KEY",
    "",
).strip()

SUPABASE_BUCKET = os.getenv(
    "SUPABASE_BUCKET",
    "screener-data",
).strip()

SUPABASE_STORAGE_URL = (
    f"{SUPABASE_URL}/storage/v1"
    if SUPABASE_URL
    else ""
)


# ============================================================
# HTTP SESSION
# ============================================================

_http = None


def _get_http() -> requests.Session:
    """Return one reusable HTTP session for Supabase requests."""

    global _http

    if _http is None:
        _http = requests.Session()
        _http.headers.update(
            {
                "User-Agent": "ScreenerFundamentalScrapper/1.0",
            }
        )

    return _http


def _require_supabase_config() -> None:
    """Validate Supabase configuration only when cloud storage is used."""

    if not SUPABASE_URL:
        raise RuntimeError(
            "SUPABASE_URL is required when STORAGE_BACKEND=supabase."
        )

    if not SUPABASE_SECRET_KEY:
        raise RuntimeError(
            "SUPABASE_SECRET_KEY is required when STORAGE_BACKEND=supabase."
        )

    if not SUPABASE_BUCKET:
        raise RuntimeError(
            "SUPABASE_BUCKET cannot be empty."
        )


def _supabase_headers(
    content_type: str | None = None,
) -> dict[str, str]:
    """
    Build headers for Supabase Storage API calls.

    New `sb_secret_...` keys are opaque API keys, not JWTs. The key is
    therefore sent via `apikey` and NOT via an Authorization Bearer header.
    """

    _require_supabase_config()

    headers = {
        "apikey": SUPABASE_SECRET_KEY,
    }

    if content_type:
        headers["Content-Type"] = content_type

    return headers


# ============================================================
# DIRECTORY INITIALIZATION
# ============================================================

def ensure_storage_dirs() -> None:
    """Create local directories used by the application/cache."""

    for directory in STORAGE_DIRECTORIES:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


# ============================================================
# PATH HELPERS
# ============================================================

def storage_path(*parts: str | os.PathLike[str]) -> Path:
    return STORAGE_ROOT.joinpath(*parts)


def data_path(*parts: str | os.PathLike[str]) -> Path:
    return BASE_DATA_DIR.joinpath(*parts)


def scanx_path(*parts: str | os.PathLike[str]) -> Path:
    return SCANX_DIR.joinpath(*parts)


def session_path(*parts: str | os.PathLike[str]) -> Path:
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
# REMOTE PATH MAPPING
# ============================================================

def _remote_key(
    path: str | os.PathLike[str],
) -> str:
    """
    Convert an application Path into a Supabase object path.

    Example:
        /tmp/screener_storage/scanx_data/example.csv
        -> scanx_data/example.csv
    """

    path = Path(path).resolve()

    try:
        relative = path.relative_to(STORAGE_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(
            f"Path is outside storage root: {path}"
        ) from exc

    return relative.as_posix()


def _object_url(remote_key: str) -> str:
    """Return the Storage API URL for one object path."""

    encoded_bucket = quote(
        SUPABASE_BUCKET,
        safe="",
    )

    encoded_key = quote(
        remote_key.lstrip("/"),
        safe="/",
    )

    return (
        f"{SUPABASE_STORAGE_URL}/object/"
        f"{encoded_bucket}/{encoded_key}"
    )


def _list_url() -> str:
    encoded_bucket = quote(
        SUPABASE_BUCKET,
        safe="",
    )

    return (
        f"{SUPABASE_STORAGE_URL}/object/list/"
        f"{encoded_bucket}"
    )


def _delete_url() -> str:
    encoded_bucket = quote(
        SUPABASE_BUCKET,
        safe="",
    )

    return (
        f"{SUPABASE_STORAGE_URL}/object/"
        f"{encoded_bucket}"
    )


# ============================================================
# ERROR HANDLING
# ============================================================

def _raise_supabase_error(
    response: requests.Response,
    action: str,
) -> None:
    """Raise a useful error without exposing the secret key."""

    message = response.text.strip()

    if len(message) > 500:
        message = message[:500]

    raise RuntimeError(
        f"Supabase {action} failed "
        f"(HTTP {response.status_code}): {message}"
    )


# ============================================================
# DOWNLOAD
# ============================================================

def _download_remote_file(
    path: Path,
) -> Path:
    """Download one Supabase object into the local cache."""

    if STORAGE_BACKEND != "supabase":
        return path

    remote_key = _remote_key(path)
    url = _object_url(remote_key)

    try:
        response = _get_http().get(
            url,
            headers=_supabase_headers(),
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not download Supabase file: {remote_key}"
        ) from exc

    if not response.ok:
        _raise_supabase_error(
            response,
            f"download of {remote_key}",
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(response.content)

    return path


# ============================================================
# UPLOAD
# ============================================================

def upload_file(
    path: str | os.PathLike[str],
) -> Path:
    """
    Persist a local file.

    LOCAL
        No remote action is performed.

    SUPABASE
        Uploads/replaces the file in the configured private bucket.
    """

    path = Path(path)

    if STORAGE_BACKEND != "supabase":
        return path

    if not path.is_file():
        raise FileNotFoundError(
            f"Cannot upload missing file: {path}"
        )

    remote_key = _remote_key(path)
    url = _object_url(remote_key)

    content_type = (
        mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )

    headers = _supabase_headers(
        content_type=content_type,
    )

    headers["x-upsert"] = "true"

    try:
        with path.open("rb") as file:
            response = _get_http().post(
                url,
                headers=headers,
                data=file,
                timeout=120,
            )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not upload Supabase file: {remote_key}"
        ) from exc

    if not response.ok:
        _raise_supabase_error(
            response,
            f"upload of {remote_key}",
        )

    return path


# ============================================================
# DELETE
# ============================================================

def delete_file(
    path: str | os.PathLike[str],
) -> None:
    """
    Delete one file from the active backend.

    LOCAL
        Removes the local file.

    SUPABASE
        Removes the remote object, then removes its local cache copy.
    """

    path = Path(path)

    if STORAGE_BACKEND != "supabase":
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Could not delete local file: {path}"
            ) from exc
        return

    remote_key = _remote_key(path)

    try:
        response = _get_http().delete(
            _delete_url(),
            headers=_supabase_headers(
                content_type="application/json",
            ),
            json={
                "prefixes": [remote_key],
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not delete Supabase file: {remote_key}"
        ) from exc

    if not response.ok:
        _raise_supabase_error(
            response,
            f"deletion of {remote_key}",
        )

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
    """Check whether a file exists locally or in Supabase."""

    path = Path(path)

    if path.is_file():
        return True

    if STORAGE_BACKEND != "supabase":
        return False

    remote_key = _remote_key(path)
    parent = str(Path(remote_key).parent).replace("\\", "/")
    filename = Path(remote_key).name

    try:
        response = _get_http().post(
            _list_url(),
            headers=_supabase_headers(
                content_type="application/json",
            ),
            json={
                "prefix": (
                    "" if parent in ("", ".") else f"{parent}/"
                ),
                "limit": 100,
                "offset": 0,
                "search": filename,
                "sortBy": {
                    "column": "name",
                    "order": "asc",
                },
            },
            timeout=60,
        )
    except requests.RequestException:
        return False

    if not response.ok:
        return False

    try:
        items = response.json()
    except ValueError:
        return False

    if not isinstance(items, list):
        return False

    return any(
        isinstance(item, dict)
        and str(item.get("name") or "") == filename
        for item in items
    )


# ============================================================
# LIST FILES
# ============================================================

def list_files(
    directory: str | os.PathLike[str],
    pattern: str = "*",
) -> list[Path]:
    """
    List files in a local directory or Supabase prefix.

    In Supabase mode, each discovered file is downloaded into the local
    cache and returned as a normal Path object.
    """

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
            key=lambda path: path.name.casefold(),
        )

    remote_directory = _remote_key(directory)

    try:
        response = _get_http().post(
            _list_url(),
            headers=_supabase_headers(
                content_type="application/json",
            ),
            json={
                "prefix": (
                    "" if remote_directory in ("", ".")
                    else f"{remote_directory}/"
                ),
                "limit": 1000,
                "offset": 0,
                "sortBy": {
                    "column": "name",
                    "order": "asc",
                },
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not list Supabase directory: {remote_directory}"
        ) from exc

    if not response.ok:
        _raise_supabase_error(
            response,
            f"listing of {remote_directory}",
        )

    try:
        items = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Could not parse Supabase directory response: "
            f"{remote_directory}"
        ) from exc

    if not isinstance(items, list):
        raise RuntimeError(
            f"Unexpected Supabase directory response: "
            f"{remote_directory}"
        )

    results: list[Path] = []

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

        # list() can return folders as well as objects. Folder entries do
        # not carry an object id in the response used by this API.
        if item.get("id") is None:
            continue

        local_path = directory / name

        if not local_path.match(pattern):
            continue

        _download_remote_file(local_path)
        results.append(local_path)

    return sorted(
        results,
        key=lambda path: path.name.casefold(),
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
    """
    Open a normal local/cache file.

    Existing application code that uses open_file() for writes should call
    upload_file() after the write is complete when running in Supabase mode.
    """

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
    "SUPABASE_URL",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_BUCKET",
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
