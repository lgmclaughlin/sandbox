"""Unit tests for logging sink abstraction."""

import json

from cli.lib.logging import EventLogger, FileSink, StdoutSink, build_envelope, create_logger


class TestFileSink:
    def test_writes_jsonl(self, tmp_path):
        sink = FileSink(log_dir=tmp_path)
        event = build_envelope("command", "test", {"command": "ls"}, session_id="s1")
        sink.write(event)

        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        assert len(jsonl_files) == 1

        content = jsonl_files[0].read_text().strip()
        parsed = json.loads(content)
        assert parsed["event_type"] == "command"

    def test_routes_by_event_type(self, tmp_path):
        sink = FileSink(log_dir=tmp_path)

        sink.write(build_envelope("session_start", "entrypoint", {}, session_id="s1"))
        sink.write(build_envelope("command", "entrypoint", {}, session_id="s1"))
        sink.write(build_envelope("mcp_request", "mcp-wrapper", {}, session_id="s1"))
        sink.write(build_envelope("firewall_allow", "firewall-log", {}, session_id="s1"))

        assert list(tmp_path.rglob("sessions/**/*.jsonl"))
        assert list(tmp_path.rglob("commands/**/*.jsonl"))
        assert list(tmp_path.rglob("mcp/**/*.jsonl"))
        assert list(tmp_path.rglob("firewall/**/*.jsonl"))

    def test_creates_date_directory(self, tmp_path):
        sink = FileSink(log_dir=tmp_path)
        event = build_envelope("command", "test", {}, session_id="s1")
        sink.write(event)

        subdirs = [d for d in (tmp_path / "commands").iterdir() if d.is_dir()]
        assert len(subdirs) == 1
        assert len(subdirs[0].name) == 10  # YYYY-MM-DD


class TestStdoutSink:
    def test_writes_json(self, capsys):
        sink = StdoutSink()
        event = build_envelope("system", "test", {"msg": "hello"})
        sink.write(event)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["event_type"] == "system"
        assert parsed["payload"]["msg"] == "hello"


class TestEventLogger:
    def test_emits_to_all_sinks(self, tmp_path, capsys):
        logger = EventLogger(
            sinks=[FileSink(log_dir=tmp_path), StdoutSink()],
            session_id="test_session",
            project="test_project",
        )

        logger.emit("command", "test", {"command": "pwd"})

        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        assert len(jsonl_files) == 1

        captured = capsys.readouterr()
        assert "command" in captured.out

    def test_enforces_session_and_project(self, tmp_path):
        logger = EventLogger(
            sinks=[FileSink(log_dir=tmp_path)],
            session_id="my_session",
            project="my_project",
        )

        logger.emit("system", "test", {})

        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        content = jsonl_files[0].read_text().strip()
        parsed = json.loads(content)
        assert parsed["session_id"] == "my_session"
        assert parsed["project"] == "my_project"

    def test_payload_truncation(self, tmp_path):
        logger = EventLogger(
            sinks=[FileSink(log_dir=tmp_path)],
            session_id="s1",
            max_payload_bytes=10,
        )

        logger.emit("mcp_response", "test", {"data": "a" * 100})

        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        content = jsonl_files[0].read_text().strip()
        parsed = json.loads(content)
        assert len(parsed["payload"]["data"]) == 10
        assert parsed["payload"]["data_truncated"] is True
        assert parsed["payload"]["data_original_size"] == 100

    def test_no_truncation_when_disabled(self, tmp_path):
        logger = EventLogger(
            sinks=[FileSink(log_dir=tmp_path)],
            session_id="s1",
            max_payload_bytes=0,
        )

        logger.emit("command", "test", {"data": "a" * 100})

        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        content = jsonl_files[0].read_text().strip()
        parsed = json.loads(content)
        assert len(parsed["payload"]["data"]) == 100

    def test_otel_compat(self, tmp_path):
        logger = EventLogger(
            sinks=[FileSink(log_dir=tmp_path)],
            session_id="s1",
            otel_compat=True,
        )

        logger.emit("mcp_request", "wrapper", {"server": "fs"})

        jsonl_files = list(tmp_path.rglob("*.jsonl"))
        content = jsonl_files[0].read_text().strip()
        parsed = json.loads(content)
        assert "otel" in parsed
        assert parsed["otel"]["trace_id"] == "s1"


class TestCreateLogger:
    def test_creates_with_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.logging.load_env", lambda: {})
        monkeypatch.setattr("cli.lib.logging.get_active_project_name", lambda: "")

        logger = create_logger(session_id="s1", log_dir=tmp_path)
        assert len(logger.sinks) == 1
        assert isinstance(logger.sinks[0], FileSink)

    def test_creates_with_stdout(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.logging.load_env", lambda: {"SANDBOX_LOG_SINKS": "file,stdout"})
        monkeypatch.setattr("cli.lib.logging.get_active_project_name", lambda: "")

        logger = create_logger(session_id="s1", log_dir=tmp_path)
        assert len(logger.sinks) == 2
        types = [type(s).__name__ for s in logger.sinks]
        assert "FileSink" in types
        assert "StdoutSink" in types
