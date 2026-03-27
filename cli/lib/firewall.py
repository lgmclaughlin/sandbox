"""Firewall management operations."""

import json
import re
from pathlib import Path

import yaml

from cli.lib.paths import get_data_dir


def _whitelist_file() -> Path:
    return get_data_dir() / "docker" / "firewall" / "whitelist.txt"


def _profiles_dir() -> Path:
    return get_data_dir() / "config" / "firewall" / "profiles"


DOMAIN_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


def validate_domain(domain: str) -> bool:
    """Validate domain format."""
    return bool(DOMAIN_PATTERN.match(domain))


def read_whitelist() -> list[str]:
    """Read domains from whitelist file."""
    if not _whitelist_file().exists():
        return []

    domains = []
    for line in _whitelist_file().read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            domains.append(line)
    return domains


def write_whitelist(domains: list[str]) -> None:
    """Write domains to whitelist file."""
    content = "\n".join(domains) + "\n"
    _whitelist_file().write_text(content)


def add_domain(domain: str) -> bool:
    """Add domain to whitelist. Returns True if added, False if already exists."""
    domains = read_whitelist()
    if domain in domains:
        return False
    domains.append(domain)
    write_whitelist(domains)
    return True


def remove_domain(domain: str) -> bool:
    """Remove domain from whitelist. Returns True if removed, False if not found."""
    domains = read_whitelist()
    if domain not in domains:
        return False
    domains.remove(domain)
    write_whitelist(domains)
    return True


def apply_rules() -> tuple[bool, str]:
    """Apply firewall rules in the firewall container. Returns (success, message)."""
    from cli.lib.docker import exec_in_firewall, _get_client, _get_container, _tar_single_file

    container = _get_container(_get_client(), "firewall")
    if not container or container.status != "running":
        return False, "Firewall container is not running"

    data = _whitelist_file().read_bytes()
    container.put_archive("/etc/firewall", _tar_single_file("whitelist.txt", data))

    exit_code, output = exec_in_firewall(["/usr/local/bin/firewall-apply.sh"])
    if exit_code != 0:
        return False, f"Firewall apply failed:\n{output}"

    return True, output


def merge_tool_domains(tool_domains: list[str]) -> None:
    """Merge tool-specific domains into whitelist."""
    domains = read_whitelist()
    for domain in tool_domains:
        if domain not in domains:
            domains.append(domain)
    write_whitelist(domains)


# --- Profiles ---

def list_profiles() -> list[dict]:
    """List available firewall profiles."""
    if not _profiles_dir().exists():
        return []

    profiles = []
    for f in sorted(_profiles_dir().glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text())
            if data:
                profiles.append(data)
        except yaml.YAMLError:
            continue
    return profiles


def load_profile(name: str) -> dict | None:
    """Load a firewall profile by name."""
    profile_file = _profiles_dir() / f"{name}.yaml"
    if not profile_file.exists():
        return None
    return yaml.safe_load(profile_file.read_text())


def apply_profile(name: str) -> tuple[bool, str]:
    """Apply a firewall profile. Replaces whitelist with profile domains + tool domains."""
    profile = load_profile(name)
    if not profile:
        return False, f"Profile '{name}' not found"

    profile_domains = profile.get("domains", [])

    from cli.lib.config import list_available_tools
    tool_domains = set()
    for tool in list_available_tools():
        for d in tool.get("firewall", {}).get("domains", []):
            tool_domains.add(d)

    merged = list(dict.fromkeys(profile_domains + sorted(tool_domains)))
    write_whitelist(merged)

    return True, f"Applied profile '{name}' ({len(merged)} domains)"


# --- Firewall logging ---

def read_firewall_logs(log_dir: Path, action: str = "all", lines: int = 50) -> list[dict]:
    """Read firewall log entries from the audit volume."""
    fw_log_dir = log_dir / "firewall"
    if not fw_log_dir.exists():
        return []

    entries = []
    for log_file in sorted(fw_log_dir.rglob("*.jsonl"), reverse=True):
        for line in reversed(log_file.read_text().splitlines()):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if action == "all" or entry.get("action") == action:
                    entries.append(entry)
                    if len(entries) >= lines:
                        return entries
            except json.JSONDecodeError:
                continue
    return entries
