# Handle notion features

import discord
from discord.ext import commands
from discord import app_commands
from notion_client import AsyncClient
from bot.config import notion_authentication_token
import pprint

class NotionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.notion_client = AsyncClient(auth=notion_authentication_token)

    # Setup a testing f
    @app_commands.command(name='ff', description="FFF.")
    async def ff(self, interaction: discord.Interaction):
        list_users_response = await self.notion_client.users.list()
        response_string = pprint.pformat(list_users_response, indent=1)
        await interaction.response.send_message(response_string[:2000])

