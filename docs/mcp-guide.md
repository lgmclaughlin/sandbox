# MCP Integration Guide

## Overview

MCP (Model Context Protocol) servers provide structured data access to AI tools. In the sandbox, MCP servers are:
- **Tool-agnostic**: Defined independently from AI tools
- **Automatically logged**: All traffic passes through a transparent wrapper
- **Permission-controlled**: Optional enforcement of filesystem and network access

## How It Works

```
AI Tool (Claude Code, Aider)
    ↓ reads mcp-config.json
    ↓ spawns what it thinks is the MCP server
mcp-log-wrapper (transparent proxy)
    ↓ logs all requests/responses
    ↓ validates permissions (if enabled)
    ↓ spawns the actual server
MCP Server (filesystem, fetch, custom)
```

The AI tool never communicates directly with the MCP server. The wrapper intercepts all stdio traffic, logs it with session correlation, and optionally validates permissions before forwarding.

## Built-in Server Definitions

### filesystem
Safe file listing and reading within `/workspace`.

```bash
sandbox mcp enable filesystem
```

### fetch
HTTP requests for API access.

```bash
sandbox mcp enable fetch
```

Both disabled by default. Enable only what's needed.

## Writing a Custom MCP Server Definition

Create `config/mcp/my-server.yaml`:

```yaml
name: my-server
description: What this server does
enabled: false
command: node
args: ["/path/to/server.js"]

permissions:
  - filesystem: read
  - network: none

allowed_paths:
  - /workspace

validation:
  blocked_patterns:
    - '\.\.\/'
    - '/etc/'

firewall:
  domains: []

env:
  MY_SERVER_API_KEY: ""
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier |
| `description` | Yes | Human-readable description |
| `enabled` | No | Default: true |
| `command` | Yes | Command to run the server |
| `args` | Yes | Arguments for the command |
| `permissions` | No | Declared access types (for documentation and enforcement) |
| `allowed_paths` | No | Filesystem paths the server can access (enforced when permissions enabled) |
| `validation.blocked_patterns` | No | Regex patterns to reject in tool call arguments |
| `firewall.domains` | No | Domains the server needs (merged into firewall whitelist) |
| `env` | No | Environment variables passed to the server |

### Permission Types

| Permission | Values | Description |
|------------|--------|-------------|
| `filesystem` | `read`, `write`, `list`, `none` | File access level |
| `network` | `read`, `write`, `none` | Network access level |

## Permission Enforcement

Enable with `SANDBOX_ENFORCE_MCP_PERMISSIONS=true` in `.env`.

When enabled, the wrapper validates every `tools/call` request:

1. **Path validation**: Arguments with "path" or "file" in the key are checked against `allowed_paths`
2. **Pattern blocking**: All string arguments are checked against `blocked_patterns`
3. **On violation**: Returns a JSON-RPC error to the AI tool, logs a `mcp_validation_error` event, does NOT forward to the server

Example violation log:
```json
{
  "event_type": "mcp_validation_error",
  "source": "mcp-wrapper",
  "payload": {
    "server": "filesystem",
    "tool": "read_file",
    "violation": "Path '/etc/passwd' not in allowed paths: ['/workspace']"
  }
}
```

## Viewing MCP Logs

```bash
# All MCP traffic
sandbox mcp logs

# Filter by server
sandbox mcp logs --server filesystem

# Full session trace (MCP + commands + firewall)
sandbox logs view --session <session_id>

# Export for analysis
sandbox logs export --session <session_id> --output trace.json
```

## Session Correlation

Every MCP log entry includes `session_id`, linking it to:
- The terminal session that triggered the AI tool
- Commands typed before/after the MCP call
- Firewall events showing network access by the MCP server

```
session_id: lgm_sandbox_20260326_120000
  ├── session_start
  ├── command: "claude review src/"
  ├── mcp_request: filesystem.read_file("/workspace/src/main.py")
  ├── mcp_response: (4200 bytes)
  ├── firewall_allow: api.anthropic.com:443
  └── session_end
```

## Troubleshooting

### Server not appearing in mcp-config.json
- Check `sandbox mcp list` to see if it's enabled
- Verify the YAML syntax with `python -c "import yaml; yaml.safe_load(open('config/mcp/my-server.yaml'))"`

### Permission denied errors
- Check `sandbox mcp logs` for `mcp_validation_error` events
- Verify `allowed_paths` includes the paths your server needs
- Check `blocked_patterns` aren't matching legitimate arguments

### Server fails to start
- Check `sandbox mcp logs` for `mcp_lifecycle` events with `"event": "error"`
- Verify the command and args are correct
- Ensure required dependencies are installed in the container
