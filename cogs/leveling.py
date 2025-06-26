import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
import os

XP_PER_MESSAGE = int(os.getenv("XP_PER_MESSAGE", 10))
XP_INCREMENT = int(os.getenv("XP_INCREMENT_PER_LEVEL", 25))
XP_BASE = int(os.getenv("XP_BASE_REQUIREMENT", 100))
DB_PATH = os.getenv("DB_FILE", "data/leveling.db")

LEVEL_ROLES = {
    5: 1368257473546551369,
    10: 1368257734922866880,
    15: 1368257891319939124,
    20: 1368257989697470545,
    30: 1368258365863497898,
    40: 1368258484541456394,
    50: 1368258618993938452,
    60: 1368258857742241933,
    70: 1368258991683276964,
    80: 1368259244033445939,
    90: 1368259502650163371,
    100: 1368259650423619705,
}


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_lock = asyncio.Lock()

    async def cog_load(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER NOT NULL,
                    level INTEGER NOT NULL
                )
            """)
            await db.commit()

    def calculate_required_xp(self, level):
        # Progressive XP: Each level requires previous + XP_BASE + (XP_INCREMENT * (level-1))
        if level == 0:
            return XP_BASE
        xp = XP_BASE
        for i in range(1, level + 1):
            xp += XP_BASE + XP_INCREMENT * (i - 1)
        return xp

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

    async def handle_role_rewards(self, member: discord.Member, level: int):
        awarded_role_id = LEVEL_ROLES.get(level)
        if not awarded_role_id:
            return None

        awarded_role = member.guild.get_role(awarded_role_id)
        if not awarded_role:
            return None

        # Remove lower level roles
        roles_to_remove = [member.guild.get_role(rid) for lvl, rid in LEVEL_ROLES.items() if lvl < level]
        await member.remove_roles(*filter(None, roles_to_remove))
        await member.add_roles(awarded_role)
        return awarded_role

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        data = await self.get_user_data(user_id)
        data["xp"] += XP_PER_MESSAGE

        leveled_up = False
        old_level = data["level"]
        while data["xp"] >= self.calculate_required_xp(data["level"]):
            data["level"] += 1
            leveled_up = True

        await self.update_user_data(user_id, data["xp"], data["level"])

        if leveled_up:
            member = message.guild.get_member(user_id)
            awarded_role = await self.handle_role_rewards(member, data["level"])
            rank = await self.get_rank(user_id)
            xp_to_next = self.calculate_required_xp(data["level"]) - data["xp"]

            embed = discord.Embed(
                title="🎉 Level Up!",
                description=(
                    f"{message.author.mention} is now **level {data['level']}**\n"
                    f"Total XP: **{data['xp']}**\n"
                    f"Next level in: **{xp_to_next}** XP\n"
                    f"Rank: **#{rank}**"
                ),
                color=0xd0b47b
            )
            if awarded_role:
                embed.add_field(name="🏅 Role Awarded", value=f"Congrats! You have been awarded {awarded_role.mention} 🎉", inline=False)

            await message.channel.send(embed=embed)

    @commands.command(name="rank")
    async def rank_command(self, ctx):
        await self.send_rank_embed(ctx.author, ctx)

    @app_commands.command(name="rank", description="Check your current level and XP.")
    async def rank_slash(self, interaction: discord.Interaction):
        await self.send_rank_embed(interaction.user, interaction)

    async def send_rank_embed(self, user, destination):
        data = await self.get_user_data(user.id)
        xp = data["xp"]
        level = data["level"]
        xp_to_next = self.calculate_required_xp(level) - xp
        rank = await self.get_rank(user.id)

        embed = discord.Embed(
            title=f"{user.name}'s Rank",
            description=(
                f"Level: **{level}**\n"
                f"XP: **{xp}**\n"
                f"Next level in: **{xp_to_next}** XP\n"
                f"Rank: **#{rank}**"
            ),
            color=0xd0b47b
        )
        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

    @commands.command(name="leaderboard")
    async def leaderboard_command(self, ctx):
        await self.send_leaderboard_embed(ctx)

    @app_commands.command(name="leaderboard", description="Show the top 10 users by XP and level.")
    async def leaderboard_slash(self, interaction: discord.Interaction):
        await self.send_leaderboard_embed(interaction)

    async def send_leaderboard_embed(self, destination):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id, xp, level FROM users ORDER BY xp DESC LIMIT 10"
            )
            top_users = await cursor.fetchall()

        embed = discord.Embed(
            title="🏆 Leaderboard",
            description="Top 10 users by XP and Level",
            color=0xd0b47b
        )

        if not top_users:
            embed.description = "No users found."
        else:
            lines = []
            for idx, (user_id, xp, level) in enumerate(top_users, start=1):
                user = self.bot.get_user(user_id)
                name = user.mention if user else f"User ID {user_id}"
                lines.append(f"**#{idx}** {name} — Level: **{level}** | XP: **{xp}**")
            embed.add_field(name="Ranks", value="\n".join(lines), inline=False)

        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))