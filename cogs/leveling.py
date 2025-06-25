import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

# Config from .env
XP_PER_MESSAGE       = int(os.getenv("XP_PER_MESSAGE",       10))
XP_INCREMENT         = int(os.getenv("XP_INCREMENT_PER_LEVEL", 20))
XP_BASE              = int(os.getenv("XP_BASE_REQUIREMENT",   100))
DB_PATH              = os.getenv("DB_FILE", "data/leveling.db")

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_lock = asyncio.Lock()

    async def cog_load(self):
        # Ensure data folder + DB table exist
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    xp       INTEGER NOT NULL,
                    level    INTEGER NOT NULL
                )
            """)
            await db.commit()

    def calculate_required_xp(self, level: int) -> int:
        return XP_BASE + (level * XP_INCREMENT)

    async def get_user_data(self, user_id: int) -> dict:
        async with self.db_lock:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute(
                    "SELECT xp, level FROM users WHERE user_id = ?",
                    (user_id,)
                )
                row = await cur.fetchone()
                if row:
                    return {"xp": row[0], "level": row[1]}
                # first time seeing this user
                await db.execute(
                    "INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)",
                    (user_id, 0, 0)
                )
                await db.commit()
                return {"xp": 0, "level": 0}

    async def update_user_data(self, user_id: int, xp: int, level: int):
        async with self.db_lock:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE users SET xp = ?, level = ? WHERE user_id = ?",
                    (xp, level, user_id)
                )
                await db.commit()

    async def get_rank(self, user_id: int) -> int:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT user_id FROM users ORDER BY xp DESC")
            users = await cur.fetchall()
            for idx, (uid,) in enumerate(users, start=1):
                if uid == user_id:
                    return idx
        return 0

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        data = await self.get_user_data(user_id)
        data["xp"] += XP_PER_MESSAGE

        leveled = False
        while data["xp"] >= self.calculate_required_xp(data["level"]):
            data["level"] += 1
            leveled = True

        await self.update_user_data(user_id, data["xp"], data["level"])

        if leveled:
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

    # PREFIX COMMANDS

    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard(self, ctx: commands.Context):
        await self._send_leaderboard(ctx)

    @commands.command(name="rank")
    async def rank_cmd(self, ctx: commands.Context):
        await self._send_rank(ctx.author, ctx)

    # SLASH COMMANDS

    @app_commands.command(name="leaderboard", description="Show the top 10 users by XP.")
    async def slash_leaderboard(self, interaction: discord.Interaction):
        await self._send_leaderboard(interaction)

    @app_commands.command(name="rank", description="Check your current level and XP.")
    async def slash_rank(self, interaction: discord.Interaction):
        await self._send_rank(interaction.user, interaction)

    # INTERNAL HELPERS

    async def _send_leaderboard(self, dest):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT user_id, xp, level FROM users ORDER BY xp DESC LIMIT 10"
            )
            top = await cur.fetchall()

        embed = discord.Embed(title="🏆 Leaderboard - Top 10 XP", color=0xd0b47b())
        for idx, (uid, xp, lvl) in enumerate(top, start=1):
            user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
            embed.add_field(
                name=f"{idx}. {user.name}",
                value=f"Level: **{lvl}** | XP: **{xp}**",
                inline=False
            )

        if isinstance(dest, discord.Interaction):
            await dest.response.send_message(embed=embed)
        else:
            await dest.send(embed=embed)

    async def _send_rank(self, user: discord.User, dest):
        data = await self.get_user_data(user.id)
        level = data["level"]
        xp    = data["xp"]
        next_xp = self.calculate_required_xp(level)
        xp_to_next = next_xp - xp
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

        if isinstance(dest, discord.Interaction):
            await dest.response.send_message(embed=embed)
        else:
            await dest.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
