"""Logging and compliance commands."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import typer

from cli.lib.config import get_log_dir, load_env
from cli.lib.docker import is_running

app = typer.Typer(no_args_is_help=True)


@app.command(name="view")
def view_cmd(
    log_type: str = typer.Argument("all", help="Log type: sessions, commands, or all"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    session: str = typer.Option("", "--session", "-s", help="View all events for a session ID"),
) -> None:
    """View audit logs."""
    view(log_type=log_type, follow=follow, lines=lines, session_id=session)


@app.command()
def rotate() -> None:
    """Rotate and clean up old logs based on retention policy."""
    rotate_logs()


@app.command()
def summary() -> None:
    """Show high-level log summary."""
    log_summary()


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
    _check("Environment configured", bool(env))

    typer.echo("")
    total = passed + failed
    color = typer.colors.GREEN if failed == 0 else typer.colors.RED
    typer.echo(typer.style(f"{passed}/{total} checks passed.", fg=color))

    if failed > 0:
        raise typer.Exit(1)


def view(
    log_type: str = "all",
    follow: bool = False,
    lines: int = 50,
    session_id: str = "",
) -> None:
    """View audit logs."""
    log_dir = get_log_dir()

    if not log_dir.exists():
        typer.echo(typer.style("error: Log directory does not exist.", fg=typer.colors.RED),
                   err=True)
        raise typer.Exit(1)

    valid_types = {"sessions", "commands", "all"}
    if log_type not in valid_types:
        typer.echo(typer.style(
            f"error: Unknown log type '{log_type}'. Use: {', '.join(sorted(valid_types))}",
            fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    if session_id:
        _view_session(log_dir, session_id)
        return

    if log_type in ("sessions", "all"):
        typer.echo(typer.style("Sessions:", bold=True))
        _view_sessions(log_dir / "sessions", lines)

    if log_type == "all":
        typer.echo("")

    if log_type in ("commands", "all"):
        typer.echo(typer.style("Command history:", bold=True))
        _view_commands(log_dir / "commands", lines)


def _collect_files(base_dir: Path, pattern: str) -> list[Path]:
    """Collect files from base_dir, including daily subdirectories."""
    if not base_dir.exists():
        return []

    files = list(base_dir.glob(pattern))
    for date_dir in base_dir.iterdir():
        if date_dir.is_dir():
            files.extend(date_dir.glob(pattern))

    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def _view_sessions(sessions_dir: Path, lines: int) -> None:
    """View session metadata."""
    files = _collect_files(sessions_dir, "*.meta.json")
    if not files:
        typer.echo("  No sessions found.")
        return

    for f in files[:lines]:
        try:
            entries = _parse_meta_file(f)
            start_event = next((e for e in entries if e.get("event") == "session_start"), entries[0])
            end_event = next((e for e in entries if e.get("event") == "session_end"), None)

            user = start_event.get("user", "?")
            start = start_event.get("start_time", "?")
            sid = start_event.get("session_id", f.stem)
            status = "ended" if end_event else "active"

            typer.echo(f"  {sid}: user={user} started={start} [{status}]")
        except (json.JSONDecodeError, OSError, IndexError):
            typer.echo(f"  {f.name}: (unreadable)")


def _view_commands(commands_dir: Path, lines: int) -> None:
    """View command logs (text history or JSON lines)."""
    files = _collect_files(commands_dir, "*")
    command_files = [f for f in files if f.suffix in (".history", ".jsonl")]
    if not command_files:
        typer.echo("  No command logs found.")
        return

    for f in command_files[:lines]:
        if f.suffix == ".jsonl":
            count = sum(1 for _ in f.open())
            typer.echo(f"  {f.name} ({count} commands, json)")
        else:
            typer.echo(f"  {f.name} ({f.stat().st_size} bytes)")


def _view_session(log_dir: Path, session_id: str) -> None:
    """View all events for a specific session."""
    typer.echo(typer.style(f"Session: {session_id}", bold=True))
    typer.echo("")

    meta_files = _collect_files(log_dir / "sessions", "*.meta.json")
    meta_file = next((f for f in meta_files if session_id in f.name), None)

    if meta_file:
        entries = _parse_meta_file(meta_file)
        start = next((e for e in entries if e.get("event") == "session_start"), None)
        if start:
            typer.echo(f"  User: {start.get('user', '?')}")
            typer.echo(f"  Host: {start.get('hostname', '?')}")
            typer.echo(f"  Started: {start.get('start_time', '?')}")
            typer.echo(f"  Format: {start.get('log_format', 'text')}")

        end = next((e for e in entries if e.get("event") == "session_end"), None)
        if end:
            typer.echo(f"  Ended: {end.get('end_time', '?')}")
    else:
        typer.echo("  Session metadata not found.")

    typer.echo("")
    typer.echo(typer.style("Commands:", bold=True))
    cmd_files = _collect_files(log_dir / "commands", "*")
    cmd_file = next((f for f in cmd_files if session_id in f.name), None)

    if cmd_file and cmd_file.suffix == ".jsonl":
        for line in cmd_file.read_text().splitlines():
            try:
                event = json.loads(line)
                ts = event.get("timestamp", "?")
                cmd = event.get("command", "?")
                code = event.get("exit_code", "?")
                typer.echo(f"  [{ts}] (exit {code}) {cmd}")
            except json.JSONDecodeError:
                continue
    elif cmd_file:
        for line in cmd_file.read_text().splitlines()[-20:]:
            typer.echo(f"  {line}")
    else:
        typer.echo("  No command log found for this session.")


def _parse_meta_file(path: Path) -> list[dict]:
    """Parse a meta.json file that may contain multiple JSON objects."""
    content = path.read_text().strip()
    entries = []
    for block in content.split("\n\n"):
        block = block.strip()
        if block:
            try:
                entries.append(json.loads(block))
            except json.JSONDecodeError:
                continue
    return entries


def log_summary() -> None:
    """Show high-level log summary."""
    log_dir = get_log_dir()
    if not log_dir.exists():
        typer.echo("No logs found.")
        return

    session_files = _collect_files(log_dir / "sessions", "*.meta.json")
    command_files = _collect_files(log_dir / "commands", "*")
    command_files = [f for f in command_files if f.suffix in (".history", ".jsonl")]

    session_dates = set()
    if (log_dir / "sessions").exists():
        for d in (log_dir / "sessions").iterdir():
            if d.is_dir():
                session_dates.add(d.name)

    typer.echo(typer.style("Log Summary:", bold=True))
    typer.echo(f"  Sessions: {len(session_files)}")
    typer.echo(f"  Command logs: {len(command_files)}")
    typer.echo(f"  Days with activity: {len(session_dates)}")

    env = load_env()
    typer.echo(f"  Log format: {env.get('SANDBOX_LOG_FORMAT', 'text')}")
    typer.echo(f"  Retention: {env.get('SANDBOX_LOG_RETENTION_DAYS', '30')} days")

    total_size = sum(f.stat().st_size for f in log_dir.rglob("*") if f.is_file())
    if total_size > 1024 * 1024:
        typer.echo(f"  Total size: {total_size / (1024 * 1024):.1f} MB")
    else:
        typer.echo(f"  Total size: {total_size / 1024:.1f} KB")


def rotate_logs() -> None:
    """Rotate and clean up old logs based on retention policy."""
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

    for type_dir in log_dir.iterdir():
        if not type_dir.is_dir():
            continue
        for date_dir in type_dir.iterdir():
            if date_dir.is_dir() and not any(date_dir.iterdir()):
                date_dir.rmdir()

    if removed:
        typer.echo(f"Removed {removed} log files older than {retention_days} days.")
