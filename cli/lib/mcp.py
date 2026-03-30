"""MCP server management: definitions, config generation, and validation."""

import json
from pathlib import Path

import yaml

from cli.lib.config import get_config_root, get_default_tool, get_project_root, load_env, load_tool_definition

MCP_LOG_WRAPPER = "/usr/local/bin/mcp-log-wrapper"


def _mcp_dir() -> Path:
    return get_config_root() / "mcp"


def list_mcp_servers() -> list[dict]:
    """List all MCP server definitions."""
    if not _mcp_dir().exists():
        return []

    servers = []
    for f in sorted(_mcp_dir().glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text())
            if data:
                servers.append(data)
        except yaml.YAMLError:
            continue
    return servers


def load_mcp_server(name: str) -> dict | None:
    """Load a specific MCP server definition."""
    server_file = _mcp_dir() / f"{name}.yaml"
    if not server_file.exists():
        return None
    return yaml.safe_load(server_file.read_text())


def get_enabled_servers() -> list[dict]:
    """Get only enabled MCP server definitions."""
    return [s for s in list_mcp_servers() if s.get("enabled", True)]


def set_server_enabled(name: str, enabled: bool) -> bool:
    """Enable or disable an MCP server. Returns True if changed."""
    server_file = _mcp_dir() / f"{name}.yaml"
    if not server_file.exists():
        return False

    data = yaml.safe_load(server_file.read_text())
    if not data:
        return False

    data["enabled"] = enabled
    server_file.write_text(yaml.dump(data, default_flow_style=False))
    return True


def generate_mcp_config(tool_name: str | None = None) -> dict:
    """Generate mcp-config.json content with logging wrapper around each server.

    The wrapper intercepts all MCP communication for automatic logging
    with session correlation. When permission enforcement is enabled,
    the wrapper validates tool call arguments against the server's
    permission model.
    """
    env = load_env()
    enforce = env.get("SANDBOX_ENFORCE_MCP_PERMISSIONS", "").lower() == "true"

    servers = get_enabled_servers()
    config = {"mcpServers": {}}

    for server in servers:
        name = server.get("name", "")
        command = server.get("command", "")
        args = server.get("args", [])

        if not name or not command:
            continue

        server_env = dict(server.get("env", {}))

        if enforce:
            permissions = {
                "allowed_paths": server.get("allowed_paths", []),
                "blocked_patterns": server.get("validation", {}).get("blocked_patterns", []),
                "permissions": server.get("permissions", []),
            }
            server_env["MCP_PERMISSIONS"] = json.dumps(permissions)
            server_env["MCP_ENFORCE"] = "true"

        config["mcpServers"][name] = {
            "command": MCP_LOG_WRAPPER,
            "args": [name, command] + args,
            "env": server_env,
        }

    return config


def write_mcp_config(tool_name: str | None = None) -> Path | None:
    """Generate and write mcp-config.json to the active tool's config path.

    Returns the path written to, or None if no tool has mcp.config_path.
    """
    tool = load_tool_definition(tool_name) if tool_name else get_default_tool()
    if not tool:
        return None

    config_path_str = tool.get("mcp", {}).get("config_path")
    if not config_path_str:
        return None

    config = generate_mcp_config(tool.get("name"))
    config_path = Path(config_path_str)

    output = get_project_root() / "mcp-config.json"
    output.write_text(json.dumps(config, indent=2) + "\n")

    return output


def get_mcp_domains() -> list[str]:
    """Collect all firewall domains required by enabled MCP servers."""
    domains = []
    for server in get_enabled_servers():
        for d in server.get("firewall", {}).get("domains", []):
            if d not in domains:
                domains.append(d)
    return domains
