"""Unit tests for OS data directory resolution."""

from cli.lib.paths import get_data_dir, get_package_data_dir


class TestGetDataDir:
    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_DATA_DIR", "/custom/path")
        assert str(get_data_dir()) == "/custom/path"

    def test_linux_default(self, monkeypatch):
        monkeypatch.delenv("SANDBOX_DATA_DIR", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setattr("cli.lib.paths.IS_WINDOWS", False)
        monkeypatch.setattr("cli.lib.paths.IS_MACOS", False)

        path = get_data_dir()
        assert str(path).endswith(".local/share/sandbox")

    def test_linux_xdg(self, monkeypatch):
        monkeypatch.delenv("SANDBOX_DATA_DIR", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", "/xdg/data")
        monkeypatch.setattr("cli.lib.paths.IS_WINDOWS", False)
        monkeypatch.setattr("cli.lib.paths.IS_MACOS", False)

        assert str(get_data_dir()) == "/xdg/data/sandbox"

    def test_macos_default(self, monkeypatch):
        monkeypatch.delenv("SANDBOX_DATA_DIR", raising=False)
        monkeypatch.setattr("cli.lib.paths.IS_WINDOWS", False)
        monkeypatch.setattr("cli.lib.paths.IS_MACOS", True)

        path = get_data_dir()
        assert "Library/Application Support/sandbox" in str(path)

    def test_windows_default(self, monkeypatch):
        monkeypatch.delenv("SANDBOX_DATA_DIR", raising=False)
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        monkeypatch.setattr("cli.lib.paths.IS_WINDOWS", True)
        monkeypatch.setattr("cli.lib.paths.IS_MACOS", False)

        path = str(get_data_dir())
        assert "AppData" in path and "sandbox" in path

    def test_env_override_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_DATA_DIR", "/override")
        monkeypatch.setattr("cli.lib.paths.IS_MACOS", True)

        assert str(get_data_dir()) == "/override"


class TestGetPackageDataDir:
    def test_returns_repo_root(self):
        path = get_package_data_dir()
        assert (path / "pyproject.toml").exists() or (path / "cli").exists()
