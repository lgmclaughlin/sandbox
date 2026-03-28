#!/usr/bin/env python3
"""MCP logging wrapper.

Sits between the AI tool and the actual MCP server, transparently
proxying stdin/stdout while logging all requests and responses
to the audit volume with session correlation.

Usage: mcp-log-wrapper <server-name> <command> [args...]
"""

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import re

LOG_DIR = Path("/var/log/sandbox/mcp")
SESSION_ID = os.environ.get("SANDBOX_SESSION_ID", "unknown")
PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "default")
LOG_SINKS = os.environ.get("SANDBOX_LOG_SINKS", "file")
LOG_LAYERS = os.environ.get("SANDBOX_LOG_LAYERS", "all")
MAX_PAYLOAD = int(os.environ.get("SANDBOX_LOG_MAX_PAYLOAD_BYTES", "0"))
OTEL_COMPAT = os.environ.get("SANDBOX_LOG_OTEL_COMPAT", "").lower() == "true"
MCP_ENFORCE = os.environ.get("MCP_ENFORCE", "").lower() == "true"
MCP_LOGGING_ENABLED = LOG_LAYERS == "all" or "mcp" in LOG_LAYERS.split(",")
MCP_PERMISSIONS = {}

if os.environ.get("MCP_PERMISSIONS"):
    try:
        MCP_PERMISSIONS = json.loads(os.environ["MCP_PERMISSIONS"])
    except json.JSONDecodeError:
        pass

_event_counter = 0


def _next_event_id() -> str:
    global _event_counter
    _event_counter += 1
    return f"evt_{_event_counter:06d}"


def get_log_file() -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = LOG_DIR / today
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{SESSION_ID}.jsonl"


def emit_event(event_type: str, server_name: str, payload: dict) -> None:
    if not MCP_LOGGING_ENABLED:
        return
    try:
        if MAX_PAYLOAD > 0:
            for key, value in list(payload.items()):
                if isinstance(value, str) and len(value) > MAX_PAYLOAD:
                    payload[key] = value[:MAX_PAYLOAD]
                    payload[f"{key}_truncated"] = True
                    payload[f"{key}_original_size"] = len(value)

        envelope = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "project": PROJECT,
            "session_id": SESSION_ID,
            "source": "mcp-wrapper",
            "payload": {"server": server_name, **payload},
        }

        if OTEL_COMPAT:
            envelope["otel"] = {
                "trace_id": SESSION_ID,
                "span_id": _next_event_id(),
                "span_name": event_type,
            }

        line = json.dumps(envelope) + "\n"

        if "file" in LOG_SINKS:
            log_file = get_log_file()
            with open(log_file, "a") as f:
                f.write(line)

        if "stdout" in LOG_SINKS:
            sys.stderr.write(line)

    except OSError:
        pass


def validate_request(parsed: dict, server_name: str) -> str | None:
    """Validate an MCP request against permissions. Returns error message or None."""
    if not MCP_ENFORCE or not MCP_PERMISSIONS:
        return None

    method = parsed.get("method", "")
    if method != "tools/call":
        return None

    params = parsed.get("params", {})
    if not isinstance(params, dict):
        return None

    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        return None

    blocked_patterns = MCP_PERMISSIONS.get("blocked_patterns", [])
    allowed_paths = MCP_PERMISSIONS.get("allowed_paths", [])

    for key, value in arguments.items():
        if not isinstance(value, str):
            continue

        for pattern in blocked_patterns:
            if re.search(pattern, value):
                return f"Blocked pattern '{pattern}' found in argument '{key}'"

        if allowed_paths and ("path" in key.lower() or "file" in key.lower()):
            if not any(value.startswith(p) for p in allowed_paths):
                return f"Path '{value}' not in allowed paths: {allowed_paths}"

    return None


def proxy_stream(source, dest, server_name: str, event_type: str) -> None:
    buffer = ""
    for chunk in iter(lambda: source.read(1), ""):
        if not chunk:
            break
        buffer += chunk
        dest.write(chunk)
        dest.flush()

        if chunk == "\n" and buffer.strip():
            payload = {"size_bytes": len(buffer.strip())}
            request_id = None

            try:
                parsed = json.loads(buffer.strip())
                if isinstance(parsed, dict):
                    payload["method"] = parsed.get("method", "")
                    request_id = parsed.get("id")
                    payload["id"] = request_id
                    if event_type == "mcp_request":
                        params = parsed.get("params", {})
                        if isinstance(params, dict):
                            payload["tool"] = params.get("name", "")

                        violation = validate_request(parsed, server_name)
                        if violation:
                            payload["violation"] = violation
                            emit_event("mcp_validation_error", server_name, payload)

                            if request_id is not None:
                                error_response = json.dumps({
                                    "jsonrpc": "2.0",
                                    "id": request_id,
                                    "error": {
                                        "code": -32600,
                                        "message": f"Permission denied: {violation}",
                                    },
                                }) + "\n"
                                # Write error back to the AI tool (stdout)
                                sys.stdout.write(error_response)
                                sys.stdout.flush()

                            buffer = ""
                            continue

            except (json.JSONDecodeError, TypeError):
                pass

            emit_event(event_type, server_name, payload)
            buffer = ""


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: mcp-log-wrapper <server-name> <command> [args...]", file=sys.stderr)
        sys.exit(1)

    server_name = sys.argv[1]
    command = sys.argv[2:]

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    emit_event("mcp_lifecycle", server_name, {"event": "start", "command": command})

    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
        )

        stdout_thread = threading.Thread(
            target=proxy_stream,
            args=(proc.stdout, sys.stdout, server_name, "mcp_response"),
            daemon=True,
        )
        stdout_thread.start()

        proxy_stream(sys.stdin, proc.stdin, server_name, "mcp_request")

        proc.stdin.close()
        proc.wait()

        emit_event("mcp_lifecycle", server_name, {
            "event": "exit",
            "exit_code": proc.returncode,
        })

        sys.exit(proc.returncode)

    except FileNotFoundError:
        emit_event("mcp_lifecycle", server_name, {
            "event": "error",
            "message": f"Command not found: {command[0]}",
        })
        print(f"error: MCP server command not found: {command[0]}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        emit_event("mcp_lifecycle", server_name, {"event": "interrupted"})
        sys.exit(130)


if __name__ == "__main__":
    main()
