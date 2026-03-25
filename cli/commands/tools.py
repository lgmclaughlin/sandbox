"""Tool management commands."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command(name="list")
def list_tools() -> None:
    """List available and installed tools."""
    typer.echo("Available tools:")
    # TODO: Read from config/tools/
    # TODO: Show installed status
    typer.echo(typer.style("tool list: not yet implemented", fg=typer.colors.YELLOW))


@app.command()
def install(
    name: str = typer.Argument(..., help="Tool name to install"),
) -> None:
    """Install a tool into the sandbox."""
    typer.echo(f"Installing tool: {name}")
    # TODO: Find tool definition
    # TODO: Run install script
    # TODO: Merge domains
    # TODO: Merge env vars
    typer.echo(typer.style("tool install: not yet implemented", fg=typer.colors.YELLOW))


@app.command()
def remove(
    name: str = typer.Argument(..., help="Tool name to remove"),
) -> None:
    """Remove a tool from the sandbox."""
    typer.echo(f"Removing tool: {name}")
    # TODO: Remove tool
    # TODO: Clean up domains/env
    typer.echo(typer.style("tool remove: not yet implemented", fg=typer.colors.YELLOW))
