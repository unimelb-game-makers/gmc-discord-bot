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

- Clone respository
- Ensure docker is installed and docker engine is active
- Type ```docker build -t gmc-discord-bot``` to build the docker image
- Type ```docker run gmc-discord-bot``` to run the image as a container.

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