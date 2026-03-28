"""Mount management commands."""

from typing import Optional

import typer
import yaml

import cli.lib.config as config

app = typer.Typer(no_args_is_help=True)


@app.command(name="list")
def list_mounts() -> None:
    """List configured mounts."""
    mounts = config.load_mounts()
    if not mounts:
        typer.echo("No mounts configured.")
        return

    for mount in mounts:
        name = mount.get("name", "unnamed")
        mount_type = mount.get("type", "rclone")
        remote = mount.get("remote", "?")
        local = mount.get("local", "?")
        typer.echo(f"  {name}: {remote} -> {local} ({mount_type})")


@app.command()
def add(
    name: str = typer.Argument(..., help="Mount name"),
    remote: str = typer.Option(..., help="Remote path (e.g., s3:bucket/path or user@host:/path)"),
    local: str = typer.Option(..., help="Local mount point"),
    mount_type: str = typer.Option("rclone", "--type", help="Mount type: rclone or sshfs"),
) -> None:
    """Add a mount definition."""
    mounts = config.load_mounts()

    if any(m.get("name") == name for m in mounts):
        typer.echo(typer.style(f"error: Mount '{name}' already exists.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    mounts.append({
        "name": name,
        "type": mount_type,
        "remote": remote,
        "local": local,
    })

    mounts_file = config.MOUNTS_FILE
    mounts_file.parent.mkdir(parents=True, exist_ok=True)
    mounts_file.write_text(yaml.dump({"mounts": mounts}, default_flow_style=False))
    typer.echo(f"Added mount '{name}'.")


@app.command()
def remove(
    name: str = typer.Argument(..., help="Mount name to remove"),
) -> None:
    """Remove a mount definition."""
    mounts = config.load_mounts()
    original_len = len(mounts)
    mounts = [m for m in mounts if m.get("name") != name]

    if len(mounts) == original_len:
        typer.echo(typer.style(f"error: Mount '{name}' not found.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    mounts_file = config.MOUNTS_FILE
    mounts_file.write_text(yaml.dump({"mounts": mounts}, default_flow_style=False))
    typer.echo(f"Removed mount '{name}'.")
