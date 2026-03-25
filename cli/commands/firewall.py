"""Firewall management commands."""

import typer

app = typer.Typer(no_args_is_help=True)


@app.command(name="ls")
def list_domains() -> None:
    """List whitelisted domains."""
    typer.echo("Whitelisted domains:")
    # TODO: Read and display whitelist
    typer.echo(typer.style("fw ls: not yet implemented", fg=typer.colors.YELLOW))


@app.command()
def add(
    domain: str = typer.Argument(..., help="Domain to add to whitelist"),
) -> None:
    """Add domain to whitelist."""
    typer.echo(f"Adding domain: {domain}")
    # TODO: Validate domain format
    # TODO: Add to whitelist
    # TODO: Apply firewall
    typer.echo(typer.style("fw add: not yet implemented", fg=typer.colors.YELLOW))


@app.command()
def remove(
    domain: str = typer.Argument(..., help="Domain to remove from whitelist"),
) -> None:
    """Remove domain from whitelist."""
    typer.echo(f"Removing domain: {domain}")
    # TODO: Remove from whitelist
    # TODO: Apply firewall
    typer.echo(typer.style("fw remove: not yet implemented", fg=typer.colors.YELLOW))


@app.command()
def apply() -> None:
    """Re-apply firewall rules."""
    typer.echo("Applying firewall rules...")
    # TODO: Invoke firewall-apply.sh in container
    typer.echo(typer.style("fw apply: not yet implemented", fg=typer.colors.YELLOW))
