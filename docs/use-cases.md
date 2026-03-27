# Use Cases

## Single Developer

The simplest setup. Clone the repo, start the sandbox, and work.

```bash
cd ~/projects/my-app
sandbox start .
```

The sandbox mounts your project directory, starts the firewall with default rules, and drops you into a shell with Claude Code available. Your files are at `/workspace` inside the container.

When you're done:
```bash
sandbox stop
```

Audit logs are in `./logs/` for review.

## Secure Environment

A locked-down setup with TLS proxy, DLP, hardened containers, and JSON logging for log agent integration.

### Setup

Create `.env.corp`:
```bash
SANDBOX_PROXY_MODE=proxy
SANDBOX_HARDENED_MODE=true
SANDBOX_ENFORCE_MCP_PERMISSIONS=true
SANDBOX_LOG_FORMAT=json
SANDBOX_LOG_SINKS=file,stdout
SANDBOX_CPU_LIMIT=2.0
SANDBOX_MEM_LIMIT=4g
SANDBOX_DLP_PROVIDER=webhook
SANDBOX_DLP_WEBHOOK_URL=https://dlp.internal.company.com/scan
```

### Usage

```bash
sandbox start --env=corp ~/projects/billing-api
```

This starts with:
- TLS-terminating proxy inspecting all HTTPS traffic
- DLP webhook scanning outbound requests
- Read-only container with dropped capabilities
- Resource limits preventing runaway processes
- JSON logs compatible with Fluent Bit, Filebeat, etc.
- MCP permission enforcement

### Compliance verification

```bash
sandbox check
```

Reports pass/fail for: container non-root, firewall running, proxy running, DLP configured, resource limits set, MCP permissions enforced.

## Multi-Project

Run multiple isolated sandboxes simultaneously, each with their own config, tools, and audit trail.

```bash
# Initialize projects
sandbox init billing --workspace ~/code/billing-api
sandbox init frontend --workspace ~/code/web-frontend

# Start both
sandbox --project billing start --no-attach
sandbox --project frontend start --no-attach

# Check status
sandbox --project billing status
sandbox --project frontend status

# Attach to one
sandbox --project billing attach

# View logs for a specific project
sandbox --project frontend logs view sessions
```

Each project gets independent firewall rules, secrets, MCP servers, and log directories.

## CI/CD Integration

Use the `env` secrets provider to inject credentials from CI environment variables without storing them on disk.

### GitHub Actions example

```yaml
jobs:
  ai-review:
    runs-on: ubuntu-latest
    env:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev]"
      - run: |
          export SANDBOX_SECRETS_PROVIDER=env
          sandbox start --no-attach .
          sandbox tool install claude-code
          # Run AI-assisted analysis inside the sandbox
          sandbox stop
```

The `env` provider reads secrets directly from environment variables. No local secret storage needed.

## Remote Data Access

Mount cloud storage or remote servers into the workspace.

### Setup `config/mounts.yaml`

```yaml
mounts:
  - name: data-lake
    type: rclone
    remote: "s3:company-data-lake/datasets"
    local: ./workspace/data
    options:
      vfs-cache-mode: full

  - name: staging
    type: sshfs
    remote: "deploy@staging.internal:/var/log"
    local: ./workspace/staging-logs
```

### Usage

```bash
sandbox start
# Inside the container:
ls /workspace/data          # S3 bucket contents
ls /workspace/staging-logs  # Remote server logs
```

## Offline / Air-Gapped

Work without network access (e.g., on a flight or in a restricted network).

```bash
sandbox start --offline
```

The firewall skips GitHub IP fetching and domain resolution. The sandbox starts with whatever was cached previously. Tools that don't require network access (local file analysis, code review) work normally.
