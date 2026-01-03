# Handle itch.io features

import discord
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import re
from discord.ext import commands
from discord import app_commands
import asyncio
from bot.utils.memory import save_jam_data, load_jam_data, clear_jam_data, save, load
from openai import OpenAI
from bot.config import openrouter_api_key

class ItchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ai_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_api_key,
        )

    # Create a command group for jam-related commands
    jam = app_commands.Group(name='jam', description='Game jam tracking commands')

    def scrape_itch_jam(self, url: str) -> dict:
        """Scrape itch.io jam page for timing information (using BeautifulSoup)"""
        try:
            # Clean URL - remove /preview if present
            url = url.replace('/preview', '')

            # Make request with proper headers to avoid blocking
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract jam title using BeautifulSoup
            jam_title = "Unknown Jam"
            title_elem = soup.find('h1', class_=re.compile(r'jam_title'))
            if not title_elem:
                title_elem = soup.find('h1')
            if title_elem:
                jam_title = title_elem.get_text(strip=True)

            # Look for jam status and dates
            status = "unknown"
            submission_time_remaining = None
            submission_end_date = None
            jam_end_date = None

            # Look for submission countdown (data-end-time - usually submission deadline)
            countdown_elem = soup.find('div', class_=re.compile(r'countdown'))
            if countdown_elem and countdown_elem.get('data-end-time'):
                end_timestamp = countdown_elem.get('data-end-time')
                try:
                    submission_end_datetime = datetime.fromtimestamp(int(end_timestamp), tz=timezone.utc)
                    submission_end_date = submission_end_datetime
                    now = datetime.now(timezone.utc)
                    time_left = submission_end_datetime - now

                    if time_left.total_seconds() > 0:
                        status = "running"
                        hours = int(time_left.total_seconds() // 3600)
                        minutes = int((time_left.total_seconds() % 3600) // 60)
                        submission_time_remaining = f"{hours}h {minutes}m"
                    else:
                        status = "ended"
                except Exception as e:
                    print(f"Error parsing submission timestamp: {e}")

            # Look for submission end_date in JavaScript/inline scripts
            if not submission_end_date:
                js_end_date_match = re.search(r'end_date["\']?\s*:\s*["\']([^"\']+)["\']', html_content, re.IGNORECASE)
                if js_end_date_match:
                    end_date_str = js_end_date_match.group(1)
                    try:
                        # Parse different date formats
                        if 'T' in end_date_str:
                            # ISO format
                            submission_end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                        else:
                            # Try parsing "YYYY-MM-DD HH:MM:SS" format
                            try:
                                submission_end_date = datetime.strptime(end_date_str, '%Y-%m-%d %H:%M:%S')
                                submission_end_date = submission_end_date.replace(tzinfo=timezone.utc)
                            except:
                                # Try other common formats
                                submission_end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                                submission_end_date = submission_end_date.replace(tzinfo=timezone.utc)

                        now = datetime.now(timezone.utc)
                        time_left = submission_end_date - now

                        if time_left.total_seconds() > 0:
                            status = "running"
                            hours = int(time_left.total_seconds() // 3600)
                            minutes = int((time_left.total_seconds() % 3600) // 60)
                            submission_time_remaining = f"{hours}h {minutes}m"
                        else:
                            status = "ended"
                    except Exception as e:
                        print(f"Error parsing submission date from JS: {e}")

            # Look for jam end date (different from submission deadline)
            # Usually found in JavaScript data
            jam_end_match = re.search(r'jam_end["\']?\s*:\s*["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if not jam_end_match:
                # Try other patterns for jam end
                jam_end_match = re.search(r'rating.*end["\']?\s*:\s*["\']([^"\']+)["\']', html_content, re.IGNORECASE)

            if jam_end_match:
                jam_end_str = jam_end_match.group(1)
                try:
                    if 'T' in jam_end_str:
                        jam_end_date = datetime.fromisoformat(jam_end_str.replace('Z', '+00:00'))
                    else:
                        try:
                            jam_end_date = datetime.strptime(jam_end_str, '%Y-%m-%d %H:%M:%S')
                            jam_end_date = jam_end_date.replace(tzinfo=timezone.utc)
                        except:
                            jam_end_date = datetime.strptime(jam_end_str, '%Y-%m-%d')
                            jam_end_date = jam_end_date.replace(tzinfo=timezone.utc)
                except Exception as e:
                    print(f"Error parsing jam end date: {e}")

            # If no separate jam end date found, use submission end date
            if not jam_end_date and submission_end_date:
                jam_end_date = submission_end_date

            # Check for text-based status indicators using BeautifulSoup
            page_text = soup.get_text().lower()
            if "submission period is over" in page_text or "submissions closed" in page_text:
                status = "ended"
            elif "submissions open" in page_text or "submit your game" in page_text:
                if status == "unknown":
                    status = "running"
            elif "starting soon" in page_text or "not yet started" in page_text:
                status = "upcoming"

            return {
                'success': True,
                'title': jam_title,
                'status': status,
                'submission_time_remaining': submission_time_remaining,
                'submission_end_date': str(submission_end_date) if submission_end_date else None,
                'jam_end_date': str(jam_end_date) if jam_end_date else None,
                'url': url
            }

        except requests.RequestException as e:
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Scraping error: {str(e)}"
            }

    async def async_scrape_itch_jam(self, url: str) -> dict:
        """Async wrapper for scraping function"""
        return await asyncio.to_thread(self.scrape_itch_jam, url)

    def format_jam_status(self, jam_data: dict) -> str:
        """Format jam data for Discord display"""
        if not jam_data['success']:
            return f"❌ **Error:** {jam_data['error']}"

        title = jam_data['title']
        status = jam_data['status']
        time_remaining = jam_data.get('submission_time_remaining')
        url = jam_data['url']

        # Status emojis
        status_emoji = {
            'running': '🟢',
            'ended': '🔴',
            'upcoming': '🟡',
            'unknown': '⚪'
        }

        emoji = status_emoji.get(status, '⚪')
        status_text = status.capitalize()

        message = f"{emoji} **{title}**\n"
        message += f"**Status:** {status_text}\n"

        if time_remaining:
            message += f"**Time Remaining:** {time_remaining}\n"
        elif status == 'ended':
            message += f"**Time Remaining:** Jam has ended\n"

        message += f"**URL:** {url}"

        return message

    # Theme Collection Helper Methods
    def _get_theme_collection_key(self, guild_id: int) -> str:
        """Get the memory key for theme collection data"""
        return f"theme_collection_{guild_id}.pkl"

    def _save_theme_collection_data(self, guild_id: int, data: dict):
        """Save theme collection data for a guild"""
        filename = self._get_theme_collection_key(guild_id)
        collection_data = {
            "data": data,
            "updated_at": datetime.now().isoformat(),
            "timestamp": datetime.now()
        }
        save(collection_data, filename)

    def _load_theme_collection_data(self, guild_id: int) -> dict:
        """Load theme collection data for a guild"""
        filename = self._get_theme_collection_key(guild_id)
        collection_data = load(filename)

        if collection_data is None:
            return {}

        try:
            if "data" in collection_data:
                return collection_data["data"]
            else:
                return collection_data
        except Exception as e:
            print(f"Error loading theme collection data: {e}")
            return {}

    async def _has_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """Check if user has administrator permissions"""
        if not interaction.guild:
            return False

        member = interaction.guild.get_member(interaction.user.id)
        if not member:
            return False

        return member.guild_permissions.administrator

    async def _refine_theme_with_ai(self, raw_theme: str) -> str:
        """Use AI to refine a raw theme suggestion into a proper game jam theme"""
        try:
            prompt = f"""Convert this user suggestion into a proper game jam theme. Make it:
- 1-4 words maximum
- Clear and specific
- Suitable for game development
- Creative but not overly complex

User suggestion: "{raw_theme}"

Reply with only the refined theme, no explanation."""

            completion = self.ai_client.chat.completions.create(
                model="google/gemma-3n-e2b-it:free",
                messages=[{"role": "user", "content": prompt}]
            )

            refined = completion.choices[0].message.content.strip()
            # Clean up the response (remove quotes, extra text)
            refined = re.sub(r'^["\']*|["\']*$', '', refined)
            refined = re.sub(r'\n.*', '', refined)  # Take only first line

            return refined if len(refined) <= 50 else raw_theme[:50]
        except Exception as e:
            print(f"Error refining theme with AI: {e}")
            return raw_theme[:50]  # Fallback to truncated original

    async def _extract_themes_from_thread(self, thread: discord.Thread) -> list:
        """Extract and rank themes from thread messages based on 👎 reactions"""
        themes = []

        try:
            # Get all messages from the thread
            async for message in thread.history(limit=None, oldest_first=True):
                # Skip bot messages and the initial pinned message
                if message.author.bot:
                    continue

                # Skip very short messages (likely not themes)
                if len(message.content.strip()) < 2:
                    continue

                # Count 👍 reactions
                thumbs_up_count = 0
                for reaction in message.reactions:
                    if str(reaction.emoji) == "👍":
                        thumbs_up_count = reaction.count
                        break

                # Clean the message content
                theme_content = re.sub(r'\s+', ' ', message.content.strip())

                # Refine theme with AI
                refined_theme = await self._refine_theme_with_ai(theme_content)

                themes.append({
                    'original': theme_content,
                    'refined': refined_theme,
                    'reactions': thumbs_up_count,
                    'author': str(message.author),
                    'message_id': message.id,
                    'created_at': message.created_at.isoformat()
                })

            # Sort by reaction count (descending), then by creation time (ascending)
            themes.sort(key=lambda x: (-x['reactions'], x['created_at']))

        except Exception as e:
            print(f"Error extracting themes from thread: {e}")

        return themes

    @jam.command(name='time', description="Get remaining time for an itch.io game jam")
    @app_commands.describe(jam_url="The itch.io jam URL (e.g., https://itch.io/jam/yourjam)")
    async def jamtime(self, interaction: discord.Interaction, jam_url: str):
        # Validate URL
        if not jam_url.startswith('https://itch.io/jam/'):
            await interaction.response.send_message("❌ Please provide a valid itch.io jam URL (must start with https://itch.io/jam/)")
            return

        # Usually takes some time, so defer interaction
        await interaction.response.defer()

        jam_data = await self.async_scrape_itch_jam(jam_url)
        message = self.format_jam_status(jam_data)

        await interaction.followup.send(message)

    @jam.command(name='broadcast', description="Broadcast jam time to current channel")
    @app_commands.describe(jam_url="The itch.io jam URL to broadcast")
    async def jambroadcast(self, interaction: discord.Interaction, jam_url: str):
        # Validate URL
        if not jam_url.startswith('https://itch.io/jam/'):
            await interaction.response.send_message("❌ Please provide a valid itch.io jam URL (must start with https://itch.io/jam/)")
            return

        await interaction.response.defer()

        jam_data = await self.async_scrape_itch_jam(jam_url)
        message = self.format_jam_status(jam_data)

        # Send to current channel instead of followup (makes it more like a broadcast)
        await interaction.followup.send(f"📢 **Game Jam Update:**\n\n{message}")

    @jam.command(name='set', description="Set the jam URL for this server")
    @app_commands.describe(jam_url="The itch.io jam URL to track for this server")
    async def set_jam_url(self, interaction: discord.Interaction, jam_url: str):
        # Validate URL
        if not jam_url.startswith('https://itch.io/jam/'):
            await interaction.response.send_message("❌ Please provide a valid itch.io jam URL (must start with https://itch.io/jam/)")
            return

        # Clean URL - remove /preview if present
        clean_url = jam_url.replace('/preview', '')

        await interaction.response.defer()

        # Test the URL by scraping it
        jam_data = await self.async_scrape_itch_jam(clean_url)

        if not jam_data['success']:
            await interaction.followup.send(f"❌ **Failed to set jam URL:** {jam_data['error']}")
            return

        # Save the URL and jam data for this server
        guild_id = interaction.guild_id if interaction.guild else 0
        server_data = {
            'jam_url': clean_url,
            'jam_title': jam_data['title'],
            'last_status': jam_data['status'],
            'set_by': str(interaction.user),
            'set_at': datetime.now().isoformat()
        }

        save_jam_data(guild_id, server_data)

        # Send confirmation message
        confirmation_message = (
            f"✅ **Jam URL Updated Successfully!**\n\n"
            f"🎮 **Jam:** {jam_data['title']}\n"
            f"📊 **Status:** {jam_data['status'].capitalize()}\n"
            f"🔗 **URL:** {clean_url}\n"
            f"👤 **Set by:** {interaction.user.mention}\n"
            f"⏰ **Set at:** <t:{int(datetime.now().timestamp())}:f>\n\n"
            f"💡 **Use `/jam remaining` to check submission deadline anytime!**"
        )

        await interaction.followup.send(confirmation_message)

        # Also send a broadcast message to the channel (more visible)
        broadcast_message = (
            f"📢 **Jam Tracking Updated**\n\n"
            f"🎯 Now tracking: **{jam_data['title']}**\n"
            f"📈 Current status: **{jam_data['status'].capitalize()}**\n"
            f"⚡ Use `/jam remaining` for submission updates!"
        )

        # Send broadcast message to the same channel
        try:
            await interaction.channel.send(broadcast_message)
        except Exception as e:
            print(f"Failed to send broadcast message: {e}")

    @jam.command(name='remaining', description="Get remaining submission time for the server's set jam")
    async def get_remaining_time(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id if interaction.guild else 0
        server_data = load_jam_data(guild_id)

        if not server_data or 'jam_url' not in server_data:
            await interaction.response.send_message(
                "❌ **No jam URL set for this server!**\n"
                "Use `/jam set <url>` to set a jam URL first."
            )
            return

        await interaction.response.defer()

        jam_url = server_data['jam_url']
        jam_data = await self.async_scrape_itch_jam(jam_url)

        if not jam_data['success']:
            await interaction.followup.send(f"❌ **Error fetching jam data:** {jam_data['error']}")
            return

        # Update stored data with latest info
        server_data['last_status'] = jam_data['status']
        server_data['last_checked'] = datetime.now().isoformat()
        save_jam_data(guild_id, server_data)

        # Format message for Discord (submission time remaining)
        title = jam_data['title']
        status = jam_data['status']
        submission_time_remaining = jam_data.get('submission_time_remaining')
        url = jam_data['url']

        # Status emojis
        status_emoji = {
            'running': '🟢',
            'ended': '🔴',
            'upcoming': '🟡',
            'unknown': '⚪'
        }

        emoji = status_emoji.get(status, '⚪')
        status_text = status.capitalize()

        message = f"{emoji} **{title}**\n"
        message += f"**Status:** {status_text}\n"

        if submission_time_remaining:
            message += f"**⏰ Submission Time Remaining:** {submission_time_remaining}\n"
        elif status == 'ended':
            message += f"**⏰ Submission Time Remaining:** Submissions closed\n"
        else:
            message += f"**⏰ Submission Time Remaining:** Not available\n"

        message += f"**URL:** {url}\n"
        message += f"*Last updated: <t:{int(datetime.now().timestamp())}:R>*"

        await interaction.followup.send(message)

    @jam.command(name='enddate', description="Get the actual end date/time of the jam")
    async def jam_end_date(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id if interaction.guild else 0
        server_data = load_jam_data(guild_id)

        if not server_data or 'jam_url' not in server_data:
            await interaction.response.send_message(
                "❌ **No jam URL set for this server!**\n"
                "Use `/jam set <url>` to set a jam URL first."
            )
            return

        await interaction.response.defer()

        jam_url = server_data['jam_url']
        jam_data = await self.async_scrape_itch_jam(jam_url)

        if not jam_data['success']:
            await interaction.followup.send(f"❌ **Error fetching jam data:** {jam_data['error']}")
            return

        # Update stored data with latest info
        server_data['last_status'] = jam_data['status']
        server_data['last_checked'] = datetime.now().isoformat()
        save_jam_data(guild_id, server_data)

        # Format message for jam end date
        title = jam_data['title']
        jam_end_date = jam_data.get('jam_end_date')
        submission_end_date = jam_data.get('submission_end_date')
        url = jam_data['url']

        message = f"📅 **{title} - Jam Schedule**\n\n"

        if submission_end_date:
            try:
                # Parse the date string back to datetime for Discord formatting
                if 'T' in submission_end_date or ' ' in submission_end_date:
                    sub_dt = datetime.fromisoformat(submission_end_date.replace('Z', '+00:00'))
                    sub_timestamp = int(sub_dt.timestamp())
                    message += f"📝 **Submission Deadline:** <t:{sub_timestamp}:F>\n"
                    message += f"⏰ **Submission Deadline (Relative):** <t:{sub_timestamp}:R>\n\n"
            except:
                message += f"📝 **Submission Deadline:** {submission_end_date}\n\n"

        if jam_end_date and jam_end_date != submission_end_date:
            try:
                # Parse the jam end date
                if 'T' in jam_end_date or ' ' in jam_end_date:
                    jam_dt = datetime.fromisoformat(jam_end_date.replace('Z', '+00:00'))
                    jam_timestamp = int(jam_dt.timestamp())
                    message += f"🏁 **Jam Actually Ends:** <t:{jam_timestamp}:F>\n"
                    message += f"🕒 **Jam End (Relative):** <t:{jam_timestamp}:R>\n\n"
            except:
                message += f"🏁 **Jam Actually Ends:** {jam_end_date}\n\n"
        elif not jam_end_date:
            message += f"🏁 **Jam End Date:** Same as submission deadline\n\n"

        message += f"🔗 **URL:** {url}\n"
        message += f"*Last updated: <t:{int(datetime.now().timestamp())}:R>*"

        await interaction.followup.send(message)

    @jam.command(name='clear', description="Clear the jam URL for this server")
    async def clear_jam_url(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id if interaction.guild else 0
        server_data = load_jam_data(guild_id)

        if not server_data or 'jam_url' not in server_data:
            await interaction.response.send_message("❌ **No jam URL set for this server.**")
            return

        jam_title = server_data.get('jam_title', 'Unknown Jam')
        clear_jam_data(guild_id)

        await interaction.response.send_message(f"✅ **Cleared jam URL for '{jam_title}'**")

    @jam.command(name='info', description="Show current jam settings for this server")
    async def jam_info(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id if interaction.guild else 0
        server_data = load_jam_data(guild_id)

        if not server_data or 'jam_url' not in server_data:
            await interaction.response.send_message(
                "❌ **No jam URL set for this server!**\n"
                "Use `/jam set <url>` to set a jam URL first."
            )
            return

        jam_url = server_data.get('jam_url', 'Unknown')
        jam_title = server_data.get('jam_title', 'Unknown Jam')
        last_status = server_data.get('last_status', 'unknown')
        set_by = server_data.get('set_by', 'Unknown')
        set_at = server_data.get('set_at', 'Unknown')
        last_checked = server_data.get('last_checked', 'Never')

        # Parse timestamps for Discord formatting
        try:
            set_timestamp = int(datetime.fromisoformat(set_at.replace('Z', '+00:00')).timestamp())
            set_at_formatted = f"<t:{set_timestamp}:R>"
        except:
            set_at_formatted = "Unknown"

        try:
            checked_timestamp = int(datetime.fromisoformat(last_checked.replace('Z', '+00:00')).timestamp())
            last_checked_formatted = f"<t:{checked_timestamp}:R>"
        except:
            last_checked_formatted = "Never"

        message = f"📋 **Server Jam Settings**\n\n"
        message += f"**Jam:** {jam_title}\n"
        message += f"**Status:** {last_status.capitalize()}\n"
        message += f"**URL:** {jam_url}\n"
        message += f"**Set by:** {set_by}\n"
        message += f"**Set:** {set_at_formatted}\n"
        message += f"**Last checked:** {last_checked_formatted}\n\n"
        message += f"Use `/jam remaining` to get current status!"

        await interaction.response.send_message(message)

    @jam.command(name='themes', description="Start theme collection in a thread")
    @app_commands.describe(
        thread_name="Name for the theme collection thread",
        collection_message="Optional custom message for theme collection"
    )
    async def start_theme_collection(
        self,
        interaction: discord.Interaction,
        thread_name: str = "🎯 Jam Theme Collection",
        collection_message: str = None
    ):
        # Check admin permissions
        if not await self._has_admin_permissions(interaction):
            await interaction.response.send_message(
                "❌ **Permission Denied:** Only administrators can start theme collection.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild_id
        existing_data = self._load_theme_collection_data(guild_id)

        # Check if collection is already active
        if existing_data.get('active', False):
            await interaction.response.send_message(
                "❌ **Theme collection is already active!**\n"
                f"Active thread: <#{existing_data.get('thread_id')}>\n"
                "Use `/jam poll` to end it and create a poll.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # Create thread in current channel
            thread = await interaction.channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread,
                reason="Theme collection for game jam"
            )

            # Default collection message
            if not collection_message:
                collection_message = (
                    "🎯 **Game Jam Theme Collection Started!**\n\n"
                    "📝 **How to participate:**\n"
                    "• Post your theme suggestions in this thread\n"
                    "• One theme per message works best\n"
                    "• React with 👍 to themes you like\n"
                    "• AI will help clean up theme suggestions\n\n"
                    "⏰ **Collection will end when an admin runs `/jam poll`**\n"
                    "🗳️ **Top 10 most-liked themes will be put in a poll**"
                )

            # Send initial message to thread
            initial_msg = await thread.send(collection_message)
            await initial_msg.pin()

            # Save collection data
            collection_data = {
                'active': True,
                'thread_id': thread.id,
                'channel_id': interaction.channel_id,
                'started_by': str(interaction.user),
                'started_at': datetime.now().isoformat(),
                'initial_message_id': initial_msg.id,
                'thread_name': thread_name
            }

            self._save_theme_collection_data(guild_id, collection_data)

            # Confirmation message
            await interaction.followup.send(
                f"✅ **Theme collection started successfully!**\n\n"
                f"🧵 **Thread:** {thread.mention}\n"
                f"👤 **Started by:** {interaction.user.mention}\n"
                f"📅 **Started:** <t:{int(datetime.now().timestamp())}:f>\n\n"
                f"💡 **Use `/jam poll <channel>` when ready to create poll from top themes!**"
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ **Failed to create theme collection thread:** {str(e)}",
                ephemeral=True
            )
            print(f"Error creating theme collection thread: {e}")

    @jam.command(name='poll', description="End theme collection and create poll from top themes")
    @app_commands.describe(
        poll_channel="Channel to create the poll in (optional, defaults to current)"
    )
    async def create_theme_poll(
        self,
        interaction: discord.Interaction,
        poll_channel: discord.TextChannel = None
    ):
        # Check admin permissions
        if not await self._has_admin_permissions(interaction):
            await interaction.response.send_message(
                "❌ **Permission Denied:** Only administrators can create theme polls.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild_id
        collection_data = self._load_theme_collection_data(guild_id)

        if not collection_data.get('active', False):
            await interaction.response.send_message(
                "❌ **No active theme collection found.**\n"
                "Use `/jam themes` to start collecting themes first.",
                ephemeral=True
            )
            return

        # Default to current channel if not specified
        if not poll_channel:
            poll_channel = interaction.channel

        await interaction.response.defer()

        try:
            # Get the thread
            thread_id = collection_data.get('thread_id')
            thread = interaction.guild.get_thread(thread_id)

            if not thread:
                await interaction.followup.send(
                    "❌ **Could not find the theme collection thread.**\n"
                    "It may have been deleted.",
                    ephemeral=True
                )
                return

            # Extract themes from thread
            await interaction.followup.send("🔄 **Processing themes with AI...**")
            themes = await self._extract_themes_from_thread(thread)

            if not themes:
                await interaction.followup.send(
                    "❌ **No themes found in the collection thread.**\n"
                    "Make sure people posted theme suggestions and reacted with 👍."
                )
                return

            # Take top 10 themes
            top_themes = themes[:10]

            # Create Discord poll (max 10 options)
            poll_question = f"🎯 Vote for your favorite game jam theme!"

            # Create poll using Discord's native poll feature
            poll_options = []
            for theme in top_themes:
                # Use refined theme, fallback to original if needed
                theme_text = theme['refined'] if theme['refined'] else theme['original']
                poll_options.append(theme_text[:55])  # Discord poll option limit

            # Create the poll message
            poll_embed = discord.Embed(
                title="🗳️ Game Jam Theme Poll",
                description=f"Vote for your favorite theme! Poll created from {len(themes)} suggestions.",
                color=0x00ff00
            )

            poll_embed.add_field(
                name="Options",
                value="\n".join([f"{i+1}. {option}" for i, option in enumerate(poll_options)]),
                inline=False
            )

            poll_embed.set_footer(text=f"Poll created from thread: {thread.name}")

            # Send poll to specified channel
            poll_message = await poll_channel.send(embed=poll_embed)

            # Add number reactions for voting (1️⃣, 2️⃣, etc.)
            number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            for i in range(min(len(poll_options), 10)):
                await poll_message.add_reaction(number_emojis[i])

            # Update collection data with results
            collection_data.update({
                'active': False,
                'ended_by': str(interaction.user),
                'ended_at': datetime.now().isoformat(),
                'themes_extracted': len(themes),
                'top_themes': top_themes,
                'poll_channel_id': poll_channel.id,
                'poll_message_id': poll_message.id
            })

            self._save_theme_collection_data(guild_id, collection_data)

            # Confirmation message
            await interaction.followup.send(
                f"✅ **Theme poll created successfully!**\n\n"
                f"📊 **Processed {len(themes)} themes** (AI-refined)\n"
                f"🗳️ **Poll:** {poll_message.jump_url}\n"
                f"📍 **Channel:** {poll_channel.mention}\n"
                f"🎯 **Top theme:** {top_themes[0]['refined']} ({top_themes[0]['reactions']} 👍)\n\n"
                f"*Theme collection thread archived.*"
            )

            # Archive the theme collection thread
            try:
                await thread.edit(archived=True, reason="Theme collection ended, poll created")
            except:
                pass  # Thread might already be closed

        except Exception as e:
            await interaction.followup.send(
                f"❌ **Error creating theme poll:** {str(e)}",
                ephemeral=True
            )
            print(f"Error creating theme poll: {e}")

    @jam.command(name='theme-status', description="Check theme collection status")
    async def theme_collection_status(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        collection_data = self._load_theme_collection_data(guild_id)

        if not collection_data:
            await interaction.response.send_message(
                "📭 **No theme collection data found.**\n"
                "Use `/jam themes` to start collecting themes!",
                ephemeral=True
            )
            return

        is_active = collection_data.get('active', False)

        if is_active:
            # Active collection status
            thread_id = collection_data.get('thread_id')
            started_by = collection_data.get('started_by', 'Unknown')
            started_at = collection_data.get('started_at')

            try:
                started_timestamp = int(datetime.fromisoformat(started_at.replace('Z', '+00:00')).timestamp())
                started_formatted = f"<t:{started_timestamp}:R>"
            except:
                started_formatted = "Unknown"

            message = f"🟢 **Theme Collection Active**\n\n"
            message += f"🧵 **Thread:** <#{thread_id}>\n"
            message += f"👤 **Started by:** {started_by}\n"
            message += f"📅 **Started:** {started_formatted}\n\n"
            message += f"💡 **Use `/jam poll [channel]` to create poll from themes!**"

        else:
            # Last collection results
            ended_by = collection_data.get('ended_by', 'Unknown')
            ended_at = collection_data.get('ended_at')
            themes_count = collection_data.get('themes_extracted', 0)
            top_themes = collection_data.get('top_themes', [])
            poll_message_id = collection_data.get('poll_message_id')
            poll_channel_id = collection_data.get('poll_channel_id')

            try:
                ended_timestamp = int(datetime.fromisoformat(ended_at.replace('Z', '+00:00')).timestamp())
                ended_formatted = f"<t:{ended_timestamp}:R>"
            except:
                ended_formatted = "Unknown"

            message = f"🔴 **Last Theme Collection (Ended)**\n\n"
            message += f"📊 **Themes processed:** {themes_count}\n"
            message += f"👤 **Ended by:** {ended_by}\n"
            message += f"📅 **Ended:** {ended_formatted}\n"

            if poll_message_id and poll_channel_id:
                message += f"🗳️ **Poll:** https://discord.com/channels/{interaction.guild_id}/{poll_channel_id}/{poll_message_id}\n"

            if top_themes:
                message += f"\n🏆 **Top 3 refined themes:**\n"
                for i, theme in enumerate(top_themes[:3], 1):
                    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                    message += f"{emoji} {theme['refined']} ({theme['reactions']} 👍)\n"

            message += f"\n💡 **Use `/jam themes` to start a new collection!**"

        await interaction.response.send_message(message, ephemeral=True)
