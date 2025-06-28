import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import os
import re
import uuid

ALLOWED_ROLE_IDS = [911072161349918720, 1329910241835352064]

def has_allowed_role(ctx):
    return any(role.id in ALLOWED_ROLE_IDS for role in getattr(ctx.author, "roles", []))

def has_allowed_role_appcmd(interaction: discord.Interaction):
    return any(role.id in ALLOWED_ROLE_IDS for role in getattr(interaction.user, "roles", []))

class NameSelect(discord.ui.Select):
    def __init__(self, date, names, ids):
        options = [discord.SelectOption(label=name, value=str(i)) for i, name in enumerate(names)]
        super().__init__(placeholder="Select a name...", min_values=1, max_values=1, options=options)
        self.date = date
        self.names = names
        self.ids = ids

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        name = self.names[idx]
        archive_id = self.ids[idx]
        db_path = os.path.join(os.getcwd(), "data", "Archive.db")
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT Content FROM Archive WHERE ID = ?", (archive_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message("Archive entry not found.", ephemeral=True)
            return
        content = row[0]
        embed = discord.Embed(
            title=f"Archive for {self.date} - {name}",
            description=content
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class NameSelectView(discord.ui.View):
    def __init__(self, date, names, ids):
        super().__init__(timeout=60)
        self.add_item(NameSelect(date, names, ids))

class DateModal(discord.ui.Modal, title="Enter Date"):
    date = discord.ui.TextInput(label="Date", placeholder="YYYY-MM-DD", required=True)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if not has_allowed_role_appcmd(interaction):
            await interaction.response.send_message("You do not have permission to use the archive.", ephemeral=True)
            return

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
                "SELECT Name, ID FROM Archive WHERE Date = ?", (date_value,)
            ) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message("No entries found for that date.", ephemeral=True)
            return

        names = [row[0] for row in rows]
        ids = [row[1] for row in rows]
        await interaction.response.send_message(
            f"Select a name for `{date_value}`:",
            view=NameSelectView(date_value, names, ids),
            ephemeral=True
        )

class ArchiveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="View an Archive", style=discord.ButtonStyle.success, custom_id="view_archive")
    async def view_archive(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DateModal(interaction.client))

class LogMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="archive")
    async def archive(self, ctx):
        if not has_allowed_role(ctx):
            await ctx.send("You do not have permission to use the archive.")
            return
        embed = discord.Embed(
            title="HRM ARCHIVE",
            description="Welcome to the HRM archives."
        )
        await ctx.send(embed=embed, view=ArchiveView())

    @commands.command(name="sendtoarchive")
    async def sendtoarchive(self, ctx, date: str, name: str, *, content: str):
        if not has_allowed_role(ctx):
            await ctx.send("You do not have permission to use this command.")
            return
        # Validate date and name
        if not re.match(r"^[\w\-]+$", date):
            await ctx.send("Invalid date format. Use only letters, numbers, dashes, or underscores.")
            return
        if not re.match(r"^[\w\-]+$", name):
            await ctx.send("Invalid name format. Use only letters, numbers, dashes, or underscores.")
            return

        archive_id = str(uuid.uuid4())
        db_path = os.path.join(os.getcwd(), "data", "Archive.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        try:
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "CREATE TABLE IF NOT EXISTS Archive (ID TEXT PRIMARY KEY, Date TEXT, Name TEXT, Content TEXT)"
                )
                await db.execute(
                    "INSERT INTO Archive (ID, Date, Name, Content) VALUES (?, ?, ?, ?)",
                    (archive_id, date, name, content)
                )
                await db.commit()
            await ctx.send(f"Archive saved for `{date}` and `{name}`. Archive ID: `{archive_id}`")
        except Exception:
            await ctx.send("Failed to save the archive.")

    @commands.command(name="viewarchivebyid")
    async def viewarchivebyid(self, ctx, archive_id: str):
        if not has_allowed_role(ctx):
            await ctx.send("You do not have permission to use this command.")
            return
        db_path = os.path.join(os.getcwd(), "data", "Archive.db")
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT Date, Name, Content FROM Archive WHERE ID = ?", (archive_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            await ctx.send("Archive entry not found.")
            return
        date, name, content = row
        embed = discord.Embed(
            title=f"Archive for {date} - {name}",
            description=content
        )
        await ctx.send(embed=embed)

    @app_commands.command(name="archive-view", description="View the HRM archive (interactive).")
    async def archive_view_slash(self, interaction: discord.Interaction):
        if not has_allowed_role_appcmd(interaction):
            await interaction.response.send_message("You do not have permission to use the archive.", ephemeral=True)
            return
        embed = discord.Embed(
            title="HRM ARCHIVE",
            description="Welcome to the HRM archives."
        )
        await interaction.response.send_message(embed=embed, view=ArchiveView(), ephemeral=True)

    @app_commands.command(name="archive-list-all", description="List all archive entries.")
    async def archive_list_all(self, interaction: discord.Interaction):
        if not has_allowed_role_appcmd(interaction):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        db_path = os.path.join(os.getcwd(), "data", "Archive.db")
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT ID, Date, Name FROM Archive ORDER BY Date DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        if not rows:
            await interaction.response.send_message("No archive entries found.", ephemeral=True)
            return
        lines = [f"**ID:** `{row[0]}` | **Date:** `{row[1]}` | **Name:** `{row[2]}`" for row in rows]
        msg = "\n".join(lines)
        await interaction.response.send_message(f"**All Archive Entries:**\n{msg}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(LogMessage(bot))