#!/bin/bash

LOG_DIR="/var/log/sandbox"
SESSION_DIR="$LOG_DIR/sessions"
COMMAND_DIR="$LOG_DIR/commands"

mkdir -p "$SESSION_DIR" "$COMMAND_DIR" 2>/dev/null || true

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SESSION_ID="${USER:-unknown}_${HOSTNAME:-unknown}_${TIMESTAMP}"

# Write session metadata
cat > "$SESSION_DIR/${SESSION_ID}.meta.json" <<METADATA
{
  "session_id": "$SESSION_ID",
  "user": "${USER:-unknown}",
  "hostname": "${HOSTNAME:-unknown}",
  "platform": "$(uname -s)",
  "start_time": "$(date -Iseconds)",
  "shell": "$SHELL"
}
METADATA

# Bash history to audit volume
export HISTFILE="$COMMAND_DIR/${SESSION_ID}.history"
export HISTTIMEFORMAT="%F %T "
export PROMPT_COMMAND='history -a'

# Session recording
RECORDING="$SESSION_DIR/${SESSION_ID}.log"
export SANDBOX_SESSION_ID="$SESSION_ID"

if [ -t 0 ] && command -v script >/dev/null 2>&1; then
    exec script -q -a "$RECORDING" -c "bash -l" 2>/dev/null || exec bash -l
else
    exec bash -l
fi
