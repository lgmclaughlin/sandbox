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
- **Multi-project**: Run multiple isolated sandbox instances with separate configs and logs
- **Full CLI coverage**: Every configuration aspect manageable via commands
- **Cross-platform**: Linux, macOS, and Windows support

## Quick start

```bash
pip install .
sandbox start
```

On first run, sandbox scaffolds configuration to your OS data directory (`~/.local/share/sandbox/` on Linux). For development:
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## CLI

```
Lifecycle       sandbox start [path]|stop|restart|rebuild|status|attach
Projects        sandbox init <name>|projects
Tools           sandbox tool list|install|remove|add|edit|show
MCP             sandbox mcp list|enable|disable|add|edit|show|logs
Secrets         sandbox secrets set|get|list|delete
Firewall        sandbox fw ls|add|remove|apply|profiles|profile|create-profile|edit-profile|logs
Proxy           sandbox proxy status|logs
Mounts          sandbox mount list|add|remove
Inspection      sandbox inspect list|add|remove
Config          sandbox config show|get|set|profiles|create-profile|edit|export|import|reset
Logs            sandbox logs view|rotate|summary|export
Observability   sandbox check|info|update|version
```

### Examples

```bash
sandbox start                           # Start with current directory as workspace
sandbox start ~/projects/my-app         # Start with specific workspace
sandbox start --env=corp                # Start with a specific profile
sandbox --project billing start         # Start a named project
sandbox init my-project -w ~/code/repo  # Initialize project with external workspace
sandbox config set SANDBOX_LOG_FORMAT json  # Set a config value
sandbox config show --path              # Show config directory location
sandbox tool add my-tool --method pip --package my-pkg  # Create tool definition
sandbox mcp add my-server --command node --args server.js  # Create MCP server
sandbox fw add api.example.com          # Whitelist a domain
sandbox fw create-profile staging --domains api.staging.com,cdn.staging.com
sandbox mount add data --type rclone --remote s3:bucket/path --local ./data
sandbox inspect add ssn --pattern '\b\d{3}-\d{2}-\d{4}\b' --action block
sandbox secrets set API_KEY sk-...      # Store a secret
sandbox config export -o backup.json    # Export config for sharing
sandbox check                           # Run compliance checks
sandbox logs view --session <id>        # View full session trace
sandbox info                            # Combined status + config overview
```

## Configuration

Configuration lives in the sandbox data directory (find with `sandbox config show --path`):

| Directory | Contents |
|-----------|----------|
| `.env` / `.env.dist` | Environment variables |
| `config/tools/` | AI tool definitions (Claude Code, Aider, Open Interpreter) |
| `config/mcp/` | MCP server definitions (filesystem, fetch) |
| `config/firewall/profiles/` | Firewall domain profiles (dev, restricted) |
| `config/network/` | Content inspection and DLP rules |
| `config/mounts.yaml` | Remote mount definitions (rclone/sshfs) |
| `docker/` | Dockerfiles, compose, firewall scripts |
| `logs/` | Audit trail |
| `projects/` | Named project overrides |

## Project structure

```
cli/                  # Python CLI (typer)
  commands/           # CLI command modules
  lib/                # Core libraries (config, docker, firewall, secrets, mcp, mounts)
  data/               # Bundled templates (scaffolded to data dir on first run)
test/                 # pytest (unit + integration, 184 tests)
docs/                 # User guide, architecture, use cases, MCP guide, deployment guide
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
