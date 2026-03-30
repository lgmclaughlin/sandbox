"""Unified event logging with pluggable sinks."""

import json
import sys
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from cli.lib.config import get_active_project_name, get_log_dir, load_env

# Map event types to their layer name for filtering
EVENT_TYPE_LAYERS = {
    "session_start": "sessions",
    "session_end": "sessions",
    "command": "commands",
    "mcp_request": "mcp",
    "mcp_response": "mcp",
    "mcp_lifecycle": "mcp",
    "mcp_validation_error": "mcp",
    "firewall_allow": "firewall",
    "firewall_block": "firewall",
    "proxy_request": "proxy",
    "system": "sessions",
}

EVENT_TYPES = {
    "session_start",
    "session_end",
    "command",
    "mcp_request",
    "mcp_response",
    "mcp_lifecycle",
    "mcp_validation_error",
    "firewall_allow",
    "firewall_block",
    "proxy_request",
    "system",
}


def build_envelope(
    event_type: str,
    source: str,
    payload: dict,
    session_id: str = "",
    project: str = "",
    otel_compat: bool = False,
) -> dict:
    """Build a canonical event envelope."""
    event_id = uuid.uuid4().hex[:12]

    envelope = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "project": project or get_active_project_name() or "default",
        "session_id": session_id,
        "source": source,
        "payload": payload,
    }

    if otel_compat:
        envelope["otel"] = {
            "trace_id": session_id or "",
            "span_id": f"evt_{event_id}",
            "span_name": event_type,
        }

    return envelope


class Sink(ABC):
    """Base class for log sinks."""

    @abstractmethod
    def write(self, event: dict) -> None:
        """Write an event to this sink."""

    def close(self) -> None:
        """Clean up resources."""


class FileSink(Sink):
    """Writes events as JSONL to the audit volume."""

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir

    def _get_log_path(self, event: dict) -> Path:
        log_dir = self.log_dir or get_log_dir()
        event_type = event.get("event_type", "system")
        today = datetime.now().strftime("%Y-%m-%d")

        type_map = {
            "session_start": "sessions",
            "session_end": "sessions",
            "command": "commands",
            "mcp_request": "mcp",
            "mcp_response": "mcp",
            "mcp_lifecycle": "mcp",
            "mcp_validation_error": "mcp",
            "firewall_allow": "firewall",
            "firewall_block": "firewall",
            "proxy_request": "proxy",
            "system": "system",
        }

        subdir = type_map.get(event_type, "system")
        path = log_dir / subdir / today
        path.mkdir(parents=True, exist_ok=True)

        session_id = event.get("session_id", "unknown")
        return path / f"{session_id}.jsonl"

    def write(self, event: dict) -> None:
        log_path = self._get_log_path(event)
        with open(log_path, "a") as f:
            f.write(json.dumps(event) + "\n")


class StdoutSink(Sink):
    """Emits events as JSON to stdout for docker logs compatibility."""

    def write(self, event: dict) -> None:
        sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()


class EventLogger:
    """Unified event logger with pluggable sinks."""

    def __init__(
        self,
        sinks: list[Sink] | None = None,
        session_id: str = "",
        project: str = "",
        otel_compat: bool = False,
        max_payload_bytes: int = 0,
        enabled_layers: str = "all",
    ):
        self.sinks = sinks or []
        self.session_id = session_id
        self.project = project
        self.otel_compat = otel_compat
        self.max_payload_bytes = max_payload_bytes
        self.enabled_layers = enabled_layers

    def _is_layer_enabled(self, event_type: str) -> bool:
        """Check if the layer for this event type is enabled."""
        if self.enabled_layers == "all":
            return True
        if self.enabled_layers == "none":
            return False
        enabled = {l.strip() for l in self.enabled_layers.split(",")}
        layer = EVENT_TYPE_LAYERS.get(event_type, "system")
        return layer in enabled

    def emit(self, event_type: str, source: str, payload: dict) -> None:
        """Emit an event through all sinks if the layer is enabled."""
        if not self._is_layer_enabled(event_type):
            return
        if self.max_payload_bytes > 0:
            payload = self._truncate_payload(payload)

        event = build_envelope(
            event_type=event_type,
            source=source,
            payload=payload,
            session_id=self.session_id,
            project=self.project,
            otel_compat=self.otel_compat,
        )

        for sink in self.sinks:
            try:
                sink.write(event)
            except OSError:
                pass

    def _truncate_payload(self, payload: dict) -> dict:
        """Truncate large payload values."""
        result = {}
        for key, value in payload.items():
            if isinstance(value, str) and len(value) > self.max_payload_bytes:
                result[key] = value[:self.max_payload_bytes]
                result[f"{key}_truncated"] = True
                result[f"{key}_original_size"] = len(value)
            else:
                result[key] = value
        return result

    def close(self) -> None:
        """Close all sinks."""
        for sink in self.sinks:
            sink.close()


def create_logger(
    session_id: str = "",
    log_dir: Path | None = None,
) -> EventLogger:
    """Create a logger from current configuration."""
    env = load_env()

    sink_names = env.get("SANDBOX_LOG_SINKS", "file")
    otel_compat = env.get("SANDBOX_LOG_OTEL_COMPAT", "").lower() == "true"
    max_payload = int(env.get("SANDBOX_LOG_MAX_PAYLOAD_BYTES", "0"))
    enabled_layers = env.get("SANDBOX_LOG_LAYERS", "all")
    project = get_active_project_name() or "default"

    sinks: list[Sink] = []
    for name in sink_names.split(","):
        name = name.strip()
        if name == "file":
            sinks.append(FileSink(log_dir=log_dir))
        elif name == "stdout":
            sinks.append(StdoutSink())

    if not sinks:
        sinks.append(FileSink(log_dir=log_dir))

    return EventLogger(
        sinks=sinks,
        session_id=session_id,
        project=project,
        otel_compat=otel_compat,
        max_payload_bytes=max_payload,
        enabled_layers=enabled_layers,
    )
