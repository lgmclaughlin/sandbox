"""MCP server management commands."""

import json
from pathlib import Path

import typer

from cli.lib.config import get_log_dir
from cli.lib.mcp import (
    get_enabled_servers,
    list_mcp_servers,
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


def _regenerate_config() -> None:
    """Regenerate mcp-config.json after enable/disable."""
    path = write_mcp_config()
    if path:
        typer.echo(f"Updated MCP config at {path}")
