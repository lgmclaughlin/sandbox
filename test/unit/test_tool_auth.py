"""Unit tests for tool auth command and credential sync."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


@pytest.fixture
def fake_creds(tmp_path):
    """Create a fake credential directory with various files."""
    cred_dir = tmp_path / ".claude"
    cred_dir.mkdir()
    (cred_dir / "credentials.json").write_text('{"token": "fake"}')
    (cred_dir / "config.json").write_text('{"setting": true}')
    (cred_dir / ".credentials.bak").write_text("backup")
    (cred_dir / "README.md").write_text("should be excluded")
    (cred_dir / "history.log").write_text("should be excluded")
    return cred_dir


class TestAuthValidation:
    def test_auth_requires_name(self):
        result = runner.invoke(app, ["tool", "auth"])
        assert result.exit_code != 0

    def test_auth_unknown_tool(self):
        result = runner.invoke(app, ["tool", "auth", "nonexistent-tool-xyz"])
        assert result.exit_code != 0
        assert "No tool definition" in result.output

    @patch("cli.commands.tools.load_tool_definition")
    def test_auth_no_auth_config(self, mock_load):
        mock_load.return_value = {"name": "test", "install": {"method": "npm"}}
        result = runner.invoke(app, ["tool", "auth", "test"])
        assert result.exit_code != 0
        assert "no auth configuration" in result.output

    @patch("cli.commands.tools.load_tool_definition")
    def test_auth_missing_command(self, mock_load):
        mock_load.return_value = {"name": "test", "auth": {"sync": {}}}
        result = runner.invoke(app, ["tool", "auth", "test"])
        assert result.exit_code != 0
        assert "missing 'command'" in result.output

    @patch("cli.commands.tools.load_tool_definition")
    def test_auth_binary_not_found(self, mock_load):
        mock_load.return_value = {
            "name": "test",
            "auth": {"command": "nonexistent-binary auth login", "sync": {}},
        }
        result = runner.invoke(app, ["tool", "auth", "test"])
        assert result.exit_code != 0
        assert "not found on the host" in result.output

    @patch("cli.commands.tools.is_running", return_value=False)
    @patch("shutil.which", return_value="/usr/bin/true")
    @patch("cli.commands.tools.load_tool_definition")
    def test_auth_container_not_running(self, mock_load, _mock_which, _mock_running):
        mock_load.return_value = {
            "name": "test",
            "auth": {"command": "true", "sync": {"host": "/tmp", "container": "/tmp"}},
        }
        result = runner.invoke(app, ["tool", "auth", "test"])
        assert result.exit_code != 0
        assert "not running" in result.output

    @patch("cli.commands.tools.is_running", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/true")
    @patch("cli.commands.tools.load_tool_definition")
    def test_auth_missing_sync_paths(self, mock_load, _mock_which, _mock_running):
        mock_load.return_value = {
            "name": "test",
            "auth": {"command": "true", "sync": {}},
        }
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = runner.invoke(app, ["tool", "auth", "test"])
        assert result.exit_code != 0
        assert "missing sync paths" in result.output


class TestAuthCredentialFiltering:
    """Test that glob filters select the right files."""

    @patch("cli.commands.tools.exec_in_sandbox", return_value=(0, ""))
    @patch("cli.commands.tools.is_running", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/true")
    @patch("cli.commands.tools.load_tool_definition")
    def test_filters_credential_files(self, mock_load, _which, _running,
                                       _exec, fake_creds):
        """Verify glob filters select only matching files."""
        copied_files = set()

        def capture_copy(path, container_dir):
            for f in path.iterdir():
                copied_files.add(f.name)
            return True

        mock_load.return_value = {
            "name": "test",
            "auth": {
                "command": "true",
                "sync": {
                    "host": str(fake_creds),
                    "container": "/home/node/.claude",
                    "files": ["*.json", ".credentials*"],
                },
            },
        }

        with patch("subprocess.run", return_value=MagicMock(returncode=0)), \
             patch("cli.commands.tools.copy_to_container", side_effect=capture_copy):
            result = runner.invoke(app, ["tool", "auth", "test"])

        assert result.exit_code == 0
        assert "Credentials synced" in result.output

        assert "credentials.json" in copied_files
        assert "config.json" in copied_files
        assert ".credentials.bak" in copied_files
        # These should NOT be included
        assert "README.md" not in copied_files
        assert "history.log" not in copied_files

    @patch("cli.commands.tools.is_running", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/true")
    @patch("cli.commands.tools.load_tool_definition")
    def test_no_matching_files_warns(self, mock_load, _which, _running, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        mock_load.return_value = {
            "name": "test",
            "auth": {
                "command": "true",
                "sync": {
                    "host": str(empty_dir),
                    "container": "/home/node/.claude",
                    "files": ["*.json"],
                },
            },
        }

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = runner.invoke(app, ["tool", "auth", "test"])

        assert result.exit_code != 0
        assert "No credential files matched" in result.output

    @patch("cli.commands.tools.exec_in_sandbox", return_value=(0, ""))
    @patch("cli.commands.tools.copy_to_container", return_value=True)
    @patch("cli.commands.tools.is_running", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/true")
    @patch("cli.commands.tools.load_tool_definition")
    def test_no_filter_syncs_all(self, mock_load, _which, _running,
                                  mock_copy, _exec, fake_creds):
        mock_load.return_value = {
            "name": "test",
            "auth": {
                "command": "true",
                "sync": {
                    "host": str(fake_creds),
                    "container": "/home/node/.claude",
                },
            },
        }

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = runner.invoke(app, ["tool", "auth", "test"])

        assert result.exit_code == 0
        # Without file filter, copy_to_container gets the full host dir
        copied_path = mock_copy.call_args[0][0]
        assert copied_path == fake_creds


class TestAuthHostCommand:
    """Test that the host auth command is executed correctly."""

    @patch("cli.commands.tools.exec_in_sandbox", return_value=(0, ""))
    @patch("cli.commands.tools.copy_to_container", return_value=True)
    @patch("cli.commands.tools.is_running", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/true")
    @patch("cli.commands.tools.load_tool_definition")
    def test_runs_host_command(self, mock_load, _which, _running,
                                _copy, _exec, fake_creds):
        mock_load.return_value = {
            "name": "test",
            "auth": {
                "command": "myauth login --flag",
                "sync": {
                    "host": str(fake_creds),
                    "container": "/home/node/.claude",
                },
            },
        }

        with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            result = runner.invoke(app, ["tool", "auth", "test"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(["myauth", "login", "--flag"], stdin=None)

    @patch("cli.commands.tools.is_running", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/true")
    @patch("cli.commands.tools.load_tool_definition")
    def test_host_command_failure(self, mock_load, _which, _running, fake_creds):
        mock_load.return_value = {
            "name": "test",
            "auth": {
                "command": "myauth login",
                "sync": {
                    "host": str(fake_creds),
                    "container": "/home/node/.claude",
                },
            },
        }

        with patch("subprocess.run", return_value=MagicMock(returncode=1)):
            result = runner.invoke(app, ["tool", "auth", "test"])

        assert result.exit_code != 0
        assert "Auth command failed" in result.output


class TestAuthOwnershipFix:
    """Test that file ownership is corrected after sync."""

    @patch("cli.commands.tools.exec_in_sandbox", return_value=(0, ""))
    @patch("cli.commands.tools.copy_to_container", return_value=True)
    @patch("cli.commands.tools.is_running", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/true")
    @patch("cli.commands.tools.load_tool_definition")
    def test_chown_after_sync(self, mock_load, _which, _running,
                               _copy, mock_exec, fake_creds):
        mock_load.return_value = {
            "name": "test",
            "auth": {
                "command": "true",
                "sync": {
                    "host": str(fake_creds),
                    "container": "/home/node/.claude",
                },
            },
        }

        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            result = runner.invoke(app, ["tool", "auth", "test"])

        assert result.exit_code == 0
        mock_exec.assert_called_once()
        chown_cmd = mock_exec.call_args[0][0]
        # Command is ["bash", "-c", "chown -R ... /home/node/.claude"]
        full_cmd = " ".join(chown_cmd)
        assert "chown" in full_cmd
        assert "/home/node/.claude" in full_cmd
