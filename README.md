# Sandbox

AI coding tools can execute code, access files, and make network requests, often without clear boundaries or audit trails. Sandbox provides a controlled runtime that enforces these boundaries and produces a complete, traceable record of what happened.

## How It Works

```
AI Tool (Claude Code, Aider, etc.)
        |
Sandbox Container (untrusted, non-root)
        |
Shared Network Namespace
        |
Firewall Container (enforces all egress)
        |
(Optional) TLS Proxy (inspection, DLP)
```

- The sandbox container has no direct network access
- All tool calls (MCP) are intercepted and logged via a transparent wrapper
- All activity is recorded as structured events with session correlation

## Capabilities

### Isolation and Enforcement
- Non-root container with deny-by-default network policy
- All traffic forced through a separate firewall container
- Domain-based egress control with named profiles (dev, restricted, custom)
- Optional TLS proxy for content inspection and DLP integration
- Resource limits and hardened mode (read-only filesystem, dropped capabilities)

### Observability and Auditability
- Unified JSON event logging across commands, MCP calls, firewall, and proxy
- Session-correlated execution traces
- OpenTelemetry-compatible field mapping
- Exportable logs for external systems (Fluent Bit, Filebeat, Vector)

### Tool and Data Control
- Pluggable AI tool definitions with per-tool firewall domains
- MCP servers with permission enforcement and path validation
- Secrets management with encrypted local storage or environment injection
- Remote mount support (rclone, sshfs) with declarative configuration

### Developer Experience
- CLI-driven workflow
- Multi-project isolation with named instances
- Environment profiles for switching between configurations
- Centralized config with first-run scaffolding
- Cross-platform support (Linux, macOS, Windows)

## Quick Start

```bash
pipx install .
sandbox start
```

On first run, configuration is scaffolded to your OS data directory. Find it with `sandbox config show --path`.

Requires Python 3.11+, Docker, and [pipx](https://pipx.pypa.io/):
```bash
pacman -S python-pipx    # Arch
brew install pipx         # macOS
apt install pipx          # Debian/Ubuntu
```

## Example: Blocked Network Request

```bash
sandbox start ~/my-project
# inside the sandbox container:
curl https://unapproved-domain.com
# request blocked by firewall
```

The event is logged:
```json
{
  "event_type": "firewall_block",
  "session_id": "lgm_sandbox_20260327_120000",
  "source": "firewall-log",
  "payload": {
    "dst": "203.0.113.50",
    "port": "443",
    "proto": "TCP"
  }
}
```

View it with `sandbox fw logs` or `sandbox logs view --session <id>` for the full session trace.

## Core Workflow

```bash
sandbox start                    # Start with current directory as workspace
sandbox attach                   # Attach to the sandbox shell
sandbox stop                     # Stop all containers
```

## Common Tasks

```bash
sandbox tool install claude-code           # Install an AI tool
sandbox fw add api.example.com             # Whitelist a domain
sandbox mcp enable filesystem              # Enable an MCP server
sandbox secrets set API_KEY sk-...         # Store a secret
sandbox config set SANDBOX_LOG_FORMAT json # Change a setting
sandbox logs view --session <id>           # View session trace
sandbox check                              # Run compliance checks
```

See the [full CLI reference](docs/user-guide.md) and [architecture documentation](docs/architecture.md) for details.

## Security Model

- **Host**: trusted
- **Firewall container**: enforcement boundary, controls all network access
- **Sandbox container**: untrusted execution environment
- **Proxy** (optional): inspects encrypted traffic, applies DLP rules
- All outbound traffic is explicitly allowed or blocked
- All tool access is mediated and logged via MCP wrappers

## Use Cases

- Run AI coding tools safely on sensitive codebases
- Enforce network and data access policies for LLM agents
- Generate audit logs for compliance or incident review
- Create reproducible, isolated AI development environments

## Configuration

Configuration lives in the sandbox data directory. Manage via `sandbox config` commands.

```bash
sandbox config show --path       # Where config lives
sandbox config show              # View merged config
sandbox config set <key> <value> # Set a value
sandbox config export            # Export for sharing
```

See the [user guide](docs/user-guide.md) for the full configuration reference.

> Sandbox produces structured execution logs. It does not replace observability platforms (Datadog, OpenTelemetry, etc.) but integrates with them via JSON log export and OTEL-compatible fields.

## Updating

```bash
# pipx install
git pull && pipx upgrade sandbox

# Development install
git pull && pip install -e ".[dev]"

# Rebuild containers after updating
sandbox rebuild
```

## Platform Status

| Feature | Linux | macOS | Windows |
|---------|-------|-------|---------|
| Core CLI | Tested | Expected to work | Expected to work |
| Containers | Tested | Docker Desktop | Docker Desktop |
| Firewall | Tested | Tested (in container) | Tested (in container) |
| Session logging | Tested | Expected to work | Expected to work |
| Mount system (rclone/sshfs) | Tested | Needs macFUSE testing | Limited (WinFsp) |
| Mount conflict detection | Tested | Needs `findmnt` alternative | Not supported |
| Bind propagation for mounts | Tested | Untested (Docker Desktop) | Untested |

Primary development and testing is on Linux. macOS and Windows support is architecturally present but needs testing on those platforms. See the [deployment guide](docs/deployment-guide.md) for details.

## Development

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## License

MIT
