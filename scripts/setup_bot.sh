#!/bin/bash
# Server setup script for first-time deployment
# Run this on your DigitalOcean droplet as root user

set -e

echo "========================================="
echo "GMC Discord Bot - Server Setup"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root"
    echo "Please run: sudo su - or sudo bash $0"
    exit 1
fi

echo "Running as root user"
echo ""

# Update system
echo "Updating system packages..."
apt update && apt upgrade -y

# Install Docker if not already installed
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo "Docker installed successfully!"
else
    echo "Docker already installed: $(docker --version)"
fi

# Install Docker Compose plugin if not already installed
if ! docker compose version &> /dev/null; then
    echo "Installing Docker Compose..."
    apt install docker-compose-plugin -y
    echo "Docker Compose installed successfully!"
else
    echo "Docker Compose already installed: $(docker compose version)"
fi

# Install Git if not already installed
if ! command -v git &> /dev/null; then
    echo "Installing Git..."
    apt install git -y
else
    echo "Git already installed: $(git --version)"
fi

# Create directory for the bot if it doesn't exist
BOT_DIR="/root/gmc-discord-bot"
if [ ! -d "$BOT_DIR" ]; then
    echo ""
    echo "========================================="
    echo "Repository Setup"
    echo "========================================="
    echo "Clone the repository to: $BOT_DIR"
    echo ""
    read -p "Enter the repository URL: " REPO_URL
    git clone "$REPO_URL" "$BOT_DIR"
    cd "$BOT_DIR"
else
    echo "Repository directory already exists at: $BOT_DIR"
    cd "$BOT_DIR"
fi

# Create working_memory directory
mkdir -p working_memory
echo "Created working_memory directory"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "========================================="
    echo "Environment Configuration"
    echo "========================================="
    echo "Creating .env file from template..."

    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo ".env file created from .env.example"
    else
        touch .env
        echo "Empty .env file created"
    fi

    echo ""
    echo "IMPORTANT: Edit the .env file with your actual credentials:"
    echo "  nano .env"
    echo ""
else
    echo ".env file already exists"
fi

# Set up firewall (optional but recommended)
echo ""
read -p "Do you want to configure UFW firewall? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Configuring firewall..."
    ufw allow OpenSSH
    ufw --force enable
    echo "Firewall configured (SSH allowed)"
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your credentials:"
echo "   cd $BOT_DIR && nano .env"
echo "2. Test the bot locally:"
echo "   docker compose up"
echo "3. Set up GitHub Actions secrets for automated deployment"
echo ""
echo "For detailed deployment instructions, see DEPLOYMENT.md"
echo ""
