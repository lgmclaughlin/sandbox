"""Firewall management commands."""

import typer

from cli.lib.firewall import (
    add_domain,
    apply_rules,
    read_whitelist,
    remove_domain,
    validate_domain,
)

app = typer.Typer(no_args_is_help=True)


@app.command(name="ls")
def list_domains() -> None:
    """List whitelisted domains."""
    domains = read_whitelist()
    if not domains:
        typer.echo("No domains in whitelist.")
        return

    for domain in domains:
        typer.echo(f"  {domain}")


@app.command()
def add(
    domain: str = typer.Argument(..., help="Domain to add to whitelist"),
) -> None:
    """Add domain to whitelist and apply."""
    if not validate_domain(domain):
        typer.echo(typer.style(f"error: Invalid domain format: {domain}",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    if not add_domain(domain):
        typer.echo(f"{domain} is already in the whitelist.")
        return

    typer.echo(f"Added {domain} to whitelist.")
    _apply_and_report()


@app.command()
def remove(
    domain: str = typer.Argument(..., help="Domain to remove from whitelist"),
) -> None:
    """Remove domain from whitelist and apply."""
    if not remove_domain(domain):
        typer.echo(typer.style(f"error: {domain} not found in whitelist.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    typer.echo(f"Removed {domain} from whitelist.")
    _apply_and_report()


@app.command()
def apply() -> None:
    """Re-apply firewall rules from current whitelist."""
    _apply_and_report()


def _apply_and_report() -> None:
    """Apply rules and print result."""
    typer.echo("Applying firewall rules...")
    success, message = apply_rules()
    if success:
        typer.echo(typer.style("Firewall updated.", fg=typer.colors.GREEN))
    else:
        typer.echo(typer.style(f"error: {message}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)
