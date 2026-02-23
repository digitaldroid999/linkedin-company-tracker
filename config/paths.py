"""Path helpers for app resources (works when run directly or as frozen exe)."""

import sys
from pathlib import Path


def get_base_path() -> Path:
    """Return the base path for app resources (project root or PyInstaller temp dir)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent
