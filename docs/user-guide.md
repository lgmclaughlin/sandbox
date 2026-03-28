# User Guide

## Installation

Requires Python 3.11+, Docker, and [pipx](https://pipx.pypa.io/).

### Install pipx

```bash
pacman -S python-pipx    # Arch
brew install pipx         # macOS
apt install pipx          # Debian/Ubuntu
```

### Install sandbox

```bash
git clone <repo>
cd sandbox
pipx install .
```

The `sandbox` command is now available system-wide. pipx manages an isolated environment behind the scenes.

### Development (editable install)

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

The `sandbox` command is available inside the venv. Changes to source code are reflected immediately.

## Quick Start

```bash
# Start with current directory as workspace
sandbox start

# Start with a specific directory
sandbox start ~/projects/my-app

# Start with a specific profile
sandbox start --env=corp
```

On first run, sandbox scaffolds its configuration to your OS data directory:
- **Linux**: `~/.local/share/sandbox/`
- **macOS**: `~/Library/Application Support/sandbox/`
- **Windows**: `%APPDATA%/sandbox/`

Override with `SANDBOX_DATA_DIR` environment variable. Find the location anytime with `sandbox config show --path`.

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
| `sandbox tool install <name>` | Install a tool into the container |
| `sandbox tool remove <name>` | Remove a tool |
| `sandbox tool add <name>` | Create a new tool definition |
| `sandbox tool edit <name>` | Open tool definition in editor |
| `sandbox tool show <name>` | Display full tool definition |

Shipped tools: Claude Code (default), Aider, Open Interpreter.

### MCP Servers

| Command | Description |
|---------|-------------|
| `sandbox mcp list` | List MCP servers with permissions |
| `sandbox mcp enable <name>` | Enable a server |
| `sandbox mcp disable <name>` | Disable a server |
| `sandbox mcp add <name>` | Create a new MCP server definition |
| `sandbox mcp edit <name>` | Open MCP definition in editor |
| `sandbox mcp show <name>` | Display full MCP definition |
| `sandbox mcp logs` | View MCP request/response trace |

Shipped servers: filesystem, fetch (both disabled by default).

### Firewall

| Command | Description |
|---------|-------------|
| `sandbox fw ls` | List whitelisted domains |
| `sandbox fw add <domain>` | Add domain |
| `sandbox fw remove <domain>` | Remove domain |
| `sandbox fw apply` | Re-apply rules |
| `sandbox fw profiles` | List firewall profiles |
| `sandbox fw profile <name>` | Apply a profile |
| `sandbox fw create-profile <name>` | Create a new firewall profile |
| `sandbox fw edit-profile <name>` | Open profile in editor |
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

Enable with `sandbox config set SANDBOX_PROXY_MODE proxy`.

### Mounts

| Command | Description |
|---------|-------------|
| `sandbox mount list` | List configured mounts |
| `sandbox mount add <name>` | Add a mount definition |
| `sandbox mount remove <name>` | Remove a mount |

### Inspection Rules

| Command | Description |
|---------|-------------|
| `sandbox inspect list` | List content inspection rules |
| `sandbox inspect add <name>` | Add a rule |
| `sandbox inspect remove <name>` | Remove a rule |

### Configuration

| Command | Description |
|---------|-------------|
| `sandbox config show` | Display merged config |
| `sandbox config show --path` | Show config directory location |
| `sandbox config get <key>` | Get a specific value |
| `sandbox config set <key> <value>` | Set a value |
| `sandbox config profiles` | List environment profiles |
| `sandbox config create-profile <name>` | Create a new profile |
| `sandbox config edit` | Open config in editor |
| `sandbox config export` | Export config to portable file |
| `sandbox config import <file>` | Import config from file |
| `sandbox config reset` | Reset to defaults |

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

Configuration lives in the sandbox data directory. Manage via `sandbox config` commands or edit directly.

All environment variables in `.env`:

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
| `SANDBOX_DATA_DIR` | OS-specific | Override config directory location |
| `CUSTOM_CA_CERT_PATH` | (empty) | Custom CA certificate |

## Environment Profiles

Create profiles via CLI or direct file creation:

```bash
sandbox config create-profile corp
sandbox config edit --project corp
```

Or create `.env.corp` in the data directory with overrides:

```bash
SANDBOX_PROXY_MODE=proxy
SANDBOX_HARDENED_MODE=true
SANDBOX_ENFORCE_MCP_PERMISSIONS=true
SANDBOX_LOG_FORMAT=json
SANDBOX_LOG_SINKS=file,stdout
```

Activate with `sandbox config set SANDBOX_ENV corp` or `sandbox start --env=corp`.
