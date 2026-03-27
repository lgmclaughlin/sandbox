#!/bin/bash
set -euo pipefail

LOG_DIR="/var/log/sandbox/firewall"
PROJECT="${COMPOSE_PROJECT_NAME:-default}"
LOG_SINKS="${SANDBOX_LOG_SINKS:-file}"

mkdir -p "$LOG_DIR"

emit_event() {
    local event_type="$1"
    local dst="$2"
    local port="$3"
    local proto="$4"
    local ts
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    local today
    today=$(date +%Y-%m-%d)
    local log_file="$LOG_DIR/$today.jsonl"

    local event
    event=$(printf '{"timestamp":"%s","event_type":"%s","project":"%s","session_id":"","source":"firewall-log","payload":{"dst":"%s","port":"%s","proto":"%s"}}' \
        "$ts" "$event_type" "$PROJECT" "$dst" "$port" "$proto")

    if echo "$LOG_SINKS" | grep -q "file"; then
        echo "$event" >> "$log_file"
    fi

    if echo "$LOG_SINKS" | grep -q "stdout"; then
        echo "$event"
    fi
}

tail -F /var/log/kern.log 2>/dev/null | while read -r line; do
    if echo "$line" | grep -q "SBX_"; then
        ACTION=""

        if echo "$line" | grep -q "SBX_ALLOW"; then
            ACTION="firewall_allow"
        elif echo "$line" | grep -q "SBX_BLOCK"; then
            ACTION="firewall_block"
        else
            continue
        fi

        DST=$(echo "$line" | grep -oP 'DST=\K[^ ]+' || echo "unknown")
        DPT=$(echo "$line" | grep -oP 'DPT=\K[^ ]+' || echo "unknown")
        PROTO=$(echo "$line" | grep -oP 'PROTO=\K[^ ]+' || echo "unknown")

        emit_event "$ACTION" "$DST" "$DPT" "$PROTO"
    fi
done
