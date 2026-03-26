#!/bin/bash
set -euo pipefail

LOG_DIR="/var/log/sandbox/firewall"
mkdir -p "$LOG_DIR"

TODAY=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/$TODAY.jsonl"

# Read kernel log for iptables LOG entries and write as JSON
# Runs as a background daemon in the firewall container
tail -F /var/log/kern.log 2>/dev/null | while read -r line; do
    if echo "$line" | grep -q "SBX_"; then
        TIMESTAMP=$(date -Iseconds)
        ACTION=""
        DST=""
        DPT=""
        PROTO=""

        if echo "$line" | grep -q "SBX_ALLOW"; then
            ACTION="allow"
        elif echo "$line" | grep -q "SBX_BLOCK"; then
            ACTION="block"
        else
            continue
        fi

        DST=$(echo "$line" | grep -oP 'DST=\K[^ ]+' || echo "unknown")
        DPT=$(echo "$line" | grep -oP 'DPT=\K[^ ]+' || echo "unknown")
        PROTO=$(echo "$line" | grep -oP 'PROTO=\K[^ ]+' || echo "unknown")

        printf '{"timestamp":"%s","action":"%s","dst":"%s","port":"%s","proto":"%s"}\n' \
            "$TIMESTAMP" "$ACTION" "$DST" "$DPT" "$PROTO" >> "$LOG_FILE"
    fi
done
