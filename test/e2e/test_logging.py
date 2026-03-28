"""E2E: Layer 2 - Logging and Observability."""

import json
import time
from pathlib import Path

from test.e2e.conftest import sandbox, sandbox_output, E2E_DATA_DIR


class TestSessionLogs:
    def test_session_directory_exists(self):
        log_dir = E2E_DATA_DIR / "logs" / "sessions"
        assert log_dir.exists(), f"Session log directory not found: {log_dir}"

    def test_session_metadata_written(self):
        result = sandbox("exec", "bash", "-c",
                         "ls /var/log/sandbox/sessions/",
                         capture_output=True, text=True)
        # Should have date directories
        assert result.stdout.strip() != "", "No session log directories found in container"

    def test_session_metadata_has_json(self):
        log_dir = E2E_DATA_DIR / "logs" / "sessions"
        jsonl_files = list(log_dir.rglob("*.jsonl"))
        meta_files = list(log_dir.rglob("*.meta.json"))
        assert len(jsonl_files) > 0 or len(meta_files) > 0, \
            f"No session log files found. Contents: {list(log_dir.rglob('*'))}"


class TestCommandLogs:
    def test_exec_produces_log(self):
        sandbox("exec", "echo", "e2e-log-test", check=True)
        time.sleep(1)

        log_dir = E2E_DATA_DIR / "logs" / "commands"
        log_files = list(log_dir.rglob("*.jsonl"))
        assert len(log_files) > 0, f"No command log files found. Dir contents: {list(log_dir.rglob('*'))}"

        found = False
        for f in log_files:
            content = f.read_text()
            if "e2e-log-test" in content:
                found = True
                break
        assert found, "exec command not found in log files"

    def test_exec_logs_exit_code(self):
        sandbox("exec", "bash", "-c", "exit 42", capture_output=True)
        time.sleep(1)

        log_dir = E2E_DATA_DIR / "logs" / "commands"
        found = False
        for f in log_dir.rglob("*.jsonl"):
            for line in f.read_text().splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("payload", {}).get("exit_code") == 42:
                    found = True
                    break
        assert found, "Exit code 42 not found in command logs"

    def test_exec_log_has_correct_source(self):
        sandbox("exec", "echo", "source-check", check=True)
        time.sleep(1)

        log_dir = E2E_DATA_DIR / "logs" / "commands"
        found = False
        for f in log_dir.rglob("*.jsonl"):
            for line in f.read_text().splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                if "source-check" in entry.get("payload", {}).get("command", ""):
                    assert entry["source"] == "sandbox-exec"
                    found = True
                    break
        assert found, "source-check command not found in logs"

    def test_special_characters_in_command(self):
        output = sandbox_output("exec", "bash", "-c",
                                "echo 'quotes \"and\" pipes | work'")
        assert "quotes" in output
        assert "pipes" in output

    def test_long_output(self):
        output = sandbox_output("exec", "bash", "-c",
                                "seq 1 1000")
        lines = output.strip().split("\n")
        assert len(lines) == 1000


class TestLogFormats:
    def test_log_format_setting(self):
        output = sandbox_output("config", "get", "SANDBOX_LOG_FORMAT")
        assert "text" in output or "json" in output


class TestLogCommands:
    def test_logs_view(self):
        result = sandbox("logs", "view", capture_output=True, text=True)
        assert result.returncode == 0

    def test_logs_summary(self):
        result = sandbox("logs", "summary", capture_output=True, text=True)
        assert result.returncode == 0
        assert "Sessions" in result.stdout
        assert "Command logs" in result.stdout

    def test_logs_export(self):
        output_file = E2E_DATA_DIR / "test-export.json"
        sandbox("logs", "export", "-o", str(output_file), check=True)

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert isinstance(data, list)
        output_file.unlink()


class TestLogPaths:
    def test_log_directory_structure(self):
        log_dir = E2E_DATA_DIR / "logs"
        assert log_dir.exists()
        # At minimum sessions should exist from container start
        assert (log_dir / "sessions").exists()
