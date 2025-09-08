# Handle message queueing
import re
import pytz
from typing import Optional
from datetime import datetime, timedelta
from dateutil import parser

import discord
from discord.ext import commands, tasks
from discord import app_commands

class MsgQueueCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.jobs: list[dict] = []   # [{id, channel_id, message, due_utc, status}]
        self._next_id = 1
        self.check_jobs.start()

    # Send message at scheduled time
    @app_commands.command(name="messagequeuing",
                            description="Send message at scheduled time.")
    @app_commands.describe(
        channel="Channel to send in",
        message="Message to send",
        date="Optional scheduled date YYYY-MM-DD (local Melbourne). If time omitted, send at 12AM",
        time_hm="Optional scheduled time HH:MM (local Melbourne). If date omitted, uses next occurrence."
    )
    async def messagequeuing(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str,
        date: Optional[str] = None,      
        time_hm: Optional[str] = None,
    ):
        try:
            if date and time_hm:
                local_dt = self.parse_time_string(f"{date}T{time_hm}")
            elif time_hm:
                local_dt = self.next_occurrence_hm_local(time_hm)  
            elif date:
                local_dt = self.parse_time_string(date)
            else:
                return await interaction.response.send_message(
                    "(X) Provide either `date` + `time_hm`, `time_hm`. or `date` to schedule your message",
                    ephemeral=True
                )
            due_utc = local_dt.astimezone(pytz.utc)
        except Exception as e:
            return await interaction.response.send_message(f"(X) Time parse error: {e}", ephemeral=True)

        # Enqueue in memory
        job = {
            "id": self._next_id,
            "channel_id": channel.id,
            "message": message,
            "due_utc": due_utc,
            "status": "pending",
        }
        self._next_id += 1
        self.jobs.append(job)

        # Confirm to the user
        await interaction.response.send_message(
            f"Queued **#{job['id']}** for {self.datetime_to_discord_short_datetime(local_dt)} in {channel.mention}.",
            ephemeral=True
        )

    def next_occurrence_hm_local(self, hm: str) -> datetime:
        fmt = "%H:%M"
        t = datetime.strptime(hm, fmt).time()
        now = self.current_time()
        cand = now.replace(hour=t.hour, minute=t.minute, second=0)
        if cand <= now:
            cand += timedelta(days=1)
        return cand

    # offload cog
    def cog_unload(self):
        self.check_jobs.cancel()

    # check every minute if there's schedule message need to be sent
    @tasks.loop(minutes=1)
    async def check_jobs(self):
        now_utc = datetime.now(pytz.utc)
        due = [j for j in self.jobs if j["status"] == "pending" and j["due_utc"] <= now_utc]
        for job in due:
            ch = self.bot.get_channel(job["channel_id"])
            if isinstance(ch, discord.TextChannel):
                try:
                    await ch.send(job["message"])
                    job["status"] = "sent"
                except Exception:
                    job["status"] = "error"


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
            # --- minimal necessary addition: localize naive datetimes ---
            if dt.tzinfo is None:
                dt = pytz.timezone(default_timezone).localize(dt)

        return dt
    
    def current_time(self, default_timezone="Australia/Melbourne"):
        return datetime.now(pytz.timezone(default_timezone))

    # datetime object to discord timestamp string, e.g. August 5, 2024 4:00 PM
    def datetime_to_discord_short_datetime(self, dt: datetime) -> str:
        epoch = round(dt.timestamp())  # Timestamp returns a float so round it
        return f"<t:{epoch}:f>"