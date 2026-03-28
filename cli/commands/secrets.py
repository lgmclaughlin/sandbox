"""Secrets management commands."""

import typer

from cli.lib.secrets import get_provider, mask_value

app = typer.Typer(no_args_is_help=True)


@app.command()
def set(
    key: str = typer.Argument(..., help="Secret key name"),
    value: str = typer.Argument(..., help="Secret value"),
) -> None:
    """Store a secret."""
    provider = get_provider()
    try:
        provider.set(key, value)
        typer.echo(f"Secret '{key}' stored.")

        from cli.lib.docker import is_running
        if is_running("sandbox"):
            typer.echo(typer.style("  Restart sandbox for changes to take effect.",
                                   fg=typer.colors.YELLOW))
    except RuntimeError as e:
        typer.echo(typer.style(f"error: {e}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)


@app.command()
def get(
    key: str = typer.Argument(..., help="Secret key name"),
    show: bool = typer.Option(False, "--show", help="Show unmasked value"),
) -> None:
    """Retrieve a secret."""
    provider = get_provider()
    value = provider.get(key)
    if value is None:
        typer.echo(typer.style(f"error: Secret '{key}' not found.", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    if show:
        typer.echo(value)
    else:
        typer.echo(f"{key}={mask_value(value)}")


@app.command(name="list")
def list_secrets() -> None:
    """List stored secret keys."""
    provider = get_provider()
    keys = provider.list_keys()
    if not keys:
        typer.echo("No secrets stored.")
        return

    for key in keys:
        typer.echo(f"  {key}")


@app.command()
def delete(
    key: str = typer.Argument(..., help="Secret key to delete"),
) -> None:
    """Delete a secret."""
    provider = get_provider()
    try:
        if provider.delete(key):
            typer.echo(f"Secret '{key}' deleted.")
        else:
            typer.echo(typer.style(f"error: Secret '{key}' not found.", fg=typer.colors.RED), err=True)
            raise typer.Exit(1)
    except RuntimeError as e:
        typer.echo(typer.style(f"error: {e}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)
