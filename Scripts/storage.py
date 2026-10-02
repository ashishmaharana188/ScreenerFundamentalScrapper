"""
Centralized application storage.

Works in:
    Local development
        APP_STORAGE_ROOT unset -> project root

    Render
        APP_STORAGE_ROOT=/var/data -> Render persistent disk

This file may live either in the project root or in Scripts/.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO


MODULE_DIR = Path(__file__).resolve().parent

# Support either:
#   project_root/storage.py
# or:
#   project_root/Scripts/storage.py
if MODULE_DIR.name.lower() == "scripts":
    PROJECT_ROOT = MODULE_DIR.parent
else:
    PROJECT_ROOT = MODULE_DIR


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


def ensure_storage_dirs() -> None:
    """Create all application storage directories."""
    for directory in STORAGE_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


def storage_path(*parts: str | os.PathLike[str]) -> Path:
    return STORAGE_ROOT.joinpath(*parts)


def data_path(*parts: str | os.PathLike[str]) -> Path:
    return BASE_DATA_DIR.joinpath(*parts)


def scanx_path(*parts: str | os.PathLike[str]) -> Path:
    return SCANX_DIR.joinpath(*parts)


def session_path(*parts: str | os.PathLike[str]) -> Path:
    return SESSION_DIR.joinpath(*parts)


def ensure_parent(path: str | os.PathLike[str]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def file_exists(path: str | os.PathLike[str]) -> bool:
    return Path(path).is_file()


def list_files(
    directory: str | os.PathLike[str],
    pattern: str = "*",
) -> list[Path]:
    directory = Path(directory)

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


def read_text(
    path: str | os.PathLike[str],
    encoding: str = "utf-8",
) -> str:
    return Path(path).read_text(encoding=encoding)


def write_text(
    path: str | os.PathLike[str],
    content: str,
    encoding: str = "utf-8",
) -> Path:
    path = ensure_parent(path)
    path.write_text(content, encoding=encoding)
    return path


def read_bytes(path: str | os.PathLike[str]) -> bytes:
    return Path(path).read_bytes()


def write_bytes(
    path: str | os.PathLike[str],
    content: bytes,
) -> Path:
    path = ensure_parent(path)
    path.write_bytes(content)
    return path


def open_file(
    path: str | os.PathLike[str],
    mode: str = "r",
    *args,
    **kwargs,
) -> BinaryIO:
    path = ensure_parent(path)
    return path.open(mode, *args, **kwargs)


ensure_storage_dirs()


__all__ = [
    "MODULE_DIR",
    "PROJECT_ROOT",
    "STORAGE_ROOT",
    "BASE_DATA_DIR",
    "GROUPS_DIR",
    "FINAL_DIR",
    "COMPARISON_DIR",
    "SCANX_DIR",
    "SESSION_DIR",
    "STORAGE_DIRECTORIES",
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
]
