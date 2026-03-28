#!/bin/bash

# Firewall log daemon.
# Parses ulogd2 output files for NFLOG entries and writes
# unified event envelopes to the audit volume.

LOG_DIR="/var/log/sandbox/firewall"
PROJECT="${COMPOSE_PROJECT_NAME:-default}"
LOG_SINKS="${SANDBOX_LOG_SINKS:-file}"
LOG_LAYERS="${SANDBOX_LOG_LAYERS:-all}"
ULOG_DIR="/var/log/sandbox/firewall"

# Exit early if firewall logging is disabled
if [ "$LOG_LAYERS" != "all" ] && ! echo ",$LOG_LAYERS," | grep -q ",firewall,"; then
    echo "firewall-log: firewall layer disabled, exiting" >&2
    exit 0
fi

ALLOW_LOG="$ULOG_DIR/ulogd_allow.log"
BLOCK_LOG="$ULOG_DIR/ulogd_block.log"

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

parse_ulogd_line() {
    local line="$1"
    local action="$2"

    # ulogd LOGEMU format: timestamp hostname prefix IN= OUT= SRC= DST= ... PROTO= ... DPT=
    local dst
    dst=$(echo "$line" | grep -oP 'DST=\K[^ ]+' || echo "unknown")
    local dpt
    dpt=$(echo "$line" | grep -oP 'DPT=\K[^ ]+' || echo "unknown")
    local proto
    proto=$(echo "$line" | grep -oP 'PROTO=\K[^ ]+' || echo "unknown")

    emit_event "$action" "$dst" "$dpt" "$proto"
}

# Wait for ulogd to create log files
for i in $(seq 1 15); do
    if [ -f "$ALLOW_LOG" ] || [ -f "$BLOCK_LOG" ]; then
        break
    fi
    sleep 1
done

# Create files if they don't exist yet (tail -F needs them)
touch "$ALLOW_LOG" "$BLOCK_LOG"

# Tail both files simultaneously
{
    tail -F "$ALLOW_LOG" 2>/dev/null | while read -r line; do
        [ -z "$line" ] && continue
        parse_ulogd_line "$line" "firewall_allow"
    done &

    tail -F "$BLOCK_LOG" 2>/dev/null | while read -r line; do
        [ -z "$line" ] && continue
        parse_ulogd_line "$line" "firewall_block"
    done &

    wait
}
