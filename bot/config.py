# Load tokens and keys from .env

import os
from dotenv import load_dotenv

load_dotenv()

discord_bot_token = os.getenv("DISCORD_BOT_TOKEN")
discord_guild_id = os.getenv("DISCORD_GUILD_ID")
notion_authentication_token = os.getenv("NOTION_AUTHENTICATION_TOKEN")