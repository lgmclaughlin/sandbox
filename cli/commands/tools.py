"""Tool management commands."""

import os
import subprocess
from typing import Optional

import typer
import yaml

import cli.lib.config as config
from cli.lib.config import list_available_tools, load_tool_definition
from cli.lib.docker import copy_to_container, exec_in_sandbox, is_running
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
        tags = []
        if tool.get("default"):
            tags.append(typer.style("default", fg=typer.colors.BLUE))
        if tool.get("install", {}).get("auto"):
            tags.append(typer.style("auto", fg=typer.colors.CYAN))
        suffix = f" ({', '.join(tags)})" if tags else ""
        typer.echo(f"  {tool['name']}: {tool.get('description', '')}{suffix}")

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
    auto: bool = typer.Option(False, "--auto", help="Auto-install on sandbox start"),
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
        "install": {"method": method, "package": package, "global": method == "npm", "auto": auto},
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


@app.command()
def auth(
    name: str = typer.Argument(..., help="Tool name to authenticate"),
) -> None:
    """Authenticate a tool on the host and sync credentials to the container."""
    import shutil
    from pathlib import Path

    definition = load_tool_definition(name)
    if not definition:
        typer.echo(typer.style(f"error: No tool definition found for '{name}'.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    auth_cfg = definition.get("auth")
    if not auth_cfg:
        typer.echo(typer.style(f"error: Tool '{name}' has no auth configuration.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    host_cmd = auth_cfg.get("command", "")
    if not host_cmd:
        typer.echo(typer.style("error: Auth config missing 'command'.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    binary = host_cmd.split()[0]
    if not shutil.which(binary):
        typer.echo(typer.style(
            f"error: '{binary}' not found on the host. Install it first to authenticate.",
            fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    if not is_running("sandbox"):
        typer.echo(typer.style("error: Sandbox is not running. Run 'sandbox start' first.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    typer.echo(f"Running '{host_cmd}' on host...")
    result = subprocess.run(host_cmd.split(), stdin=None)
    if result.returncode != 0:
        typer.echo(typer.style(f"error: Auth command failed (exit {result.returncode}).",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    sync_cfg = auth_cfg.get("sync", {})
    host_dir = sync_cfg.get("host", "")
    container_dir = sync_cfg.get("container", "")

    if not host_dir or not container_dir:
        typer.echo(typer.style("error: Auth config missing sync paths.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    host_path = Path(host_dir).expanduser()
    if not host_path.exists():
        typer.echo(typer.style(f"error: Host credential path not found: {host_path}",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    # Filter to only credential files if specified, otherwise sync all
    files_filter = sync_cfg.get("files")

    if files_filter:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for pattern in files_filter:
                for match in host_path.glob(pattern):
                    if match.is_file():
                        dest = tmp_path / match.name
                        shutil.copy2(str(match), str(dest))

            if not any(tmp_path.iterdir()):
                typer.echo(typer.style("warning: No credential files matched the filter.",
                                       fg=typer.colors.YELLOW))
                raise typer.Exit(1)

            typer.echo(f"Syncing credentials to container:{container_dir}...")
            ok = copy_to_container(tmp_path, container_dir)
    else:
        typer.echo(f"Syncing {host_path} to container:{container_dir}...")
        ok = copy_to_container(host_path, container_dir)

    if ok:
        # Fix ownership inside container (files arrive as root from docker cp)
        exec_in_sandbox(["bash", "-c", f"chown -R $(id -u):$(id -g) {container_dir}"])
        typer.echo(typer.style(f"Credentials synced for {name}.", fg=typer.colors.GREEN))
    else:
        typer.echo(typer.style("error: Failed to copy credentials to container.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)


def auto_install_tools() -> list[dict]:
    """Install tools marked with auto: true that aren't already installed.

    Returns list of results: [{"name": ..., "ok": bool, "error": str}]
    """
    results = []
    for tool in list_available_tools():
        install_cfg = tool.get("install", {})
        if not install_cfg.get("auto"):
            continue

        name = tool["name"]
        method = install_cfg.get("method")
        package = install_cfg.get("package")

        if not method or not package:
            continue

        if _is_tool_installed(method, package):
            continue

        if method not in INSTALL_COMMANDS:
            results.append({"name": name, "ok": False, "error": f"Unknown method '{method}'"})
            continue

        cmd = INSTALL_COMMANDS[method](package, install_cfg.get("global", False))
        exit_code, output = exec_in_sandbox(cmd)

        if exit_code == 0:
            results.append({"name": name, "ok": True, "error": ""})
        else:
            results.append({"name": name, "ok": False, "error": output.strip().split("\n")[-1]})

    return results


def _is_tool_installed(method: str, package: str) -> bool:
    """Check if a tool package is already installed in the container."""
    if method == "npm":
        cmd = ["npm", "list", "-g", "--depth=0", package]
    elif method == "pip":
        cmd = ["pip", "show", package]
    else:
        return False

    exit_code, _ = exec_in_sandbox(cmd)
    return exit_code == 0


def _get_all_tool_domains_except(exclude_name: str) -> set[str]:
    """Get domains from all tools except the named one."""
    domains = set()
    for tool in list_available_tools():
        if tool["name"] != exclude_name:
            for d in tool.get("firewall", {}).get("domains", []):
                domains.add(d)
    return domains
