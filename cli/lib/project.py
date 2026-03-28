"""Multi-project management."""

import os
import shutil
from pathlib import Path

from cli.lib.paths import get_data_dir


def _projects_dir() -> Path:
    return get_data_dir() / "projects"


def list_projects() -> list[dict]:
    """List all initialized projects."""
    projects_dir = _projects_dir()
    if not projects_dir.exists():
        return []

    projects = []
    for d in sorted(projects_dir.iterdir()):
        if d.is_dir() and (d / ".env").exists():
            projects.append({
                "name": d.name,
                "path": d,
                "has_config": (d / "config").exists(),
            })
    return projects


def get_active_project() -> str:
    """Determine the active project name.

    Resolution order:
    1. SANDBOX_PROJECT env var
    2. Current working directory (if inside a project dir)
    3. Empty string (use default config)
    """
    from_env = os.environ.get("SANDBOX_PROJECT", "")
    if from_env:
        return from_env

    cwd = Path.cwd()
    projects_dir = _projects_dir()
    if projects_dir.exists():
        try:
            rel = cwd.relative_to(projects_dir)
            return rel.parts[0] if rel.parts else ""
        except ValueError:
            pass

    return ""


def get_project_dir(name: str) -> Path:
    """Get the directory for a named project."""
    return _projects_dir() / name


def get_project_paths(name: str = "") -> dict[str, Path]:
    """Get all paths for a project. Empty name uses default paths."""
    data_dir = get_data_dir()

    if not name:
        return {
            "root": data_dir,
            "env": data_dir / ".env",
            "env_dist": data_dir / ".env.dist",
            "config": data_dir / "config",
            "tools": data_dir / "config" / "tools",
            "mcp": data_dir / "config" / "mcp",
            "mounts": data_dir / "config" / "mounts.yaml",
            "logs": data_dir / "logs",
            "secrets": data_dir / ".secrets",
        }

    project_dir = _projects_dir() / name
    return {
        "root": project_dir,
        "env": project_dir / ".env",
        "env_dist": data_dir / ".env.dist",
        "config": project_dir / "config",
        "tools": project_dir / "config" / "tools",
        "mcp": project_dir / "config" / "mcp",
        "mounts": project_dir / "config" / "mounts.yaml",
        "logs": project_dir / "logs",
        "secrets": project_dir / ".secrets",
    }


def init_project(name: str, workspace: str | None = None) -> Path:
    """Initialize a new project directory with scaffolding."""
    _validate_project_name(name)
    data_dir = get_data_dir()
    project_dir = _projects_dir() / name

    if project_dir.exists():
        raise ValueError(f"Project '{name}' already exists")

    project_dir.mkdir(parents=True)
    (project_dir / "config" / "tools").mkdir(parents=True)
    (project_dir / "config" / "mcp").mkdir(parents=True)
    (project_dir / "logs" / "sessions").mkdir(parents=True)
    (project_dir / "logs" / "commands").mkdir(parents=True)
    (project_dir / "config" / "mounts.yaml").write_text("mounts: []\n")

    workspace_path = Path(workspace).resolve() if workspace else None

    if workspace_path:
        if not workspace_path.is_dir():
            raise ValueError(f"Workspace directory not found: {workspace_path}")

    dist_file = data_dir / ".env.dist"
    if dist_file.exists():
        env_content = dist_file.read_text()
        env_content = env_content.replace(
            "COMPOSE_PROJECT_NAME=project",
            f"COMPOSE_PROJECT_NAME={name}",
        )
        if workspace_path:
            env_content += f"\nSANDBOX_WORKSPACE_DIR={workspace_path}\n"
        (project_dir / ".env").write_text(env_content)

    root_tools = data_dir / "config" / "tools"
    if root_tools.exists():
        for tool_file in root_tools.glob("*.yaml"):
            shutil.copy2(tool_file, project_dir / "config" / "tools" / tool_file.name)

    root_mcp = data_dir / "config" / "mcp"
    if root_mcp.exists():
        for mcp_file in root_mcp.glob("*.yaml"):
            shutil.copy2(mcp_file, project_dir / "config" / "mcp" / mcp_file.name)

    return project_dir


def _validate_project_name(name: str) -> None:
    """Validate project name is safe (no path traversal)."""
    if not name or "/" in name or "\\" in name or name.startswith(".") or ".." in name:
        raise ValueError(f"Invalid project name: '{name}'")


def remove_project(name: str) -> None:
    """Remove a project directory and all its contents."""
    _validate_project_name(name)
    project_dir = _projects_dir() / name

    # Safety check: resolved path must be inside projects directory
    if not project_dir.resolve().is_relative_to(_projects_dir().resolve()):
        raise ValueError(f"Invalid project path: '{name}'")

    if not project_dir.exists():
        raise ValueError(f"Project '{name}' not found")
    shutil.rmtree(project_dir)
