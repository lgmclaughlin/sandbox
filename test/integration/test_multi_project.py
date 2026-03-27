"""Integration tests for multi-project isolation."""

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
    PROJECTS_DIR,
)


class TestProjectInit:
    def test_init_creates_structure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.project.PROJECTS_DIR", tmp_path / "projects")
        monkeypatch.setattr("cli.lib.project.PROJECT_ROOT", tmp_path)

        dist = tmp_path / ".env.dist"
        dist.write_text("COMPOSE_PROJECT_NAME=project\nTZ=\n")

        (tmp_path / "config" / "tools").mkdir(parents=True)
        (tmp_path / "config" / "tools" / "claude.yaml").write_text(
            "name: claude\ndefault: true\n"
        )
        (tmp_path / "config" / "mcp").mkdir(parents=True)

        path = init_project("my-project")

        assert path.exists()
        assert (path / ".env").exists()
        assert (path / "workspace").exists()
        assert (path / "config" / "tools").exists()
        assert (path / "config" / "mcp").exists()
        assert (path / "logs" / "sessions").exists()
        assert (path / "logs" / "commands").exists()
        assert (path / "config" / "mounts.yaml").exists()

    def test_init_sets_project_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.project.PROJECTS_DIR", tmp_path / "projects")
        monkeypatch.setattr("cli.lib.project.PROJECT_ROOT", tmp_path)

        dist = tmp_path / ".env.dist"
        dist.write_text("COMPOSE_PROJECT_NAME=project\n")
        (tmp_path / "config" / "tools").mkdir(parents=True)
        (tmp_path / "config" / "mcp").mkdir(parents=True)

        path = init_project("billing")

        env_content = (path / ".env").read_text()
        assert "COMPOSE_PROJECT_NAME=billing" in env_content

    def test_init_duplicate_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.project.PROJECTS_DIR", tmp_path / "projects")
        monkeypatch.setattr("cli.lib.project.PROJECT_ROOT", tmp_path)

        dist = tmp_path / ".env.dist"
        dist.write_text("COMPOSE_PROJECT_NAME=project\n")
        (tmp_path / "config" / "tools").mkdir(parents=True)
        (tmp_path / "config" / "mcp").mkdir(parents=True)

        init_project("first")
        try:
            init_project("first")
            assert False, "Should have raised"
        except ValueError as e:
            assert "already exists" in str(e)

    def test_init_with_workspace(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.project.PROJECTS_DIR", tmp_path / "projects")
        monkeypatch.setattr("cli.lib.project.PROJECT_ROOT", tmp_path)

        dist = tmp_path / ".env.dist"
        dist.write_text("COMPOSE_PROJECT_NAME=project\n")
        (tmp_path / "config" / "tools").mkdir(parents=True)
        (tmp_path / "config" / "mcp").mkdir(parents=True)

        ext_workspace = tmp_path / "external" / "code"
        ext_workspace.mkdir(parents=True)

        path = init_project("custom", workspace=str(ext_workspace))

        assert not (path / "workspace").exists()
        env_content = (path / ".env").read_text()
        assert str(ext_workspace) in env_content

    def test_init_with_bad_workspace(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.project.PROJECTS_DIR", tmp_path / "projects")
        monkeypatch.setattr("cli.lib.project.PROJECT_ROOT", tmp_path)

        dist = tmp_path / ".env.dist"
        dist.write_text("COMPOSE_PROJECT_NAME=project\n")
        (tmp_path / "config" / "tools").mkdir(parents=True)
        (tmp_path / "config" / "mcp").mkdir(parents=True)

        try:
            init_project("bad", workspace="/nonexistent/path")
            assert False, "Should have raised"
        except ValueError as e:
            assert "not found" in str(e)


class TestProjectList:
    def test_lists_projects(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.project.PROJECTS_DIR", tmp_path / "projects")
        monkeypatch.setattr("cli.lib.project.PROJECT_ROOT", tmp_path)

        dist = tmp_path / ".env.dist"
        dist.write_text("COMPOSE_PROJECT_NAME=project\n")
        (tmp_path / "config" / "tools").mkdir(parents=True)
        (tmp_path / "config" / "mcp").mkdir(parents=True)

        init_project("alpha")
        init_project("beta")

        projects = list_projects()
        names = [p["name"] for p in projects]
        assert "alpha" in names
        assert "beta" in names

    def test_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.project.PROJECTS_DIR", tmp_path / "projects")
        assert list_projects() == []


class TestProjectIsolation:
    def test_config_paths_switch(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.project.PROJECTS_DIR", tmp_path / "projects")
        monkeypatch.setattr("cli.lib.project.PROJECT_ROOT", tmp_path)

        dist = tmp_path / ".env.dist"
        dist.write_text("COMPOSE_PROJECT_NAME=project\n")
        (tmp_path / "config" / "tools").mkdir(parents=True)
        (tmp_path / "config" / "mcp").mkdir(parents=True)

        init_project("proj-a")

        # Temporarily set PROJECT_ROOT so set_active_project resolves to tmp_path
        import cli.lib.config as config_mod
        original_root = config_mod.PROJECT_ROOT
        config_mod.PROJECT_ROOT = tmp_path

        try:
            set_active_project("proj-a")
            assert "proj-a" in str(config_mod.CONFIG_DIR)
            assert "proj-a" in str(config_mod.TOOLS_DIR)
            assert "proj-a" in str(config_mod.ENV_FILE)
            assert "proj-a" in str(config_mod.DEFAULT_LOG_DIR)
        finally:
            config_mod.PROJECT_ROOT = original_root
            set_active_project("")
