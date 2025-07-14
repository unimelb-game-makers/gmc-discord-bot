# Main entry point
import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

# Load token from .env file
load_dotenv()
discord_bot_token = os.getenv("DISCORD_BOT_TOKEN")

# Configure bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='>', intents=intents)

# Setup a testing ping command
@bot.command()
async def ping(ctx):
    await ctx.send('pong')

# Start bot
bot.run(discord_bot_token)