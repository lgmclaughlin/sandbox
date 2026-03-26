# Sandbox

Secure, auditable execution environment for LLM-based development tools.

Run AI coding assistants (Claude Code, Aider, etc.) inside a locked-down container with network controls, session logging, and compliance checks.

## Features

- **Isolated runtime**: Non-root container with separate firewall container
- **Network control**: Domain whitelist firewall that blocks unauthorized outbound traffic
- **Audit logging**: Terminal session recording, command history, user identity capture
- **Tool management**: Install/switch AI tools via CLI, each with its own dependencies and firewall rules
- **Secrets management**: Encrypted local storage or environment variable injection for API keys
- **Environment profiles**: Switch between dev, corp, and custom configurations
- **Zero-config start**: Clone, run `sandbox start`, and get a working environment with sensible defaults
- **Cross-platform**: Linux, macOS, and Windows support

## Quick start

```bash
git clone <repo>
cd sandbox
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
sandbox start
```

## CLI

```
Lifecycle       sandbox start|stop|restart|rebuild|status|attach
Firewall        sandbox fw ls|add|remove|apply
Tools           sandbox tool list|install|remove
Secrets         sandbox secrets set|get|list|delete
Config          sandbox config show|profiles
Observability   sandbox logs|check|rotate
```

### Examples

```bash
sandbox start                       # Start with defaults
sandbox start --env=corp            # Start with corporate profile
sandbox fw add api.example.com      # Whitelist a domain
sandbox tool install aider          # Install a tool
sandbox secrets set API_KEY sk-...  # Store a secret
sandbox config show                 # View merged configuration
sandbox check                       # Run compliance checks
```

## Configuration

| File | Purpose |
|------|---------|
| `.env.dist` | Default configuration (committed) |
| `.env` | Local overrides (gitignored, auto-created) |
| `.env.{profile}` | Profile-specific config (e.g., `.env.corp`) |
| `config/tools/` | AI tool definitions |
| `config/mounts.yaml` | Remote mount definitions (rclone/sshfs) |

## Project structure

```
cli/                  # Python CLI (typer)
  commands/           # CLI command modules
  lib/                # Core libraries (config, docker, firewall, secrets)
config/               # Tool definitions, mount config
docker/               # Dockerfiles, compose, firewall scripts
test/                 # pytest (unit + integration)
logs/                 # Audit trail (gitignored)
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
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
