"""Main CLI entry point."""

import os
from typing import Optional

import click
import typer
from typer.core import TyperGroup

from cli import __version__
from cli.commands import config_cmd, firewall, lifecycle, logs, mcp, proxy, secrets, tools

COMMAND_ORDER = [
    "start", "stop", "restart", "rebuild", "status", "attach",
    "init", "projects",
    "tool", "mcp", "secrets", "fw", "proxy", "config", "logs",
    "check", "info", "update", "version",
]


class OrderedGroup(TyperGroup):
    def list_commands(self, ctx: click.Context) -> list[str]:
        commands = super().list_commands(ctx)
        ordered = [c for c in COMMAND_ORDER if c in commands]
        remaining = [c for c in commands if c not in ordered]
        return ordered + remaining


app = typer.Typer(
    name="sandbox",
    help="Secure AI development environment",
    no_args_is_help=True,
    add_completion=False,
    cls=OrderedGroup,
)


@app.callback()
def main_callback(
    project: Optional[str] = typer.Option(
        None, "--project", "-p", help="Project name to operate on",
        envvar="SANDBOX_PROJECT",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-essential output"),
) -> None:
    """Resolve active project and output settings before any command runs."""
    os.environ["SANDBOX_VERBOSE"] = "1" if verbose else ""
    os.environ["SANDBOX_QUIET"] = "1" if quiet else ""

    if project:
        from cli.lib.config import set_active_project
        from cli.lib.project import get_project_dir
        if not get_project_dir(project).exists():
            typer.echo(typer.style(
                f"error: Project '{project}' not found. Run 'sandbox init {project}' first.",
                fg=typer.colors.RED), err=True)
            raise typer.Exit(1)
        set_active_project(project)
    else:
        from cli.lib.project import get_active_project
        from cli.lib.config import set_active_project
        auto = get_active_project()
        if auto:
            set_active_project(auto)


# --- Lifecycle ---

LIFECYCLE = "Lifecycle"
PROJECTS = "Projects"
OBSERVE = "Observability"

@app.command(rich_help_panel=LIFECYCLE)
def start(
    workspace: Optional[str] = typer.Argument(None, help="Workspace directory to mount (default: current directory)"),
    attach: bool = typer.Option(True, "--attach/--no-attach", help="Attach to shell after start"),
    env: str = typer.Option("", "--env", "-e", help="Environment profile to use"),
    offline: bool = typer.Option(False, "--offline", help="Start without network-dependent operations"),
) -> None:
    """Start the sandbox environment."""
    lifecycle.start(attach=attach, env_profile=env, workspace=workspace, offline=offline)


@app.command(rich_help_panel=LIFECYCLE)
def stop() -> None:
    """Stop all sandbox containers."""
    lifecycle.stop()


@app.command(rich_help_panel=LIFECYCLE)
def restart() -> None:
    """Restart the sandbox environment."""
    lifecycle.restart()


@app.command(rich_help_panel=LIFECYCLE)
def rebuild() -> None:
    """Rebuild images and restart."""
    lifecycle.rebuild()


@app.command(rich_help_panel=LIFECYCLE)
def status() -> None:
    """Show container status."""
    lifecycle.status()


@app.command(rich_help_panel=LIFECYCLE)
def attach() -> None:
    """Attach to the sandbox shell."""
    lifecycle.attach()


@app.command(rich_help_panel=PROJECTS)
def init(
    name: str = typer.Argument(..., help="Project name to initialize"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="Workspace directory to use"),
) -> None:
    """Initialize a new project."""
    from cli.lib.project import init_project
    try:
        path = init_project(name, workspace=workspace)
        typer.echo(typer.style(f"Project '{name}' initialized at {path}", fg=typer.colors.GREEN))
        typer.echo(f"  Use: sandbox --project {name} start")
    except ValueError as e:
        typer.echo(typer.style(f"error: {e}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)


@app.command(name="projects", rich_help_panel=PROJECTS)
def list_projects() -> None:
    """List all initialized projects."""
    from cli.lib.project import list_projects as _list_projects
    from cli.lib.config import get_active_project_name
    projects = _list_projects()
    active = get_active_project_name()

    if not projects:
        typer.echo("No projects initialized. Use 'sandbox init <name>' to create one.")
        return

    for p in projects:
        marker = " (active)" if p["name"] == active else ""
        typer.echo(f"  {p['name']}{marker}")


MANAGE = "Management"

app.add_typer(tools.app, name="tool", help="Tool management", rich_help_panel=MANAGE)
app.add_typer(mcp.app, name="mcp", help="MCP server management", rich_help_panel=MANAGE)
app.add_typer(secrets.app, name="secrets", help="Secrets management", rich_help_panel=MANAGE)
app.add_typer(firewall.app, name="fw", help="Firewall management", rich_help_panel=MANAGE)
app.add_typer(proxy.app, name="proxy", help="TLS proxy management", rich_help_panel=MANAGE)
app.add_typer(config_cmd.app, name="config", help="Configuration management", rich_help_panel=MANAGE)
app.add_typer(logs.app, name="logs", help="Audit log management", rich_help_panel=MANAGE)


@app.command(rich_help_panel=OBSERVE)
def check() -> None:
    """Run compliance checks."""
    logs.check()


@app.command(rich_help_panel=OBSERVE)
def info() -> None:
    """Show combined status, config, and environment overview."""
    typer.echo(f"sandbox version {__version__}")
    typer.echo("")
    lifecycle.status()
    typer.echo("")
    config_cmd.show()


@app.command(rich_help_panel=OBSERVE)
def update(
    check_only: bool = typer.Option(False, "--check", help="Check for updates without applying"),
    apply: bool = typer.Option(False, "--apply", help="Pull latest and rebuild"),
) -> None:
    """Check for updates or update the sandbox."""
    import subprocess

    typer.echo(f"Current version: {__version__}")

    if check_only or not apply:
        typer.echo("")
        typer.echo("To update:")
        typer.echo("  1. git pull")
        typer.echo("  2. pip install -e '.[dev]'")
        typer.echo("  3. sandbox rebuild")
        typer.echo("")
        typer.echo("Or run: sandbox update --apply")
        return

    if apply:
        typer.echo("Pulling latest changes...")
        result = subprocess.run(["git", "pull"], capture_output=True, text=True)
        if result.returncode != 0:
            typer.echo(typer.style(f"error: git pull failed: {result.stderr.strip()}",
                                   fg=typer.colors.RED), err=True)
            raise typer.Exit(1)
        typer.echo(result.stdout.strip())

        typer.echo("Updating dependencies...")
        result = subprocess.run(
            ["pip", "install", "-e", ".[dev]"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            typer.echo(typer.style(f"error: pip install failed",
                                   fg=typer.colors.RED), err=True)
            raise typer.Exit(1)

        typer.echo("Rebuilding containers...")
        lifecycle.rebuild()

        typer.echo(typer.style("Update complete.", fg=typer.colors.GREEN))


@app.command(rich_help_panel=OBSERVE)
def version() -> None:
    """Show version information."""
    typer.echo(f"sandbox version {__version__}")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
