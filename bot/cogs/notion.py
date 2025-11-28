# Handle notion features

import discord
from datetime import datetime, timedelta
from dateutil import parser
import pytz
import re
from discord.ext import commands, tasks
from discord import app_commands
from notion_client import AsyncClient
from bot.config import notion_authentication_token, notion_events_database_id, \
    notion_tasks_database_id, notion_people_database_id
from bot.memory import load_object, sync_object
import requests

class NotionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.notion_client = AsyncClient(auth=notion_authentication_token)
        self.notion_events_database_id = notion_events_database_id
        self.notion_tasks_database_id = notion_tasks_database_id
        self.notion_people_database_id = notion_people_database_id
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
        self.notion_tasks_filter = {
            "or": [
                {
                    "property": "Status",
                    "status": {
                        "equals": "In progress"
                    }
                },
                {
                    "property": "Status",
                    "status": {
                        "equals": "Not started"
                    }
                }
            ]
        }
        self.daily_scheduled_time_filename = "daily_scheduled_time.pkl"
        self.daily_scheduled_time = load_object(self.daily_scheduled_time_filename, default_value={"hour": 10, "minute": 0})
        self.last_run_date_filename = "last_run_date.pkl"
        self.last_run_date = load_object(self.last_run_date_filename, default_value=None)
        self.report_channel_id_filename = "report_channel_id.pkl"
        self.report_channel_id = load_object(self.report_channel_id_filename, default_value=1369549200676884552)
        self.name_masks_filename = "name_masks.pkl"
        self.name_masks = load_object(self.name_masks_filename, default_value={})
        self.daily_report.start()

    def cog_unload(self):
        self.daily_report.cancel()

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
                event_end_time_dt = self.parse_time_string(event_start_time_str, 23, 59) + timedelta(minutes=1)
            # Public description seems to be removed from event database? For now just use empty string
            # event_description = self.parse_rich_text(page["properties"]["Public Description"]["rich_text"])
            event_description = ""
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

    # Attempt to sync events from notion to guild
    # Returns update status as string
    async def sync_bot_events(self, guild: discord.Guild):
        response_string = ""

        # Query notion events
        try:
            response_object = await self.notion_client.databases.query(
                self.notion_events_database_id,
                filter=self.notion_events_filter)
            assert "results" in response_object, "No results found in the response object"
        except Exception as e:
            print(f"Notion fetching Error: {e}")
            return "Failed to query Notion events, with .env database id and filters."

        # Fetch discord events
        try:
            discord_events = {ev.name: ev for ev in await guild.fetch_scheduled_events()}
        except Exception as e:
            print(f"Discord event fetching Error: {e}")
            return "Failed to fetch existing discord events."
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

        return response_string

    # Setup the event synchronization command
    # Also keeps memory of what discord events are managed by the bot!
    @app_commands.command(name="eventsync",
                          description="Update events from Notion to discord.")
    async def eventsync(self, interaction: discord.Interaction):
        # Usually takes some time, so defers interaction
        await interaction.response.defer()
        guild = interaction.guild

        response_string = self.sync_bot_events(guild)

        paginator = commands.Paginator(prefix="", suffix="")
        for line in response_string.splitlines():
            paginator.add_line(line)
        for chunk in paginator.pages:
            await interaction.followup.send(chunk)

    # Parse notion ids to discord url
    def parse_ids_to_url(self, notion_ids) -> str:
        notion_ids = [re.sub(r'[^0-9a-z]', '', s.lower()) for s in notion_ids]
        n = len(notion_ids)
        if n == 0:
            return ""
        elif n == 1:
            return "[Related project](https://www.notion.so/" + notion_ids[0] + ")"
        else:
            response_string = "Related projects: "
            for x in range(1, n + 1):
                if x == n:
                    response_string += "[" + str(x) + "](https://www.notion.so/" + notion_ids[x - 1] + ")"
                else:
                    response_string += "[" + str(x) + "](https://www.notion.so/" + notion_ids[x - 1] + ") "
            return response_string

    # Parse notion task page as a dict object. Blank properties marked as None.
    # Returns None if failed to parse or lack critical info
    def parse_notion_task_page(self, page):
        try:
            task_name = self.parse_rich_text(page["properties"]["Task"]["title"])
            task_date_object = page["properties"]["Due"]["date"]
            if task_date_object is None:
                return None
            task_due_time_str = task_date_object["start"]
            if task_date_object["end"] is not None:
                task_due_time_str = task_date_object["end"]
            task_due_time_dt = self.parse_time_string(task_due_time_str, 21, 0)
            task_related_team = [tag["name"] for tag in page["properties"]["Team"]["multi_select"]]
            task_assignee = [person["name"] for person in page["properties"]["Assignee"]["people"]]
            task_status = page["properties"]["Status"]["status"]["name"]
            task_related_project = self.parse_ids_to_url([project["id"] for project in page["properties"]["Project"]["relation"]])
            return {"name": task_name, "due_time": task_due_time_dt, "related_teams": task_related_team,
            "assignee": task_assignee, "status": task_status, "related_project": task_related_project}
        except Exception as e:
            print(f"Error parsing Notion task page: {e}")
            return None

    # Display name masks
    @app_commands.command(name="listnamemask",
                          description="List the current name mask for pinging correct users in daily reports.")
    async def listnamemask(self, interaction: discord.Interaction):
        response_string = "Current name masks:\n"
        if len(list(self.name_masks.items())) == 0:
            response_string += "No name masks set.\n"
        for name, mask in self.name_masks.items():
            response_string += f"- {name}: {mask}\n"
        try:
            paginator = commands.Paginator(prefix="", suffix="")
            for line in response_string.splitlines():
                paginator.add_line(line)
            for idx, chunk in enumerate(paginator.pages):
                if idx == 0:
                    await interaction.response.send_message(chunk)
                else:
                    await interaction.channel.send(chunk)
        except Exception as e:
            print(f"Error while sending response: {e}")
            await interaction.response.send_message("An error occurred while sending response.")

    # Add or update the name mask
    @app_commands.command(name="addnamemask",
                          description="Add or update a name mask for pinging correct users in daily reports.")
    @app_commands.describe(
        name="Raw name as fetched from Notion",
        masked_name="Masked name, for example @user_id. If masked to \"remove\", entry is removed."
    )
    async def addnamemask(self, interaction: discord.Interaction, name: str, masked_name: str):
        if masked_name.lower() == "remove":
            if name in self.name_masks:
                del self.name_masks[name]
                sync_object(self.name_masks, self.name_masks_filename)
                response_string = f"Name mask removed: {name}"
            else:
                response_string = f"Name mask not found: {name}"
            await interaction.response.send_message(response_string)
            return
        status = "updated" if name in self.name_masks else "added"
        self.name_masks[name] = masked_name
        sync_object(self.name_masks, self.name_masks_filename)
        response_string = f"Name mask {status}: {name} -> {masked_name}"
        await interaction.response.send_message(response_string)

    # Name mask for pinging users and teams
    def mask_name(self, name):
        if name in self.name_masks:
            return self.name_masks[name]
        else:
            return name

    # Fetch notion tasks summary string
    def fetch_notion_tasks_summary(self, response_object):
        # Fetch each notion task
        task_count = 0
        response_string_success = "Tasks due " + self.datetime_to_discord_long_date(self.current_time()) + ":\n"
        for page in response_object["results"]:
            # Get task properties
            page_parsed = self.parse_notion_task_page(page)
            if page_parsed is None:
                continue
            task_name = page_parsed["name"]
            task_date_object = page_parsed["due_time"]
            task_related_teams = page_parsed["related_teams"]
            task_assignee = page_parsed["assignee"]
            task_status = page_parsed["status"]
            task_related_project = page_parsed["related_project"]

            if task_date_object.date() != self.current_time().date():
                continue

            ping_string = " ".join([self.mask_name(name) for name in (task_assignee + task_related_teams)]) + "\n"

            response_string_success += "- " + task_name + " (" + task_status + ") " + task_related_project + " | " + ping_string
            task_count += 1
        return (task_count, response_string_success)

    # Current time command
    @app_commands.command(name="currenttime",
                          description="Name current time in discord format.")
    async def currenttime(self, interaction: discord.Interaction):
        response_string = "Current time: " + self.datetime_to_discord_short_datetime(self.current_time())
        await interaction.response.send_message(response_string)

    # Format time command
    @app_commands.command(name="formattime",
                          description="Name time in discord format.")
    @app_commands.describe(
        hours="Hour of the day (0–23)",
        minutes="Minute of the hour (0–59)"
    )
    async def formattime(self, interaction: discord.Interaction, hours: int, minutes: int):
        try:
            # Build datetime object using today's date and provided time
            now = self.current_time()
            dt = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

            # Format to Discord timestamp using your existing method
            formatted = self.datetime_to_discord_short_datetime(dt)

            await interaction.response.send_message(f"Formatted time: {formatted}")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid time provided: {e}", ephemeral=True)

    # Set daily schedule time command
    @app_commands.command(name="setdailytime",
                          description="Set daily scheduled reminders time.")
    @app_commands.describe(
        hours="Hour of the day (0–23)",
        minutes="Minute of the hour (0–59)"
    )
    async def setdailytime(self, interaction: discord.Interaction, hours: int, minutes: int):
        try:
            now = self.current_time()
            dt = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            formatted = self.datetime_to_discord_short_time(dt)
            self.daily_scheduled_time = {"hour": hours, "minute": minutes}
            sync_object(self.daily_scheduled_time, self.daily_scheduled_time_filename)
            self.last_run_date = None
            sync_object(self.last_run_date, self.last_run_date_filename)

            await interaction.response.send_message(f"New scheduled time: {formatted}")
        except ValueError as e:
            await interaction.response.send_message(f"Invalid time provided: {e}", ephemeral=True)

    # Setup the task fetch command
    @app_commands.command(name="listtasks",
                          description="List tasks with due dates set as today from Notion.")
    async def listtasks(self, interaction: discord.Interaction):
        # Usually takes some time, so defers interaction
        await interaction.response.defer()
        response_string = ""

        # Query notion tasks
        try:
            response_string += "Filtering by status as In progress or Not started.\n"
            response_object = await self.notion_client.databases.query(
                self.notion_tasks_database_id,
                filter=self.notion_tasks_filter)
            assert "results" in response_object, "No results found in the response object"
        except Exception as e:
            print(f"Query Notion Tasks Error: {e}")
            await interaction.followup.send("Failed to query Notion tasks, with .env database id and filters.")
            return

        task_count, response_string_success = self.fetch_notion_tasks_summary(response_object)
        # Follow up message
        if task_count == 0:
            response_string += "No tasks due today.\n"
        else:
            response_string += response_string_success

        try:
            paginator = commands.Paginator(prefix="", suffix="")
            for line in response_string.splitlines():
                paginator.add_line(line)
            for chunk in paginator.pages:
                await interaction.followup.send(chunk)
        except Exception as e:
            print(f"Error while sending response: {e}")
            await interaction.followup.send("An error occurred while sending response.")

    # Set daily schedule channel id
    @app_commands.command(name="setdailychannel",
                          description="Set daily post channel ID.")
    @app_commands.describe(channel_id="Channel ID to post daily reminders to. (all digits, no #)")
    async def setdailychannel(self, interaction: discord.Interaction, channel_id: str):
        self.report_channel_id = int(channel_id)
        sync_object(self.report_channel_id, self.report_channel_id_filename)
        await interaction.response.send_message(f"New channel ID: {self.report_channel_id}")

    # daily report task run every day at self.daily_scheduled_time
    @tasks.loop(minutes=1)
    async def daily_report(self):
        try:
            now = self.current_time()
            if (now.hour > self.daily_scheduled_time["hour"] or
               (now.hour == self.daily_scheduled_time["hour"] and now.minute >= self.daily_scheduled_time["minute"])):
                if self.last_run_date is None or self.last_run_date != now.date():
                    self.last_run_date = now.date()  # Prevent repeat runs that day
                    sync_object(self.last_run_date, self.last_run_date_filename)
                    try:
                        channel = self.bot.get_channel(self.report_channel_id)
                    except Exception as e:
                        print(f"Channel ID not found: {e}")
                        return

                    # Query notion tasks
                    try:
                        response_object = await self.notion_client.databases.query(
                            self.notion_tasks_database_id,
                            filter=self.notion_tasks_filter)
                        assert "results" in response_object, "No results found in the response object"
                    except Exception as e:
                        print(f"Query Notion Tasks Error: {e}")
                        return

                    task_count, response_string = self.fetch_notion_tasks_summary(response_object)
                    # Follow up message
                    if task_count == 0:
                        return

                    try:
                        paginator = commands.Paginator(prefix="", suffix="")
                        for line in response_string.splitlines():
                            paginator.add_line(line)
                        for chunk in paginator.pages:
                            await channel.send(chunk)
                    except Exception as e:
                        print(f"Error while sending response: {e}")
                        await channel.send("An error occurred while sending response.")
        except Exception as e:
            print(f"Error while executing daily report: {e}")

    # Make sure bot is ready before starting doing the daily report
    @daily_report.before_loop
    async def before_daily_report(self):
        await self.bot.wait_until_ready()

    # daily report task run every day at self.daily_scheduled_time
    # @tasks.loop(hours=1)
    # async def hourly_event_update(self):
    #     # TODO
    #     await self.eventsync()
    #     try:
    #         now = self.current_time()
    #         if (now.hour > self.daily_scheduled_time["hour"] or
    #            (now.hour == self.daily_scheduled_time["hour"] and now.minute >= self.daily_scheduled_time["minute"])):
    #             if self.last_run_date is None or self.last_run_date != now.date():
    #                 self.last_run_date = now.date()  # Prevent repeat runs that day
    #                 sync_object(self.last_run_date, self.last_run_date_filename)
    #                 try:
    #                     channel = self.bot.get_channel(self.report_channel_id)
    #                 except Exception as e:
    #                     print(f"Channel ID not found: {e}")
    #                     return

    #                 # Query notion tasks
    #                 try:
    #                     response_object = await self.notion_client.databases.query(
    #                         self.notion_tasks_database_id,
    #                         filter=self.notion_tasks_filter)
    #                     assert "results" in response_object, "No results found in the response object"
    #                 except Exception as e:
    #                     print(f"Query Notion Tasks Error: {e}")
    #                     return

    #                 task_count, response_string = self.fetch_notion_tasks_summary(response_object)
    #                 # Follow up message
    #                 if task_count == 0:
    #                     return

    #                 try:
    #                     paginator = commands.Paginator(prefix="", suffix="")
    #                     for line in response_string.splitlines():
    #                         paginator.add_line(line)
    #                     for chunk in paginator.pages:
    #                         await channel.send(chunk)
    #                 except Exception as e:
    #                     print(f"Error while sending response: {e}")
    #                     await channel.send("An error occurred while sending response.")
    #     except Exception as e:
    #         print(f"Error while executing daily report: {e}")

    # 	paginator = commands.Paginator(prefix="", suffix="")
    # 	for line in response_string.splitlines():
    # 		paginator.add_line(line)
    # 	for chunk in paginator.pages:
    # 		await channel.send(chunk)

    # Parse notion people page into {name: Str (display name), notion: Str (user id), discord: Str (tag)}
    # or None if failed
    def parse_notion_people_page(self, page):
        try:
            name = self.parse_rich_text(page["properties"]["Display Name"]["rich_text"])
            notion = page["properties"]["Notion Account"]["people"][0]["id"]
            discord = self.parse_rich_text(page["properties"]["Discord"]["rich_text"])
            # Field not filled, then treat it as fail
            if (len(name) == 0 or len(notion) == 0 or len(discord) == 0):
                return None
            return {"name": name,
                "notion": notion,
                "discord": discord,
            }
        except Exception as e:
            print(f"Error parsing Notion people page: {e}")
            return None

    # Parse people database command
    @app_commands.command(name="listpeople",
                          description="Fetch and parse the Committee Details Database.")
    async def listpeople(self, interaction: discord.Interaction):
        # Usually takes some time, so defers interaction
        await interaction.response.defer()
        response_string = "List people OK"

        # Query notion people database
        try:
            response_object = await self.notion_client.databases.query(
                self.notion_people_database_id)
            assert "results" in response_object, "No results found in the response object"
        except Exception as e:
            print(f"Notion fetching Error: {e}")
            await interaction.followup.send("Failed to query Notion Committee Database, with .env database id and filters.")
            return

        # Parse People Database
        for page in response_object["results"]:
            parsed_page = self.parse_notion_people_page(page)
            print(parsed_page)

        await interaction.followup.send(response_string)
