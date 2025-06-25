import discord
from discord.ext import commands
from discord import app_commands
import os
import math
import asyncio
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

XP_PER_MESSAGE = int(os.getenv("XP_PER_MESSAGE"))
XP_INCREMENT = int(os.getenv("XP_INCREMENT_PER_LEVEL"))
XP_BASE = int(os.getenv("XP_BASE_REQUIREMENT"))
DB_PATH = os.getenv("DB_FILE", "data/leveling.db")

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_lock = asyncio.Lock()

    async def cog_load(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER NOT NULL,
                    level INTEGER NOT NULL
                )
            """)
            await db.commit()
        # Sync slash commands globally
        await self.bot.tree.sync()

    def calculate_required_xp(self, level):
        return XP_BASE + (level * XP_INCREMENT)

    async def get_user_data(self, user_id):
        async with self.db_lock:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()
                if row:
                    return {"xp": row[0], "level": row[1]}
                else:
                    await db.execute("INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)", (user_id, 0, 0))
                    await db.commit()
                    return {"xp": 0, "level": 0}

    async def update_user_data(self, user_id, xp, level):
        async with self.db_lock:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (xp, level, user_id))
                await db.commit()

    async def get_rank(self, user_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id, xp FROM users ORDER BY xp DESC")
            users = await cursor.fetchall()
            for index, (uid, _) in enumerate(users, start=1):
                if uid == user_id:
                    return index
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        data = await self.get_user_data(user_id)
        data["xp"] += XP_PER_MESSAGE

        leveled_up = False
        while data["xp"] >= self.calculate_required_xp(data["level"]):
            data["level"] += 1
            leveled_up = True

        await self.update_user_data(user_id, data["xp"], data["level"])

        if leveled_up:
            next_xp = self.calculate_required_xp(data["level"])
            xp_to_next = next_xp - data["xp"]
            rank = await self.get_rank(user_id)

            embed = discord.Embed(
                title="New Level!",
                description=(
                    f"{message.author.mention} has levelled up to level **{data['level']}**\n"
                    f"Total XP: **{data['xp']}**\n"
                    f"Next level in: **{xp_to_next}** XP\n\n"
                    f"Current rank: **#{rank}**"
                ),
                color=0xd0b47b
            )
            await message.channel.send(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard(self, ctx):
        await self.send_leaderboard(ctx)

    @app_commands.command(name="leaderboard", description="Show the top 10 users by XP.")
    async def slash_leaderboard(self, interaction: discord.Interaction):
        await self.send_leaderboard(interaction)

    async def send_leaderboard(self, ctx_or_interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id, xp, level FROM users ORDER BY xp DESC LIMIT 10")
            top_users = await cursor.fetchall()

        embed = discord.Embed(title="🏆 Leaderboard - Top 10 XP", color=discord.Color.gold())
        for index, (user_id, xp, level) in enumerate(top_users, start=1):
            user = self.bot.get_user(user_id)
            embed.add_field(
                name=f"{index}. {user.name if user else 'Unknown'}",
                value=f"Level: **{level}** | XP: **{xp}**",
                inline=False
            )

        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)

    @commands.command(name="rank")
    async def rank_cmd(self, ctx):
        await self.send_rank_embed(ctx.author, ctx)

    @app_commands.command(name="rank", description="Check your current level and XP.")
    async def rank_slash(self, interaction: discord.Interaction):
        await self.send_rank_embed(interaction.user, interaction)

    async def send_rank_embed(self, user, destination):
        data = await self.get_user_data(user.id)
        xp = data["xp"]
        level = data["level"]
        next_level_xp = self.calculate_required_xp(level)
        xp_to_next = next_level_xp - xp
        rank = await self.get_rank(user.id)

        embed = discord.Embed(
            title=f"{user.name}'s Rank",
            description=(
                f"Level: **{level}**\n"
                f"Total XP: **{xp}**\n"
                f"Next level in: **{xp_to_next}** XP\n"
                f"Leaderboard rank: **#{rank}**"
            ),
            color=0x7289da
        )

        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Leveling(bot))
