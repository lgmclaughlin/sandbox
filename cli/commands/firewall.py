"""Firewall management commands."""

import os
import subprocess
from typing import Optional

import typer
import yaml

from cli.lib.config import get_log_dir
from cli.lib.firewall import (
    _profiles_dir,
    add_domain,
    apply_profile,
    apply_rules,
    list_profiles,
    read_firewall_logs,
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


@app.command()
def profiles() -> None:
    """List available firewall profiles."""
    available = list_profiles()
    if not available:
        typer.echo("No firewall profiles found.")
        return

    for p in available:
        domain_count = len(p.get("domains", []))
        desc = p.get("description", "")
        typer.echo(f"  {p['name']}: {desc} ({domain_count} domains)")


@app.command()
def profile(
    name: str = typer.Argument(..., help="Profile name to apply"),
) -> None:
    """Apply a firewall profile."""
    ok, message = apply_profile(name)
    if not ok:
        typer.echo(typer.style(f"error: {message}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    typer.echo(message)
    _apply_and_report()


@app.command(name="logs")
def fw_logs(
    action: str = typer.Option("all", "--action", "-a", help="Filter: all, allow, block"),
    lines: int = typer.Option(20, "--lines", "-n", help="Number of entries to show"),
) -> None:
    """View firewall connection logs."""
    log_dir = get_log_dir()
    entries = read_firewall_logs(log_dir, action=action, lines=lines)

    if not entries:
        typer.echo("No firewall logs found.")
        return

    for entry in entries:
        ts = entry.get("timestamp", "?")
        act = entry.get("action", "?")
        dst = entry.get("dst", "?")
        port = entry.get("port", "?")
        proto = entry.get("proto", "?")

        color = typer.colors.GREEN if act == "allow" else typer.colors.RED
        act_styled = typer.style(act.upper(), fg=color)
        typer.echo(f"  [{ts}] {act_styled} {dst}:{port} ({proto})")


@app.command(name="create-profile")
def create_fw_profile(
    name: str = typer.Argument(..., help="Profile name"),
    domains: Optional[str] = typer.Option(None, help="Comma-separated domains"),
) -> None:
    """Create a new firewall profile."""
    profiles_dir = _profiles_dir()
    profile_file = profiles_dir / f"{name}.yaml"

    if profile_file.exists():
        typer.echo(typer.style(f"error: Profile '{name}' already exists.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    definition = {
        "name": name,
        "description": "",
        "domains": domains.split(",") if domains else [],
    }

    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_file.write_text(yaml.dump(definition, default_flow_style=False))
    typer.echo(f"Created firewall profile: {profile_file}")
    typer.echo(f"  Apply with: sandbox fw profile {name}")


@app.command(name="edit-profile")
def edit_fw_profile(
    name: str = typer.Argument(..., help="Profile name to edit"),
) -> None:
    """Open a firewall profile in editor."""
    profile_file = _profiles_dir() / f"{name}.yaml"
    if not profile_file.exists():
        typer.echo(typer.style(f"error: Profile '{name}' not found.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(profile_file)])


def _apply_and_report() -> None:
    """Apply rules and print result."""
    typer.echo("Applying firewall rules...")
    success, message = apply_rules()
    if success:
        typer.echo(typer.style("Firewall updated.", fg=typer.colors.GREEN))
    else:
        typer.echo(typer.style(f"error: {message}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)
