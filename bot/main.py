# Main entry point
import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Load token from .env file
load_dotenv()
discord_bot_token = os.getenv("DISCORD_BOT_TOKEN")
discord_guild_id = os.getenv("DISCORD_GUILD_ID")

# Configure bot and guild
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Bot ready
@bot.event
async def on_ready():
    print("Ready!")

# Setup resync command.
# Resync bot in case of command changes
@bot.command(name='sync', description='Sync commands. Careful not to spam due to rate limit.')
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send('Command tree synced.')

# Setup a testing ping command
@bot.tree.command(name='ping', description="Test command.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message('pong')

# Start bot
if __name__ == "__main__":
    bot.run(discord_bot_token)