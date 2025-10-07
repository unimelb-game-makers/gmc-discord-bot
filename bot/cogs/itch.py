# Handle itch.io features

import discord
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import re
from discord.ext import commands
from discord import app_commands
import asyncio
from bot.memory import save_jam_data, load_jam_data, clear_jam_data

class ItchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def scrape_itch_jam(self, url: str) -> dict:
        """Scrape itch.io jam page for timing information (using regex parsing)"""
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

            # Extract jam title using regex (since BeautifulSoup might fail)
            title_match = re.search(r'<h1[^>]*class="[^"]*jam_title[^"]*"[^>]*>(.*?)</h1>', html_content, re.DOTALL | re.IGNORECASE)
            if not title_match:
                title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.DOTALL)

            jam_title = title_match.group(1).strip() if title_match else "Unknown Jam"
            jam_title = re.sub(r'<[^>]+>', '', jam_title).strip()  # Remove HTML tags

            # Look for jam status and dates
            status = "unknown"
            submission_time_remaining = None
            submission_end_date = None
            jam_end_date = None

            # Look for submission countdown (data-end-time - usually submission deadline)
            countdown_match = re.search(r'<div[^>]*class="[^"]*countdown[^"]*"[^>]*data-end-time="([^"]+)"', html_content, re.IGNORECASE)
            if countdown_match:
                end_timestamp = countdown_match.group(1)
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

            # Look for submission end_date in JavaScript
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
            # Usually found in different patterns
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

            # If no separate jam end date found, use submission end date + some buffer
            if not jam_end_date and submission_end_date:
                # Assume jam ends sometime after submission deadline (common pattern)
                jam_end_date = submission_end_date

            # Check for text-based status indicators
            page_text_lower = html_content.lower()
            if "submission period is over" in page_text_lower or "submissions closed" in page_text_lower:
                status = "ended"
            elif "submissions open" in page_text_lower or "submit your game" in page_text_lower:
                if status == "unknown":
                    status = "running"
            elif "starting soon" in page_text_lower or "not yet started" in page_text_lower:
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

    @app_commands.command(name='jamtime', description="Get remaining time for an itch.io game jam")
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

    @app_commands.command(name='jambroadcast', description="Broadcast jam time to current channel")
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

    @app_commands.command(name='setjam', description="Set the jam URL for this server")
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
            f"💡 **Use `/remaining-time` to check submission deadline anytime!**"
        )

        await interaction.followup.send(confirmation_message)

        # Also send a broadcast message to the channel (more visible)
        broadcast_message = (
            f"📢 **Jam Tracking Updated**\n\n"
            f"🎯 Now tracking: **{jam_data['title']}**\n"
            f"📈 Current status: **{jam_data['status'].capitalize()}**\n"
            f"⚡ Use `/remaining-time` for submission updates!"
        )

        # Send broadcast message to the same channel
        try:
            await interaction.channel.send(broadcast_message)
        except Exception as e:
            print(f"Failed to send broadcast message: {e}")

    @app_commands.command(name='remaining-time', description="Get remaining submission time for the server's set jam")
    async def get_remaining_time(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id if interaction.guild else 0
        server_data = load_jam_data(guild_id)

        if not server_data or 'jam_url' not in server_data:
            await interaction.response.send_message(
                "❌ **No jam URL set for this server!**\n"
                "Use `/setjam <url>` to set a jam URL first."
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

    @app_commands.command(name='jam-end-date', description="Get the actual end date/time of the jam")
    async def jam_end_date(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id if interaction.guild else 0
        server_data = load_jam_data(guild_id)

        if not server_data or 'jam_url' not in server_data:
            await interaction.response.send_message(
                "❌ **No jam URL set for this server!**\n"
                "Use `/setjam <url>` to set a jam URL first."
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

    @app_commands.command(name='clear-jam', description="Clear the jam URL for this server")
    async def clear_jam_url(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id if interaction.guild else 0
        server_data = load_jam_data(guild_id)

        if not server_data or 'jam_url' not in server_data:
            await interaction.response.send_message("❌ **No jam URL set for this server.**")
            return

        jam_title = server_data.get('jam_title', 'Unknown Jam')
        clear_jam_data(guild_id)

        await interaction.response.send_message(f"✅ **Cleared jam URL for '{jam_title}'**")

    @app_commands.command(name='jam-info', description="Show current jam settings for this server")
    async def jam_info(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id if interaction.guild else 0
        server_data = load_jam_data(guild_id)

        if not server_data or 'jam_url' not in server_data:
            await interaction.response.send_message(
                "❌ **No jam URL set for this server!**\n"
                "Use `/setjam <url>` to set a jam URL first."
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
        message += f"Use `/remaining-time` to get current status!"

        await interaction.response.send_message(message)
