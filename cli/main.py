"""Main CLI entry point."""

import typer

from cli import __version__
from cli.commands import config_cmd, firewall, lifecycle, logs, secrets, tools

app = typer.Typer(
    name="sandbox",
    help="Secure AI development environment",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(firewall.app, name="fw", help="Firewall management")
app.add_typer(tools.app, name="tool", help="Tool management")
app.add_typer(secrets.app, name="secrets", help="Secrets management")
app.add_typer(config_cmd.app, name="config", help="Configuration management")


@app.command()
def start(
    attach: bool = typer.Option(True, "--attach/--no-attach", help="Attach to shell after start"),
    env: str = typer.Option("", "--env", "-e", help="Environment profile to use"),
) -> None:
    """Start the sandbox environment."""
    lifecycle.start(attach=attach, env_profile=env)


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
) -> None:
    """View audit logs."""
    logs.view(log_type=log_type, follow=follow, lines=lines)


@app.command()
def rotate() -> None:
    """Rotate and clean up old logs based on retention policy."""
    logs.rotate_logs()


@app.command()
def version() -> None:
    """Show version information."""
    typer.echo(f"sandbox version {__version__}")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
