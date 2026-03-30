"""Container lifecycle commands: start, stop, restart, rebuild, status, attach."""

import os
from pathlib import Path

import typer

from cli.lib.config import (
    ensure_config_dirs,
    ensure_env,
    ensure_mounts_config,
    get_active_profile,
    get_active_project_name,
    get_default_tool,
    list_available_tools,
    load_mounts,
)
from cli.lib.docker import (
    attach_to_sandbox,
    get_status,
    is_running,
    rebuild_containers,
    start_containers,
    stop_containers,
)
from cli.lib.firewall import merge_tool_domains
from cli.lib.mcp import get_enabled_servers, get_mcp_domains, write_mcp_config
from cli.lib.mounts import setup_mounts, unmount_all
from cli.commands.tools import auto_install_tools
from cli.lib.paths import get_data_dir
from cli.lib.platform import check_docker, is_quiet
from cli.lib.scaffold import is_scaffolded, scaffold
from cli.lib.secrets import get_secrets_for_container


def start(attach: bool = True, env_profile: str = "", workspace: str | None = None, offline: bool = False) -> None:
    """Start the sandbox environment."""
    docker_err = check_docker()
    if docker_err:
        typer.echo(typer.style(f"error: {docker_err}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    if not is_scaffolded():
        data_dir = scaffold()
        typer.echo(f"First run: initialized config at {data_dir}")

    if env_profile:
        os.environ["SANDBOX_ENV"] = env_profile

    env = ensure_env()
    if offline or env.get("SANDBOX_OFFLINE_MODE", "").lower() == "true":
        offline = True
        if not is_quiet():
            typer.echo("Offline mode enabled.")

    workspace_path = Path(workspace or ".").resolve()
    if not workspace_path.is_dir():
        typer.echo(typer.style(f"error: Workspace directory not found: {workspace_path}",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    os.environ["SANDBOX_WORKSPACE_DIR"] = str(workspace_path)
    if not is_quiet():
        typer.echo(f"Workspace: {workspace_path}")

    if not is_quiet():
        typer.echo("Initializing configuration...")
    ensure_config_dirs()
    ensure_mounts_config()

    profile = get_active_profile()
    if profile:
        typer.echo(f"Using profile: {profile}")

    default_tool = get_default_tool()
    if default_tool:
        domains = default_tool.get("firewall", {}).get("domains", [])
        if domains:
            typer.echo(f"Merging firewall domains for {default_tool['name']}...")
            merge_tool_domains(domains)

    mcp_servers = get_enabled_servers()
    if mcp_servers:
        typer.echo(f"Configuring {len(mcp_servers)} MCP server(s)...")
        mcp_domains = get_mcp_domains()
        if mcp_domains:
            merge_tool_domains(mcp_domains)
        config_path = write_mcp_config()
        if config_path:
            typer.echo(f"  MCP config written to {config_path}")

    mounts = load_mounts()
    if mounts:
        typer.echo("Setting up mounts...")
        results = setup_mounts(workspace=workspace_path)
        for r in results:
            if r["ok"]:
                typer.echo(f"  {r['name']}: mounted")
            else:
                typer.echo(typer.style(f"  {r['name']}: {r['error']}",
                                       fg=typer.colors.YELLOW), err=True)

    container_secrets = get_secrets_for_container()
    if container_secrets:
        typer.echo(f"Injecting {len(container_secrets)} secret(s) into container...")

    typer.echo("Starting containers...")
    start_containers(build=not is_running("firewall"), secrets=container_secrets, offline=offline)

    auto_results = auto_install_tools()
    for r in auto_results:
        if r["ok"]:
            typer.echo(f"  Auto-installed {r['name']}")
        else:
            typer.echo(typer.style(f"  Failed to auto-install {r['name']}: {r['error']}",
                                   fg=typer.colors.YELLOW), err=True)

    typer.echo(typer.style("Sandbox is running.", fg=typer.colors.GREEN))

    if attach:
        typer.echo("Attaching to sandbox shell...")
        attach_to_sandbox()


def stop() -> None:
    """Stop all sandbox containers."""
    typer.echo("Stopping sandbox containers...")
    stop_containers()

    mounts = load_mounts()
    if mounts:
        typer.echo("Unmounting remote filesystems...")
        unmount_all()

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
    mounts = load_mounts()
    project = get_active_project_name()

    if project:
        typer.echo(typer.style(f"Project: {project}", bold=True))
        typer.echo("")

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

    if mounts:
        typer.echo("")
        typer.echo(typer.style("Mounts:", bold=True))
        for mount in mounts:
            typer.echo(f"  {mount.get('name', 'unnamed')}: {mount.get('remote', '?')} -> {mount.get('local', '?')} ({mount.get('type', 'rclone')})")


def attach() -> None:
    """Attach to the sandbox shell."""
    if not is_running("sandbox"):
        typer.echo(typer.style("error: Sandbox is not running. Run 'sandbox start' first.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    attach_to_sandbox()


def exec_cmd(command: list[str]) -> None:
    """Execute a command inside the sandbox container."""
    if not is_running("sandbox"):
        typer.echo(typer.style("error: Sandbox is not running. Run 'sandbox start' first.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    from cli.lib.docker import exec_in_sandbox
    exit_code, output = exec_in_sandbox(command)
    if output:
        typer.echo(output, nl=False)
    raise typer.Exit(exit_code)
