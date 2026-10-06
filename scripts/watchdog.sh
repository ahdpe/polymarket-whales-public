#!/bin/bash
# Watchdog for PolymarketWhales.
# Keep process ownership inside systemd; never start main.py directly.

SERVICE="polywhales.service"
BOT_DIR="/root/PolymarketWhales"
LOG_FILE="$BOT_DIR/bot_output.log"
MAX_STALE_SECONDS=900

now() {
    date '+%Y-%m-%d %H:%M:%S %Z'
}

restart_service() {
    echo "[$(now)] Restarting $SERVICE via systemd..."
    timeout 35 systemctl restart "$SERVICE"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "[$(now)] Normal restart failed/timed out (rc=$rc). Killing unit and starting cleanly..."
        systemctl kill -s SIGKILL "$SERVICE" 2>/dev/null || true
        sleep 3
        systemctl reset-failed "$SERVICE" 2>/dev/null || true
        systemctl start "$SERVICE"
    fi
}

if ! systemctl is-active --quiet "$SERVICE"; then
    echo "[$(now)] $SERVICE is not active. Starting..."
    systemctl reset-failed "$SERVICE" 2>/dev/null || true
    systemctl start "$SERVICE"
    exit 0
fi

current_time=$(date +%s)
log_mtime=$(stat -c %Y "$LOG_FILE" 2>/dev/null || echo 0)
stale_seconds=$((current_time - log_mtime))

if [ "$stale_seconds" -gt "$MAX_STALE_SECONDS" ]; then
    echo "[$(now)] Bot log is stale for ${stale_seconds}s (>${MAX_STALE_SECONDS}s)."
    restart_service
else
    echo "[$(now)] Bot healthy. Log updated ${stale_seconds}s ago."
fi
