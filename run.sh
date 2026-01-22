#!/bin/bash

# ===========================================
# Polymarket Whale Alerts Launcher
# ===========================================
# Usage:
#   ./run.sh dev   - Run with development environment
#   ./run.sh prod  - Run with production environment
#   ./run.sh       - Run with current .env (default)
# ===========================================

set -e

ENV_MODE="${1:-current}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

case "$ENV_MODE" in
    dev|development)
        echo "🧪 Starting in DEVELOPMENT mode..."
        if [ ! -f ".env.development" ]; then
            echo "❌ Error: .env.development not found!"
            exit 1
        fi
        # Backup current .env if exists
        if [ -f ".env" ]; then
            cp .env .env.backup
        fi
        cp .env.development .env
        echo "✅ Loaded .env.development"
        ;;
    prod|production)
        echo "🚀 Starting in PRODUCTION mode..."
        if [ -f ".env.production" ]; then
            cp .env.production .env
            echo "✅ Loaded .env.production"
        elif [ -f ".env.backup" ]; then
            cp .env.backup .env
            echo "✅ Restored .env from backup"
        else
            echo "⚠️  Using current .env (no .env.production found)"
        fi
        ;;
    current)
        echo "▶️  Starting with current .env..."
        ;;
    *)
        echo "Usage: $0 [dev|prod|current]"
        echo "  dev   - Use .env.development"
        echo "  prod  - Use .env.production (or restore backup)"
        echo "  current - Use current .env (default)"
        exit 1
        ;;
esac

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Activated virtual environment"
fi

# Check if bot is already running
EXISTING_PID=$(pgrep -f "python.*main\.py" | head -1)
if [ -n "$EXISTING_PID" ]; then
    echo "⚠️  Bot already running (PID: $EXISTING_PID). Stopping..."
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 2
fi

# Run the bot
echo "🤖 Starting bot..."
python main.py
