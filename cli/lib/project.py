"""Multi-project management."""

import os
import shutil
from pathlib import Path

from cli.lib.config import PROJECT_ROOT

PROJECTS_DIR = PROJECT_ROOT / "projects"


def list_projects() -> list[dict]:
    """List all initialized projects."""
    if not PROJECTS_DIR.exists():
        return []

    projects = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if d.is_dir() and (d / ".env").exists():
            projects.append({
                "name": d.name,
                "path": d,
                "has_workspace": (d / "workspace").exists(),
                "has_config": (d / "config").exists(),
            })
    return projects


def get_active_project() -> str:
    """Determine the active project name.

    Resolution order:
    1. SANDBOX_PROJECT env var
    2. Current working directory (if inside a project dir)
    3. Empty string (use root-level config, backward compatible)
    """
    from_env = os.environ.get("SANDBOX_PROJECT", "")
    if from_env:
        return from_env

    cwd = Path.cwd()
    if PROJECTS_DIR.exists():
        try:
            rel = cwd.relative_to(PROJECTS_DIR)
            return rel.parts[0] if rel.parts else ""
        except ValueError:
            pass

    return ""


def get_project_dir(name: str) -> Path:
    """Get the directory for a named project."""
    return PROJECTS_DIR / name


def get_project_paths(name: str = "") -> dict[str, Path]:
    """Get all paths for a project. Empty name uses root-level paths."""
    if not name:
        return {
            "root": PROJECT_ROOT,
            "env": PROJECT_ROOT / ".env",
            "env_dist": PROJECT_ROOT / ".env.dist",
            "config": PROJECT_ROOT / "config",
            "tools": PROJECT_ROOT / "config" / "tools",
            "mcp": PROJECT_ROOT / "config" / "mcp",
            "mounts": PROJECT_ROOT / "config" / "mounts.yaml",
            "workspace": PROJECT_ROOT / "workspace",
            "logs": PROJECT_ROOT / "logs",
            "secrets": PROJECT_ROOT / ".secrets",
        }

    project_dir = PROJECTS_DIR / name
    return {
        "root": project_dir,
        "env": project_dir / ".env",
        "env_dist": PROJECT_ROOT / ".env.dist",
        "config": project_dir / "config",
        "tools": project_dir / "config" / "tools",
        "mcp": project_dir / "config" / "mcp",
        "mounts": project_dir / "config" / "mounts.yaml",
        "workspace": project_dir / "workspace",
        "logs": project_dir / "logs",
        "secrets": project_dir / ".secrets",
    }


def init_project(name: str, workspace: str | None = None) -> Path:
    """Initialize a new project directory with scaffolding."""
    project_dir = PROJECTS_DIR / name

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
    else:
        (project_dir / "workspace").mkdir()

    dist_file = PROJECT_ROOT / ".env.dist"
    if dist_file.exists():
        env_content = dist_file.read_text()
        env_content = env_content.replace(
            "COMPOSE_PROJECT_NAME=project",
            f"COMPOSE_PROJECT_NAME={name}",
        )
        if workspace_path:
            env_content += f"\nSANDBOX_WORKSPACE_DIR={workspace_path}\n"
        (project_dir / ".env").write_text(env_content)

    root_tools = PROJECT_ROOT / "config" / "tools"
    if root_tools.exists():
        for tool_file in root_tools.glob("*.yaml"):
            shutil.copy2(tool_file, project_dir / "config" / "tools" / tool_file.name)

    root_mcp = PROJECT_ROOT / "config" / "mcp"
    if root_mcp.exists():
        for mcp_file in root_mcp.glob("*.yaml"):
            shutil.copy2(mcp_file, project_dir / "config" / "mcp" / mcp_file.name)

    return project_dir
