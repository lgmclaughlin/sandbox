"""Unit tests for unified event envelope."""

from cli.lib.logging import build_envelope, EVENT_TYPES


class TestBuildEnvelope:
    def test_required_fields(self):
        event = build_envelope("command", "entrypoint", {"command": "ls"}, session_id="s1")
        assert "timestamp" in event
        assert event["event_type"] == "command"
        assert event["source"] == "entrypoint"
        assert event["session_id"] == "s1"
        assert event["payload"]["command"] == "ls"
        assert "project" in event

    def test_default_project(self):
        event = build_envelope("system", "test", {})
        assert event["project"] == "default"

    def test_custom_project(self):
        event = build_envelope("system", "test", {}, project="billing")
        assert event["project"] == "billing"

    def test_no_otel_by_default(self):
        event = build_envelope("command", "test", {})
        assert "otel" not in event

    def test_otel_compat(self):
        event = build_envelope(
            "mcp_request", "mcp-wrapper", {"server": "fs"},
            session_id="sess_123", otel_compat=True,
        )
        assert "otel" in event
        assert event["otel"]["trace_id"] == "sess_123"
        assert event["otel"]["span_name"] == "mcp_request"
        assert event["otel"]["span_id"].startswith("evt_")

    def test_all_event_types_valid(self):
        for event_type in EVENT_TYPES:
            event = build_envelope(event_type, "test", {})
            assert event["event_type"] == event_type


class TestEventTypes:
    def test_contains_session_events(self):
        assert "session_start" in EVENT_TYPES
        assert "session_end" in EVENT_TYPES

    def test_contains_command(self):
        assert "command" in EVENT_TYPES

    def test_contains_mcp_events(self):
        assert "mcp_request" in EVENT_TYPES
        assert "mcp_response" in EVENT_TYPES
        assert "mcp_lifecycle" in EVENT_TYPES
        assert "mcp_validation_error" in EVENT_TYPES

    def test_contains_firewall_events(self):
        assert "firewall_allow" in EVENT_TYPES
        assert "firewall_block" in EVENT_TYPES

    def test_contains_proxy_and_system(self):
        assert "proxy_request" in EVENT_TYPES
        assert "system" in EVENT_TYPES
