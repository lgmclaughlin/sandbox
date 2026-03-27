# Sandbox

Secure, auditable execution environment for LLM-based development tools.

Run AI coding assistants (Claude Code, Aider, etc.) inside a locked-down container with network controls, session logging, and compliance checks.

## Features

- **Isolated runtime**: Non-root container with separate firewall container
- **Network control**: Domain whitelist firewall with profiles, connection logging, and per-tool domain management
- **Audit logging**: Terminal session recording, command history, structured JSON logs, daily rotation
- **Tool management**: Install/switch AI tools via CLI, each with its own dependencies and firewall rules
- **MCP server support**: Tool-agnostic MCP servers with automatic session-correlated logging via transparent wrapper
- **Secrets management**: Encrypted local storage or environment variable injection for API keys
- **Environment profiles**: Switch between dev, corp, and custom configurations
- **Multi-project**: Run multiple isolated sandbox instances with separate configs, workspaces, and logs
- **Zero-config start**: Clone, run `sandbox start`, and get a working environment with sensible defaults
- **Cross-platform**: Linux, macOS, and Windows support

## Quick start

```bash
git clone <repo>
cd sandbox
pip install .
sandbox start
```

For development (editable install with test dependencies):
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## CLI

```
Lifecycle       sandbox start [path]|stop|restart|rebuild|status|attach
Projects        sandbox init <name>|projects
Tools           sandbox tool list|install|remove
MCP             sandbox mcp list|enable|disable|logs
Secrets         sandbox secrets set|get|list|delete
Firewall        sandbox fw ls|add|remove|apply|profiles|profile|logs
Config          sandbox config show|profiles
Logs            sandbox logs view|rotate|summary
Observability   sandbox check|info|version
```

### Examples

```bash
sandbox start                           # Start with current directory as workspace
sandbox start ~/projects/my-app         # Start with specific workspace
sandbox start --env=corp                # Start with a specific profile
sandbox --project billing start         # Start a named project
sandbox init my-project -w ~/code/repo  # Initialize project with external workspace
sandbox fw add api.example.com          # Whitelist a domain
sandbox fw profile dev                  # Apply dev firewall profile
sandbox tool install aider              # Install a tool
sandbox mcp enable filesystem           # Enable an MCP server
sandbox secrets set API_KEY sk-...      # Store a secret
sandbox config show                     # View merged configuration
sandbox check                           # Run compliance checks
sandbox logs view --session <id>        # View full session trace
sandbox info                            # Combined status + config overview
```

## Configuration

| File | Purpose |
|------|---------|
| `.env.dist` | Default configuration (committed) |
| `.env` | Local overrides (gitignored, auto-created) |
| `.env.{profile}` | Profile-specific config (e.g., `.env.corp`) |
| `config/tools/` | AI tool definitions (Claude Code, Aider, Open Interpreter) |
| `config/mcp/` | MCP server definitions (tool-agnostic) |
| `config/mounts.yaml` | Remote mount definitions (rclone/sshfs) |
| `config/firewall/profiles/` | Firewall domain profiles (dev, restricted) |

## Project structure

```
cli/                  # Python CLI (typer)
  commands/           # CLI command modules
  lib/                # Core libraries (config, docker, firewall, secrets, mcp, mounts)
config/               # Tool definitions, MCP servers, mount config, firewall profiles
docker/               # Dockerfiles, compose, firewall scripts, MCP log wrapper
test/                 # pytest (unit + integration, 163 tests)
projects/             # Multi-project instances (gitignored)
logs/                 # Audit trail (gitignored)
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Testing

```bash
pytest              # Run all tests
pytest test/unit    # Unit tests only
pytest -v           # Verbose output
```

## License

MIT
