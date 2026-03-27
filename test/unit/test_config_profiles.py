"""Unit tests for environment profile merging."""

from cli.lib.config import get_active_profile, load_env


class TestProfileMerging:
    def test_no_profile(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("COMPOSE_PROJECT_NAME=test\n")
        dist_file = tmp_path / ".env.dist"

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist_file)
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        env = load_env()
        assert env["COMPOSE_PROJECT_NAME"] == "test"

    def test_profile_overrides(self, tmp_path, monkeypatch):
        dist = tmp_path / ".env.dist"
        dist.write_text("COMPOSE_PROJECT_NAME=default\nSANDBOX_LOG_FORMAT=text\n")
        env_file = tmp_path / ".env"
        env_file.write_text("SANDBOX_ENV=corp\n")
        corp_file = tmp_path / ".env.corp"
        corp_file.write_text("SANDBOX_LOG_FORMAT=json\nCUSTOM_VAR=corporate\n")

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        env = load_env()
        assert env["SANDBOX_LOG_FORMAT"] == "json"
        assert env["CUSTOM_VAR"] == "corporate"
        assert env["COMPOSE_PROJECT_NAME"] == "default"

    def test_env_var_override(self, tmp_path, monkeypatch):
        dist = tmp_path / ".env.dist"
        dist.write_text("SANDBOX_LOG_FORMAT=text\n")
        env_file = tmp_path / ".env"
        env_file.write_text("")
        dev_file = tmp_path / ".env.dev"
        dev_file.write_text("SANDBOX_LOG_FORMAT=json\n")

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_path)
        monkeypatch.setenv("SANDBOX_ENV", "dev")

        env = load_env()
        assert env["SANDBOX_LOG_FORMAT"] == "json"

    def test_missing_profile_file(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("SANDBOX_ENV=nonexistent\nFOO=bar\n")
        dist = tmp_path / ".env.dist"

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        env = load_env()
        assert env["FOO"] == "bar"

    def test_merge_order_dist_then_env_then_profile(self, tmp_path, monkeypatch):
        dist = tmp_path / ".env.dist"
        dist.write_text("A=from_dist\nB=from_dist\nC=from_dist\n")
        env_file = tmp_path / ".env"
        env_file.write_text("B=from_env\nSANDBOX_ENV=test\n")
        profile = tmp_path / ".env.test"
        profile.write_text("C=from_profile\n")

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        env = load_env()
        assert env["A"] == "from_dist"
        assert env["B"] == "from_env"
        assert env["C"] == "from_profile"


class TestGetActiveProfile:
    def test_returns_profile(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("SANDBOX_ENV=corp\n")
        dist = tmp_path / ".env.dist"

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        assert get_active_profile() == "corp"

    def test_returns_empty(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\n")
        dist = tmp_path / ".env.dist"

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        assert get_active_profile() == ""
