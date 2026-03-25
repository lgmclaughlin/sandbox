"""Container lifecycle commands: start, stop, restart, rebuild, status, attach."""

import typer


def start(attach: bool = True) -> None:
    """Start the sandbox environment."""
    typer.echo("Starting sandbox environment...")
    # TODO: Implement first-run flow
    # TODO: Load .env, create if missing
    # TODO: Initialize config directories
    # TODO: Install default tool if none
    # TODO: Merge tool domains into firewall
    # TODO: Start firewall container
    # TODO: Start sandbox container
    # TODO: Run compliance check
    # TODO: Attach to shell if requested
    typer.echo(typer.style("start: not yet implemented", fg=typer.colors.YELLOW))


def stop() -> None:
    """Stop all sandbox containers."""
    typer.echo("Stopping sandbox containers...")
    # TODO: Graceful shutdown of sandbox
    # TODO: Graceful shutdown of firewall
    typer.echo(typer.style("stop: not yet implemented", fg=typer.colors.YELLOW))


def restart() -> None:
    """Restart the sandbox environment."""
    stop()
    start()


def rebuild() -> None:
    """Rebuild images and restart."""
    typer.echo("Rebuilding sandbox images...")
    # TODO: Stop containers
    # TODO: Rebuild images
    # TODO: Start containers
    typer.echo(typer.style("rebuild: not yet implemented", fg=typer.colors.YELLOW))


def status() -> None:
    """Show container status."""
    typer.echo("Sandbox status:")
    # TODO: Show container states
    # TODO: Show mounted volumes
    # TODO: Show installed tools
    typer.echo(typer.style("status: not yet implemented", fg=typer.colors.YELLOW))


def attach() -> None:
    """Attach to the sandbox shell."""
    typer.echo("Attaching to sandbox...")
    # TODO: Check if running
    # TODO: Attach to sandbox container
    typer.echo(typer.style("attach: not yet implemented", fg=typer.colors.YELLOW))
