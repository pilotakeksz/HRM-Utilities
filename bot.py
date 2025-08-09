import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
import sys
import io
import base64  # <-- built-in module, no install needed

load_dotenv(".env")
# load_dotenv(".env.token")

APPLICATION_ID = int(os.getenv("APPLICATION_ID"))

encoded_token = os.getenv("DISCORD_BOT_TOKEN_BASE64")
if encoded_token is None:
    raise ValueError("No DISCORD_BOT_TOKEN_BASE64 found in environment variables")

# Decode the base64-encoded token
TOKEN = base64.b64decode(encoded_token).decode()

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

async def load_cog_with_error_handling(cog_name):
    try:
        await bot.load_extension(cog_name)
        print(f"✅ Loaded {cog_name}")
    except Exception as e:
        print(f"❌ Failed to load {cog_name}: {e}")
        import traceback
        traceback.print_exc()

async def main():
    async with bot:
        cogs = [
            "cogs.welcome",
            "cogs.verification", 
            "cogs.misc",
            "cogs.leveling",
            "cogs.economy",
            "cogs.say",
            "cogs.suggestion",
            "cogs.Rules",
            "cogs.about_us",
            "cogs.applications",
            "cogs.ticket_system",
            "cogs.divisons",
            "cogs.infract",
            "cogs.delete_archive",
            "cogs.callsign",
            "cogs.afk",
            "cogs.blacklist",
            "cogs.archive_commands",
            "cogs.MDT", #test
            "cogs.embed",
            "cogs.token_editor",
            "cogs.reviews"
        ]
        
        for cog in cogs:
            await load_cog_with_error_handling(cog)
        
        print("All cogs loaded. Starting bot...")
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
