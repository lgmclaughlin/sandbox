"""Configuration and environment profile commands."""

import typer

from cli.lib.config import get_active_profile, load_env
from cli.lib.paths import get_data_dir
from cli.lib.secrets import mask_value

app = typer.Typer(no_args_is_help=True)

SENSITIVE_KEYS = {"ANTHROPIC_API_KEY", "HTTP_PROXY", "HTTPS_PROXY", "CUSTOM_CA_CERT_PATH"}


@app.command()
def show() -> None:
    """Display merged configuration."""
    env = load_env()
    profile = get_active_profile()

    if profile:
        typer.echo(typer.style(f"Active profile: {profile}", bold=True))
    else:
        typer.echo(typer.style("Active profile: (none)", bold=True))

    typer.echo("")
    for key, value in sorted(env.items()):
        if not value:
            typer.echo(f"  {key}=")
        elif key in SENSITIVE_KEYS:
            typer.echo(f"  {key}={mask_value(value)}")
        else:
            typer.echo(f"  {key}={value}")


@app.command()
def profiles() -> None:
    """List available environment profiles."""
    active = get_active_profile()

    found = False
    for env_file in sorted(get_data_dir().glob(".env.*")):
        if env_file.name == ".env.dist":
            continue
        profile_name = env_file.name.removeprefix(".env.")
        marker = " (active)" if profile_name == active else ""
        typer.echo(f"  {profile_name}{marker}")
        found = True

    if not found:
        typer.echo("No profiles found. Create .env.dev, .env.corp, etc.")
