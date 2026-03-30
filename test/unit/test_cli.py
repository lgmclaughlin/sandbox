"""Unit tests for CLI argument parsing and validation."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


class TestCLIHelp:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Secure AI development environment" in result.output

    def test_fw_help(self):
        result = runner.invoke(app, ["fw", "--help"])
        assert result.exit_code == 0
        assert "ls" in result.output
        assert "add" in result.output
        assert "remove" in result.output

    def test_tool_help(self):
        result = runner.invoke(app, ["tool", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "install" in result.output
        assert "remove" in result.output


class TestVersion:
    def test_version_output(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "sandbox" in result.output


class TestFwValidation:
    def test_add_requires_domain(self):
        result = runner.invoke(app, ["fw", "add"])
        assert result.exit_code != 0

    def test_add_invalid_domain(self):
        result = runner.invoke(app, ["fw", "add", "not a domain!"])
        assert result.exit_code != 0
        assert "Invalid domain" in result.output

    def test_remove_requires_domain(self):
        result = runner.invoke(app, ["fw", "remove"])
        assert result.exit_code != 0


class TestToolValidation:
    def test_install_requires_name(self):
        result = runner.invoke(app, ["tool", "install"])
        assert result.exit_code != 0

    def test_remove_requires_name(self):
        result = runner.invoke(app, ["tool", "remove"])
        assert result.exit_code != 0


class TestExec:
    def test_exec_no_command(self):
        result = runner.invoke(app, ["exec"])
        assert result.exit_code != 0
        assert "No command" in result.output

    def test_exec_help(self):
        result = runner.invoke(app, ["exec", "--help"])
        assert result.exit_code == 0
        assert "Execute" in result.output


class TestFwLs:
    def test_lists_domains(self):
        result = runner.invoke(app, ["fw", "ls"])
        assert result.exit_code == 0

    def test_tool_list(self):
        result = runner.invoke(app, ["tool", "list"])
        assert result.exit_code == 0


@pytest.fixture
def log_dir(tmp_path):
    """Create a temporary log directory with sample data for all types."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    meta = {
        "session_id": "test-session-123",
        "event": "session_start",
        "user": "testuser",
        "hostname": "sandbox",
        "start_time": "2026-03-29T20:00:00Z",
    }
    (sessions_dir / "test-session-123.meta.json").write_text(json.dumps(meta))

    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    (commands_dir / "test.history").write_text("ls\ncd /workspace\npwd\n")

    fw_dir = tmp_path / "firewall"
    fw_dir.mkdir()
    fw_entries = [
        {"timestamp": "2026-03-29T21:00:00Z", "event_type": "firewall_allow",
         "project": "test", "source": "firewall-log",
         "payload": {"dst": "104.18.0.1", "port": "443", "proto": "TCP"}},
        {"timestamp": "2026-03-29T21:00:01Z", "event_type": "firewall_block",
         "project": "test", "source": "firewall-log",
         "payload": {"dst": "93.184.216.34", "port": "443", "proto": "TCP"}},
    ]
    (fw_dir / "2026-03-29.jsonl").write_text(
        "\n".join(json.dumps(e) for e in fw_entries) + "\n"
    )

    mcp_dir = tmp_path / "mcp"
    mcp_dir.mkdir()
    mcp_entries = [
        {"timestamp": "2026-03-29T21:00:00Z", "server": "filesystem",
         "direction": "request", "method": "tools/call", "tool": "read_file"},
        {"timestamp": "2026-03-29T21:00:01Z", "server": "filesystem",
         "direction": "response", "method": "tools/call", "tool": "read_file"},
    ]
    (mcp_dir / "2026-03-29.jsonl").write_text(
        "\n".join(json.dumps(e) for e in mcp_entries) + "\n"
    )

    proxy_dir = tmp_path / "proxy"
    proxy_dir.mkdir()
    proxy_entries = [
        {"timestamp": "2026-03-29T21:00:00Z", "event_type": "proxy_request",
         "payload": {"method": "POST", "url": "https://api.anthropic.com/v1/messages",
                     "status_code": 200, "blocked": False}},
        {"timestamp": "2026-03-29T21:00:01Z", "event_type": "proxy_request",
         "payload": {"method": "GET", "url": "https://evil.com/exfil",
                     "blocked": True, "violations": [{"rule": "domain-block"}]}},
    ]
    (proxy_dir / "2026-03-29.jsonl").write_text(
        "\n".join(json.dumps(e) for e in proxy_entries) + "\n"
    )

    return tmp_path


class TestLogsView:
    """Test sandbox logs view across all log types."""

    def _invoke(self, log_dir, log_type):
        with patch("cli.commands.logs.get_log_dir", return_value=log_dir):
            return runner.invoke(app, ["logs", "view", log_type])

    def test_view_sessions(self, log_dir):
        result = self._invoke(log_dir, "sessions")
        assert result.exit_code == 0
        assert "Sessions:" in result.output

    def test_view_commands(self, log_dir):
        result = self._invoke(log_dir, "commands")
        assert result.exit_code == 0
        assert "Command history:" in result.output

    def test_view_firewall(self, log_dir):
        result = self._invoke(log_dir, "firewall")
        assert result.exit_code == 0
        assert "Firewall:" in result.output
        assert "104.18.0.1:443" in result.output
        assert "93.184.216.34:443" in result.output
        assert "TCP" in result.output

    def test_view_firewall_shows_allow_block(self, log_dir):
        result = self._invoke(log_dir, "firewall")
        assert "ALLOW" in result.output
        assert "BLOCK" in result.output

    def test_view_firewall_no_question_marks(self, log_dir):
        result = self._invoke(log_dir, "firewall")
        assert "?:?" not in result.output

    def test_view_mcp(self, log_dir):
        result = self._invoke(log_dir, "mcp")
        assert result.exit_code == 0
        assert "MCP:" in result.output
        assert "filesystem" in result.output
        assert "read_file" in result.output

    def test_view_proxy(self, log_dir):
        result = self._invoke(log_dir, "proxy")
        assert result.exit_code == 0
        assert "Proxy:" in result.output
        assert "api.anthropic.com" in result.output
        assert "evil.com" in result.output

    def test_view_all(self, log_dir):
        result = self._invoke(log_dir, "all")
        assert result.exit_code == 0
        assert "Sessions:" in result.output
        assert "Command history:" in result.output
        assert "Firewall:" in result.output
        assert "MCP:" in result.output
        assert "Proxy:" in result.output

    def test_view_invalid_type(self, log_dir):
        result = self._invoke(log_dir, "bogus")
        assert result.exit_code != 0
        assert "Unknown log type" in result.output

    def test_empty_firewall(self, tmp_path):
        (tmp_path / "firewall").mkdir()
        with patch("cli.commands.logs.get_log_dir", return_value=tmp_path):
            result = runner.invoke(app, ["logs", "view", "firewall"])
        assert result.exit_code == 0
        assert "No firewall logs" in result.output

    def test_empty_mcp(self, tmp_path):
        with patch("cli.commands.logs.get_log_dir", return_value=tmp_path):
            result = runner.invoke(app, ["logs", "view", "mcp"])
        assert result.exit_code == 0
        assert "No logs found" in result.output

    def test_empty_proxy(self, tmp_path):
        with patch("cli.commands.logs.get_log_dir", return_value=tmp_path):
            result = runner.invoke(app, ["logs", "view", "proxy"])
        assert result.exit_code == 0
        assert "No logs found" in result.output
