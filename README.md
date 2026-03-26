# Sandbox

Secure, auditable execution environment for LLM-based development tools.

Run AI coding assistants (Claude Code, Aider, etc.) inside a locked-down container with network controls, session logging, and compliance checks.

## Features (Phase 1 in progress)

- **Isolated runtime**: Non-root container with separate firewall container
- **Network control**: Domain whitelist firewall that blocks unauthorized outbound traffic
- **Audit logging**: Terminal session recording, command history, user identity capture
- **Tool management**: Install/switch AI tools via CLI, each with its own dependencies and firewall rules
- **Zero-config start**: Clone, run `sandbox start`, and get a working environment with sensible defaults

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
sandbox start|stop|restart|rebuild|status|attach
sandbox fw ls|add|remove|apply
sandbox tool list|install|remove
sandbox logs|check
```

## Project structure

```
cli/                  # Python CLI (typer)
config/               # mounts.yaml, tools/
docker/               # Dockerfiles, compose, firewall scripts
docs/                 # DLP.md, etc.
test/                 # pytest
logs/                 # Audit trail (gitignored)
```

## Testing

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest              # Run all tests
pytest test/unit    # Unit tests only
pytest -v           # Verbose output
```

## License

MIT
