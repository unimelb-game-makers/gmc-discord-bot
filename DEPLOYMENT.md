# Deployment Guide

This guide explains how to deploy the GMC Discord Bot to a DigitalOcean droplet using GitHub Actions.

## Prerequisites

1. A DigitalOcean droplet with Ubuntu (recommended: 20.04 or 22.04)
2. Docker and Docker Compose installed on the droplet
3. Git installed on the droplet
4. SSH key pair for authentication

## Initial Droplet Setup

You can choose between automated setup (recommended) or manual setup.

### Option A: Automated Setup (Recommended)

Use the provided setup script to automatically install all dependencies:

```bash
# Download and run the setup script
curl -fsSL https://raw.githubusercontent.com/unimelb-game-makers/gmc-discord-bot/main/scripts/setup_bot.sh -o setup_bot.sh
chmod +x setup_bot.sh
./setup_bot.sh
```

The script will:
- Install Docker and Docker Compose
- Install Git
- Clone the repository
- Create necessary directories
- Set up .env file from template
- Optionally configure UFW firewall

After running the script, skip to [GitHub Secrets Setup](#github-secrets-setup).

### Option B: Manual Setup

If you prefer to set up manually, follow these steps:

#### 1. Install Docker and Docker Compose

SSH into your droplet and run:

```bash
# Update package index
sudo apt update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Note: When running as root, no need to add user to docker group

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify installations
docker --version
docker compose version
```

Log out and log back in for group changes to take effect.

#### 2. Clone the Repository

```bash
cd /root
git clone https://github.com/unimelb-game-makers/gmc-discord-bot.git
cd gmc-discord-bot
```

#### 3. Create Environment File

Create a `.env` file with your bot credentials:

```bash
nano .env
```

Add your environment variables (refer to the main README for required variables):

```env
DISCORD_BOT_TOKEN=your_bot_token_here
NOTION_TOKEN=your_notion_token_here
NOTION_EVENTS_DATABASE_ID=your_events_db_id_here
NOTION_TASKS_DATABASE_ID=your_tasks_db_id_here
OPENAI_API_KEY=your_openrouter_api_key_here
# Add other required variables...
```

Save and exit (Ctrl+X, then Y, then Enter).

#### 4. Create Working Memory Directory

```bash
mkdir -p working_memory
```

#### 5. Test Manual Deployment

```bash
# Build and start the container
docker compose up -d

# Check logs
docker compose logs -f

# Stop the container
docker compose down
```

## GitHub Secrets Setup

In your GitHub repository, add the following secrets:

1. Go to Settings > Secrets and variables > Actions
2. Add the following repository secrets:

   - **SSH_PRIVATE_KEY**: Your OpenSSH format private key
     ```bash
     # Generate a new key pair if needed (on your local machine)
     ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy

     # Copy the private key content
     cat ~/.ssh/github_deploy

     # Copy the public key to your droplet (as root user)
     ssh-copy-id -i ~/.ssh/github_deploy.pub root@your-droplet-ip
     ```

   - **DROPLET_IP**: Your droplet's IP address (e.g., `123.45.67.89`)

> **Note:** The deployment workflow is configured to use the `root` user. No need to set DROPLET_USER secret.

## Deployment Workflow

The deployment workflow triggers automatically on:
- Push to `main` branch
- Manual trigger via GitHub Actions UI

### What the Workflow Does

1. Checks out the code
2. Sets up SSH authentication
3. Connects to your droplet as root user
4. Pulls latest code from the repository
5. Stops existing containers
6. Builds new Docker image
7. Starts containers
8. Shows container status and logs
9. Performs health check

### Manual Deployment

To manually trigger deployment:
1. Go to Actions tab in GitHub
2. Select "Deploy to DigitalOcean" workflow
3. Click "Run workflow"
4. Select the branch (usually `main`)
5. Click "Run workflow" button

## Viewing Logs

To view logs on the droplet:

```bash
# SSH into droplet
ssh user@your-droplet-ip

# Navigate to project directory
cd /root/gmc-discord-bot

# View logs
docker compose logs -f

# View last 100 lines
docker compose logs --tail=100

# View logs for specific time
docker compose logs --since 30m
```

## Managing the Bot

### Start the bot
```bash
docker compose up -d
```

### Stop the bot
```bash
docker compose down
```

### Restart the bot
```bash
docker compose restart
```

### Rebuild and restart
```bash
docker compose up -d --build
```

### Check container status
```bash
docker compose ps
```

## Troubleshooting

### Container keeps restarting
```bash
# Check logs for errors
docker compose logs --tail=100

# Common issues:
# - Missing or incorrect .env variables
# - Invalid Discord bot token
# - Invalid Notion credentials
```

### Deployment fails
```bash
# Check GitHub Actions logs for details
# Common issues:
# - SSH key not properly configured
# - Incorrect DROPLET_IP
# - SSH public key not added to droplet's authorized_keys
# - Git repository not cloned on droplet at /root/gmc-discord-bot
# - Docker not installed on droplet
```

### Bot not responding to commands
```bash
# Verify bot is running
docker compose ps

# Check if bot logged in successfully
docker compose logs | grep -i "logged in"

# Verify bot token is correct
docker compose exec bot python -c "import os; print('Token exists:', bool(os.getenv('DISCORD_BOT_TOKEN')))"
```

## Security Best Practices

1. **Never commit `.env` files** - Already in `.gitignore`
2. **Use SSH keys** - Disable password authentication on droplet
3. **Firewall configuration** - Only allow necessary ports (SSH, optionally HTTP/HTTPS)
4. **Regular updates** - Keep droplet and Docker updated
5. **Monitor logs** - Regularly check for errors or suspicious activity
6. **Backup data** - Regularly backup `working_memory` directory

## Monitoring

Set up a simple health check using a cron job:

```bash
# On the droplet, the health check script is included in the repository
cd /root/gmc-discord-bot
chmod +x scripts/check_health.sh

# Test the script
./scripts/check_health.sh

# Add to crontab for automatic monitoring
crontab -e
# Add this line to check every 5 minutes
*/5 * * * * /root/gmc-discord-bot/scripts/check_health.sh
```

The health check script will:
- Check if the bot container is running
- Restart it automatically if it's down
- Log all actions to `health_check.log`
- Detect crash loops (frequent restarts)
- Rotate logs automatically when they get too large

## Next Steps

- Set up monitoring and alerting
- Configure automatic backups
- Add staging environment
- Implement rollback mechanism
- Add Discord webhook notifications for deployments
