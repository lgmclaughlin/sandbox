"""Tool management commands."""

import typer

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


def _get_all_tool_domains_except(exclude_name: str) -> set[str]:
    """Get domains from all tools except the named one."""
    domains = set()
    for tool in list_available_tools():
        if tool["name"] != exclude_name:
            for d in tool.get("firewall", {}).get("domains", []):
                domains.add(d)
    return domains
