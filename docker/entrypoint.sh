#!/bin/bash

LOG_DIR="/var/log/sandbox"
SESSION_DIR="$LOG_DIR/sessions"
COMMAND_DIR="$LOG_DIR/commands"
LOG_FORMAT="${SANDBOX_LOG_FORMAT:-text}"

TODAY=$(date +%Y-%m-%d)
SESSION_DIR="$SESSION_DIR/$TODAY"
COMMAND_DIR="$COMMAND_DIR/$TODAY"

mkdir -p "$SESSION_DIR" "$COMMAND_DIR" 2>/dev/null || true

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SESSION_ID="${USER:-unknown}_${HOSTNAME:-unknown}_${TIMESTAMP}"

# Write session start event
cat > "$SESSION_DIR/${SESSION_ID}.meta.json" <<METADATA
{
  "event": "session_start",
  "session_id": "$SESSION_ID",
  "user": "${USER:-unknown}",
  "hostname": "${HOSTNAME:-unknown}",
  "platform": "$(uname -s)",
  "start_time": "$(date -Iseconds)",
  "shell": "$SHELL",
  "log_format": "$LOG_FORMAT"
}
METADATA

export SANDBOX_SESSION_ID="$SESSION_ID"

if [ "$LOG_FORMAT" = "json" ]; then
    COMMAND_LOG="$COMMAND_DIR/${SESSION_ID}.jsonl"

    _log_cmd() {
        local last_exit=$?
        local cmd
        cmd=$(HISTTIMEFORMAT= history 1 | sed 's/^[ ]*[0-9]*[ ]*//')
        [ -z "$cmd" ] && return
        printf '{"event":"command","timestamp":"%s","session_id":"%s","command":"%s","exit_code":%d,"cwd":"%s"}\n' \
            "$(date -Iseconds)" "$SESSION_ID" "$(echo "$cmd" | sed 's/"/\\"/g')" "$last_exit" "$PWD" \
            >> "$COMMAND_LOG"
    }
    export PROMPT_COMMAND='_log_cmd'
    export -f _log_cmd
else
    export HISTFILE="$COMMAND_DIR/${SESSION_ID}.history"
    export HISTTIMEFORMAT="%F %T "
    export PROMPT_COMMAND='history -a'
fi

# Write session end event on exit
_on_exit() {
    cat >> "$SESSION_DIR/${SESSION_ID}.meta.json" <<END

{
  "event": "session_end",
  "session_id": "$SESSION_ID",
  "end_time": "$(date -Iseconds)"
}
END
}
trap _on_exit EXIT

# Session recording
RECORDING="$SESSION_DIR/${SESSION_ID}.log"

if [ -t 0 ] && command -v script >/dev/null 2>&1; then
    exec script -q -a "$RECORDING" -c "bash -l" 2>/dev/null || exec bash -l
else
    exec bash -l
fi
