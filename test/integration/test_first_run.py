"""Integration tests for the first-run flow."""

from cli.lib.config import (
    ensure_config_dirs,
    ensure_env,
    ensure_mounts_config,
    load_env,
    load_mounts,
)


class TestFirstRunFlow:
    def test_ensure_env_creates_from_dist(self, tmp_project, monkeypatch):
        env_file = tmp_project / ".env"
        dist_file = tmp_project / ".env.dist"

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist_file)

        assert not env_file.exists()
        env = ensure_env()
        assert env_file.exists()
        assert "COMPOSE_PROJECT_NAME" in env

    def test_ensure_config_dirs_creates_structure(self, tmp_project, monkeypatch):
        log_dir = tmp_project / "logs"
        monkeypatch.setattr("cli.lib.config.CONFIG_DIR", tmp_project / "config")
        monkeypatch.setattr("cli.lib.config.TOOLS_DIR", tmp_project / "config" / "tools")
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_project)
        monkeypatch.setattr("cli.lib.config.DEFAULT_LOG_DIR", log_dir)
        monkeypatch.setattr("cli.lib.config.ENV_FILE", tmp_project / ".env")
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", tmp_project / ".env.dist")

        ensure_config_dirs()

        assert (tmp_project / "config").is_dir()
        assert (tmp_project / "config" / "tools").is_dir()
        assert log_dir.is_dir()
        assert (log_dir / "sessions").is_dir()
        assert (log_dir / "commands").is_dir()

    def test_ensure_mounts_creates_empty(self, tmp_project, monkeypatch):
        mounts_file = tmp_project / "config" / "mounts.yaml"
        monkeypatch.setattr("cli.lib.config.MOUNTS_FILE", mounts_file)

        ensure_mounts_config()
        assert mounts_file.exists()

        monkeypatch.setattr("cli.lib.config.MOUNTS_FILE", mounts_file)
        assert load_mounts() == []

    def test_full_first_run_idempotent(self, tmp_project, monkeypatch):
        env_file = tmp_project / ".env"
        dist_file = tmp_project / ".env.dist"
        mounts_file = tmp_project / "config" / "mounts.yaml"
        log_dir = tmp_project / "logs"

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist_file)
        monkeypatch.setattr("cli.lib.config.CONFIG_DIR", tmp_project / "config")
        monkeypatch.setattr("cli.lib.config.TOOLS_DIR", tmp_project / "config" / "tools")
        monkeypatch.setattr("cli.lib.config.MOUNTS_FILE", mounts_file)
        monkeypatch.setattr("cli.lib.config.DEFAULT_LOG_DIR", log_dir)

        # First run
        ensure_env()
        ensure_config_dirs()
        ensure_mounts_config()

        env1 = load_env()

        # Second run (idempotent)
        ensure_env()
        ensure_config_dirs()
        ensure_mounts_config()

        env2 = load_env()

        assert env1 == env2
