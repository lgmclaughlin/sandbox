"""Unit tests for MCP config generation."""

import json

import yaml

from cli.lib.mcp import (
    generate_mcp_config,
    get_enabled_servers,
    get_mcp_domains,
    list_mcp_servers,
    load_mcp_server,
    set_server_enabled,
    MCP_LOG_WRAPPER,
)


class TestListMcpServers:
    def test_lists_servers(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "test-server.yaml").write_text(
            "name: test-server\n"
            "description: A test server\n"
            "enabled: true\n"
            "command: node\n"
            "args: [server.js]\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        servers = list_mcp_servers()
        assert len(servers) == 1
        assert servers[0]["name"] == "test-server"

    def test_empty_dir(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        assert list_mcp_servers() == []

    def test_missing_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "nonexistent" / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path / "nonexistent")
        assert list_mcp_servers() == []


class TestLoadMcpServer:
    def test_load_existing(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "my-server.yaml").write_text(
            "name: my-server\ncommand: python\nargs: [server.py]\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        server = load_mcp_server("my-server")
        assert server is not None
        assert server["command"] == "python"

    def test_load_missing(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        assert load_mcp_server("nonexistent") is None


class TestGetEnabledServers:
    def test_filters_disabled(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "enabled.yaml").write_text(
            "name: enabled\nenabled: true\ncommand: node\nargs: [a.js]\n"
        )
        (mcp_dir / "disabled.yaml").write_text(
            "name: disabled\nenabled: false\ncommand: node\nargs: [b.js]\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        enabled = get_enabled_servers()
        assert len(enabled) == 1
        assert enabled[0]["name"] == "enabled"

    def test_default_enabled(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "server.yaml").write_text(
            "name: server\ncommand: node\nargs: [s.js]\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        enabled = get_enabled_servers()
        assert len(enabled) == 1


class TestSetServerEnabled:
    def test_enable_disable(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "server.yaml").write_text(
            "name: server\nenabled: true\ncommand: node\nargs: [s.js]\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        assert set_server_enabled("server", False) is True
        data = yaml.safe_load((mcp_dir / "server.yaml").read_text())
        assert data["enabled"] is False

        assert set_server_enabled("server", True) is True
        data = yaml.safe_load((mcp_dir / "server.yaml").read_text())
        assert data["enabled"] is True

    def test_missing_server(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        assert set_server_enabled("nope", True) is False


class TestGenerateMcpConfig:
    def test_wraps_with_logger(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "test.yaml").write_text(
            "name: test\nenabled: true\ncommand: node\nargs: [server.js, --port, '3000']\nenv: {}\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        config = generate_mcp_config()
        assert "test" in config["mcpServers"]
        server_config = config["mcpServers"]["test"]
        assert server_config["command"] == MCP_LOG_WRAPPER
        assert server_config["args"] == ["test", "node", "server.js", "--port", "3000"]

    def test_skips_disabled(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "off.yaml").write_text(
            "name: off\nenabled: false\ncommand: node\nargs: [s.js]\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        config = generate_mcp_config()
        assert config["mcpServers"] == {}

    def test_skips_empty_command(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "bad.yaml").write_text(
            "name: bad\nenabled: true\ncommand: ''\nargs: []\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        config = generate_mcp_config()
        assert config["mcpServers"] == {}


class TestGetMcpDomains:
    def test_collects_domains(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "a.yaml").write_text(
            "name: a\nenabled: true\ncommand: x\nargs: []\n"
            "firewall:\n  domains:\n    - api.a.com\n    - cdn.a.com\n"
        )
        (mcp_dir / "b.yaml").write_text(
            "name: b\nenabled: true\ncommand: x\nargs: []\n"
            "firewall:\n  domains:\n    - api.b.com\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        domains = get_mcp_domains()
        assert "api.a.com" in domains
        assert "cdn.a.com" in domains
        assert "api.b.com" in domains

    def test_skips_disabled(self, tmp_path, monkeypatch):
        mcp_dir = tmp_path / "config" / "mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "off.yaml").write_text(
            "name: off\nenabled: false\ncommand: x\nargs: []\n"
            "firewall:\n  domains:\n    - should.not.appear\n"
        )
        monkeypatch.setattr("cli.lib.mcp.get_config_root", lambda: tmp_path / "config")
        monkeypatch.setattr("cli.lib.mcp.get_project_root", lambda: tmp_path)

        assert get_mcp_domains() == []
