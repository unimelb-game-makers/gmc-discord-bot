# Handle message queueing
import re
import pytz
from typing import Optional
from datetime import datetime, timedelta
from dateutil import parser

from discord import Interaction

import discord
from discord.ext import commands, tasks
from discord import app_commands
 
from bot.memory import load_object, sync_object
from enum import Enum

MAX_MSGN_DISPLAY = 5
MSG_MEMORY_PATH = "message_queue.pkl"
# whitelist for message queuening: discor user IDs set
AUTHORISED_IDS = {
    # put your (tester) or authorized people's user IDs here to use message queuening
    # Do NOT commit real IDs to public repos
    # Get IDs via Developer Mode → Right-click user → Copy ID
}

# enum for msg job status
class JobStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    ERROR = "error"

class MsgQueueCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # keys of dict: [{id, channel_id, message, due_utc, status, author_id}]
        self.jobs: list[dict] = []   
        self._next_id = 1
        self.queue_filename = MSG_MEMORY_PATH
        state = load_object(self.queue_filename, default_value={"jobs": [], "next_id": 1})
        try:
            self.jobs = state.get("jobs", [])
            for j in self.jobs:
                if not isinstance(j.get("status"), JobStatus):
                    j["status"] = JobStatus(j.get("status", JobStatus.PENDING))
            self._next_id = int(state.get("next_id", 1))
        except Exception as e:
            print(f"[msgqueue] load failed, starting fresh: {e}")
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
        if interaction.user.id not in AUTHORISED_IDS:
            return await interaction.response.send_message(
            "(X) You don’t have permission to schedule messages here.", ephemeral=True
        )
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
            "status": JobStatus.PENDING,
            "author_id": interaction.user.id,
        }
        self._next_id += 1
        self.jobs.append(job)
        self._save_state()

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

    # save current queue state 
    def _save_state(self):
        try:
            sync_object({"jobs": self.jobs, "next_id": self._next_id}, self.queue_filename)
        except Exception as e:
            print(f"[msgqueue] save failed: {e}")

    # offload cog
    def cog_unload(self):
        self._save_state()
        self.check_jobs.cancel()

    # check every minute if there's schedule message need to be sent
    @tasks.loop(minutes=1)
    async def check_jobs(self):
        now_utc = datetime.now(pytz.utc)
        due = [j for j in self.jobs if j["status"] == JobStatus.PENDING and j["due_utc"] <= now_utc] 
        for job in due:
            ch = self.bot.get_channel(job["channel_id"])
            if isinstance(ch, discord.TextChannel):
                try:
                    sender_label = ""
                    author_id = job.get("author_id")
                    sender_label = f"<@{author_id}>"
                    
                    await ch.send(f"{sender_label}: {job['message']}")  
                    job["status"] = JobStatus.SENT   
                except Exception:
                    job["status"] = JobStatus.ERROR  
                finally:
                    self._save_state()
 
    # Print out first 5 schedule messages need to be sent 
    @app_commands.command(name="checkmessagequeue", 
                        description=" Print out all schedule messages need to be sent")
    async def check_message_queue(self, interaction):
        if interaction.user.id not in AUTHORISED_IDS:
            return await interaction.response.send_message(
            "(X) You don’t have permission to check messages scheduled here.", ephemeral=True
        )
        now_utc = datetime.now(pytz.utc)

        # store all pending msgs
        pending = [j for j in self.jobs if j["status"] == JobStatus.PENDING] 
        if not pending:
            return await interaction.response.send_message("No pending messages in queue.", ephemeral=True)

        # display in time order
        pending.sort(key=lambda j: (j["due_utc"], j["id"]))
        mel = pytz.timezone("Australia/Melbourne")

        msgN = min(MAX_MSGN_DISPLAY, len(pending))
        lines = [f"Showing next {msgN} of {len(pending)} pending messages:"]
        for j in pending[:MAX_MSGN_DISPLAY]:  
            local_dt = j["due_utc"].astimezone(mel)
            ts = self.datetime_to_discord_short_datetime(local_dt)
            author = f"<@{j['author_id']}>" if j.get("author_id") else "someone"
            lines.append(f"{author} scheduled message **#{j['id']}** to be sent in <#{j['channel_id']}> on {ts}.")

        if len(pending) > MAX_MSGN_DISPLAY:
            lines.append(f"...and {len(pending) - MAX_MSGN_DISPLAY} more")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    # ----- helpers for time parsing from notion.py -----
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