import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
import sys
import io

load_dotenv(".env")
load_dotenv(".env.token")
APPLICATION_ID = int(os.getenv("APPLICATION_ID"))
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if TOKEN is None:
    raise ValueError("No DISCORD_BOT_TOKEN found in environment variables")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    application_id=APPLICATION_ID
)

# --- Capture stdout/stderr ---
startup_output = io.StringIO()
old_stdout = sys.stdout
old_stderr = sys.stderr
sys.stdout = startup_output
sys.stderr = startup_output

@bot.event
async def on_ready():
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    output = startup_output.getvalue()
    print(output)
    try:
        user = await bot.fetch_user(840949634071658507)
        if user:
            # Discord DMs have a 2000 char limit per message
            for i in range(0, len(output), 1900):
                await user.send(f"Console output (part {i//1900+1}):\n```\n{output[i:i+1900]}\n```")
    except Exception as e:
        print(f"Failed to DM console output: {e}")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="High Rock"))
    if not getattr(bot, "_synced", False):
        await bot.tree.sync()
        bot._synced = True
        print("⏳ Slash commands synced!")

async def main():
    async with bot:
        await bot.load_extension("cogs.welcome")
        await bot.load_extension("cogs.verification")
        await bot.load_extension("cogs.misc")
        await bot.load_extension("cogs.leveling")
        await bot.load_extension("cogs.economy")
        await bot.load_extension("cogs.say")
        await bot.load_extension("cogs.suggestion")
        await bot.load_extension("cogs.Rules")
        await bot.load_extension("cogs.about_us")
        await bot.load_extension("cogs.applications")
        await bot.load_extension("cogs.ticket_system")
        await bot.load_extension("cogs.divisons")
        await bot.load_extension("cogs.infract")
        await bot.load_extension("cogs.delete_archive")
        await bot.load_extension("cogs.callsign")
        await bot.load_extension("cogs.afk")
        await bot.load_extension("cogs.blacklist")
        await bot.load_extension("cogs.archive_commands")
        await bot.load_extension("cogs.MDT")
        await bot.load_extension("cogs.embed")
        await bot.load_extension("cogs.Admin_Exec")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())