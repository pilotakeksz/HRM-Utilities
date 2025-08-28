import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import re
import datetime

ALLOWED_ROLE_IDS = [1329910280834252903, 1394667511374680105, 1355842403134603275]
ACTION_LOG_PATH = os.path.join("logs", "archive_action_log.txt")
DOC_CHANNEL_ID = 1343686645815181382

def has_allowed_role(ctx):
    return any(role.id in ALLOWED_ROLE_IDS for role in getattr(ctx.author, "roles", []))

def has_allowed_role_appcmd(interaction: discord.Interaction):
    return any(role.id in ALLOWED_ROLE_IDS for role in getattr(interaction.user, "roles", []))

def log_action(user, action, details):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(ACTION_LOG_PATH), exist_ok=True)
    with open(ACTION_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {user} | {action} | {details}\n")

async def log_to_discord_channel(bot, user, action, details):
    channel = bot.get_channel(DOC_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="Archive Action Log",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user} ({getattr(user, 'id', 'N/A')})", inline=False)
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Details", value=details, inline=False)
        await channel.send(embed=embed)

class NameSelect(discord.ui.Select):
    def __init__(self, date, names, messages):
        options = [discord.SelectOption(label=name, value=str(i)) for i, name in enumerate(names)]
        super().__init__(placeholder="Select a name...", min_values=1, max_values=1, options=options)
        self.date = date
        self.names = names
        self.messages = messages

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        name = self.names[idx]
        message = self.messages[idx]
        embed = discord.Embed(
            title=f"Archive for {self.date} - {name}",
            description=message
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_action(interaction.user, "Viewed Archive Entry", f"{self.date} - {name}")

class NameSelectView(discord.ui.View):
    def __init__(self, date, names, messages):
        super().__init__(timeout=60)
        self.add_item(NameSelect(date, names, messages))

class DateModal(discord.ui.Modal, title="Enter Date"):
    date = discord.ui.TextInput(label="Date", placeholder="YYYY-MM-DD", required=True)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        date_value = self.date.value
        if not re.match(r"^[\w\-]+$", date_value):
            await interaction.response.send_message(
                "Invalid date format. Use only letters, numbers, dashes, or underscores.",
                ephemeral=True
            )
            return

        db_path = os.path.join(os.getcwd(), "data", "Archive.db")
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT Name, Message FROM Archive WHERE Date = ?", (date_value,)
            ) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message("No entries found for that date.", ephemeral=True)
            return

        names = [row[0] for row in rows]
        messages = [row[1] for row in rows]
        await interaction.response.send_message(
            f"Select a name for `{date_value}`:",
            view=NameSelectView(date_value, names, messages),
            ephemeral=True
        )
        log_action(interaction.user, "Viewed Archive List", f"Date: {date_value}")

class ArchiveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="View a Archive", style=discord.ButtonStyle.success, custom_id="view_archive")
    async def view_archive(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DateModal(interaction.client))

class LogMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="archive")
    async def archive(self, ctx):
        embed = discord.Embed(
            title="MCNG ARCHIVE",
            description="Welcome to the MCNG archives."
        )
        await ctx.send(embed=embed, view=ArchiveView())
        log_action(ctx.author, "Opened Archive Interface", f"Channel: {ctx.channel}")
        await log_to_discord_channel(self.bot, ctx.author, "Opened Archive Interface", f"Channel: {ctx.channel}")

    @commands.command(name="sendtoarchive")
    async def sendtoarchive(self, ctx, date: str, name: str, *, message: str):
        if not has_allowed_role(ctx):
            embed = discord.Embed(
                title="Permission Denied",
                description="You do not have permission to use this command. Only users with the allowed roles can save to the archive.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        # Validate date and name
        if not re.match(r"^[\w\-]+$", date):
            await ctx.send("Invalid date format. Use only letters, numbers, dashes, or underscores.")
            return
        if not re.match(r"^[\w\-]+$", name):
            await ctx.send("Invalid name format. Use only letters, numbers, dashes, or underscores.")
            return

        db_path = os.path.join(os.getcwd(), "data", "Archive.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        try:
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS Archive (Date TEXT, Name TEXT, Message TEXT)"
                )
                await db.execute(
                    "INSERT INTO Archive (Date, Name, Message) VALUES (?, ?, ?)",
                    (date, name, message)
                )
                await db.commit()
            await ctx.send(f"Archive saved for `{date}` and `{name}`.")
            log_action(ctx.author, "Saved Archive", f"Date: {date} | Name: {name}")
            await log_to_discord_channel(self.bot, ctx.author, "Saved Archive", f"Date: {date} | Name: {name}")
        except Exception: # test
            await ctx.send("Failed to save the archive.")
#testing tetsing
    @commands.command(name="viewallarchives")
    async def viewallarchives(self, ctx):
        db_path = os.path.join(os.getcwd(), "data", "Archive.db")
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT Date, Name FROM Archive ORDER BY Date DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            await ctx.send("No archive entries found.")
            return
        msg = "\n".join([f"**Date:** `{row[0]}` | **Name:** `{row[1]}`" for row in rows])
        await ctx.send(f"**All Archive Entries:**\n{msg}")
        log_action(ctx.author, "Viewed All Archives", f"Total: {len(rows)}")
        await log_to_discord_channel(self.bot, ctx.author, "Viewed All Archives", f"Total: {len(rows)}")

    @app_commands.command(name="archive", description="Open the MCNG archive interface (interactive).")
    async def archive_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="MCNG ARCHIVE",
            description="Welcome to the MCNG archives."
        )
        await interaction.response.send_message(embed=embed, view=ArchiveView(), ephemeral=True)
        log_action(interaction.user, "Opened Archive Interface (slash)", f"Channel: {interaction.channel}")
        await log_to_discord_channel(self.bot, interaction.user, "Opened Archive Interface (slash)", f"Channel: {interaction.channel}")

    @app_commands.command(name="archive-viewall", description="View all archive entries (date and name).")
    async def archive_viewall_slash(self, interaction: discord.Interaction):
        db_path = os.path.join(os.getcwd(), "data", "Archive.db")
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT Date, Name FROM Archive ORDER BY Date DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message("No archive entries found.", ephemeral=True)
            return
        msg = "\n".join([f"**Date:** `{row[0]}` | **Name:** `{row[1]}`" for row in rows])
        await interaction.response.send_message(f"**All Archive Entries:**\n{msg}", ephemeral=True)
        log_action(interaction.user, "Viewed All Archives (slash)", f"Total: {len(rows)}")
        await log_to_discord_channel(self.bot, interaction.user, "Viewed All Archives (slash)", f"Total: {len(rows)}")

    @app_commands.command(name="sendtoarchive", description="Save a new archive entry. Only allowed roles can use this.")
    @app_commands.describe(
        date="Date for the archive entry (YYYY-MM-DD)",
        name="Name for the archive entry",
        message="Text to archive"
    )
    async def sendtoarchive_slash(self, interaction: discord.Interaction, date: str, name: str, message: str):
        if not has_allowed_role_appcmd(interaction):
            embed = discord.Embed(
                title="Permission Denied",
                description="You do not have permission to use this command. Only users with the allowed roles can save to the archive.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        # Validate date and name
        if not re.match(r"^[\w\-]+$", date):
            await interaction.response.send_message(
                "Invalid date format. Use only letters, numbers, dashes, or underscores.",
                ephemeral=True
            )
            return
        if not re.match(r"^[\w\-]+$", name):
            await interaction.response.send_message(
                "Invalid name format. Use only letters, numbers, dashes, or underscores.",
                ephemeral=True
            )
            return

        db_path = os.path.join(os.getcwd(), "data", "Archive.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        try:
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS Archive (Date TEXT, Name TEXT, Message TEXT)"
                )
                await db.execute(
                    "INSERT INTO Archive (Date, Name, Message) VALUES (?, ?, ?)",
                    (date, name, message)
                )
                await db.commit()
            await interaction.response.send_message(
                f"Archive saved for `{date}` and `{name}`.",
                ephemeral=True
            )
            log_action(interaction.user, "Saved Archive (slash)", f"Date: {date} | Name: {name}")
            await log_to_discord_channel(self.bot, interaction.user, "Saved Archive (slash)", f"Date: {date} | Name: {name}")
        except Exception:
            await interaction.response.send_message(
                "Failed to save the archive.",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_ready(self):
        # Do NOT send documentation to the log channel anymore.
        pass

async def setup(bot):
    await bot.add_cog(LogMessage(bot))