# Unified Event Envelope Schema

All sandbox log events use a canonical envelope format for consistent ingestion, correlation, and compatibility with external systems.

## Envelope Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string (ISO 8601) | Yes | UTC timestamp of the event |
| `event_type` | string | Yes | One of the fixed event types below |
| `project` | string | Yes | Project name (or "default" for root-level) |
| `session_id` | string | Yes | Session identifier for correlation |
| `source` | string | Yes | Component that generated the event |
| `payload` | object | Yes | Event-specific data |
| `otel` | object | No | OpenTelemetry compatibility fields (when enabled) |

## Event Types

| Type | Source | Description |
|------|--------|-------------|
| `session_start` | entrypoint | Container session began |
| `session_end` | entrypoint | Container session ended |
| `command` | entrypoint | Shell command executed |
| `mcp_request` | mcp-wrapper | MCP tool call sent to server |
| `mcp_response` | mcp-wrapper | MCP server responded |
| `mcp_lifecycle` | mcp-wrapper | MCP server started, stopped, or errored |
| `firewall_allow` | firewall-log | Outbound connection allowed |
| `firewall_block` | firewall-log | Outbound connection blocked |
| `proxy_request` | proxy | Request passed through TLS proxy |
| `system` | various | System-level events (startup, config changes) |

## Example Events

### Session start
```json
{
  "timestamp": "2026-03-26T12:00:00Z",
  "event_type": "session_start",
  "project": "billing-api",
  "session_id": "lgm_sandbox_20260326_120000",
  "source": "entrypoint",
  "payload": {
    "user": "lgm",
    "hostname": "sandbox",
    "platform": "Linux",
    "shell": "/bin/bash",
    "log_format": "json"
  }
}
```

### Command
```json
{
  "timestamp": "2026-03-26T12:01:00Z",
  "event_type": "command",
  "project": "billing-api",
  "session_id": "lgm_sandbox_20260326_120000",
  "source": "entrypoint",
  "payload": {
    "command": "npm test",
    "exit_code": 0,
    "cwd": "/workspace"
  }
}
```

### MCP request
```json
{
  "timestamp": "2026-03-26T12:02:00Z",
  "event_type": "mcp_request",
  "project": "billing-api",
  "session_id": "lgm_sandbox_20260326_120000",
  "source": "mcp-wrapper",
  "payload": {
    "server": "filesystem",
    "method": "tools/call",
    "tool": "read_file",
    "size_bytes": 142
  }
}
```

### Firewall block
```json
{
  "timestamp": "2026-03-26T12:03:00Z",
  "event_type": "firewall_block",
  "project": "billing-api",
  "session_id": "",
  "source": "firewall-log",
  "payload": {
    "dst": "198.51.100.1",
    "port": "443",
    "proto": "TCP"
  }
}
```

## OpenTelemetry Compatibility

When `SANDBOX_LOG_OTEL_COMPAT=true`, events include an `otel` section:

```json
{
  "timestamp": "...",
  "event_type": "mcp_request",
  "session_id": "lgm_sandbox_20260326_120000",
  "otel": {
    "trace_id": "lgm_sandbox_20260326_120000",
    "span_id": "evt_a1b2c3",
    "span_name": "mcp_request"
  },
  "payload": { ... }
}
```

This allows logs to be mapped to OpenTelemetry traces without implementing a full OTEL exporter.
