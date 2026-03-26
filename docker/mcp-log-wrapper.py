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
import time
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("/var/log/sandbox/mcp")
SESSION_ID = os.environ.get("SANDBOX_SESSION_ID", "unknown")


def get_log_file() -> Path:
    """Get today's log file path."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = LOG_DIR / today
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{SESSION_ID}.jsonl"


def log_event(server_name: str, direction: str, data: str, duration_ms: float = 0) -> None:
    """Write a log entry."""
    try:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": SESSION_ID,
            "server": server_name,
            "direction": direction,
            "duration_ms": round(duration_ms, 2),
        }

        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                entry["method"] = parsed.get("method", "")
                entry["id"] = parsed.get("id")
                if direction == "request":
                    params = parsed.get("params", {})
                    if isinstance(params, dict):
                        entry["tool"] = params.get("name", "")
        except (json.JSONDecodeError, TypeError):
            pass

        entry["size_bytes"] = len(data)

        log_file = get_log_file()
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def proxy_stream(source, dest, server_name: str, direction: str) -> None:
    """Proxy data from source to dest, logging each message."""
    buffer = ""
    for chunk in iter(lambda: source.read(1), ""):
        if not chunk:
            break
        buffer += chunk
        dest.write(chunk)
        dest.flush()

        if chunk == "\n" and buffer.strip():
            log_event(server_name, direction, buffer.strip())
            buffer = ""


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: mcp-log-wrapper <server-name> <command> [args...]", file=sys.stderr)
        sys.exit(1)

    server_name = sys.argv[1]
    command = sys.argv[2:]

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_event(server_name, "lifecycle", json.dumps({"event": "start", "command": command}))

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
            args=(proc.stdout, sys.stdout, server_name, "response"),
            daemon=True,
        )
        stdout_thread.start()

        proxy_stream(sys.stdin, proc.stdin, server_name, "request")

        proc.stdin.close()
        proc.wait()

        log_event(server_name, "lifecycle", json.dumps({
            "event": "exit",
            "exit_code": proc.returncode,
        }))

        sys.exit(proc.returncode)

    except FileNotFoundError:
        log_event(server_name, "lifecycle", json.dumps({
            "event": "error",
            "message": f"Command not found: {command[0]}",
        }))
        print(f"error: MCP server command not found: {command[0]}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        log_event(server_name, "lifecycle", json.dumps({"event": "interrupted"}))
        sys.exit(130)


if __name__ == "__main__":
    main()
