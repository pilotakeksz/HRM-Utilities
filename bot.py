import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if TOKEN is None:
    raise ValueError("No DISCORD_BOT_TOKEN found in environment variables")


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="High Rock"))

async def main():
    async with bot:
        await bot.load_extension("cogs.welcome")
        await bot.load_extension("cogs.verification")
        await bot.load_extension("cogs.misc")  # <-- add this line
        await bot.load_extension("cogs.leveling")  # <-- Add this line
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
