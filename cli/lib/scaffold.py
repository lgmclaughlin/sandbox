"""First-run scaffolding: populate data directory from bundled templates."""

import shutil
from pathlib import Path

from cli.lib.paths import get_data_dir, get_package_data_dir


SCAFFOLD_DIRS = [
    "config/tools",
    "config/mcp",
    "config/firewall/profiles",
    "config/network",
    "docker/firewall",
    "docker/proxy",
    "logs/sessions",
    "logs/commands",
]

SCAFFOLD_FILES = {
    ".env.dist": ".env.dist",
    "config/tools/claude-code.yaml": "config/tools/claude-code.yaml",
    "config/tools/aider.yaml": "config/tools/aider.yaml",
    "config/tools/open-interpreter.yaml": "config/tools/open-interpreter.yaml",
    "config/mcp/filesystem.yaml": "config/mcp/filesystem.yaml",
    "config/mcp/fetch.yaml": "config/mcp/fetch.yaml",
    "config/mounts.yaml.example": "config/mounts.yaml.example",
    "config/firewall/profiles/dev.yaml": "config/firewall/profiles/dev.yaml",
    "config/firewall/profiles/restricted.yaml": "config/firewall/profiles/restricted.yaml",
    "config/network/inspection.yaml": "config/network/inspection.yaml",
    "config/network/dlp.yaml": "config/network/dlp.yaml",
    "docker/Dockerfile": "docker/Dockerfile",
    "docker/docker-compose.yml": "docker/docker-compose.yml",
    "docker/entrypoint.sh": "docker/entrypoint.sh",
    "docker/session-wrapper.sh": "docker/session-wrapper.sh",
    "docker/mcp-log-wrapper.py": "docker/mcp-log-wrapper.py",
    "docker/firewall/Dockerfile_firewall": "docker/firewall/Dockerfile_firewall",
    "docker/firewall/firewall-init.sh": "docker/firewall/firewall-init.sh",
    "docker/firewall/firewall-apply.sh": "docker/firewall/firewall-apply.sh",
    "docker/firewall/firewall-log.sh": "docker/firewall/firewall-log.sh",
    "docker/firewall/entrypoint-firewall.sh": "docker/firewall/entrypoint-firewall.sh",
    "docker/firewall/ulogd.conf": "docker/firewall/ulogd.conf",
    "docker/firewall/whitelist.txt": "docker/firewall/whitelist.txt",
    "docker/proxy/addon.py": "docker/proxy/addon.py",
}


def is_scaffolded() -> bool:
    """Check if the data directory has been scaffolded."""
    data_dir = get_data_dir()
    return (data_dir / ".env.dist").exists() and (data_dir / "docker" / "docker-compose.yml").exists()


def scaffold(force: bool = False) -> Path:
    """Scaffold the data directory from bundled package data.

    Returns the data directory path.
    """
    data_dir = get_data_dir()
    pkg_dir = get_package_data_dir()

    if is_scaffolded() and not force:
        return data_dir

    for d in SCAFFOLD_DIRS:
        (data_dir / d).mkdir(parents=True, exist_ok=True)

    for src_rel, dst_rel in SCAFFOLD_FILES.items():
        src = pkg_dir / src_rel
        dst = data_dir / dst_rel

        if not src.exists():
            continue

        if dst.exists() and not force:
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    if not (data_dir / ".env").exists() and (data_dir / ".env.dist").exists():
        shutil.copy2(data_dir / ".env.dist", data_dir / ".env")

    return data_dir
