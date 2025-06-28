import discord
from discord.ext import commands
import aiosqlite
import os
import re

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
            title="HRM ARCHIVE",
            description="Welcome to the HRM archives."
        )
        await ctx.send(embed=embed, view=ArchiveView())

    @commands.command(name="sendtoarchive")
    async def sendtoarchive(self, ctx, date: str, name: str, *, message: str):
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
        except Exception:
            await ctx.send("Failed to save the archive.")

async def setup(bot):
    await bot.add_cog(LogMessage(bot))