"""Proxy management commands."""

import json
from pathlib import Path

import typer

from cli.lib.config import get_log_dir, load_env
from cli.lib.docker import is_running

app = typer.Typer(no_args_is_help=True)


@app.command()
def status() -> None:
    """Show proxy state."""
    env = load_env()
    mode = env.get("SANDBOX_PROXY_MODE", "firewall-only")
    dlp = env.get("SANDBOX_DLP_PROVIDER", "none")

    typer.echo(typer.style("Proxy:", bold=True))
    typer.echo(f"  Mode: {mode}")

    if mode == "proxy":
        running = is_running("proxy")
        color = typer.colors.GREEN if running else typer.colors.RED
        state = typer.style("running" if running else "not running", fg=color)
        typer.echo(f"  Status: {state}")
        typer.echo(f"  DLP provider: {dlp}")

        if dlp == "webhook":
            webhook = env.get("SANDBOX_DLP_WEBHOOK_URL", "")
            typer.echo(f"  DLP webhook: {webhook or '(not configured)'}")

        ca_cert = env.get("SANDBOX_PROXY_CA_CERT", "")
        typer.echo(f"  CA cert: {ca_cert or 'auto-generated'}")
    else:
        typer.echo("  Proxy is not enabled. Set SANDBOX_PROXY_MODE=proxy to enable.")


@app.command(name="logs")
def proxy_logs(
    lines: int = typer.Option(20, "--lines", "-n", help="Number of entries to show"),
) -> None:
    """View proxy request logs."""
    log_dir = get_log_dir() / "proxy"
    if not log_dir.exists():
        typer.echo("No proxy logs found.")
        return

    entries = []
    for log_file in sorted(log_dir.rglob("*.jsonl"), reverse=True):
        for line in reversed(log_file.read_text().splitlines()):
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
                if len(entries) >= lines:
                    break
            except json.JSONDecodeError:
                continue
        if len(entries) >= lines:
            break

    if not entries:
        typer.echo("No proxy log entries found.")
        return

    for entry in reversed(entries):
        payload = entry.get("payload", {})
        ts = entry.get("timestamp", "?")
        method = payload.get("method", "?")
        url = payload.get("url", "?")
        status_code = payload.get("status_code", "")
        blocked = payload.get("blocked", False)

        if blocked:
            action = typer.style("BLOCKED", fg=typer.colors.RED)
        elif status_code:
            action = typer.style(str(status_code), fg=typer.colors.GREEN)
        else:
            action = typer.style("->", fg=typer.colors.BLUE)

        violations = payload.get("violations", [])
        violation_str = ""
        if violations:
            names = [v.get("rule", "?") for v in violations]
            violation_str = typer.style(f" [{', '.join(names)}]", fg=typer.colors.YELLOW)

        typer.echo(f"  [{ts}] {action} {method} {url}{violation_str}")
