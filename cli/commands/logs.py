"""Logging and compliance commands."""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import typer

from cli.lib.config import get_log_dir, load_env
from cli.lib.docker import is_running, get_status
from cli.lib.platform import get_user_info


def check() -> None:
    """Run compliance checks."""
    typer.echo(typer.style("Running compliance checks...", bold=True))
    passed = 0
    failed = 0

    def _check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if ok:
            passed += 1
            typer.echo(f"  {typer.style('PASS', fg=typer.colors.GREEN)} {name}")
        else:
            failed += 1
            msg = f"  {typer.style('FAIL', fg=typer.colors.RED)} {name}"
            if detail:
                msg += f" ({detail})"
            typer.echo(msg)

    _check("Firewall container running", is_running("firewall"))
    _check("Sandbox container running", is_running("sandbox"))

    log_dir = get_log_dir()
    _check("Log directory exists", log_dir.exists())
    _check("Session log directory exists", (log_dir / "sessions").exists())
    _check("Command log directory exists", (log_dir / "commands").exists())

    if is_running("sandbox"):
        from cli.lib.docker import exec_in_sandbox
        exit_code, output = exec_in_sandbox(["whoami"])
        username = output.strip() if exit_code == 0 else ""
        _check("Sandbox running as non-root", username != "root",
               f"running as '{username}'" if username == "root" else "")

    env = load_env()
    env_file = get_log_dir().parent / ".env"
    _check("Environment configured", bool(env))

    typer.echo("")
    total = passed + failed
    color = typer.colors.GREEN if failed == 0 else typer.colors.RED
    typer.echo(typer.style(f"{passed}/{total} checks passed.", fg=color))

    if failed > 0:
        raise typer.Exit(1)


def view(log_type: str = "all", follow: bool = False, lines: int = 50) -> None:
    """View audit logs."""
    log_dir = get_log_dir()

    if not log_dir.exists():
        typer.echo(typer.style("error: Log directory does not exist.", fg=typer.colors.RED),
                   err=True)
        raise typer.Exit(1)

    if log_type == "sessions":
        _view_dir(log_dir / "sessions", "*.meta.json", lines)
    elif log_type == "commands":
        _view_dir(log_dir / "commands", "*.history", lines)
    elif log_type == "all":
        typer.echo(typer.style("Sessions:", bold=True))
        _view_dir(log_dir / "sessions", "*.meta.json", lines)
        typer.echo("")
        typer.echo(typer.style("Command history:", bold=True))
        _view_dir(log_dir / "commands", "*.history", lines)
    else:
        typer.echo(typer.style(f"error: Unknown log type '{log_type}'. Use: sessions, commands, all",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)


def _view_dir(directory: Path, pattern: str, lines: int) -> None:
    """View log files from a directory."""
    if not directory.exists():
        typer.echo("  No logs found.")
        return

    files = sorted(directory.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        typer.echo("  No logs found.")
        return

    for f in files[:lines]:
        if f.suffix == ".json":
            try:
                data = json.loads(f.read_text())
                user = data.get("user", "?")
                start = data.get("start_time", "?")
                typer.echo(f"  {f.stem}: user={user} started={start}")
            except (json.JSONDecodeError, OSError):
                typer.echo(f"  {f.name}: (unreadable)")
        else:
            typer.echo(f"  {f.name} ({f.stat().st_size} bytes)")


def rotate_logs() -> None:
    """Rotate and clean up old logs based on retention policy."""
    import gzip

    env = load_env()
    retention_days = int(env.get("SANDBOX_LOG_RETENTION_DAYS", "30"))
    if retention_days == 0:
        return

    log_dir = get_log_dir()
    if not log_dir.exists():
        return

    cutoff = datetime.now() - timedelta(days=retention_days)

    removed = 0
    for log_file in log_dir.rglob("*"):
        if not log_file.is_file():
            continue

        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        if mtime < cutoff:
            log_file.unlink()
            removed += 1

    if removed:
        typer.echo(f"Removed {removed} log files older than {retention_days} days.")
