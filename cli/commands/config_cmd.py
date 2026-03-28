"""Configuration and environment profile commands."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
import yaml

import cli.lib.config as config
from cli.lib.config import (
    get_active_profile,
    get_active_project_name,
    load_env,
    load_mounts,
    list_available_tools,
)
from cli.lib.mcp import list_mcp_servers
from cli.lib.paths import get_data_dir
from cli.lib.secrets import mask_value

app = typer.Typer(no_args_is_help=True)

SENSITIVE_KEYS = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "HTTP_PROXY", "HTTPS_PROXY",
                  "CUSTOM_CA_CERT_PATH", "SANDBOX_DLP_WEBHOOK_URL"}


@app.command()
def show(
    path: bool = typer.Option(False, "--path", help="Show config directory path"),
) -> None:
    """Display merged configuration."""
    if path:
        typer.echo(get_data_dir())
        return

    env = load_env()
    profile = get_active_profile()
    project = get_active_project_name()

    if project:
        typer.echo(typer.style(f"Project: {project}", bold=True))
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
def get(
    key: str = typer.Argument(..., help="Configuration key"),
    show_value: bool = typer.Option(False, "--show", help="Show unmasked value for sensitive keys"),
) -> None:
    """Get a specific configuration value."""
    env = load_env()
    if key not in env:
        typer.echo(typer.style(f"error: Key '{key}' not found in configuration.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    value = env[key]
    if key in SENSITIVE_KEYS and not show_value and value:
        typer.echo(f"{key}={mask_value(value)}")
    else:
        typer.echo(f"{key}={value}")


@app.command()
def set(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a configuration value."""
    from dotenv import set_key as dotenv_set_key

    dist_env = {}
    if config.ENV_DIST_FILE.exists():
        from dotenv import dotenv_values
        dist_env = dotenv_values(config.ENV_DIST_FILE)

    if key not in dist_env:
        typer.echo(typer.style(f"warning: '{key}' is not a known config key.",
                               fg=typer.colors.YELLOW), err=True)

    env_file = config.ENV_FILE
    env_file.parent.mkdir(parents=True, exist_ok=True)

    dotenv_set_key(str(env_file), key, value)
    typer.echo(f"Set {key}={value}")


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
        typer.echo("No profiles found. Use 'sandbox config create-profile <name>' to create one.")


@app.command(name="create-profile")
def create_profile(
    name: str = typer.Argument(..., help="Profile name to create"),
    from_profile: Optional[str] = typer.Option(None, "--from", help="Copy from existing profile"),
) -> None:
    """Create a new environment profile."""
    data_dir = get_data_dir()
    profile_file = data_dir / f".env.{name}"

    if profile_file.exists():
        typer.echo(typer.style(f"error: Profile '{name}' already exists.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    if from_profile:
        source = data_dir / f".env.{from_profile}"
        if not source.exists():
            typer.echo(typer.style(f"error: Source profile '{from_profile}' not found.",
                                   fg=typer.colors.RED), err=True)
            raise typer.Exit(1)
        shutil.copy2(source, profile_file)
    else:
        profile_file.write_text(f"# Profile: {name}\n")

    typer.echo(f"Created profile '{name}' at {profile_file}")
    typer.echo(f"  Activate with: sandbox config set SANDBOX_ENV {name}")


@app.command()
def edit(
    project: Optional[str] = typer.Option(None, "--project", help="Edit project-specific config"),
) -> None:
    """Open configuration in editor."""
    if project:
        env_file = get_data_dir() / "projects" / project / ".env"
    else:
        env_file = config.ENV_FILE

    if not env_file.exists():
        typer.echo(typer.style(f"error: Config file not found: {env_file}",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(env_file)])


@app.command()
def export(
    output: str = typer.Option("sandbox-config.json", "--output", "-o", help="Output file"),
    include_secrets: bool = typer.Option(False, "--include-secrets", help="Include secrets in export"),
) -> None:
    """Export full configuration to a portable file."""
    data_dir = get_data_dir()
    env = load_env()
    tools = list_available_tools()
    mcp_servers = list_mcp_servers()
    mounts = load_mounts()

    export_data = {
        "env": {k: v for k, v in env.items() if k not in SENSITIVE_KEYS or include_secrets},
        "tools": tools,
        "mcp_servers": mcp_servers,
        "mounts": mounts,
    }

    if include_secrets:
        from cli.lib.secrets import get_provider
        provider = get_provider()
        keys = provider.list_keys()
        export_data["secrets"] = {k: provider.get(k) for k in keys}

    output_path = Path(output)
    output_path.write_text(json.dumps(export_data, indent=2) + "\n")
    typer.echo(f"Exported configuration to {output_path}")


@app.command(name="import")
def import_config(
    file: str = typer.Argument(..., help="Config file to import"),
) -> None:
    """Import configuration from an exported file."""
    input_path = Path(file)
    if not input_path.exists():
        typer.echo(typer.style(f"error: File not found: {file}",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    data = json.loads(input_path.read_text())
    data_dir = get_data_dir()

    if "env" in data:
        from dotenv import set_key as dotenv_set_key
        env_file = data_dir / ".env"
        env_file.parent.mkdir(parents=True, exist_ok=True)
        for key, value in data["env"].items():
            dotenv_set_key(str(env_file), key, value)
        typer.echo(f"  Imported {len(data['env'])} env vars")

    if "tools" in data:
        tools_dir = data_dir / "config" / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        for tool in data["tools"]:
            name = tool.get("name", "")
            if name:
                (tools_dir / f"{name}.yaml").write_text(yaml.dump(tool, default_flow_style=False))
        typer.echo(f"  Imported {len(data['tools'])} tool definitions")

    if "mcp_servers" in data:
        mcp_dir = data_dir / "config" / "mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)
        for server in data["mcp_servers"]:
            name = server.get("name", "")
            if name:
                (mcp_dir / f"{name}.yaml").write_text(yaml.dump(server, default_flow_style=False))
        typer.echo(f"  Imported {len(data['mcp_servers'])} MCP server definitions")

    if "secrets" in data:
        from cli.lib.secrets import get_provider
        provider = get_provider()
        for key, value in data["secrets"].items():
            provider.set(key, value)
        typer.echo(f"  Imported {len(data['secrets'])} secrets")

    typer.echo(typer.style("Import complete.", fg=typer.colors.GREEN))


@app.command()
def reset(
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Reset configuration to defaults."""
    if not confirm:
        typer.confirm("This will reset all configuration to defaults. Continue?", abort=True)

    from cli.lib.scaffold import scaffold
    scaffold(force=True)
    typer.echo(typer.style("Configuration reset to defaults.", fg=typer.colors.GREEN))
