"""Content inspection rule management commands."""

import typer
import yaml

from cli.lib.config import get_config_root

app = typer.Typer(no_args_is_help=True)


def _inspection_file():
    return get_config_root() / "network" / "inspection.yaml"


def _load_rules() -> list[dict]:
    """Load inspection rules."""
    path = _inspection_file()
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text())
    if not data:
        return []
    return data.get("rules", [])


def _save_rules(rules: list[dict]) -> None:
    """Save inspection rules."""
    path = _inspection_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump({"rules": rules}, default_flow_style=False))


@app.command(name="list")
def list_rules() -> None:
    """List content inspection rules."""
    rules = _load_rules()
    if not rules:
        typer.echo("No inspection rules configured.")
        return

    for rule in rules:
        name = rule.get("name", "unnamed")
        pattern = rule.get("pattern", "?")
        action = rule.get("action", "alert")
        color = typer.colors.RED if action == "block" else typer.colors.YELLOW
        action_styled = typer.style(action, fg=color)
        typer.echo(f"  {name}: /{pattern}/ [{action_styled}]")


@app.command()
def add(
    name: str = typer.Argument(..., help="Rule name"),
    pattern: str = typer.Option(..., help="Regex pattern to match"),
    action: str = typer.Option("alert", help="Action: alert or block"),
) -> None:
    """Add a content inspection rule."""
    if action not in ("alert", "block"):
        typer.echo(typer.style("error: Action must be 'alert' or 'block'.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    rules = _load_rules()

    if any(r.get("name") == name for r in rules):
        typer.echo(typer.style(f"error: Rule '{name}' already exists.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    rules.append({"name": name, "pattern": pattern, "action": action})
    _save_rules(rules)
    typer.echo(f"Added inspection rule '{name}'.")


@app.command()
def remove(
    name: str = typer.Argument(..., help="Rule name to remove"),
) -> None:
    """Remove a content inspection rule."""
    rules = _load_rules()
    original_len = len(rules)
    rules = [r for r in rules if r.get("name") != name]

    if len(rules) == original_len:
        typer.echo(typer.style(f"error: Rule '{name}' not found.",
                               fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    _save_rules(rules)
    typer.echo(f"Removed inspection rule '{name}'.")
