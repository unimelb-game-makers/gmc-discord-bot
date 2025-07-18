# Handle other features

import discord
from discord.ext import commands
from discord import app_commands

class OthersCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
                
    # Setup a testing ping command
    @app_commands.command(name="ping", description="Test command for bot online testing.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("pong")
                
    # Setup a meme duck command
    @app_commands.command(name="duck", description="Quack.")
    async def duck(self, interaction: discord.Interaction):
        await interaction.response.send_message("\U0001F986")