"""Unit tests for config CLI commands."""

import json

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


class TestConfigShow:
    def test_show_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
        from cli.lib.scaffold import scaffold
        scaffold()
        from cli.lib.config import _init_paths
        _init_paths()

        result = runner.invoke(app, ["config", "show", "--path"])
        assert result.exit_code == 0
        assert str(tmp_path) in result.output

    def test_show_config(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
        from cli.lib.scaffold import scaffold
        scaffold()
        from cli.lib.config import _init_paths
        _init_paths()

        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "COMPOSE_PROJECT_NAME" in result.output


class TestConfigGetSet:
    def test_get_existing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
        from cli.lib.scaffold import scaffold
        scaffold()
        from cli.lib.config import _init_paths
        _init_paths()

        result = runner.invoke(app, ["config", "get", "COMPOSE_PROJECT_NAME"])
        assert result.exit_code == 0
        assert "project" in result.output

    def test_get_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
        from cli.lib.scaffold import scaffold
        scaffold()
        from cli.lib.config import _init_paths
        _init_paths()

        result = runner.invoke(app, ["config", "get", "NONEXISTENT_KEY"])
        assert result.exit_code != 0

    def test_set_writes_value(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
        from cli.lib.scaffold import scaffold
        scaffold()

        result = runner.invoke(app, ["config", "set", "SANDBOX_LOG_FORMAT", "json"])
        assert result.exit_code == 0
        assert "Set SANDBOX_LOG_FORMAT=json" in result.output

        env_content = (tmp_path / ".env").read_text()
        assert "json" in env_content


class TestConfigProfiles:
    def test_no_profiles(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
        from cli.lib.scaffold import scaffold
        scaffold()
        from cli.lib.config import _init_paths
        _init_paths()

        result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0
        assert "No profiles" in result.output

    def test_create_profile(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
        from cli.lib.scaffold import scaffold
        scaffold()
        from cli.lib.config import _init_paths
        _init_paths()

        result = runner.invoke(app, ["config", "create-profile", "dev"])
        assert result.exit_code == 0
        assert "Created profile" in result.output

        result = runner.invoke(app, ["config", "profiles"])
        assert "dev" in result.output


class TestConfigExportImport:
    def test_export(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
        from cli.lib.scaffold import scaffold
        scaffold()
        from cli.lib.config import _init_paths
        _init_paths()

        output = tmp_path / "export.json"
        result = runner.invoke(app, ["config", "export", "-o", str(output)])
        assert result.exit_code == 0
        assert output.exists()

        data = json.loads(output.read_text())
        assert "env" in data
        assert "tools" in data

    def test_import(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
        from cli.lib.scaffold import scaffold
        scaffold()
        from cli.lib.config import _init_paths
        _init_paths()

        import_file = tmp_path / "import.json"
        import_file.write_text(json.dumps({
            "env": {"SANDBOX_LOG_FORMAT": "json"},
            "tools": [],
            "mcp_servers": [],
            "mounts": [],
        }))

        result = runner.invoke(app, ["config", "import", str(import_file)])
        assert result.exit_code == 0
        assert "Import complete" in result.output
