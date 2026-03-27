"""OS-specific data directory resolution."""

import os
from pathlib import Path

from cli.lib.platform import PLATFORM, IS_WINDOWS, IS_MACOS


def get_data_dir() -> Path:
    """Resolve the sandbox data directory.

    Resolution order:
    1. SANDBOX_DATA_DIR env var
    2. OS-specific standard location

    OS defaults:
    - Linux: $XDG_DATA_HOME/sandbox or ~/.local/share/sandbox
    - macOS: ~/Library/Application Support/sandbox
    - Windows: %APPDATA%/sandbox
    """
    from_env = os.environ.get("SANDBOX_DATA_DIR", "")
    if from_env:
        return Path(from_env)

    if IS_WINDOWS:
        base = os.environ.get("APPDATA", "")
        if base:
            return Path(base) / "sandbox"
        return Path.home() / "AppData" / "Roaming" / "sandbox"

    if IS_MACOS:
        return Path.home() / "Library" / "Application Support" / "sandbox"

    # Linux (XDG)
    xdg = os.environ.get("XDG_DATA_HOME", "")
    if xdg:
        return Path(xdg) / "sandbox"
    return Path.home() / ".local" / "share" / "sandbox"


def get_package_data_dir() -> Path:
    """Get the directory containing bundled package data (templates).

    Points to cli/data/ which contains docker/, config/, .env.dist.
    Works for both editable and non-editable installs since the data
    files are inside the cli package itself.
    """
    return Path(__file__).parent.parent / "data"


def ensure_data_dir() -> Path:
    """Ensure the data directory exists with required subdirectories."""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
