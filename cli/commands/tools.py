"""Tool management commands."""

import os
import subprocess
from typing import Optional

import typer
import yaml

import cli.lib.config as config
from cli.lib.config import list_available_tools, load_tool_definition
from cli.lib.docker import exec_in_sandbox, is_running
from cli.lib.firewall import merge_tool_domains, read_whitelist, remove_domain, apply_rules

app = typer.Typer(no_args_is_help=True)

INSTALL_COMMANDS = {
    "npm": lambda pkg, global_: ["npm", "install"] + (["-g"] if global_ else []) + [pkg],
    "pip": lambda pkg, global_: ["pip", "install"] + ([] if global_ else ["--user"]) + [pkg],
}


@app.command(name="list")
def list_tools() -> None:
    """List available and installed tools."""
    tools = list_available_tools()
    if not tools:
        typer.echo("No tool definitions found in config/tools/.")
        return

    for tool in tools:
        default = typer.style(" (default)", fg=typer.colors.BLUE) if tool.get("default") else ""
        typer.echo(f"  {tool['name']}: {tool.get('description', '')}{default}")

        domains = tool.get("firewall", {}).get("domains", [])
        if domains:
            typer.echo(f"    domains: {', '.join(domains)}")

        env_vars = tool.get("env", {})
        if env_vars:
            typer.echo(f"    env: {', '.join(env_vars.keys())}")


@app.command()
def install(
    name: str = typer.Argument(..., help="Tool name to install"),
) -> None:
    """Install a tool into the sandbox."""
    definition = load_tool_definition(name)
    if not definition:
        typer.echo(typer.style(f"error: No tool definition found for '{name}'.",
                               fg=typer.colors.RED), err=True)
        typer.echo(f"Available definitions: {', '.join(t['name'] for t in list_available_tools())}")
        raise typer.Exit(1)

    if not is_running("sandbox"):
        typer.echo(typer.style("error: Sandbox is not running. Run 'sandbox start' first.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    install_cfg = definition.get("install", {})
    method = install_cfg.get("method")
    package = install_cfg.get("package")

    if not method or not package:
        typer.echo(typer.style("error: Tool definition missing install method or package.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    if method not in INSTALL_COMMANDS:
        typer.echo(typer.style(f"error: Unknown install method '{method}'.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    cmd = INSTALL_COMMANDS[method](package, install_cfg.get("global", False))
    typer.echo(f"Installing {name} via {method}...")
    exit_code, output = exec_in_sandbox(cmd)
    typer.echo(output)

    if exit_code != 0:
        typer.echo(typer.style(f"error: Installation failed (exit code {exit_code}).",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    domains = definition.get("firewall", {}).get("domains", [])
    if domains:
        typer.echo(f"Merging firewall domains: {', '.join(domains)}")
        merge_tool_domains(domains)
        if is_running("firewall"):
            apply_rules()

    typer.echo(typer.style(f"{name} installed successfully.", fg=typer.colors.GREEN))


@app.command()
def remove(
    name: str = typer.Argument(..., help="Tool name to remove"),
) -> None:
    """Remove a tool from the sandbox."""
    definition = load_tool_definition(name)
    if not definition:
        typer.echo(typer.style(f"error: No tool definition found for '{name}'.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    if not is_running("sandbox"):
        typer.echo(typer.style("error: Sandbox is not running. Run 'sandbox start' first.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    install_cfg = definition.get("install", {})
    method = install_cfg.get("method")
    package = install_cfg.get("package")

    if method == "npm":
        cmd = ["npm", "uninstall"] + (["-g"] if install_cfg.get("global") else []) + [package]
    elif method == "pip":
        cmd = ["pip", "uninstall", "-y", package]
    else:
        typer.echo(typer.style(f"error: Unknown install method '{method}'.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    typer.echo(f"Removing {name}...")
    exit_code, output = exec_in_sandbox(cmd)
    typer.echo(output)

    if exit_code != 0:
        typer.echo(typer.style(f"warning: Removal may have failed (exit code {exit_code}).",
                               fg=typer.colors.YELLOW), err=True)

    domains = definition.get("firewall", {}).get("domains", [])
    if domains:
        whitelist = read_whitelist()
        other_tool_domains = _get_all_tool_domains_except(name)
        for domain in domains:
            if domain not in other_tool_domains:
                remove_domain(domain)
        if is_running("firewall"):
            apply_rules()

    typer.echo(typer.style(f"{name} removed.", fg=typer.colors.GREEN))


@app.command()
def add(
    name: str = typer.Argument(..., help="Tool name"),
    method: str = typer.Option("npm", help="Install method: npm or pip"),
    package: str = typer.Option(..., help="Package name"),
    domains: Optional[str] = typer.Option(None, help="Comma-separated firewall domains"),
    env: Optional[str] = typer.Option(None, help="Comma-separated env vars (KEY=val,KEY2=val2)"),
    default: bool = typer.Option(False, "--default", help="Set as default tool"),
) -> None:
    """Create a new tool definition."""
    tool_file = config.TOOLS_DIR / f"{name}.yaml"
    if tool_file.exists():
        typer.echo(typer.style(f"error: Tool '{name}' already exists.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    definition = {
        "name": name,
        "description": "",
        "default": default,
        "install": {"method": method, "package": package, "global": method == "npm"},
        "firewall": {"domains": domains.split(",") if domains else []},
        "env": {},
        "mcp": {"config_path": ""},
        "volumes": [],
    }

    if env:
        for pair in env.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                definition["env"][k.strip()] = v.strip()

    config.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    tool_file.write_text(yaml.dump(definition, default_flow_style=False))
    typer.echo(f"Created tool definition: {tool_file}")


@app.command()
def edit(
    name: str = typer.Argument(..., help="Tool name to edit"),
) -> None:
    """Open a tool definition in editor."""
    tool_file = config.TOOLS_DIR / f"{name}.yaml"
    if not tool_file.exists():
        typer.echo(typer.style(f"error: Tool '{name}' not found.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(tool_file)])


@app.command()
def show(
    name: str = typer.Argument(..., help="Tool name to display"),
) -> None:
    """Display full tool definition."""
    definition = load_tool_definition(name)
    if not definition:
        typer.echo(typer.style(f"error: Tool '{name}' not found.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    typer.echo(yaml.dump(definition, default_flow_style=False).rstrip())


def _get_all_tool_domains_except(exclude_name: str) -> set[str]:
    """Get domains from all tools except the named one."""
    domains = set()
    for tool in list_available_tools():
        if tool["name"] != exclude_name:
            for d in tool.get("firewall", {}).get("domains", []):
                domains.add(d)
    return domains
