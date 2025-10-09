import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
import sys
import io
import base64 
import traceback
from aiohttp import web
from version_manager import get_version
import json
from datetime import datetime, timezone, date


load_dotenv(".env")
load_dotenv(".env.token")


APPLICATION_ID = os.getenv("APPLICATION_ID")
if not APPLICATION_ID:
    print("❌ ERROR: APPLICATION_ID not set in environment variables")
else:
    try:
        APPLICATION_ID = int(APPLICATION_ID)
    except ValueError:
        raise ValueError("APPLICATION_ID must be an integer")

# Load the base64-encoded Discord bot token and decode it
encoded_token = os.getenv("DISCORD_BOT_TOKEN_BASE64")
if not encoded_token:
    raise ValueError("No DISCORD_BOT_TOKEN_BASE64 found in environment variables")

try:
    TOKEN = base64.b64decode(encoded_token).decode("utf-8")
except Exception as e:
    raise ValueError(f"Failed to decode DISCORD_BOT_TOKEN_BASE64: {e}")

# --- Discord Bot Setup ---
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
    # Restore stdout/stderr
    sys.stdout = old_stdout
    sys.stderr = old_stderr
    
    output = startup_output.getvalue()
    print(output)
    
    # Get and increment version
    version_num, version_string, version_info = get_version()
    print(f"Bot version: {version_string}")
    
    # Print additional info
    if version_info.get("commit_message"):
        print(f"Commit message: {version_info['commit_message']}")
    if version_info.get("updated_cogs"):
        print(f"Updated cogs: {', '.join(version_info['updated_cogs'])}")
    
    # DM yourself logs on startup
    try:
        user = await bot.fetch_user(840949634071658507)  # Your user ID here
        if user:
            for i in range(0, len(output), 1900):
                await user.send(f"Console output (part {i//1900+1}):\n```\n{output[i:i+1900]}\n```")
    except Exception as e:
        print(f"Failed to DM console output: {e}")
    
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="High Rock"))
    
    # Send version to specified channel
    try:
        version_channel_id = 1329910508182179900
        secondary_channel_id = 1329910465333170216
        # Build embed once
        embed = discord.Embed(
            title="Bot Restart",
            description=f"Bot has restarted with version **{version_string}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Version Number", value=str(version_num), inline=True)
        if version_info.get("commit_message"):
            commit_msg = version_info['commit_message'][:100] + "..." if len(version_info['commit_message']) > 100 else version_info['commit_message']
            embed.add_field(name="Commit Message", value=commit_msg, inline=False)
        if version_info.get("updated_cogs"):
            cogs_list = ", ".join(version_info['updated_cogs'])
            if len(cogs_list) > 100:
                cogs_list = cogs_list[:100] + "..."
            embed.add_field(name="Updated Cogs", value=cogs_list, inline=False)
        else:
            embed.add_field(name="Updated Cogs", value="No cogs updated", inline=False)
        embed.set_footer(text="Developed with love by Tuna 🐟")

        # Decide where to send: only send to the main version channel if we are actually able to ping the role (rate OK).
        role_id_to_ping = 1371198982935806033
        ping_data_path = os.path.join("data", "version_ping.json")
        os.makedirs("data", exist_ok=True)
        ping_data = {"last_ping_ts": 0, "daily_count": 0, "day": ""}
        try:
            if os.path.exists(ping_data_path):
                with open(ping_data_path, "r", encoding="utf-8") as f:
                    ping_data = json.load(f)
        except Exception as e:
            print(f"Failed to read ping data file: {e}")

        today_str = date.today().isoformat()
        if ping_data.get("day") != today_str:
            ping_data["day"] = today_str
            ping_data["daily_count"] = 0

        now_ts = int(datetime.now(timezone.utc).timestamp())
        can_ping = (now_ts - int(ping_data.get("last_ping_ts", 0)) >= 3600) and (int(ping_data.get("daily_count", 0)) < 5)

        # Fetch channels
        version_channel = bot.get_channel(version_channel_id)
        secondary_channel = bot.get_channel(secondary_channel_id)

        if can_ping and version_channel:
            # Send to main version channel with role ping and update ping counters
            try:
                content = f"<@&{role_id_to_ping}>"
                allowed = discord.AllowedMentions(everyone=False, users=False, roles=True)
                await version_channel.send(content=content, embed=embed, allowed_mentions=allowed)
                print(f"Version {version_string} sent with role ping to channel {version_channel_id}")
                ping_data["last_ping_ts"] = now_ts
                ping_data["daily_count"] = int(ping_data.get("daily_count", 0)) + 1
                with open(ping_data_path, "w", encoding="utf-8") as f:
                    json.dump(ping_data, f, indent=2)
            except Exception as e:
                print(f"Failed to send pinged version message to {version_channel_id}: {e}")
                # fallback: send without ping to secondary channel if available
                if secondary_channel:
                    try:
                        await secondary_channel.send(embed=embed)
                        print(f"Version {version_string} sent to secondary channel {secondary_channel_id} after main send failed")
                    except Exception as e2:
                        print(f"Failed to send to secondary channel as fallback: {e2}")
        else:
            # Do NOT send to main version channel when we can't ping; send to secondary channel without ping
            if secondary_channel:
                try:
                    await secondary_channel.send(embed=embed)
                    print(f"Version {version_string} sent to secondary channel {secondary_channel_id} without ping")
                except Exception as e:
                    print(f"Failed to send version to secondary channel {secondary_channel_id}: {e}")
            else:
                # As a last resort, try sending to main version channel without ping
                if version_channel:
                    try:
                        await version_channel.send(embed=embed)
                        print(f"Version {version_string} sent to version channel {version_channel_id} without ping (secondary missing)")
                    except Exception as e:
                        print(f"Failed to send version to main channel as last resort: {e}")
    except Exception as e:
        print(f"Failed to send version to channel: {e}")
    
    if not getattr(bot, "_synced", False):
        try:
            # Try syncing commands globally (can be slow)
            print("⏳ Syncing global commands...")
            synced_global = await bot.tree.sync()
            print(f"✅ Synced {len(synced_global)} global commands")
            
            # Also sync guild commands for your main guild for instant update EEEEEEEEEE
            if APPLICATION_ID:
                guild_obj = discord.Object(id=int(os.getenv("GUILD_ID", "0")))
                if guild_obj.id != 0:
                    print(f"⏳ Syncing guild commands to guild {guild_obj.id} ...")
                    synced_guild = await bot.tree.sync(guild=guild_obj)
                    print(f"✅ Synced {len(synced_guild)} guild commands")
                else:
                    print("⚠️ GUILD_ID environment variable not set or invalid. Skipping guild sync.")
            else:
                print("⚠️ APPLICATION_ID missing, skipping guild sync.")
                
            bot._synced = True
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")
            traceback.print_exc()

# --- Cog Loader ---
async def load_cog_with_error_handling(cog_name):
    try:
        await bot.load_extension(cog_name)
        print(f"✅ Loaded {cog_name}")
    except Exception as e:
        print(f"❌ Failed to load {cog_name}: {e}")
        traceback.print_exc()

# --- HTTP Server ---
async def start_webserver():
    # Path to "./HTTP" relative to this Python file
    http_dir = os.path.join(os.path.dirname(__file__), "HTTP")
    os.makedirs(http_dir, exist_ok=True)

    app = web.Application()
    app.router.add_static("/", http_dir, show_index=True)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print(f"HTTP server serving {http_dir} at http://0.0.0.0:8080")

# --- Main Entry ---
async def main():
    async with bot:
        # Start HTTP server
        await start_webserver()

        # Load cogs
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
            "cogs.infract",
            "cogs.delete_archive",
            "cogs.callsign",
            "cogs.afk",
            "cogs.blacklist",
            "cogs.archive_commands",
            "cogs.MDT",
            "cogs.embed",
            "cogs.review",
            "cogs.message",
            "cogs.backups",
            "cogs.shift",
            "cogs.rolereq",
            "cogs.loa",
            "cogs.version",
            "cogs.trainings"
        ]
        
        for cog in cogs:
            print(f"🔄 Loading cog {cog} ...")
            await load_cog_with_error_handling(cog)
        
        print("All cogs loaded. Starting bot...")
        await bot.start(TOKEN)

@bot.tree.command(name="sync", description="Sync slash commands (admin only).")
async def sync_commands(interaction: discord.Interaction):
    # Only allow admins
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You lack permission.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await interaction.client.tree.sync()
        await interaction.followup.send(f"✅ Synced {len(synced)} commands globally.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Sync failed: {e}", ephemeral=True)

if __name__ == "__main__":
    asyncio.run(main())
