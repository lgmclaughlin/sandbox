"""E2E: Layer 1 - Container Basics."""

import time
from pathlib import Path

from test.e2e.conftest import sandbox, sandbox_output, E2E_WORKSPACE


class TestContainerRunning:
    def test_sandbox_container_running(self):
        output = sandbox_output("status")
        assert "running" in output

    def test_runs_as_non_root(self):
        output = sandbox_output("exec", "whoami")
        assert output != "root"
        assert output == "node"

    def test_entrypoint_created_session_metadata(self):
        result = sandbox("exec", "bash", "-c",
                         "ls /var/log/sandbox/sessions/",
                         capture_output=True, text=True)
        assert result.returncode == 0
        # Should have at least one date directory
        assert result.stdout.strip() != ""


class TestExecCommand:
    def test_simple_command(self):
        output = sandbox_output("exec", "echo", "hello")
        assert "hello" in output

    def test_command_exit_code_success(self):
        result = sandbox("exec", "true", capture_output=True)
        assert result.returncode == 0

    def test_command_exit_code_failure(self):
        result = sandbox("exec", "false", capture_output=True)
        assert result.returncode != 0

    def test_empty_exec_shows_error(self):
        result = sandbox("exec", capture_output=True, text=True)
        assert result.returncode != 0
        assert "No command" in result.stdout or "No command" in result.stderr


class TestWorkspace:
    def test_workspace_mounted(self):
        output = sandbox_output("exec", "ls", "/workspace")
        assert "test-file.txt" in output

    def test_workspace_file_readable(self):
        output = sandbox_output("exec", "cat", "/workspace/test-file.txt")
        assert "hello from e2e test" in output

    def test_workspace_writable(self):
        sandbox("exec", "bash", "-c",
                "echo 'written from container' > /workspace/container-output.txt",
                check=True)
        assert (E2E_WORKSPACE / "container-output.txt").exists()
        assert "written from container" in (E2E_WORKSPACE / "container-output.txt").read_text()

    def test_cannot_write_outside_workspace(self):
        result = sandbox("exec", "bash", "-c",
                         "touch /etc/test-file 2>&1",
                         capture_output=True, text=True)
        assert result.returncode != 0


class TestPrivilegeEscalation:
    def test_no_sudo(self):
        result = sandbox("exec", "bash", "-c",
                         "sudo echo test 2>&1",
                         capture_output=True, text=True)
        # sudo should either not exist or fail
        assert result.returncode != 0

    def test_no_su(self):
        result = sandbox("exec", "bash", "-c",
                         "su -c 'echo test' root 2>&1",
                         capture_output=True, text=True)
        assert result.returncode != 0

    def test_cannot_modify_etc(self):
        result = sandbox("exec", "bash", "-c",
                         "echo 'hack' >> /etc/passwd 2>&1",
                         capture_output=True, text=True)
        assert result.returncode != 0


class TestIdempotency:
    def test_start_twice_no_crash(self):
        result = sandbox("start", "--no-attach", str(E2E_WORKSPACE),
                         capture_output=True, text=True)
        assert result.returncode == 0
