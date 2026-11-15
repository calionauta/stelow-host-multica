#!/usr/bin/env bash
# board-check.sh — the timer that keeps a waiting card visible.
#
# `stelow-host doctor --fix` reads the board, marks the cards that wait on a
# person, and names the ones whose run ended with nothing queued. It starts no
# agent, so a run costs no tokens; that is why it can go on a timer.
#
# Three things it does around that, because a check nobody hears is not a check:
#
#   1. rotates its own log, so an append-only cron log cannot fill the disk;
#   2. counts consecutive failures and keeps talking after the third one, since a
#      daemon that died looks exactly like a quiet week;
#   3. says so out loud once a streak starts, using notify-telegram.sh when this
#      host has it.
#
# Usage: board-check.sh [--status]
#   --status  print the streak and the last run, change nothing
set -uo pipefail

REPO="${STELOW_HOST_REPO:-$HOME/repos/stelow-host-multica}"
LOG="${STELOW_BOARD_LOG:-$HOME/logs/stelow-host-board.log}"
STREAK="${STELOW_BOARD_STREAK:-$HOME/logs/stelow-host-board.streak}"
ALERT_AFTER="${STELOW_BOARD_ALERT_AFTER:-3}"
MAX_BYTES="${STELOW_BOARD_LOG_MAX:-1048576}"

if [ "${1:-}" = "--status" ]; then
    printf 'streak: %s (alerts after %s)\n' "$(cat "$STREAK" 2>/dev/null || echo 0)" "$ALERT_AFTER"
    printf 'log:    %s (%s bytes)\n' "$LOG" "$(wc -c <"$LOG" 2>/dev/null || echo 0)"
    printf 'last:   %s\n' "$(date -r "$LOG" -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo never)"
    exit 0
fi

mkdir -p "$(dirname "$LOG")" "$(dirname "$STREAK")"

# 1. one rotation, not a pile of them
if [ -f "$LOG" ] && [ "$(wc -c <"$LOG" 2>/dev/null || echo 0)" -gt "$MAX_BYTES" ]; then
    mv -f "$LOG" "$LOG.1"
fi

export PATH="$HOME/bin:/usr/local/bin:/usr/bin:/bin"
export MULTICA_WORKSPACE_ID="${MULTICA_WORKSPACE_ID:-ebb2409a-3e9b-48f0-a91d-0804c42afd39}"
export MULTICA_PROJECT_ID="${MULTICA_PROJECT_ID:-9abf9451-cb8c-494c-b8d2-51a268aef70b}"
export MULTICA_RUNTIME_ID="${MULTICA_RUNTIME_ID:-e722b9f0-ffbb-4423-a55d-1b1a4d101f29}"
export MULTICA_BIN="${MULTICA_BIN:-$HOME/bin/multica}"

cd "$REPO" || { echo "board-check: no repo at $REPO"; exit 1; }
output=$(timeout 240 ./bin/stelow-host doctor --fix 2>&1)
code=$?

{
    printf '=== %s (exit %s)\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$code"
    printf '%s\n' "$output" | tail -20
} >>"$LOG"

# 2. a streak survives restarts, because the daemon does not
runs=0
[ -f "$STREAK" ] && runs=$(cat "$STREAK" 2>/dev/null || echo 0)
case "$runs" in ''|*[!0-9]*) runs=0 ;; esac

if [ "$code" -eq 0 ]; then
    printf '0' >"$STREAK"
    exit 0
fi

runs=$((runs + 1))
printf '%s' "$runs" >"$STREAK"

# 3. say it once when the streak starts, and again every ten runs after
if { [ "$runs" -eq "$ALERT_AFTER" ] || [ $((runs % 10)) -eq 0 ]; } && [ -x "$HOME/bin/notify-telegram.sh" ]; then
    headline=$(printf '%s\n' "$output" | grep -E '^\s*(FAIL|WARN)' | head -3)
    "$HOME/bin/notify-telegram.sh" "stelow board check failing ${runs}x on $(hostname -s):
${headline:-no check line, see $LOG}" >/dev/null 2>&1 || true
fi

exit "$code"
