# Architecture

## Container Topology

```
Host Machine
├── sandbox CLI (Python/typer)
│
└── Docker
    ├── firewall container (NET_ADMIN, iptables, ipset)
    │   ├── Manages all network rules
    │   ├── ulogd2 + firewall log daemon (NFLOG → JSONL)
    │   └── Shared network stack with proxy and sandbox
    │
    ├── proxy container (optional, mitmproxy)
    │   ├── TLS termination for HTTPS inspection
    │   ├── Content inspection rules
    │   ├── DLP webhook integration
    │   └── network_mode: service:firewall
    │
    └── sandbox container (non-root, USER node)
        ├── AI tool (Claude Code, Aider, etc.)
        ├── MCP servers (via mcp-log-wrapper)
        ├── Workspace bind mount
        ├── Audit volume bind mount
        └── network_mode: service:firewall
```

All containers share the firewall's network stack. The sandbox has no independent network access.

### Trust boundaries
- **Sandbox container**: untrusted. No capabilities, non-root, `no-new-privileges: true`.
- **Firewall container**: trusted enforcement boundary. Requires `NET_ADMIN` and `NET_RAW` to configure iptables, scoped to its own bridge-isolated network namespace (cannot modify host networking). Connection logging via NFLOG + ulogd2 (userspace, no extra capabilities).
- **Proxy container**: optional. No special capabilities. Shares firewall network.

## Layer 1: Runtime

The sandbox container runs as non-root (`USER node`). Security features:
- `no-new-privileges: true` prevents privilege escalation
- Optional hardened mode: read-only filesystem, all capabilities dropped, tmpfs for writable paths
- Optional resource limits via `docker-compose.override.yml` (auto-generated)
- Health check verifies non-root execution
- Container keepalive entrypoint (`sleep infinity`), sessions managed via `session-wrapper.sh`

## Layer 2: Data Access

### Mounts
Remote filesystems mounted via rclone (default) or sshfs (fallback). Configured in `config/mounts.yaml`. Mount logic dispatches by type, handles missing config gracefully.

### MCP Servers
MCP server definitions live in `config/mcp/*.yaml`, independent from tool definitions. Tools declare where they read MCP config via `mcp.config_path`.

On `sandbox start`:
1. CLI scans `config/mcp/` for enabled servers
2. Generates `mcp-config.json` wrapping each server through `mcp-log-wrapper`
3. Writes config to the active tool's expected path

### MCP Log Wrapper
```
AI Tool <--stdin/stdout--> mcp-log-wrapper <--stdin/stdout--> MCP Server
                                |
                          logs/mcp/ (JSONL)
```

The wrapper is a Python script (`docker/mcp-log-wrapper.py`) baked into the Docker image. It:
- Proxies stdin/stdout transparently between the AI tool and the MCP server
- Logs every request and response as unified event envelopes
- Inherits `SANDBOX_SESSION_ID` from the container environment
- Optionally validates tool call arguments against declared permissions
- Returns JSON-RPC errors to the AI tool on permission violations

### MCP Permissions
When `SANDBOX_ENFORCE_MCP_PERMISSIONS=true`:
- `allowed_paths` restricts filesystem arguments to declared directories
- `blocked_patterns` rejects arguments matching regex patterns (e.g., path traversal)
- Violations logged as `mcp_validation_error` events
- Blocked requests return JSON-RPC error to the AI tool without forwarding

## Layer 3: Network Control

### Firewall
The firewall container uses iptables with ipset for domain-based filtering:
1. `firewall-init.sh` sets up base rules (DNS, SSH, loopback, Docker DNS)
2. GitHub IPs fetched and added to `git-domains` ipset
3. Whitelisted domains resolved and added to `allowed-domains` ipset
4. Default policy: DROP all outbound, REJECT with logged prefix

Firewall apply is atomic: domains resolve into a temporary ipset, then `ipset swap` replaces the active set with zero downtime.

### Firewall Profiles
Named sets of domains in `config/firewall/profiles/*.yaml`. When applied, profile domains merge with tool-specific domains. Profiles: `dev` (common registries), `restricted` (no domains).

### Firewall Logging
iptables NFLOG rules send packets to userspace via netlink. ulogd2 captures them and writes to log files. A daemon parses these into unified event envelopes at `logs/firewall/`. No kernel log access required.

### TLS Proxy (optional)
When `SANDBOX_PROXY_MODE=proxy`:
- mitmproxy container starts with the sandbox addon (`docker/proxy/addon.py`)
- Sandbox container gets `HTTP_PROXY`/`HTTPS_PROXY` env vars via compose override
- Proxy CA certificate shared via Docker volume, trusted by sandbox
- All HTTPS traffic decrypted, inspected, logged, and re-encrypted

### Content Inspection
Regex rules in `config/network/inspection.yaml` applied to request/response bodies. Actions: `alert` (log only) or `block` (reject with 403).

### DLP Integration
Optional webhook provider (`SANDBOX_DLP_PROVIDER=webhook`). The proxy addon calls the external DLP API before forwarding requests. Supports `allow`, `block`, and `redact` responses.

## Layer 4: Observability

### Unified Event Envelope
All log sources emit a canonical JSON schema:
```json
{
  "timestamp": "ISO 8601 UTC",
  "event_type": "command|mcp_request|firewall_block|...",
  "project": "project name",
  "session_id": "correlation ID",
  "source": "entrypoint|mcp-wrapper|firewall-log|proxy",
  "payload": { ... }
}
```

### Logging Sinks
`EventLogger` with pluggable sinks:
- `FileSink`: writes JSONL to audit volume, routes by event type, daily directories
- `StdoutSink`: emits JSON to stdout for `docker logs` compatibility

### Per-Layer Control
`SANDBOX_LOG_LAYERS` controls which layers produce logs. Default: `all`. Set to a comma-separated list to enable specific layers: `sessions`, `commands`, `firewall`, `mcp`, `proxy`. Each log source (session-wrapper, firewall daemon, MCP wrapper) checks this setting before writing.

### Session Correlation
`SANDBOX_SESSION_ID` set by `session-wrapper.sh`, available within the session. Every event includes the session ID for cross-layer tracing.

### OpenTelemetry Compatibility
When `SANDBOX_LOG_OTEL_COMPAT=true`, events include an `otel` section mapping `session_id` to `trace_id` and `event_id` to `span_id`. Enables integration with OTEL-compatible platforms via log field mapping.

### Log Management
- Daily rotation: `logs/{type}/{YYYY-MM-DD}/`
- Compression: gzip files older than 1 day on `sandbox logs rotate`
- Retention: delete files older than `SANDBOX_LOG_RETENTION_DAYS`
- Export: `sandbox logs export` produces portable JSON

## Layer 5: Workflow Engine

### Centralized Configuration
All sandbox config lives in a standard OS data directory:
- Linux: `$XDG_DATA_HOME/sandbox` or `~/.local/share/sandbox`
- macOS: `~/Library/Application Support/sandbox`
- Windows: `%APPDATA%/sandbox`

Override with `SANDBOX_DATA_DIR` env var.

On first run, sandbox scaffolds this directory from bundled templates (`cli/data/`). This works for both `pip install .` and `pip install -e .`.

Structure:
```
<data_dir>/
  .env, .env.dist          # Environment config
  config/                   # Tools, MCP, firewall, mounts, inspection
  docker/                   # Dockerfiles, compose, scripts
  logs/                     # Audit trail
  projects/                 # Named project overrides
```

Profile-based config merging: `.env.dist` (defaults) -> `.env` (local) -> `.env.{profile}` (profile-specific). Every configurable value has a corresponding CLI command (`sandbox config set/get`, `sandbox tool add`, etc.).

### Secrets
Pluggable provider interface (`SecretsProvider` ABC): `local` (obfuscated file) or `env` (environment variables). Secrets injected into containers as env vars on start, never baked into images.

### Multi-Project
Projects in `<data_dir>/projects/<name>/` with isolated config and logs. Container names scoped by `COMPOSE_PROJECT_NAME`. Active project resolved from `--project` flag, `SANDBOX_PROJECT` env var, or current directory. Workspace is always a user-provided path.
