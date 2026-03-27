"""Unit tests for MCP permission validation."""

import json

from cli.lib.mcp import generate_mcp_config


class TestPermissionGeneration:
    def test_no_permissions_when_disabled(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "server.yaml").write_text(
            "name: server\nenabled: true\ncommand: node\nargs: [s.js]\n"
            "allowed_paths:\n  - /workspace\n"
            "validation:\n  blocked_patterns:\n    - '\\.\\./'\n"
        )
        monkeypatch.setattr("cli.lib.mcp.MCP_DIR", mcp_dir)
        monkeypatch.setattr("cli.lib.mcp.load_env", lambda: {
            "SANDBOX_ENFORCE_MCP_PERMISSIONS": "false",
        })

        config = generate_mcp_config()
        server_env = config["mcpServers"]["server"]["env"]
        assert "MCP_PERMISSIONS" not in server_env
        assert "MCP_ENFORCE" not in server_env

    def test_permissions_when_enabled(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "server.yaml").write_text(
            "name: server\nenabled: true\ncommand: node\nargs: [s.js]\n"
            "allowed_paths:\n  - /workspace\n  - /tmp\n"
            "validation:\n  blocked_patterns:\n    - '\\.\\./'\n    - '/etc/'\n"
            "permissions:\n  - filesystem: read\n"
        )
        monkeypatch.setattr("cli.lib.mcp.MCP_DIR", mcp_dir)
        monkeypatch.setattr("cli.lib.mcp.load_env", lambda: {
            "SANDBOX_ENFORCE_MCP_PERMISSIONS": "true",
        })

        config = generate_mcp_config()
        server_env = config["mcpServers"]["server"]["env"]
        assert server_env["MCP_ENFORCE"] == "true"

        perms = json.loads(server_env["MCP_PERMISSIONS"])
        assert perms["allowed_paths"] == ["/workspace", "/tmp"]
        assert "\\.\\./" in perms["blocked_patterns"]
        assert "/etc/" in perms["blocked_patterns"]

    def test_empty_permissions(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "server.yaml").write_text(
            "name: server\nenabled: true\ncommand: node\nargs: [s.js]\nenv: {}\n"
        )
        monkeypatch.setattr("cli.lib.mcp.MCP_DIR", mcp_dir)
        monkeypatch.setattr("cli.lib.mcp.load_env", lambda: {
            "SANDBOX_ENFORCE_MCP_PERMISSIONS": "true",
        })

        config = generate_mcp_config()
        server_env = config["mcpServers"]["server"]["env"]
        perms = json.loads(server_env["MCP_PERMISSIONS"])
        assert perms["allowed_paths"] == []
        assert perms["blocked_patterns"] == []

    def test_multiple_servers_independent(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "fs.yaml").write_text(
            "name: fs\nenabled: true\ncommand: node\nargs: [fs.js]\n"
            "allowed_paths:\n  - /workspace\n"
        )
        (mcp_dir / "net.yaml").write_text(
            "name: net\nenabled: true\ncommand: node\nargs: [net.js]\n"
            "allowed_paths: []\n"
            "permissions:\n  - network: read\n"
        )
        monkeypatch.setattr("cli.lib.mcp.MCP_DIR", mcp_dir)
        monkeypatch.setattr("cli.lib.mcp.load_env", lambda: {
            "SANDBOX_ENFORCE_MCP_PERMISSIONS": "true",
        })

        config = generate_mcp_config()
        fs_perms = json.loads(config["mcpServers"]["fs"]["env"]["MCP_PERMISSIONS"])
        net_perms = json.loads(config["mcpServers"]["net"]["env"]["MCP_PERMISSIONS"])

        assert fs_perms["allowed_paths"] == ["/workspace"]
        assert net_perms["allowed_paths"] == []
