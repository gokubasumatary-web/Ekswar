"""Project settings: paths, API keys and external tools.

Keys are read from the environment (loaded from `.env`). They are never printed.
Run `python -m src.config` to check the environment.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "outputs"

GNANI_BASE_URL = "https://api.vachana.ai"  # docs.gnani.ai, verified 2026-11-06

SUPPORTED_TARGETS = {"ta-IN": "Tamil", "bn-IN": "Bengali", "mr-IN": "Marathi"}
SOURCE_LANGUAGE = "hi-IN"

load_dotenv(ROOT / ".env")


class ConfigError(RuntimeError):
    """A required setting or tool is missing."""


def get_setting(name: str) -> str:
    """Return a required setting from the environment, or raise a clear error.

    The error message names the variable but never contains its value.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set. Add it to {ROOT / '.env'} (see .env.example).")
    return value


def find_tool(name: str) -> str:
    """Return the full path of a command-line tool such as ffmpeg."""
    path = shutil.which(name)
    if not path:
        raise ConfigError(
            f"'{name}' was not found on PATH. Install ffmpeg, then open a new terminal."
        )
    return path


def check_environment() -> list[tuple[str, bool, str]]:
    """Return (item, ok, detail) rows describing the environment. Never includes secrets."""
    rows: list[tuple[str, bool, str]] = []
    ok_py = sys.version_info >= (3, 11)
    rows.append(("Python", ok_py, sys.version.split()[0]))
    for tool in ("ffmpeg", "ffprobe"):
        try:
            rows.append((tool, True, find_tool(tool)))
        except ConfigError as e:
            rows.append((tool, False, str(e)))
    for key in ("GNANI_API_KEY", "GEMINI_API_KEY", "GEMINI_MODEL"):
        try:
            get_setting(key)
            detail = "set" if key.endswith("KEY") else os.environ[key].strip()
            rows.append((key, True, detail))
        except ConfigError:
            rows.append((key, False, "missing"))
    return rows


if __name__ == "__main__":
    all_ok = True
    for item, ok, detail in check_environment():
        all_ok &= ok
        print(f"[{'OK ' if ok else 'MISSING'}] {item:15} {detail}")
    sys.exit(0 if all_ok else 1)
