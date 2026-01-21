#!/bin/bash
# Watchdog script for PolymarketWhales bot
# Checks if bot is responsive (logs are being written)
# If logs are stale for more than 10 minutes, restarts the bot

BOT_DIR="/root/PolymarketWhales"
LOG_FILE="$BOT_DIR/bot_output.log"
PID_CHECK="python.*main.py"
MAX_STALE_SECONDS=600  # 10 minutes

# Get current time and log file modification time
CURRENT_TIME=$(date +%s)
LOG_MTIME=$(stat -c %Y "$LOG_FILE" 2>/dev/null || echo 0)
STALE_SECONDS=$((CURRENT_TIME - LOG_MTIME))

# Check if process is running
if ! pgrep -f "$PID_CHECK" > /dev/null; then
    echo "[$(date)] Bot process not found. Starting..."
    cd "$BOT_DIR" && nohup ./run.sh >> /dev/null 2>&1 &
    exit 0
fi

# Check if logs are stale
if [ "$STALE_SECONDS" -gt "$MAX_STALE_SECONDS" ]; then
    echo "[$(date)] Bot logs stale for ${STALE_SECONDS}s (>${MAX_STALE_SECONDS}s). Restarting..."
    pkill -9 -f "$PID_CHECK"
    sleep 3
    cd "$BOT_DIR" && nohup ./run.sh >> /dev/null 2>&1 &
    echo "[$(date)] Bot restarted."
else
    echo "[$(date)] Bot healthy. Logs updated ${STALE_SECONDS}s ago."
fi
