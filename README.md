# gmc-discord-bot
Custom python discord bot for UMGMC discord

## Setup

### Raw

- Clone repository on UNIX machine
- Install python and pip
- Setup .env environment file
- Create and enter virtual environment with ```python3 -m venv .venv && source .venv/bin/activate``` (change to your venv directory)
- ```pip install -r requirements.txt``` to install dependencies
- ```python3 -m bot.main``` to run the bot for testing
- ```python3 -m test.main``` to run tests
- Create system service for continuous deployment (```sudo systemctl start gmcbot```)

### Using Docker

- Ensure docker and docker compose are installed and docker engine is active
- Clone repository
- Setup .env environment file (see `.env.example` for template)
- Type ```docker compose up -d``` to build and run the container in detached mode
- Type ```docker compose logs -f``` to view logs
- Type ```docker compose down``` to stop the container

### Automated Deployment to DigitalOcean

For production deployment with automated CI/CD, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Notion features

- Notion events integration


- Notion task reminders



## Message features

- Message queue



## Itch features



## AI features



## Other features

Nothing yet

## Reference

- [Discord.py Docs](https://discordpy.readthedocs.io/en/stable/ext/commands/cogs.html)
- [Notion SDK](https://ramnes.github.io/notion-sdk-py/reference/api_endpoints/)