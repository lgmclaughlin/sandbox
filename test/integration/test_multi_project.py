"""Integration tests for multi-project isolation."""

import pytest
from pathlib import Path

from cli.lib.config import (
    load_env,
    load_mounts,
    list_available_tools,
    set_active_project,
)
from cli.lib.project import (
    get_project_dir,
    init_project,
    list_projects,
)


@pytest.fixture
def mp_setup(tmp_path, monkeypatch):
    """Set up multi-project test environment."""
    monkeypatch.setattr("cli.lib.paths.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("cli.lib.project.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("cli.lib.config.get_data_dir", lambda: tmp_path)

    # Re-init config paths
    from cli.lib.config import _init_paths
    _init_paths()

    dist = tmp_path / ".env.dist"
    dist.write_text("COMPOSE_PROJECT_NAME=project\nTZ=\n")

    (tmp_path / "config" / "tools").mkdir(parents=True)
    (tmp_path / "config" / "tools" / "claude.yaml").write_text(
        "name: claude\ndefault: true\n"
    )
    (tmp_path / "config" / "mcp").mkdir(parents=True)

    return tmp_path


class TestProjectInit:
    def test_init_creates_structure(self, mp_setup):
        path = init_project("my-project")

        assert path.exists()
        assert (path / ".env").exists()
        assert (path / "config" / "tools").exists()
        assert (path / "config" / "mcp").exists()
        assert (path / "logs" / "sessions").exists()
        assert (path / "logs" / "commands").exists()
        assert (path / "config" / "mounts.yaml").exists()

    def test_init_sets_project_name(self, mp_setup):
        path = init_project("billing")

        env_content = (path / ".env").read_text()
        assert "COMPOSE_PROJECT_NAME=billing" in env_content

    def test_init_duplicate_fails(self, mp_setup):
        init_project("first")
        with pytest.raises(ValueError, match="already exists"):
            init_project("first")

    def test_init_with_workspace(self, mp_setup, tmp_path):
        ext_workspace = tmp_path / "external" / "code"
        ext_workspace.mkdir(parents=True)

        path = init_project("custom", workspace=str(ext_workspace))

        env_content = (path / ".env").read_text()
        assert str(ext_workspace) in env_content

    def test_init_with_bad_workspace(self, mp_setup):
        with pytest.raises(ValueError, match="not found"):
            init_project("bad", workspace="/nonexistent/path")


class TestProjectList:
    def test_lists_projects(self, mp_setup):
        init_project("alpha")
        init_project("beta")

        projects = list_projects()
        names = [p["name"] for p in projects]
        assert "alpha" in names
        assert "beta" in names

    def test_empty(self, mp_setup):
        assert list_projects() == []


class TestProjectIsolation:
    def test_config_paths_switch(self, mp_setup):
        init_project("proj-a")

        set_active_project("proj-a")

        from cli.lib.config import CONFIG_DIR, TOOLS_DIR, ENV_FILE, DEFAULT_LOG_DIR
        assert "proj-a" in str(CONFIG_DIR)
        assert "proj-a" in str(TOOLS_DIR)
        assert "proj-a" in str(ENV_FILE)
        assert "proj-a" in str(DEFAULT_LOG_DIR)

        set_active_project("")
