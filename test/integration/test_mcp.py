"""Integration tests for MCP server lifecycle."""

import json

from cli.lib.mcp import (
    generate_mcp_config,
    get_enabled_servers,
    set_server_enabled,
    write_mcp_config,
    MCP_LOG_WRAPPER,
)


class TestMcpLifecycle:
    def _setup_mcp(self, tmp_path, monkeypatch):
        """Set up MCP and tool directories for testing."""
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "server-a.yaml").write_text(
            "name: server-a\n"
            "description: Server A\n"
            "enabled: true\n"
            "command: node\n"
            "args: [a.js]\n"
            "firewall:\n  domains:\n    - api.a.com\n"
            "env: {}\n"
        )
        (mcp_dir / "server-b.yaml").write_text(
            "name: server-b\n"
            "description: Server B\n"
            "enabled: false\n"
            "command: python\n"
            "args: [b.py]\n"
            "firewall:\n  domains:\n    - api.b.com\n"
            "env:\n  B_KEY: ''\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_data_dir", lambda: tmp_path)

        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "test-tool.yaml").write_text(
            "name: test-tool\n"
            "default: true\n"
            "mcp:\n"
            "  config_path: /home/user/.config/mcp.json\n"
        )
        monkeypatch.setattr("cli.lib.config.TOOLS_DIR", tools_dir)

        return mcp_dir

    def test_enable_disable_cycle(self, tmp_path, monkeypatch):
        mcp_dir = self._setup_mcp(tmp_path, monkeypatch)

        assert len(get_enabled_servers()) == 1

        set_server_enabled("server-b", True)
        assert len(get_enabled_servers()) == 2

        set_server_enabled("server-a", False)
        enabled = get_enabled_servers()
        assert len(enabled) == 1
        assert enabled[0]["name"] == "server-b"

    def test_config_generation_reflects_state(self, tmp_path, monkeypatch):
        self._setup_mcp(tmp_path, monkeypatch)

        config = generate_mcp_config()
        assert "server-a" in config["mcpServers"]
        assert "server-b" not in config["mcpServers"]

        set_server_enabled("server-b", True)
        config = generate_mcp_config()
        assert "server-a" in config["mcpServers"]
        assert "server-b" in config["mcpServers"]

    def test_wrapper_args_correct(self, tmp_path, monkeypatch):
        self._setup_mcp(tmp_path, monkeypatch)

        config = generate_mcp_config()
        server_a = config["mcpServers"]["server-a"]
        assert server_a["command"] == MCP_LOG_WRAPPER
        assert server_a["args"] == ["server-a", "node", "a.js"]

    def test_write_config_to_workspace(self, tmp_path, monkeypatch):
        self._setup_mcp(tmp_path, monkeypatch)

        path = write_mcp_config()
        assert path is not None
        assert path.exists()

        data = json.loads(path.read_text())
        assert "mcpServers" in data
        assert "server-a" in data["mcpServers"]
