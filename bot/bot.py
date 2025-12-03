# Main bot running script
# Load cogs and run the bot

import os
import discord
from discord.ext import commands
from bot.config import discord_bot_token
from bot.cogs.itch import ItchCog
from bot.cogs.notion import NotionCog
from bot.cogs.others import OthersCog
from bot.cogs.ai import AiCog
from bot.utils.memory import remove_all_filelocks
from bot.cogs.msgqueueing import MsgQueueCog

def run():

    # Remove filelocks
    remove_all_filelocks()

    # Configure bot intents
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix='/', intents=intents)

    # Dynamically load cogs: itch, notion, ai, and others from './bot/cogs' when ready
    @bot.event
    async def on_ready():
        await bot.add_cog(ItchCog(bot))
        await bot.add_cog(NotionCog(bot))
        await bot.add_cog(OthersCog(bot))
        await bot.add_cog(AiCog(bot))
        await bot.add_cog(MsgQueueCog(bot))
        # await bot.tree.sync()
        print("Bot ready!")

    # Setup resync command.
    # Resync bot in case of command changes
    @bot.command(name='sync', description='Sync command tree. Careful not to spam due to rate limit.')
    async def sync(ctx):
        await bot.tree.sync()
        await ctx.send('Command tree synced. Use Ctrl+R to refresh commands in Desktop Discord.')

    bot.run(discord_bot_token)
