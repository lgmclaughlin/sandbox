"""Container lifecycle commands: start, stop, restart, rebuild, status, attach."""

import typer

from cli.lib.config import ensure_config_dirs, ensure_env, list_available_tools, get_default_tool
from cli.lib.docker import (
    attach_to_sandbox,
    get_status,
    is_running,
    rebuild_containers,
    start_containers,
    stop_containers,
)
from cli.lib.firewall import merge_tool_domains
from cli.lib.platform import check_docker


def start(attach: bool = True) -> None:
    """Start the sandbox environment."""
    docker_err = check_docker()
    if docker_err:
        typer.echo(typer.style(f"error: {docker_err}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    typer.echo("Initializing configuration...")
    env = ensure_env()
    ensure_config_dirs()

    default_tool = get_default_tool()
    if default_tool:
        domains = default_tool.get("firewall", {}).get("domains", [])
        if domains:
            typer.echo(f"Merging firewall domains for {default_tool['name']}...")
            merge_tool_domains(domains)

    typer.echo("Starting containers...")
    start_containers(build=not is_running("firewall"))

    typer.echo(typer.style("Sandbox is running.", fg=typer.colors.GREEN))

    if attach:
        typer.echo("Attaching to sandbox shell...")
        attach_to_sandbox()


def stop() -> None:
    """Stop all sandbox containers."""
    typer.echo("Stopping sandbox containers...")
    stop_containers()
    typer.echo(typer.style("Sandbox stopped.", fg=typer.colors.GREEN))


def restart() -> None:
    """Restart the sandbox environment."""
    stop()
    start()


def rebuild() -> None:
    """Rebuild images and restart."""
    docker_err = check_docker()
    if docker_err:
        typer.echo(typer.style(f"error: {docker_err}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    typer.echo("Rebuilding sandbox images...")
    rebuild_containers()
    typer.echo(typer.style("Rebuild complete.", fg=typer.colors.GREEN))


def status() -> None:
    """Show container status."""
    docker_err = check_docker()
    if docker_err:
        typer.echo(typer.style(f"error: {docker_err}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    statuses = get_status()
    tools = list_available_tools()

    typer.echo(typer.style("Containers:", bold=True))
    for service, info in statuses.items():
        color = typer.colors.GREEN if info["status"] == "running" else typer.colors.RED
        status_str = typer.style(info["status"], fg=color)
        typer.echo(f"  {service:12s} {status_str:20s} [{info['id']}]")

    typer.echo("")
    typer.echo(typer.style("Tools:", bold=True))
    if tools:
        for tool in tools:
            default = " (default)" if tool.get("default") else ""
            typer.echo(f"  {tool['name']}{default}")
    else:
        typer.echo("  No tools configured")


def attach() -> None:
    """Attach to the sandbox shell."""
    if not is_running("sandbox"):
        typer.echo(typer.style("error: Sandbox is not running. Run 'sandbox start' first.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    attach_to_sandbox()
