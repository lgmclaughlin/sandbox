"""MCP server management commands."""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

import typer
import yaml

from cli.lib.config import get_log_dir
from cli.lib.mcp import (
    _mcp_dir,
    get_enabled_servers,
    list_mcp_servers,
    load_mcp_server,
    set_server_enabled,
    write_mcp_config,
)

app = typer.Typer(no_args_is_help=True)


@app.command(name="list")
def list_servers() -> None:
    """List available MCP servers with permissions."""
    servers = list_mcp_servers()
    if not servers:
        typer.echo("No MCP server definitions found in config/mcp/.")
        return

    for server in servers:
        enabled = server.get("enabled", True)
        status = typer.style("enabled", fg=typer.colors.GREEN) if enabled else typer.style("disabled", fg=typer.colors.RED)
        typer.echo(f"  {server['name']}: {server.get('description', '')} [{status}]")

        permissions = server.get("permissions", [])
        if permissions:
            perms = ", ".join(
                f"{k}: {v}" for p in permissions for k, v in p.items()
            )
            typer.echo(f"    permissions: {perms}")


@app.command()
def enable(
    name: str = typer.Argument(..., help="MCP server name to enable"),
) -> None:
    """Enable an MCP server."""
    if set_server_enabled(name, True):
        typer.echo(f"MCP server '{name}' enabled.")
        _regenerate_config()
    else:
        typer.echo(typer.style(f"error: MCP server '{name}' not found.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)


@app.command()
def disable(
    name: str = typer.Argument(..., help="MCP server name to disable"),
) -> None:
    """Disable an MCP server."""
    if set_server_enabled(name, False):
        typer.echo(f"MCP server '{name}' disabled.")
        _regenerate_config()
    else:
        typer.echo(typer.style(f"error: MCP server '{name}' not found.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)


@app.command(name="logs")
def mcp_logs(
    server: str = typer.Option("", "--server", "-s", help="Filter by server name"),
    lines: int = typer.Option(20, "--lines", "-n", help="Number of entries to show"),
) -> None:
    """View MCP request/response trace."""
    log_dir = get_log_dir() / "mcp"
    if not log_dir.exists():
        typer.echo("No MCP logs found.")
        return

    entries = []
    for log_file in sorted(log_dir.rglob("*.jsonl"), reverse=True):
        for line in reversed(log_file.read_text().splitlines()):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if server and entry.get("server") != server:
                    continue
                entries.append(entry)
                if len(entries) >= lines:
                    break
            except json.JSONDecodeError:
                continue
        if len(entries) >= lines:
            break

    if not entries:
        typer.echo("No MCP log entries found.")
        return

    for entry in reversed(entries):
        ts = entry.get("timestamp", "?")
        srv = entry.get("server", "?")
        direction = entry.get("direction", "?")
        method = entry.get("method", "")
        tool = entry.get("tool", "")

        if direction == "lifecycle":
            typer.echo(f"  [{ts}] {srv} {typer.style(direction, bold=True)}")
        else:
            color = typer.colors.BLUE if direction == "request" else typer.colors.GREEN
            dir_styled = typer.style(direction, fg=color)
            detail = method or tool or f"{entry.get('size_bytes', 0)}b"
            typer.echo(f"  [{ts}] {srv} {dir_styled} {detail}")


@app.command()
def add(
    name: str = typer.Argument(..., help="MCP server name"),
    command: str = typer.Option(..., help="Command to run the server"),
    args: Optional[str] = typer.Option(None, help="Comma-separated args"),
    permissions: Optional[str] = typer.Option(None, help="Permissions (e.g., filesystem:read,network:none)"),
    allowed_paths: Optional[str] = typer.Option(None, "--allowed-paths", help="Comma-separated allowed paths"),
    domains: Optional[str] = typer.Option(None, help="Comma-separated firewall domains"),
) -> None:
    """Create a new MCP server definition."""
    mcp_dir = _mcp_dir()
    server_file = mcp_dir / f"{name}.yaml"
    if server_file.exists():
        typer.echo(typer.style(f"error: MCP server '{name}' already exists.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    definition: dict = {
        "name": name,
        "description": "",
        "enabled": False,
        "command": command,
        "args": args.split(",") if args else [],
        "permissions": [],
        "allowed_paths": allowed_paths.split(",") if allowed_paths else [],
        "validation": {"blocked_patterns": []},
        "firewall": {"domains": domains.split(",") if domains else []},
        "env": {},
    }

    if permissions:
        for perm in permissions.split(","):
            if ":" in perm:
                k, v = perm.split(":", 1)
                definition["permissions"].append({k.strip(): v.strip()})

    mcp_dir.mkdir(parents=True, exist_ok=True)
    server_file.write_text(yaml.dump(definition, default_flow_style=False))
    typer.echo(f"Created MCP server definition: {server_file}")
    typer.echo(f"  Enable with: sandbox mcp enable {name}")


@app.command()
def edit(
    name: str = typer.Argument(..., help="MCP server name to edit"),
) -> None:
    """Open an MCP server definition in editor."""
    server_file = _mcp_dir() / f"{name}.yaml"
    if not server_file.exists():
        typer.echo(typer.style(f"error: MCP server '{name}' not found.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(server_file)])


@app.command()
def show(
    name: str = typer.Argument(..., help="MCP server name to display"),
) -> None:
    """Display full MCP server definition."""
    definition = load_mcp_server(name)
    if not definition:
        typer.echo(typer.style(f"error: MCP server '{name}' not found.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    typer.echo(yaml.dump(definition, default_flow_style=False).rstrip())


def _regenerate_config() -> None:
    """Regenerate mcp-config.json after enable/disable."""
    path = write_mcp_config()
    if path:
        typer.echo(f"Updated MCP config at {path}")
