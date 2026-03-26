"""Configuration management: .env, mounts.yaml, tool definitions."""

import os
import shutil
import subprocess
import time
from pathlib import Path

import yaml
from dotenv import dotenv_values, set_key

# Project root (relative to this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Config paths
CONFIG_DIR = PROJECT_ROOT / "config"
MOUNTS_FILE = CONFIG_DIR / "mounts.yaml"
TOOLS_DIR = CONFIG_DIR / "tools"
ENV_FILE = PROJECT_ROOT / ".env"
ENV_DIST_FILE = PROJECT_ROOT / ".env.dist"

# Log paths
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"

from cli.lib.platform import PLATFORM


def get_log_dir() -> Path:
    """Get log directory from env or default."""
    env = load_env()
    log_dir = env.get("SANDBOX_LOG_DIR", "")
    if log_dir:
        path = Path(log_dir)
        return path if path.is_absolute() else PROJECT_ROOT / path
    return DEFAULT_LOG_DIR


def ensure_config_dirs() -> None:
    """Create config directories if they don't exist."""
    CONFIG_DIR.mkdir(exist_ok=True)
    TOOLS_DIR.mkdir(exist_ok=True)
    log_dir = get_log_dir()
    log_dir.mkdir(exist_ok=True)
    (log_dir / "sessions").mkdir(exist_ok=True)
    (log_dir / "commands").mkdir(exist_ok=True)


def ensure_env() -> dict[str, str]:
    """Ensure .env exists (copy from .env.dist if missing) and return values."""
    if not ENV_FILE.exists() and ENV_DIST_FILE.exists():
        shutil.copy2(ENV_DIST_FILE, ENV_FILE)

    env = load_env()

    if not env.get("TZ"):
        tz = detect_timezone()
        if tz:
            set_key(str(ENV_FILE), "TZ", tz)
            env["TZ"] = tz

    return env


def detect_timezone() -> str:
    """Detect timezone from host system (Linux, macOS, Windows)."""
    tz = os.environ.get("TZ")
    if tz:
        return tz

    if PLATFORM == "linux":
        localtime = Path("/etc/localtime")
        if localtime.is_symlink():
            target = str(localtime.resolve())
            if "zoneinfo/" in target:
                return target.split("zoneinfo/")[-1]

        timezone_file = Path("/etc/timezone")
        if timezone_file.exists():
            return timezone_file.read_text().strip()

    elif PLATFORM == "darwin":
        localtime = Path("/etc/localtime")
        if localtime.is_symlink():
            target = str(localtime.resolve())
            if "zoneinfo/" in target:
                return target.split("zoneinfo/")[-1]

    elif PLATFORM == "windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command", "(Get-TimeZone).Id"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return _windows_tz_to_iana(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return time.tzname[0]


def _windows_tz_to_iana(windows_tz: str) -> str:
    """Convert common Windows timezone names to IANA format."""
    mapping = {
        "Pacific Standard Time": "America/Los_Angeles",
        "Mountain Standard Time": "America/Denver",
        "Central Standard Time": "America/Chicago",
        "Eastern Standard Time": "America/New_York",
        "UTC": "UTC",
        "GMT Standard Time": "Europe/London",
        "Central European Standard Time": "Europe/Berlin",
        "Tokyo Standard Time": "Asia/Tokyo",
    }
    return mapping.get(windows_tz, windows_tz)


def load_env() -> dict[str, str]:
    """Load environment variables from .env file."""
    if not ENV_FILE.exists():
        return {}
    values = dotenv_values(ENV_FILE)
    return {k: v for k, v in values.items() if v is not None}


def load_mounts() -> list[dict]:
    """Load mount definitions from mounts.yaml. Returns empty list if missing."""
    if not MOUNTS_FILE.exists():
        return []

    content = MOUNTS_FILE.read_text().strip()
    if not content:
        return []

    data = yaml.safe_load(content)
    if not data:
        return []

    return data.get("mounts", []) if isinstance(data, dict) else data


def load_tool_definition(name: str) -> dict | None:
    """Load a tool definition by name."""
    tool_file = TOOLS_DIR / f"{name}.yaml"
    if not tool_file.exists():
        return None
    return yaml.safe_load(tool_file.read_text())


def list_available_tools() -> list[dict]:
    """List all available tool definitions with metadata."""
    tools = []
    if not TOOLS_DIR.exists():
        return tools

    for tool_file in sorted(TOOLS_DIR.glob("*.yaml")):
        definition = yaml.safe_load(tool_file.read_text())
        if definition:
            tools.append(definition)
    return tools


def get_default_tool() -> dict | None:
    """Find the tool definition marked as default."""
    for tool in list_available_tools():
        if tool.get("default"):
            return tool
    return None
