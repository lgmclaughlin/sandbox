"""E2E: Layer 5 - MCP."""

import json

from test.e2e.conftest import sandbox, sandbox_output, E2E_DATA_DIR


class TestMcpServers:
    def test_list_servers(self):
        output = sandbox_output("mcp", "list")
        assert "filesystem" in output
        assert "fetch" in output

    def test_enable_disable(self):
        sandbox("mcp", "enable", "filesystem", check=True)
        output = sandbox_output("mcp", "list")
        assert "enabled" in output

        sandbox("mcp", "disable", "filesystem", check=True)
        output = sandbox_output("mcp", "list")
        assert "disabled" in output

    def test_show_definition(self):
        output = sandbox_output("mcp", "show", "filesystem")
        assert "allowed_paths" in output
        assert "/workspace" in output
        assert "permissions" in output


class TestMcpConfig:
    def test_config_generated(self):
        sandbox("mcp", "enable", "filesystem", check=True)

        config_path = E2E_DATA_DIR / "mcp-config.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            assert "mcpServers" in data
            assert "filesystem" in data["mcpServers"]

        sandbox("mcp", "disable", "filesystem", check=True)

    def test_wrapper_in_config(self):
        sandbox("mcp", "enable", "filesystem", check=True)

        config_path = E2E_DATA_DIR / "mcp-config.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            fs_config = data["mcpServers"]["filesystem"]
            assert "mcp-log-wrapper" in fs_config["command"]

        sandbox("mcp", "disable", "filesystem", check=True)

    def test_wrapper_binary_in_container(self):
        result = sandbox("exec", "bash", "-c",
                         "test -x /usr/local/bin/mcp-log-wrapper && echo exists",
                         capture_output=True, text=True)
        assert "exists" in result.stdout

    def test_permissions_in_config_when_enforced(self):
        sandbox("config", "set", "SANDBOX_ENFORCE_MCP_PERMISSIONS", "true", check=True)
        sandbox("mcp", "enable", "filesystem", check=True)

        config_path = E2E_DATA_DIR / "mcp-config.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            fs_env = data["mcpServers"]["filesystem"].get("env", {})
            assert fs_env.get("MCP_ENFORCE") == "true"
            perms = json.loads(fs_env.get("MCP_PERMISSIONS", "{}"))
            assert "/workspace" in perms.get("allowed_paths", [])

        sandbox("mcp", "disable", "filesystem", check=True)
        sandbox("config", "set", "SANDBOX_ENFORCE_MCP_PERMISSIONS", "false", check=True)
