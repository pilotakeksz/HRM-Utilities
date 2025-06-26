import os
import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import datetime
import asyncio

LOG_CHANNEL_ID = 1343686645815181382
LOG_FILE = os.path.join("logs", "infraction.txt")
DB_PATH = os.path.join("data", "infractions.db")

# Ensure directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

class Infraction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.init_db())

    async def init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS infractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    user_name TEXT,
                    moderator_id INTEGER,
                    moderator_name TEXT,
                    action TEXT,
                    reason TEXT,
                    proof TEXT,
                    date TEXT
                )
            """)
            await db.commit()

    def log_to_file(self, user_id, info):
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{now}] User: {user_id} | {info}\n")

    async def log_to_channel(self, guild, user, moderator, action, reason, proof):
        channel = guild.get_channel(LOG_CHANNEL_ID)
        embed = discord.Embed(
            title="New Infraction",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator} ({moderator.id})", inline=False)
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        if proof:
            embed.add_field(name="Proof", value=proof, inline=False)
        await channel.send(embed=embed)

    @app_commands.command(name="infraction", description="Add an infraction to a user.")
    @app_commands.describe(
        user="User to infract",
        action="Type of infraction (warn, mute, ban, etc.)",
        reason="Reason for the infraction",
        proof="Proof (optional, can be a link or text)"
    )
    async def infraction_slash(self, interaction: discord.Interaction, user: discord.Member, action: str, reason: str, proof: str = None):
        moderator = interaction.user
        now = datetime.datetime.utcnow().isoformat()
        # Save to DB
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO infractions (user_id, user_name, moderator_id, moderator_name, action, reason, proof, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user.id, str(user), moderator.id, str(moderator), action, reason, proof, now))
            await db.commit()
        # Log to file
        self.log_to_file(user.id, f"Action: {action} | Reason: {reason} | Proof: {proof or 'None'} | By: {moderator.id}")
        # Log to channel
        await self.log_to_channel(interaction.guild, user, moderator, action, reason, proof)
        # DM user
        try:
            dm_embed = discord.Embed(
                title="You have received an infraction",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            dm_embed.add_field(name="Action", value=action, inline=True)
            dm_embed.add_field(name="Reason", value=reason, inline=True)
            if proof:
                dm_embed.add_field(name="Proof", value=proof, inline=False)
            dm_embed.set_footer(text=f"Issued by {moderator}")
            await user.send(embed=dm_embed)
        except Exception:
            pass
        await interaction.response.send_message(f"Infraction logged for {user.mention}.", ephemeral=True)

    @app_commands.command(name="infractions-log", description="Show the last 10 infractions.")
    async def infractions_log(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_name, moderator_name, action, reason, proof, date FROM infractions ORDER BY date DESC LIMIT 10"
            )
            rows = await cursor.fetchall()
        embed = discord.Embed(
            title="Recent Infractions",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        if not rows:
            embed.description = "No infractions found."
        else:
            for row in rows:
                user_name, moderator_name, action, reason, proof, date = row
                date_fmt = datetime.datetime.fromisoformat(date).strftime("%Y-%m-%d %H:%M")
                value = (
                    f"**User:** {user_name}\n"
                    f"**By:** {moderator_name}\n"
                    f"**Type:** {action}\n"
                    f"**Reason:** {reason}\n"
                    f"**Proof:** {proof or 'None'}\n"
                    f"**Date:** {date_fmt}"
                )
                embed.add_field(name="\u200b", value=value, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await