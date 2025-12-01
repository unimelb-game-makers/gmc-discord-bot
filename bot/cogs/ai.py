# Handle ai features

import os
from openai import OpenAI
import discord
from discord.ext import commands
from discord import app_commands
from bot.config import openrouter_api_key
import asyncio

class AiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ai_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_api_key,
        )

    def ask_gemma_3n_2b(self, question: str) -> str:
        try:
            completion = self.ai_client.chat.completions.create(
                model="google/gemma-3n-e2b-it:free",
                messages=[
                    {
                    "role": "user",
                    "content": question
                    }
                ]
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Error while asking Gemma 3n 2B: {e}")
            return "An error occurred while using the AI. PS. this feature is unfortunately easy to break."

    async def async_ask_gemma_3n_2b(self, question: str) -> str:
        return await asyncio.to_thread(self.ask_gemma_3n_2b, question)

    # Setup a testing ask command

    @app_commands.command(name='askai', description="Ask something to Gemma 3n 2B! Likely to break. No memories.")
    @app_commands.describe(user_question="Your question as a string for the AI. Optionally add quotes.")
    async def askai(self, interaction: discord.Interaction, user_question: str):
        # Usually takes some time, so defers interaction
        await interaction.response.defer()

        response_string = await self.async_ask_gemma_3n_2b(user_question)

        try:
            paginator = commands.Paginator(prefix="", suffix="")
            for line in response_string.splitlines():
                paginator.add_line(line)
            for chunk in paginator.pages:
                await interaction.followup.send(chunk)
        except Exception as e:
            print(f"Error while sending AI response: {e}")
            await interaction.followup.send("An error occurred while sending the AI response.")
