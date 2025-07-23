# Handle other features

import discord
from discord.ext import commands
from discord import app_commands
from bot.memory import clear_memory
import pprint

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

    # Clear all memory files
    @app_commands.command(name="clearmemory", description="Clear all memory files.")
    async def clearmemory(self, interaction: discord.Interaction):
        response_string = clear_memory()
        response_string = "Clearing memory files:\n" + response_string
        await interaction.response.send_message(response_string)

    # @app_commands.command(name="test", description="Temporary dev testing.")
    # async def test(self, interaction: discord.Interaction):
    #     await interaction.response.defer()
    #     guild = interaction.guild
    #     discord_events = {ev.name: ev for ev in await guild.fetch_scheduled_events()}
    #     pprint.pprint(discord_events["Winter Fest Booth"].start_time)
    #     pprint.pprint(discord_events["Winter Fest Booth"].end_time)
    #     pprint.pprint(discord_events["Winter Fest Booth"].description)
    #     pprint.pprint(discord_events["Winter Fest Booth"].location)
    #     pprint.pprint(discord_events["Winter Fest Booth"].cover_image)
    #     await interaction.followup.send("Done!")