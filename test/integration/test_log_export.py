"""Integration tests for log export."""

import json
from pathlib import Path

from cli.lib.logging import EventLogger, FileSink, build_envelope
from cli.commands.logs import export_logs


class TestLogExport:
    def _populate_logs(self, log_dir: Path, session_id: str = "test_session"):
        """Write sample log events to the audit volume."""
        logger = EventLogger(
            sinks=[FileSink(log_dir=log_dir)],
            session_id=session_id,
            project="test",
        )

        logger.emit("session_start", "entrypoint", {"user": "tester"})
        logger.emit("command", "entrypoint", {"command": "ls", "exit_code": 0})
        logger.emit("mcp_request", "mcp-wrapper", {"server": "fs", "tool": "read_file"})
        logger.emit("session_end", "entrypoint", {"end_time": "2026-03-26T12:00:00Z"})

    def test_export_all(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        self._populate_logs(log_dir)

        monkeypatch.setattr("cli.commands.logs.get_log_dir", lambda: log_dir)

        output = tmp_path / "export.json"
        export_logs(output=str(output))

        assert output.exists()
        events = json.loads(output.read_text())
        assert len(events) == 4
        types = [e["event_type"] for e in events]
        assert "session_start" in types
        assert "command" in types
        assert "mcp_request" in types

    def test_export_session_filter(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        self._populate_logs(log_dir, session_id="session_a")
        self._populate_logs(log_dir, session_id="session_b")

        monkeypatch.setattr("cli.commands.logs.get_log_dir", lambda: log_dir)

        output = tmp_path / "export.json"
        export_logs(output=str(output), session_id="session_a")

        events = json.loads(output.read_text())
        assert all(e["session_id"] == "session_a" for e in events)

    def test_export_empty(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        monkeypatch.setattr("cli.commands.logs.get_log_dir", lambda: log_dir)

        output = tmp_path / "export.json"
        export_logs(output=str(output))

        events = json.loads(output.read_text())
        assert events == []

    def test_export_sorted_by_timestamp(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "logs"
        self._populate_logs(log_dir)

        monkeypatch.setattr("cli.commands.logs.get_log_dir", lambda: log_dir)

        output = tmp_path / "export.json"
        export_logs(output=str(output))

        events = json.loads(output.read_text())
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)
