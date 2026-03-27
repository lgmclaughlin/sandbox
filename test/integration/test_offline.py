"""Integration tests for offline mode."""

from cli.lib.config import load_env


class TestOfflineConfig:
    def test_offline_mode_default_false(self, tmp_path, monkeypatch):
        dist = tmp_path / ".env.dist"
        dist.write_text("SANDBOX_OFFLINE_MODE=false\n")
        env_file = tmp_path / ".env"

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_path)

        env = load_env()
        assert env.get("SANDBOX_OFFLINE_MODE") == "false"

    def test_offline_mode_enabled(self, tmp_path, monkeypatch):
        dist = tmp_path / ".env.dist"
        dist.write_text("SANDBOX_OFFLINE_MODE=false\n")
        env_file = tmp_path / ".env"
        env_file.write_text("SANDBOX_OFFLINE_MODE=true\n")

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_path)

        env = load_env()
        assert env.get("SANDBOX_OFFLINE_MODE") == "true"

    def test_offline_flag_detected(self, tmp_path, monkeypatch):
        dist = tmp_path / ".env.dist"
        dist.write_text("SANDBOX_OFFLINE_MODE=true\n")
        env_file = tmp_path / ".env"

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)
        monkeypatch.setattr("cli.lib.config.PROJECT_ROOT", tmp_path)

        env = load_env()
        offline = env.get("SANDBOX_OFFLINE_MODE", "").lower() == "true"
        assert offline is True
