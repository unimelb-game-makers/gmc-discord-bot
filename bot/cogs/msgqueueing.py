# Handle message queueing
import re
import pytz
from typing import Optional
from datetime import datetime
from dateutil import parser

import discord
from discord.ext import commands
from discord import app_commands

class MsgQueueCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Send message at scheduled time
    @app_commands.command(name="messagequeuing",
                            description="Send message at scheduled time.")
    @app_commands.describe(
        channel="Channel to send in",
        message="Message to send",
        date="Optional scheduled date YYYY-MM-DD (local Melbourne)",
        time_hms="Time HH:MM or HH:MM:SS (local Melbourne). If date omitted, uses next occurrence."
    )
    async def messagequeuing(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str,
        date: Optional[str] = None,      
        time_hms: Optional[str] = None,
    ):
        await interaction.response.send_message(
            f"Scheduled: {message!r} in {channel.mention} at 
            {date or 'today'} {time_hms or '(no time)'} AEST",
            ephemeral=True
        )


    # --- helpers for time parsing from notion.py ---

        # Parse notion time string to datetime object
    def parse_time_string(self, time_str: str, default_hour = 0, default_minute = 0, default_timezone="Australia/Melbourne"):
        # Regular expression to check if it's date-only (e.g., 2025-08-22)
        date_only_pattern = r"^\d{4}-\d{2}-\d{2}$"

        if re.match(date_only_pattern, time_str):
            # Format 1: 2025-08-22
            dt = datetime.strptime(time_str, "%Y-%m-%d")
            dt = pytz.timezone(default_timezone).localize(dt)
            dt = dt.replace(hour=default_hour, minute=default_minute)
        else:
            # Format 2: 2025-07-24T16:00:00.000+10:00
            dt = parser.isoparse(time_str)

        return dt
    
    def current_time(self, default_timezone="Australia/Melbourne"):
        return datetime.now(pytz.timezone(default_timezone))

    # datetime object to discord timestamp string, e.g. July 19, 2025
    def datetime_to_discord_long_date(self, dt: datetime) -> str:
        epoch = round(dt.timestamp())  # Timestamp returns a float so round it
        return f"<t:{epoch}:D>"

    # datetime object to discord timestamp string, e.g. August 5, 2024 4:00 PM
    def datetime_to_discord_short_datetime(self, dt: datetime) -> str:
        epoch = round(dt.timestamp())  # Timestamp returns a float so round it
        return f"<t:{epoch}:f>"

    # datetime object to discord timestamp string, e.g. 4:00 PM
    def datetime_to_discord_short_time(self, dt: datetime) -> str:
        epoch = round(dt.timestamp())  # Timestamp returns a float so round it
        return f"<t:{epoch}:t>"
