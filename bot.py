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
    
    if not getattr(bot, "_synced", False):
        try:
            # Try syncing commands globally (can be slow)
            print("⏳ Syncing global commands...")
            synced_global = await bot.tree.sync()
            print(f"✅ Synced {len(synced_global)} global commands")
            
            # Also sync guild commands for your main guild for instant update
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
            "cogs.divisons",
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
            "cogs.loa"
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

@bot.tree.command(name="reload", description="Reload a cog (admin only).")
async def reload_cog(interaction: discord.Interaction, cog_name: str):
    # Only allow admins
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You lack permission.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Try to unload first
        try:
            await bot.unload_extension(cog_name)
            print(f"✅ Unloaded {cog_name}")
        except Exception as e:
            print(f"⚠️ Failed to unload {cog_name} (might not be loaded): {e}")
        
        # Force reload by removing the cog from the internal registry if it exists
        cog_name_clean = cog_name.replace("cogs.", "").replace("cog", "").title() + "Cog"
        if cog_name_clean in bot.cogs:
            print(f"🔧 Manually removing {cog_name_clean} from bot.cogs")
            del bot.cogs[cog_name_clean]
        
        # Load the cog
        await bot.load_extension(cog_name)
        await interaction.followup.send(f"✅ Successfully reloaded {cog_name}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to reload {cog_name}: {e}", ephemeral=True)
        print(f"❌ Reload error details: {e}")
        traceback.print_exc()

@bot.tree.command(name="cogs", description="List currently loaded cogs (admin only).")
async def list_cogs(interaction: discord.Interaction):
    # Only allow admins
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You lack permission.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    loaded_cogs = list(bot.cogs.keys())
    if loaded_cogs:
        cog_list = "\n".join(f"• {cog}" for cog in loaded_cogs)
        await interaction.followup.send(f"**Loaded Cogs ({len(loaded_cogs)}):**\n{cog_list}", ephemeral=True)
    else:
        await interaction.followup.send("No cogs currently loaded.", ephemeral=True)

if __name__ == "__main__":
    asyncio.run(main())
