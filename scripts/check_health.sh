#!/bin/bash
# Health check script for GMC Discord Bot
# Checks if the bot container is running and restarts if needed
# Designed to be run via cron job as root user

set -e

# Configuration
BOT_DIR="/root/gmc-discord-bot"
LOG_FILE="$BOT_DIR/health_check.log"
MAX_LOG_SIZE=1048576  # 1MB in bytes

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Rotate log file if it gets too large
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$LOG_SIZE" -gt "$MAX_LOG_SIZE" ]; then
        mv "$LOG_FILE" "$LOG_FILE.old"
        log_message "Rotated log file (size: $LOG_SIZE bytes)"
    fi
fi

# Change to bot directory
cd "$BOT_DIR" || {
    log_message "ERROR: Could not change to directory $BOT_DIR"
    exit 1
}

# Check if container is running
if docker compose ps | grep -q "Up"; then
    # Container is running - perform additional health checks

    # Check container uptime
    UPTIME=$(docker compose ps --format json | grep -o '"Status":"[^"]*"' | cut -d'"' -f4)

    # Check for recent restarts (container running less than 2 minutes might indicate crash loop)
    if echo "$UPTIME" | grep -q "seconds"; then
        SECONDS=$(echo "$UPTIME" | grep -o '[0-9]*' | head -1)
        if [ "$SECONDS" -lt 120 ]; then
            log_message "WARNING: Container recently restarted (uptime: $UPTIME)"
            log_message "Recent logs:"
            docker compose logs --tail=20 | tee -a "$LOG_FILE"
        fi
    fi

    # Optional: Check if bot is actually responsive (uncomment if needed)
    # You could add a custom health endpoint or check Discord API here

else
    # Container is not running - restart it
    log_message "ERROR: Bot container is not running!"
    log_message "Attempting to restart..."

    # Get recent logs before restart
    log_message "Last 30 lines of logs before restart:"
    docker compose logs --tail=30 | tee -a "$LOG_FILE"

    # Attempt restart
    if docker compose up -d; then
        log_message "SUCCESS: Bot container restarted"
        sleep 5

        # Verify it started
        if docker compose ps | grep -q "Up"; then
            log_message "VERIFIED: Container is now running"
            docker compose ps | tee -a "$LOG_FILE"
        else
            log_message "CRITICAL: Container failed to start after restart attempt"
            docker compose logs --tail=50 | tee -a "$LOG_FILE"
            exit 1
        fi
    else
        log_message "CRITICAL: Failed to restart bot container"
        exit 1
    fi
fi
