# Deployment Scripts

This folder contains utility scripts for deploying and managing the GMC Discord Bot on a DigitalOcean droplet.

## Scripts

### setup_bot.sh

**Purpose:** Initial server setup and configuration

**Usage:**
```bash
# Download and run from GitHub
curl -fsSL https://raw.githubusercontent.com/unimelb-game-makers/gmc-discord-bot/main/scripts/setup_bot.sh -o setup_bot.sh
chmod +x setup_bot.sh
./setup_bot.sh

# Or run from cloned repository
cd /root/gmc-discord-bot
chmod +x scripts/setup_bot.sh
./scripts/setup_bot.sh
```

**What it does:**
- Checks for and installs Docker
- Checks for and installs Docker Compose
- Checks for and installs Git
- Clones the repository (if not already cloned)
- Creates the `working_memory` directory
- Creates `.env` file from template
- Optionally configures UFW firewall

**When to use:**
- First-time setup of a new droplet
- Setting up a fresh development environment
- After a server reinstall

**Requirements:**
- Ubuntu/Debian-based Linux system
- Must be run as root user
- Internet connection

---

### check_health.sh

**Purpose:** Automated health monitoring and recovery

**Usage:**
```bash
# Manual run
cd /root/gmc-discord-bot
./scripts/check_health.sh

# Add to crontab for automatic monitoring every 5 minutes
crontab -e
# Add this line:
*/5 * * * * /root/gmc-discord-bot/scripts/check_health.sh
```

**What it does:**
- Checks if the bot container is running
- Automatically restarts the container if it's down
- Detects crash loops (frequent restarts within 2 minutes)
- Logs all actions with timestamps to `health_check.log`
- Automatically rotates logs when they exceed 1MB
- Captures container logs before and after restart attempts

**When to use:**
- Production monitoring via cron job
- Debugging container issues
- Ensuring high availability

**Log file location:**
- `/root/gmc-discord-bot/health_check.log`
- `/root/gmc-discord-bot/health_check.log.old` (rotated logs)

**Exit codes:**
- `0`: Container is healthy
- `1`: Critical error (container failed to start, directory not found, etc.)

---

## Setting Up Automated Monitoring

For production deployments, set up the health check script as a cron job:

```bash
# Make the script executable
chmod +x /root/gmc-discord-bot/scripts/check_health.sh

# Test it manually first
/root/gmc-discord-bot/scripts/check_health.sh

# Add to crontab
crontab -e

# Add one of these lines depending on your preference:
# Every 5 minutes (recommended for production)
*/5 * * * * /root/gmc-discord-bot/scripts/check_health.sh

# Every 10 minutes (for less critical environments)
*/10 * * * * /root/gmc-discord-bot/scripts/check_health.sh

# Every minute (for high-availability requirements)
* * * * * /root/gmc-discord-bot/scripts/check_health.sh
```

## Viewing Health Check Logs

```bash
# View recent health check logs
tail -f /root/gmc-discord-bot/health_check.log

# View last 50 lines
tail -n 50 /root/gmc-discord-bot/health_check.log

# Search for errors
grep "ERROR" /root/gmc-discord-bot/health_check.log

# Search for restarts
grep "restarted" /root/gmc-discord-bot/health_check.log
```

## Troubleshooting

### Script won't run
```bash
# Make sure it's executable
chmod +x /root/gmc-discord-bot/scripts/check_health.sh

# Check file permissions
ls -l /root/gmc-discord-bot/scripts/
```

### Cron job not working
```bash
# Check cron logs (Ubuntu/Debian)
grep CRON /var/log/syslog

# Verify crontab is set
crontab -l

# Make sure to use absolute paths in crontab
# BAD:  */5 * * * * ./scripts/check_health.sh
# GOOD: */5 * * * * /home/user/gmc-discord-bot/scripts/check_health.sh
```

### Health check fails immediately
```bash
# Make sure you're in the right directory
cd /root/gmc-discord-bot

# Check if docker compose is working
docker compose ps

# Check if docker daemon is running
sudo systemctl status docker
```

## Best Practices

1. **Test before automating**: Always run scripts manually first to ensure they work
2. **Monitor logs**: Regularly check health_check.log for issues
3. **Adjust frequency**: Start with 5-minute intervals and adjust based on your needs
4. **Keep scripts updated**: Pull latest changes from the repository periodically
5. **Backup logs**: Consider archiving old logs for troubleshooting historical issues

## Security Notes

- Setup script requires root privileges
- Health check script is designed to run as root via cron
- All scripts use `set -e` to fail fast on errors
- Health check script includes log rotation to prevent disk space issues
- Setup script prompts before making system changes (firewall, etc.)
