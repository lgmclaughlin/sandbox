"""Unit tests for mount CLI commands."""

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def _scaffold(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
    from cli.lib.scaffold import scaffold
    from cli.lib.config import _init_paths
    scaffold()
    _init_paths()


class TestMountClear:
    def test_clear_no_mounts(self, monkeypatch, tmp_path):
        _scaffold(tmp_path, monkeypatch)

        result = runner.invoke(app, ["mount", "clear"])
        assert result.exit_code == 0
        assert "No mounts configured" in result.output

    def test_clear_with_unmounted_entries(self, monkeypatch, tmp_path):
        _scaffold(tmp_path, monkeypatch)

        runner.invoke(app, ["mount", "add", "test",
                            "--type", "rclone",
                            "--remote", "test:/path",
                            "--local", "./data"])

        result = runner.invoke(app, ["mount", "clear"])
        assert result.exit_code == 0, f"clear crashed: {result.output}\n{result.exception}"
        assert "No active mounts found" in result.output

    def test_clear_specific_path_not_mounted(self, monkeypatch, tmp_path):
        _scaffold(tmp_path, monkeypatch)

        result = runner.invoke(app, ["mount", "clear", str(tmp_path / "nope")])
        assert result.exit_code != 0
        assert "not mounted" in result.output
