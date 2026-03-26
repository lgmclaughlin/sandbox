"""Firewall management operations."""

import re
from pathlib import Path

WHITELIST_FILE = Path(__file__).parent.parent.parent / "docker" / "firewall" / "whitelist.txt"

# Simple domain validation pattern
DOMAIN_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


def validate_domain(domain: str) -> bool:
    """Validate domain format."""
    return bool(DOMAIN_PATTERN.match(domain))


def read_whitelist() -> list[str]:
    """Read domains from whitelist file."""
    if not WHITELIST_FILE.exists():
        return []

    domains = []
    for line in WHITELIST_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            domains.append(line)
    return domains


def write_whitelist(domains: list[str]) -> None:
    """Write domains to whitelist file."""
    content = "\n".join(domains) + "\n"
    WHITELIST_FILE.write_text(content)


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

    data = WHITELIST_FILE.read_bytes()
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
