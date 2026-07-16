"""Application data directory resolution.

Runtime state (SQLite DB, refreshed item database, logs) lives outside the
repo in the platform-appropriate app-data directory. Override with the
``CSFLOAT_TRACKER_DATA`` environment variable (used by Docker and tests).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "csfloat-tracker"


def bundle_dir() -> Path | None:
    """Extraction dir of a PyInstaller bundle (sys._MEIPASS), else None."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return None


def data_dir() -> Path:
    override = os.environ.get("CSFLOAT_TRACKER_DATA")
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        path = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library/Application Support" / APP_NAME
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "tracker.db"


def itemdb_path() -> Path:
    return data_dir() / "cs2_items.json"


def bundled_itemdb_path() -> Path:
    """The baseline item database shipped with the bundle/package/repo."""
    frozen = bundle_dir()
    if frozen and (frozen / "data" / "cs2_items.json").exists():
        return frozen / "data" / "cs2_items.json"
    packaged = Path(__file__).resolve().parent.parent / "data" / "cs2_items.json"
    if packaged.exists():
        return packaged
    # Repo checkout layout: <root>/data/cs2_items.json
    return Path(__file__).resolve().parents[3] / "data" / "cs2_items.json"
