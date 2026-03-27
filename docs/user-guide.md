# User Guide

## Installation

Requires Python 3.11+ and Docker.

### System-wide

```bash
git clone <repo>
cd sandbox
pip install .
```

This installs the `sandbox` command to your PATH. Location varies by platform:
- **Linux**: `~/.local/bin/sandbox`
- **macOS**: `~/.local/bin/sandbox` (or `~/Library/Python/3.x/bin/` depending on Python install)
- **Windows**: `%APPDATA%\Python\Scripts\sandbox.exe`

Ensure the install location is in your PATH. Works from any directory without activating a venv.

### Development (editable, venv-scoped)

**Linux / macOS:**
```bash
git clone <repo>
cd sandbox
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

**Windows:**
```powershell
git clone <repo>
cd sandbox
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

The `sandbox` command is available inside the venv. Changes to the source code are reflected immediately.

## Quick Start

```bash
# Start with current directory as workspace
sandbox start

# Start with a specific directory
sandbox start ~/projects/my-app

# Start with a specific profile
sandbox start --env=corp
```

On first run, `.env` is auto-created from `.env.dist` with sensible defaults. The firewall and sandbox containers start, and you're attached to a shell inside the sandbox.

## CLI Commands

### Lifecycle

| Command | Description |
|---------|-------------|
| `sandbox start [path]` | Start sandbox with workspace directory |
| `sandbox stop` | Stop all containers |
| `sandbox restart` | Stop then start |
| `sandbox rebuild` | Rebuild images and restart |
| `sandbox status` | Show container and tool status |
| `sandbox attach` | Attach to running sandbox shell |

Options for `start`:
- `--no-attach` to start without attaching
- `--env <profile>` to use an environment profile
- `--offline` to skip network-dependent operations

### Projects

| Command | Description |
|---------|-------------|
| `sandbox init <name>` | Create a new project |
| `sandbox projects` | List all projects |

Use `--project <name>` or `-p <name>` on any command to scope it to a project.

```bash
sandbox init billing --workspace ~/code/billing-api
sandbox --project billing start
sandbox --project billing status
```

### Tool Management

| Command | Description |
|---------|-------------|
| `sandbox tool list` | List available tools |
| `sandbox tool install <name>` | Install a tool |
| `sandbox tool remove <name>` | Remove a tool |

Tools are defined in `config/tools/*.yaml`. Shipped tools: Claude Code (default), Aider, Open Interpreter.

### MCP Servers

| Command | Description |
|---------|-------------|
| `sandbox mcp list` | List MCP servers with permissions |
| `sandbox mcp enable <name>` | Enable a server |
| `sandbox mcp disable <name>` | Disable a server |
| `sandbox mcp logs` | View MCP request/response trace |

MCP servers are defined in `config/mcp/*.yaml`. Shipped servers: filesystem, fetch (both disabled by default).

### Firewall

| Command | Description |
|---------|-------------|
| `sandbox fw ls` | List whitelisted domains |
| `sandbox fw add <domain>` | Add domain |
| `sandbox fw remove <domain>` | Remove domain |
| `sandbox fw apply` | Re-apply rules |
| `sandbox fw profiles` | List firewall profiles |
| `sandbox fw profile <name>` | Apply a profile |
| `sandbox fw logs` | View connection logs |

### Secrets

| Command | Description |
|---------|-------------|
| `sandbox secrets set <key> <value>` | Store a secret |
| `sandbox secrets get <key>` | Retrieve (masked) |
| `sandbox secrets get <key> --show` | Retrieve (plaintext) |
| `sandbox secrets list` | List key names |
| `sandbox secrets delete <key>` | Delete a secret |

### Proxy

| Command | Description |
|---------|-------------|
| `sandbox proxy status` | Show proxy state |
| `sandbox proxy logs` | View proxy request logs |

Enable with `SANDBOX_PROXY_MODE=proxy` in `.env`.

### Configuration

| Command | Description |
|---------|-------------|
| `sandbox config show` | Display merged config |
| `sandbox config profiles` | List environment profiles |

### Logs

| Command | Description |
|---------|-------------|
| `sandbox logs view [type]` | View audit logs |
| `sandbox logs rotate` | Clean up old logs |
| `sandbox logs summary` | High-level overview |
| `sandbox logs export` | Export as portable JSON |

### Observability

| Command | Description |
|---------|-------------|
| `sandbox check` | Run compliance checks |
| `sandbox info` | Combined status + config overview |
| `sandbox update --check` | Check for updates |
| `sandbox update --apply` | Pull and rebuild |
| `sandbox version` | Show version |

## Configuration Reference

All configuration is via environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPOSE_PROJECT_NAME` | `project` | Container naming prefix |
| `TZ` | auto-detected | Timezone |
| `SANDBOX_ENV` | (empty) | Active profile name |
| `SANDBOX_LOG_DIR` | `./logs` | Audit log directory |
| `SANDBOX_LOG_FORMAT` | `text` | Log format: `text` or `json` |
| `SANDBOX_LOG_RETENTION_DAYS` | `30` | Days to keep logs |
| `SANDBOX_LOG_SINKS` | `file` | Log sinks: `file`, `stdout`, `file,stdout` |
| `SANDBOX_LOG_OTEL_COMPAT` | `false` | OpenTelemetry field mapping |
| `SANDBOX_LOG_MAX_PAYLOAD_BYTES` | `0` | Truncate large payloads (0=off) |
| `SANDBOX_SECRETS_PROVIDER` | `local` | Secrets provider: `local` or `env` |
| `SANDBOX_PROXY_MODE` | `firewall-only` | `firewall-only` or `proxy` |
| `SANDBOX_DLP_PROVIDER` | `none` | DLP provider: `none` or `webhook` |
| `SANDBOX_CPU_LIMIT` | (empty) | CPU limit (e.g., `2.0`) |
| `SANDBOX_MEM_LIMIT` | (empty) | Memory limit (e.g., `4g`) |
| `SANDBOX_HARDENED_MODE` | `false` | Read-only filesystem, drop caps |
| `SANDBOX_OFFLINE_MODE` | `false` | Skip network operations |
| `SANDBOX_ENFORCE_MCP_PERMISSIONS` | `false` | Validate MCP tool calls |
| `HTTP_PROXY` / `HTTPS_PROXY` | (empty) | Corporate proxy |
| `CUSTOM_CA_CERT_PATH` | (empty) | Custom CA certificate |

## Environment Profiles

Create `.env.dev`, `.env.corp`, etc. with profile-specific overrides:

```bash
# .env.corp
SANDBOX_PROXY_MODE=proxy
SANDBOX_HARDENED_MODE=true
SANDBOX_ENFORCE_MCP_PERMISSIONS=true
SANDBOX_LOG_FORMAT=json
SANDBOX_LOG_SINKS=file,stdout
```

Activate with `SANDBOX_ENV=corp` in `.env` or `sandbox start --env=corp`.
