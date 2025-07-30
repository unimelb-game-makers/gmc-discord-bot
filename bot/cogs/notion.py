# Handle notion features

import discord
from datetime import datetime
from dateutil import parser
import pytz
import re
from discord.ext import commands
from discord import app_commands
from notion_client import AsyncClient
from bot.config import notion_authentication_token, notion_events_database_id, notion_tasks_database_id
from bot.memory import load_object, sync_object
import requests

class NotionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.notion_client = AsyncClient(auth=notion_authentication_token)
        self.notion_events_database_id = notion_events_database_id
        self.notion_tasks_database_id = notion_tasks_database_id
        self.discord_managing_event_names_filename = "discord_managing_event_names.pkl"
        self.discord_managing_event_names = load_object(self.discord_managing_event_names_filename, default_value=[])
        self.notion_events_filter = {
            "property": "Public Checkbox",
            "checkbox": {
                "equals": True
            }
        }
        self.discord_events_thumbnails_filename = "discord_events_thumbnails.pkl"
        self.discord_events_thumbnails = load_object(self.discord_events_thumbnails_filename, default_value={})

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

    # Parse rich text from Notion for discord markdown with a best-effort approach
    def parse_rich_text(self, rich_text) -> str:
        output = ""
        for text_obj in rich_text:
            text = text_obj.get("plain_text", "")
            annotations = text_obj.get("annotations", {})
            href = text_obj.get("href")
            if annotations.get("code"):
                text = f"`{text}`"
            if annotations.get("bold"):
                text = f"**{text}**"
            if annotations.get("italic"):
                text = f"*{text}*"
            if annotations.get("underline"):
                text = f"__{text}__"
            if annotations.get("strikethrough"):
                text = f"~~{text}~~"
            if href:
                text = f"[{text}]({href})"
            output += text
        return output

    # Parse notion event page into {name: Str, start_time: dt obj, end_time: dt obj, description: Str, venue: Str, thumbnail: Str}
    # or None if failed
    def parse_notion_event_page(self, page):
        try:
            event_name = self.parse_rich_text(page["properties"]["Public Name"]["rich_text"])
            event_date_object = page["properties"]["Event Date"]["date"]
            event_start_time_str = event_date_object["start"]
            event_end_time_str = event_date_object["end"]
            event_start_time_dt = self.parse_time_string(event_start_time_str)
            if event_end_time_str is not None:
                event_end_time_dt = self.parse_time_string(event_end_time_str, 23, 59)
            else:
                event_end_time_dt = self.parse_time_string(event_start_time_str, 23, 59)
            event_description = self.parse_rich_text(page["properties"]["Public Description"]["rich_text"])
            if len(page["properties"]["Venue"]["rich_text"]) > 0:
                event_venue = self.parse_rich_text(page["properties"]["Venue"]["rich_text"])
            else:
                event_venue = ""
            if len(page["properties"]["Thumbnail"]["files"]) > 0:
                file_info = page["properties"]["Thumbnail"]["files"][0]
                if file_info["type"] == "external":
                    event_thumbnail = file_info["external"]["url"]
                elif file_info["type"] == "file":
                    event_thumbnail = file_info["file"]["url"]
                else:
                    event_thumbnail = ""
            else:
                event_thumbnail = ""
            return {"name": event_name,
                "start_time": event_start_time_dt,
                "end_time": event_end_time_dt,
                "description": event_description,
                "venue": event_venue,
                "thumbnail": event_thumbnail,
            }
        except Exception as e:
            print(f"Error parsing Notion event page: {e}")
            return None
    
    # Update self.discord_events_thumbnails, if url is "" remove the thumbnail instead
    def update_thumbnail(self, key, url):
        if url == "":
            self.discord_events_thumbnails.pop(key, None)
            sync_object(self.discord_events_thumbnails, self.discord_events_thumbnails_filename)
            return
        try:
            response = requests.get(url)
            if response.status_code == 200:
                image_bytes = response.content
                self.discord_events_thumbnails[key] = image_bytes
                sync_object(self.discord_events_thumbnails, self.discord_events_thumbnails_filename)
        except Exception as e:
            print(f"Error fetching image from URL: {e}")
    
    # Clear all discord event memory
    @app_commands.command(name="cleardiscordeventsmemory", 
        description="Clear memory for what discord events the bot is managing. Keyed by discord event name.")
    async def cleardiscordeventsmemory(self, interaction: discord.Interaction):
        self.discord_managing_event_names = []
        sync_object(self.discord_managing_event_names, self.discord_managing_event_names_filename)
        self.discord_events_thumbnails = {}
        sync_object(self.discord_events_thumbnails, self.discord_events_thumbnails_filename)
        response_string = "Clear complete!"
        await interaction.response.send_message(response_string)
    
    # Remove all discord events created by the bot
    @app_commands.command(name="clearbotevents", description="Delete all scheduled events created by the bot userid.")
    async def clear_bot_events(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            guild = interaction.guild
            bot_user = guild.me

            scheduled_events = await guild.fetch_scheduled_events()
            response_string = "Clearing events:\n"
            count_deleted_events = 0

            for event in scheduled_events:
                if event.creator_id == bot_user.id:
                    try:
                        await event.delete()
                        count_deleted_events += 1
                    except Exception as e:
                        print(f"Failed to delete event {event.name}: {e}")
                        response_string += "Failed to delete: " + event.name + "\n"

            response_string += f"Successfully deleted {count_deleted_events} events\n"

            paginator = commands.Paginator(prefix="", suffix="")
            for line in response_string.splitlines(): 
                paginator.add_line(line)
            for chunk in paginator.pages:
                await interaction.followup.send(chunk)
        except Exception as e:
            print(f"Error clearing bot events: {e}")
            await interaction.followup.send("An error occurred while trying to delete scheduled events.")
        # Also clear memory
        self.discord_managing_event_names = []
        sync_object(self.discord_managing_event_names, self.discord_managing_event_names_filename)
        self.discord_events_thumbnails = {}
        sync_object(self.discord_events_thumbnails, self.discord_events_thumbnails_filename)

    # Setup the event synchronization command
    # Also keeps memory of what discord events are managed by the bot!
    @app_commands.command(name="eventsync", 
                          description="Update events from Notion to discord.")
    async def eventsync(self, interaction: discord.Interaction):
        # Usually takes some time, so defers interaction
        await interaction.response.defer()
        response_string = ""

        # Query notion events
        try:
            response_object = await self.notion_client.databases.query(
                self.notion_events_database_id,
                filter=self.notion_events_filter)
            assert "results" in response_object, "No results found in the response object"
        except Exception as e:
            print(f"Notion fetching Error: {e}")
            await interaction.followup.send("Failed to query Notion events, with .env database id and filters.")
            return
        
        # Fetch discord events
        try:
            guild = interaction.guild
            discord_events = {ev.name: ev for ev in await guild.fetch_scheduled_events()}
        except Exception as e:
            print(f"Discord event fetching Error: {e}")
            await interaction.followup.send("Failed to fetch existing discord events.")
            return
        
        # Update each notion event
        response_string_success = "Updated events:\n"
        response_string_failure = "Failed to update events:\n"
        has_failure = False
        for page in response_object["results"]:
            # Get event properties
            page_parsed = self.parse_notion_event_page(page)
            if page_parsed is None:
                has_failure = True
                response_string_failure += "- <Unknown Notion Event> (Cannot parse page)\n"
                continue
            else:
                event_name = page_parsed["name"]
                event_start_time_dt = page_parsed["start_time"]
                event_end_time_dt = page_parsed["end_time"]
                event_description = page_parsed["description"]
                event_venue = page_parsed["venue"]
                event_thumbnail_url = page_parsed["thumbnail"]
                self.update_thumbnail(event_name, event_thumbnail_url)

                if event_end_time_dt < self.current_time():
                    has_failure = True
                    response_string_failure += f"- {event_name} (End time is in the past)\n"
                    continue
                if len(event_venue) > 100:
                    has_failure = True
                    response_string_failure += f"- {event_name} (Location string length is greater than 100 characters)\n"
                    continue
            
            if event_name in discord_events:
                try:
                    ev = discord_events[event_name]
                    edit_kwargs = {}
                    if ev.start_time != event_start_time_dt:
                        edit_kwargs["start_time"] = event_start_time_dt
                    if ev.end_time != event_end_time_dt:
                        edit_kwargs["end_time"] = event_end_time_dt
                    if ev.description != event_description:
                        edit_kwargs["description"] = event_description
                    if ev.location != event_venue:
                        edit_kwargs["location"] = event_venue
                    if (event_name in self.discord_events_thumbnails) or \
                      (ev.cover_image is not None):
                        if event_name in self.discord_events_thumbnails:
                            edit_kwargs["image"] = self.discord_events_thumbnails[event_name]
                        else:
                            edit_kwargs["image"] = None
                    if edit_kwargs:
                        await ev.edit(**edit_kwargs)
                        response_string_success += "- " + event_name + " (Edited)\n"
                    else:
                        response_string_success += "- " + event_name + " (Unchanged)\n"
                except Exception as e:
                    print(f"Discord event editing {event_name} with {edit_kwargs} Error: {e}")
                    has_failure = True
                    response_string_failure += "- " + event_name + " (Error when editing existing discord event)\n"
                    continue
            else:
                try:
                    if event_name in self.discord_events_thumbnails:
                        ev = await guild.create_scheduled_event(
                            name=event_name,
                            description=event_description,
                            start_time=event_start_time_dt,
                            end_time=event_end_time_dt,
                            entity_type=discord.EntityType.external,
                            privacy_level=discord.PrivacyLevel.guild_only,
                            location=event_venue,
                            image=self.discord_events_thumbnails[event_name],
                        )
                    else:
                        ev = await guild.create_scheduled_event(
                            name=event_name,
                            description=event_description,
                            start_time=event_start_time_dt,
                            end_time=event_end_time_dt,
                            entity_type=discord.EntityType.external,
                            privacy_level=discord.PrivacyLevel.guild_only,
                            location=event_venue
                        )
                    response_string_success += "- " + event_name + " (Created)\n"
                except Exception as e:
                    print(f"Discord event creation of {event_name} Error: {e}")
                    has_failure = True
                    response_string_failure += "- " + event_name + " (Error when creating new discord event)\n"
                    continue
        
        # Remove unmentioned memorized tracking discord events
        sync_object(self.discord_managing_event_names, self.discord_managing_event_names_filename)
        notion_event_names = []
        for page in response_object["results"]:
            parsed_page = self.parse_notion_event_page(page)
            if parsed_page is not None:
                notion_event_names.append(parsed_page["name"])
        delete_keys = set(self.discord_managing_event_names) - set(notion_event_names)
        for event_name in delete_keys:
            if event_name in discord_events:
                try:
                    # Delete the discord event if it exists
                    ev = discord_events[event_name]
                    await ev.delete()
                    response_string_success += "- " + event_name + " (Removed)\n"
                except Exception as e:
                    print(f"Removing old event Error: {e}")
                    has_failure = True
                    response_string_failure += "- " + event_name + " (Cannot remove the event)\n"
                self.discord_events_thumbnails.pop(event_name, None)
                sync_object(self.discord_events_thumbnails, self.discord_events_thumbnails_filename)
            else:
                response_string_success += "- " + event_name + " (Already removed)\n"
        self.discord_managing_event_names = notion_event_names
        sync_object(self.discord_managing_event_names, self.discord_managing_event_names_filename)

        # Follow up message
        response_string += response_string_success
        if has_failure:
            response_string += response_string_failure

        paginator = commands.Paginator(prefix="", suffix="")
        for line in response_string.splitlines(): 
            paginator.add_line(line)
        for chunk in paginator.pages:
            await interaction.followup.send(chunk)

    # Setup the task fetch command
    @app_commands.command(name="listtasks", 
                          description="List tasks marked as In progress from Notion.")
    async def listtasks(self, interaction: discord.Interaction):
        # Usually takes some time, so defers interaction
        await interaction.response.defer()
        response_string = ""

        # Query notion tasks
        try:
            response_string += "Filtering by status as In progress.\n"
            response_object = await self.notion_client.databases.query(
                self.notion_tasks_database_id,
                filter={
                    "property": "Status",
                    "status": {
                        "equals": "In progress"
                    }
                })
            assert "results" in response_object, "No results found in the response object"
        except Exception as e:
            print(f"Query Notion Tasks Error: {e}")
            await interaction.followup.send("Failed to query Notion tasks, with .env database id and filters.")
            return
        
        # Update each notion task
        response_string_success = "Tasks in progress:\n"
        response_string_failure = "Failed to fetch tasks:\n"
        has_failure = False
        for page in response_object["results"]:
            # Get task properties
            try:
                task_name = page["properties"]["Task"]["title"][0]["plain_text"]
                task_date_object = page["properties"]["Due"]["date"]
            except Exception as e:
                print(f"Fetching Notion Task Properties Error: {e}")
                has_failure = True
                response_string_failure += "- <Unknown Notion Task> (Cannot fetch task name and date)\n"
                continue
            # Convert task dates to datetime objects
            if task_date_object is None:
                has_failure = True
                response_string_failure += "- " + task_name + " (Nothing set in the Due Date column)\n"
                continue
            try:
                task_due_time_str = task_date_object["start"]
                if task_date_object["end"] is not None:
                    task_due_time_str = task_date_object["end"]
                task_due_time_dt = self.parse_time_string(task_due_time_str, 21, 0)
                task_due_time_discord_str = self.datetime_to_discord_long_date(task_due_time_dt)
            except Exception as e:
                print(f"Converting Task Due Dates Error: {e}")
                has_failure = True
                response_string_failure += "- " + task_name + " (Cannot convert task due dates)\n"
                continue
            response_string_success += "- " + task_name + " - Due: " + task_due_time_discord_str + ")\n"

        # Follow up message
        response_string += response_string_success
        if has_failure:
            response_string += response_string_failure

        try:
            paginator = commands.Paginator(prefix="", suffix="")
            for line in response_string.splitlines(): 
                paginator.add_line(line)
            for chunk in paginator.pages:
                await interaction.followup.send(chunk)
        except Exception as e:
            print(f"Error while sending response: {e}")
            await interaction.followup.send("An error occurred while sending response.")