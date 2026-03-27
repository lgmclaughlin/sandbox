"""Integration tests for config export/import portability."""

import json

from cli.lib.scaffold import scaffold


class TestConfigPortability:
    def _setup(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SANDBOX_DATA_DIR", str(tmp_path))
        monkeypatch.setattr("cli.lib.scaffold.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("cli.lib.paths.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("cli.lib.config.get_data_dir", lambda: tmp_path)
        from cli.lib.config import _init_paths
        _init_paths()
        scaffold()

    def test_export_contains_all_sections(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch)

        from cli.lib.config import load_env, list_available_tools, load_mounts
        from cli.lib.mcp import list_mcp_servers

        env = load_env()
        tools = list_available_tools()
        mcp_servers = list_mcp_servers()
        mounts = load_mounts()

        export_data = {
            "env": env,
            "tools": tools,
            "mcp_servers": mcp_servers,
            "mounts": mounts,
        }

        assert "COMPOSE_PROJECT_NAME" in export_data["env"]
        assert len(export_data["tools"]) >= 1
        assert isinstance(export_data["mcp_servers"], list)
        assert isinstance(export_data["mounts"], list)

    def test_roundtrip(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch)

        from cli.lib.config import load_env, list_available_tools
        from cli.lib.mcp import list_mcp_servers

        original_env = load_env()
        original_tools = list_available_tools()
        original_mcp = list_mcp_servers()

        export_data = {
            "env": original_env,
            "tools": original_tools,
            "mcp_servers": original_mcp,
            "mounts": [],
        }

        export_file = tmp_path / "export.json"
        export_file.write_text(json.dumps(export_data, indent=2))

        target = tmp_path / "target"
        monkeypatch.setattr("cli.lib.config.get_data_dir", lambda: target)
        from cli.lib.config import _init_paths
        _init_paths()
        monkeypatch.setattr("cli.lib.scaffold.get_data_dir", lambda: target)
        monkeypatch.setattr("cli.lib.paths.get_data_dir", lambda: target)
        scaffold()

        import_data = json.loads(export_file.read_text())

        from dotenv import set_key
        env_file = target / ".env"
        for k, v in import_data["env"].items():
            set_key(str(env_file), k, v)

        imported_env = load_env()
        assert imported_env["COMPOSE_PROJECT_NAME"] == original_env["COMPOSE_PROJECT_NAME"]
