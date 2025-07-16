# Handle notion features

import discord
from datetime import datetime
from dateutil import parser
import pytz
import re
from discord.ext import commands
from discord import app_commands
from notion_client import AsyncClient
from bot.config import notion_authentication_token, notion_events_database_id
import pprint

class NotionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.notion_client = AsyncClient(auth=notion_authentication_token)
        self.notion_events_database_id = notion_events_database_id

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

    # Setup the event synchronization command
    @app_commands.command(name="eventsync", 
                          description="Update events from Notion.")
    async def eventsync(self, interaction: discord.Interaction):
        # Usually takes some time, so defers interaction
        await interaction.response.defer()
        response_string = ""

        # Query notion events
        try:
            response_string += "Filtering by status as Planning or In progress.\n"
            response_object = await self.notion_client.databases.query(
                self.notion_events_database_id,
                filter={
                    "or": [{
                        "property": "Status",
                        "status": {
                            "equals": "Planning"
                        }
                    }, {
                        "property": "Status",
                        "status": {
                            "equals": "In progress"
                        }
                    }]
                })
            assert "results" in response_object, "No results found in the response object"
        except Exception as e:
            await interaction.followup.send("Failed to query Notion events, with .env database id and filters.")
            return
        
        # Fetch discord events
        try:
            guild = interaction.guild
            discord_events = {ev.name: ev for ev in await guild.fetch_scheduled_events()}
        except Exception as e:
            await interaction.followup.send("Failed to fetch existing discord events.")
            return
        
        # Update each notion event
        response_string_success = "Updated events:\n"
        response_string_failure = "Failed to update events:\n"
        has_failure = False
        for page in response_object["results"]:
            # Get event properties
            try:
                event_name = page["properties"]["Project name"]["title"][0]["plain_text"]
                event_date_object = page["properties"]["Event Date"]["date"]
            except Exception as e:
                has_failure = True
                response_string_failure += "- <Unknown Notion Event> (Cannot fetch event name and date)\n"
                continue
            # Convert event dates to datetime objects
            if event_date_object is None:
                has_failure = True
                response_string_failure += "- " + event_name + " (Nothing set in the Event Date column)\n"
                continue
            try:
                event_start_time_str = event_date_object["start"]
                event_end_time_str = event_date_object["end"]
                event_start_time_dt = self.parse_time_string(event_start_time_str)
                if event_end_time_str is not None:
                    event_end_time_dt = self.parse_time_string(event_end_time_str, 23, 59)
                else:
                    event_end_time_dt = self.parse_time_string(event_start_time_str, 23, 59)
            except Exception as e:
                has_failure = True
                response_string_failure += "- " + event_name + " (Cannot convert event dates)\n"
                continue
            
            if event_name in discord_events:
                try:
                    ev = discord_events[event_name]
                    edit_kwargs = {}
                    if ev.start_time != event_start_time_dt:
                        edit_kwargs["start_time"] = event_start_time_dt
                    if ev.end_time != event_end_time_dt:
                        edit_kwargs["end_time"] = event_end_time_dt
                    if edit_kwargs:
                        await ev.edit(**edit_kwargs)
                        response_string_success += "- " + event_name + " (Edited)\n"
                    else:
                        response_string_success += "- " + event_name + " (Unchanged)\n"
                except Exception as e:
                    has_failure = True
                    response_string_failure += "- " + event_name + " (Cannot edit existing discord event)\n"
                    continue
            else:
                try:
                    await guild.create_scheduled_event(
                        name=event_name,
                        start_time=event_start_time_dt,
                        end_time=event_end_time_dt,
                        entity_type=discord.EntityType.external,
                        privacy_level=discord.PrivacyLevel.guild_only,
                        location="",
                    )
                    response_string_success += "- " + event_name + " (Created)\n"
                except Exception as e:
                    has_failure = True
                    response_string_failure += "- " + event_name + " (Cannot create new discord event)\n"
                    continue

        # Follow up message
        response_string += response_string_success
        if has_failure:
            response_string += response_string_failure

        paginator = commands.Paginator(prefix="", suffix="")
        for line in response_string.splitlines(): 
            paginator.add_line(line)
        for chunk in paginator.pages:
            await interaction.followup.send(chunk)

