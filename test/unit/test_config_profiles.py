"""Unit tests for environment profile merging."""

from cli.lib.config import get_active_profile, load_env


def _patch_config(monkeypatch, tmp_path):
    """Patch config to use tmp_path for all path resolution."""
    monkeypatch.setattr("cli.lib.config.ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", tmp_path / ".env.dist")
    monkeypatch.setattr("cli.lib.config._active_project", "")
    monkeypatch.setattr("cli.lib.config.get_data_dir", lambda: tmp_path)


class TestProfileMerging:
    def test_no_profile(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("COMPOSE_PROJECT_NAME=test\n")
        _patch_config(monkeypatch, tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        env = load_env()
        assert env["COMPOSE_PROJECT_NAME"] == "test"

    def test_profile_overrides(self, tmp_path, monkeypatch):
        (tmp_path / ".env.dist").write_text("COMPOSE_PROJECT_NAME=default\nSANDBOX_LOG_FORMAT=text\n")
        (tmp_path / ".env").write_text("SANDBOX_ENV=corp\n")
        (tmp_path / ".env.corp").write_text("SANDBOX_LOG_FORMAT=json\nCUSTOM_VAR=corporate\n")

        _patch_config(monkeypatch, tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        env = load_env()
        assert env["SANDBOX_LOG_FORMAT"] == "json"
        assert env["CUSTOM_VAR"] == "corporate"
        assert env["COMPOSE_PROJECT_NAME"] == "default"

    def test_env_var_override(self, tmp_path, monkeypatch):
        (tmp_path / ".env.dist").write_text("SANDBOX_LOG_FORMAT=text\n")
        (tmp_path / ".env").write_text("")
        (tmp_path / ".env.dev").write_text("SANDBOX_LOG_FORMAT=json\n")

        _patch_config(monkeypatch, tmp_path)
        monkeypatch.setenv("SANDBOX_ENV", "dev")

        env = load_env()
        assert env["SANDBOX_LOG_FORMAT"] == "json"

    def test_missing_profile_file(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("SANDBOX_ENV=nonexistent\nFOO=bar\n")

        _patch_config(monkeypatch, tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        env = load_env()
        assert env["FOO"] == "bar"

    def test_merge_order_dist_then_env_then_profile(self, tmp_path, monkeypatch):
        (tmp_path / ".env.dist").write_text("A=from_dist\nB=from_dist\nC=from_dist\n")
        (tmp_path / ".env").write_text("B=from_env\nSANDBOX_ENV=test\n")
        (tmp_path / ".env.test").write_text("C=from_profile\n")

        _patch_config(monkeypatch, tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        env = load_env()
        assert env["A"] == "from_dist"
        assert env["B"] == "from_env"
        assert env["C"] == "from_profile"


class TestGetActiveProfile:
    def test_returns_profile(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("SANDBOX_ENV=corp\n")

        _patch_config(monkeypatch, tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        assert get_active_profile() == "corp"

    def test_returns_empty(self, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("FOO=bar\n")

        _patch_config(monkeypatch, tmp_path)
        monkeypatch.delenv("SANDBOX_ENV", raising=False)

        assert get_active_profile() == ""
