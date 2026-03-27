#!/bin/bash

LOG_DIR="/var/log/sandbox"
LOG_FORMAT="${SANDBOX_LOG_FORMAT:-text}"
PROJECT="${COMPOSE_PROJECT_NAME:-default}"

TODAY=$(date +%Y-%m-%d)
SESSION_DIR="$LOG_DIR/sessions/$TODAY"
COMMAND_DIR="$LOG_DIR/commands/$TODAY"

mkdir -p "$SESSION_DIR" "$COMMAND_DIR" 2>/dev/null || true

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SESSION_ID="${USER:-unknown}_${HOSTNAME:-unknown}_${TIMESTAMP}"
export SANDBOX_SESSION_ID="$SESSION_ID"

_emit_event() {
    local event_type="$1"
    local source="$2"
    local payload="$3"
    local ts
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    local event
    event=$(printf '{"timestamp":"%s","event_type":"%s","project":"%s","session_id":"%s","source":"%s","payload":%s}' \
        "$ts" "$event_type" "$PROJECT" "$SESSION_ID" "$source" "$payload")

    local log_file="$LOG_DIR/${source}s/$TODAY/${SESSION_ID}.jsonl"
    mkdir -p "$(dirname "$log_file")" 2>/dev/null || true
    echo "$event" >> "$log_file"

    if echo "${SANDBOX_LOG_SINKS:-file}" | grep -q "stdout"; then
        echo "$event"
    fi
}

_emit_event "session_start" "session" "$(printf '{"user":"%s","hostname":"%s","platform":"%s","shell":"%s","log_format":"%s"}' \
    "${USER:-unknown}" "${HOSTNAME:-unknown}" "$(uname -s)" "$SHELL" "$LOG_FORMAT")"

if [ "$LOG_FORMAT" = "json" ]; then
    _log_cmd() {
        local last_exit=$?
        local cmd
        cmd=$(HISTTIMEFORMAT= history 1 | sed 's/^[ ]*[0-9]*[ ]*//')
        [ -z "$cmd" ] && return
        local escaped_cmd
        escaped_cmd=$(echo "$cmd" | sed 's/"/\\"/g')
        _emit_event "command" "command" "$(printf '{"command":"%s","exit_code":%d,"cwd":"%s"}' \
            "$escaped_cmd" "$last_exit" "$PWD")"
    }
    export PROMPT_COMMAND='_log_cmd'
    export -f _log_cmd
    export -f _emit_event
else
    export HISTFILE="$COMMAND_DIR/${SESSION_ID}.history"
    export HISTTIMEFORMAT="%F %T "
    export PROMPT_COMMAND='history -a'
fi

_on_exit() {
    _emit_event "session_end" "session" "$(printf '{"end_time":"%s"}' "$(date -u +%Y-%m-%dT%H:%M:%SZ)")"
}
trap _on_exit EXIT

RECORDING="$SESSION_DIR/${SESSION_ID}.log"

if [ -t 0 ] && command -v script >/dev/null 2>&1; then
    exec script -q -a "$RECORDING" -c "bash -l" 2>/dev/null || exec bash -l
else
    exec bash -l
fi
