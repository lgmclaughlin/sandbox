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


@app.command()
def clear(
    path: Optional[str] = typer.Argument(None, help="Specific directory to unmount (default: all configured mounts)"),
) -> None:
    """Unmount active FUSE mounts."""
    from cli.lib.mounts import _is_mounted, _unmount

    if path is not None:
        local_path = Path(path)
        if not local_path.is_absolute():
            local_path = Path.cwd() / local_path

        if not _is_mounted(local_path):
            typer.echo(typer.style(f"error: {local_path} is not mounted.",
                                   fg=typer.colors.RED), err=True)
            raise typer.Exit(1)

        _unmount(local_path)
        typer.echo(f"Unmounted {local_path}.")
        return

    mounts = config.load_mounts()
    if not mounts:
        typer.echo("No mounts configured.")
        return

    cleared = 0
    for mount in mounts:
        local = mount.get("local", "")
        if not local:
            continue
        local_path = Path(local)
        if not local_path.is_absolute():
            local_path = Path.cwd() / local_path
        if _is_mounted(local_path):
            _unmount(local_path)
            typer.echo(f"  Unmounted {local_path}")
            cleared += 1

    if cleared == 0:
        typer.echo("No active mounts found.")
    else:
        typer.echo(f"Cleared {cleared} mount(s).")
