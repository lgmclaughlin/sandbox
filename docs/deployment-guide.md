# Deployment Guide

## Overview

This guide covers deploying the sandbox in sensitive environments with proxy, DLP, secrets management, and log agent integration.

## Proxy Setup

### Enabling the proxy

Set `SANDBOX_PROXY_MODE=proxy` in `.env` or a profile:

```bash
# .env.corp
SANDBOX_PROXY_MODE=proxy
```

Start with the profile:
```bash
sandbox start --env=corp
```

This starts a mitmproxy container that terminates TLS for all HTTPS traffic from the sandbox. The sandbox automatically trusts the proxy's CA certificate.

### Custom CA Certificate

If your organization has its own CA:

```bash
SANDBOX_PROXY_CA_CERT=/path/to/custom-ca.pem
```

The proxy will use this certificate instead of auto-generating one.

### Verifying proxy is active

```bash
sandbox proxy status
sandbox check
```

## Content Inspection

Define regex rules in `config/network/inspection.yaml`:

```yaml
rules:
  - name: ssn-pattern
    pattern: '\b\d{3}-\d{2}-\d{4}\b'
    action: block

  - name: api-key-leak
    pattern: 'sk-[a-zA-Z0-9]{20,}'
    action: alert

  - name: credit-card
    pattern: '\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
    action: block
```

- `block`: Rejects the request with a 403 response
- `alert`: Logs the violation but allows the request

View violations:
```bash
sandbox proxy logs
```

## DLP Integration

### Webhook Provider

Configure an external DLP API:

```bash
SANDBOX_DLP_PROVIDER=webhook
SANDBOX_DLP_WEBHOOK_URL=https://dlp-api.internal.company.com/scan
```

The proxy calls this webhook before forwarding each request. The webhook receives:
```json
{
  "url": "https://api.anthropic.com/v1/messages",
  "method": "POST",
  "direction": "request",
  "content_length": 4200,
  "content_preview": "first 1000 characters..."
}
```

Expected response:
```json
{"action": "allow"}
{"action": "block"}
{"action": "redact", "redacted_content": "..."}
```

Compatible with: Nightfall AI, Lakera Guard, or any HTTP-based DLP API.

## Secrets Management

### Local Provider (default)

Secrets stored in an obfuscated file at `.secrets/local.json`:

```bash
sandbox secrets set ANTHROPIC_API_KEY sk-ant-...
sandbox secrets set OPENAI_API_KEY sk-...
```

Secrets are injected into the container as environment variables on `sandbox start`. Never baked into Docker images.

### Environment Provider (for CI)

```bash
SANDBOX_SECRETS_PROVIDER=env
```

Reads secrets directly from the host's environment variables. Useful for CI/CD where secrets are injected by the pipeline.

### External Providers (future)

The provider interface (`cli/lib/secrets.py`) is designed for extension. Adding Vault or AWS Secrets Manager requires implementing the `SecretsProvider` base class with `get`, `set`, `delete`, and `list_keys` methods.

## Log Agent Integration

### Log Format

Set `SANDBOX_LOG_FORMAT=json` and `SANDBOX_LOG_SINKS=file,stdout` for log agent compatibility.

All logs use the unified event envelope (see `docs/event-schema.md`).

### Fluent Bit

```ini
[INPUT]
    Name tail
    Path /path/to/sandbox/logs/**/*.jsonl
    Tag sandbox
    Parser json

[OUTPUT]
    Name loki
    Match sandbox.*
    Host loki.internal.company.com
    Port 3100
    Labels job=sandbox
```

### Filebeat

```yaml
filebeat.inputs:
  - type: log
    paths:
      - /path/to/sandbox/logs/**/*.jsonl
    json.keys_under_root: true
    json.add_error_key: true

output.elasticsearch:
  hosts: ["https://es.internal.company.com:9200"]
  index: "sandbox-logs-%{+yyyy.MM.dd}"
```

### Vector

```toml
[sources.sandbox]
type = "file"
include = ["/path/to/sandbox/logs/**/*.jsonl"]

[transforms.parse]
type = "remap"
inputs = ["sandbox"]
source = '. = parse_json!(.message)'

[sinks.datadog]
type = "datadog_logs"
inputs = ["parse"]
default_api_key = "${DATADOG_API_KEY}"
```

### Docker Logs

With `SANDBOX_LOG_SINKS=file,stdout`, events also emit to stdout:

```bash
docker logs project_sandbox
```

Compatible with any Docker log driver (syslog, fluentd, gelf, etc.).

## Hardened Mode

For maximum security:

```bash
SANDBOX_HARDENED_MODE=true
SANDBOX_CPU_LIMIT=2.0
SANDBOX_MEM_LIMIT=4g
SANDBOX_ENFORCE_MCP_PERMISSIONS=true
```

This enables:
- Read-only filesystem (tmpfs for writable paths)
- All Linux capabilities dropped
- CPU and memory limits
- MCP permission validation

Verify with `sandbox check`.

## Security Model and Capabilities

### Container privilege breakdown

| Container | Capabilities | Network Mode | Privileges | Purpose |
|-----------|-------------|--------------|------------|---------|
| **Sandbox** | None (all dropped in hardened mode) | `service:firewall` (shared) | `no-new-privileges: true`, non-root user | Untrusted execution |
| **Firewall** | `NET_ADMIN`, `NET_RAW` | `bridge` (isolated) | `no-new-privileges: false` | Network enforcement |
| **Proxy** (optional) | None | `service:firewall` (shared) | Default | TLS inspection |

### Why the firewall needs capabilities

**NET_ADMIN and NET_RAW** are required to configure iptables rules and ipsets. These are used exclusively to set up egress filtering for the sandbox container. The firewall container uses `network_mode: bridge`, giving it its own isolated network namespace. These capabilities modify the container's own network rules, not the host's.

**What these capabilities cannot do in this configuration:**
- Cannot modify host iptables (bridge mode isolates the namespace)
- Cannot access host network interfaces
- Cannot affect other containers outside this compose project

### Blast radius analysis

If the **sandbox container** is compromised:
- No capabilities to escalate with
- Cannot modify network rules (no NET_ADMIN)
- All traffic still passes through the firewall
- Cannot reach the host filesystem (only /workspace and /var/log/sandbox are mounted)

If the **firewall container** is compromised:
- Can modify its own network routing (bridge-isolated, not the host)
- Cannot access the host network namespace
- Worst case: sandbox loses internet access or firewall rules are disabled for this project's containers
- Other containers and the host are unaffected

The sandbox cannot escalate to the firewall. They are separate containers with no shared access beyond the network namespace.

## Compliance Checklist

| Requirement | How Sandbox Addresses It |
|-------------|-------------------------|
| Data doesn't leave perimeter | Firewall whitelist + proxy inspection |
| PII not sent to AI APIs | Content inspection rules + DLP webhook |
| Audit trail of all actions | Unified event logging with session correlation |
| Non-root execution | Container runs as `node` user, `no-new-privileges` |
| Minimal capabilities | Sandbox: none. Firewall: NET_ADMIN, NET_RAW (bridge-isolated) |
| Resource isolation | CPU/memory limits, separate network namespace |
| Credential management | Secrets provider, never in Docker images |
| MCP access control | Permission enforcement with path validation |
| Log retention | Configurable retention with compression |
| Integration with SIEM | JSON logs, OTEL field compatibility, stdout sink |
