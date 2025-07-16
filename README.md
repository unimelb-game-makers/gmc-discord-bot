# gmc-discord-bot
Custom python discord bot for UMGMC discord

## Setup

- Clone repository on UNIX machine
- Install python and pip
- Setup .env environment file
- I use python venv, so python3 -m venv ~/py3venv (change to your venv directory)
- ~/py3venv/bin/pip install -r requirements.txt
- ~/py3venv/bin/python3 -m bot.main (To run the bot for testing)
- ~/py3venv/bin/python3 -m test.main (To run tests)
- Create system service for continuous deployment

## Planned features

- Notion events to discord events, commands for managing
- Notion task reminder
- Game jam itch announcement synchronization
- Memes

## Reference

- [Discord.py Docs](https://discordpy.readthedocs.io/en/stable/ext/commands/cogs.html)
- [Notion SDK](https://ramnes.github.io/notion-sdk-py/reference/api_endpoints/)