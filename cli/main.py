"""Main CLI entry point."""

import os
from typing import Optional

import typer

from cli import __version__
from cli.commands import config_cmd, firewall, lifecycle, logs, mcp, secrets, tools

app = typer.Typer(
    name="sandbox",
    help="Secure AI development environment",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(firewall.app, name="fw", help="Firewall management")
app.add_typer(tools.app, name="tool", help="Tool management")
app.add_typer(mcp.app, name="mcp", help="MCP server management")
app.add_typer(secrets.app, name="secrets", help="Secrets management")
app.add_typer(config_cmd.app, name="config", help="Configuration management")


@app.callback()
def main_callback(
    project: Optional[str] = typer.Option(
        None, "--project", "-p", help="Project name to operate on",
        envvar="SANDBOX_PROJECT",
    ),
) -> None:
    """Resolve active project before any command runs."""
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


@app.command()
def start(
    workspace: Optional[str] = typer.Argument(None, help="Workspace directory to mount (default: current directory)"),
    attach: bool = typer.Option(True, "--attach/--no-attach", help="Attach to shell after start"),
    env: str = typer.Option("", "--env", "-e", help="Environment profile to use"),
) -> None:
    """Start the sandbox environment."""
    lifecycle.start(attach=attach, env_profile=env, workspace=workspace)


@app.command()
def stop() -> None:
    """Stop all sandbox containers."""
    lifecycle.stop()


@app.command()
def restart() -> None:
    """Restart the sandbox environment."""
    lifecycle.restart()


@app.command()
def rebuild() -> None:
    """Rebuild images and restart."""
    lifecycle.rebuild()


@app.command()
def status() -> None:
    """Show container status."""
    lifecycle.status()


@app.command()
def attach() -> None:
    """Attach to the sandbox shell."""
    lifecycle.attach()


@app.command()
def check() -> None:
    """Run compliance checks."""
    logs.check()


@app.command(name="logs")
def logs_cmd(
    log_type: str = typer.Argument("all", help="Log type: sessions, commands, or all"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    session: str = typer.Option("", "--session", "-s", help="View all events for a session ID"),
) -> None:
    """View audit logs."""
    logs.view(log_type=log_type, follow=follow, lines=lines, session_id=session)


@app.command()
def rotate() -> None:
    """Rotate and clean up old logs based on retention policy."""
    logs.rotate_logs()


@app.command(name="summary")
def logs_summary() -> None:
    """Show high-level log summary."""
    logs.summary()


@app.command()
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


@app.command(name="projects")
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


@app.command()
def version() -> None:
    """Show version information."""
    typer.echo(f"sandbox version {__version__}")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
