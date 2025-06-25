import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import aiosqlite
import os

# Read config from environment variables
XP_PER_MESSAGE = int(os.getenv("XP_PER_MESSAGE", 10))
XP_INCREMENT = int(os.getenv("XP_INCREMENT_PER_LEVEL", 50))
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

EMBED_COLOR = 0xd0b47b  # Gold color as requested

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

        self.bot.tree.add_command(self.leaderboard_slash)
        self.bot.tree.add_command(self.rank_slash)

    def calculate_required_xp(self, level: int) -> int:
        return XP_BASE + (level * XP_INCREMENT)

    async def get_user_data(self, user_id: int) -> dict:
        async with self.db_lock:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()
                if row:
                    return {"xp": row[0], "level": row[1]}
                else:
                    await db.execute("INSERT INTO users (user_id, xp, level) VALUES (?, 0, 0)", (user_id,))
                    await db.commit()
                    return {"xp": 0, "level": 0}

    async def update_user_data(self, user_id: int, xp: int, level: int):
        async with self.db_lock:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (xp, level, user_id))
                await db.commit()

    async def get_rank(self, user_id: int) -> int | None:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT user_id FROM users ORDER BY xp DESC")
            users = await cursor.fetchall()
            for index, (uid,) in enumerate(users, start=1):
                if uid == user_id:
                    return index
            return None

    async def handle_role_rewards(self, member: discord.Member, new_level: int):
        guild = member.guild
        if new_level in LEVEL_ROLES:
            role_id_to_add = LEVEL_ROLES[new_level]
            role_to_add = guild.get_role(role_id_to_add)
            if not role_to_add:
                return None

            roles_to_remove = []
            for lvl, rid in LEVEL_ROLES.items():
                if lvl < new_level:
                    role = guild.get_role(rid)
                    if role and role in member.roles:
                        roles_to_remove.append(role)

            try:
                if roles_to_remove:
                    await member.remove_roles(*roles_to_remove, reason="Leveling role upgrade")
                if role_to_add not in member.roles:
                    await member.add_roles(role_to_add, reason="Leveling role awarded")
            except discord.Forbidden:
                pass
            except Exception:
                pass

            return role_to_add
        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        data = await self.get_user_data(user_id)

        data["xp"] += XP_PER_MESSAGE
        leveled_up = False

        # Level up while possible (in case of multiple level gains)
        while data["xp"] >= self.calculate_required_xp(data["level"]):
            data["level"] += 1
            leveled_up = True

        await self.update_user_data(user_id, data["xp"], data["level"])

        if leveled_up:
            next_xp = self.calculate_required_xp(data["level"])
            xp_to_next = next_xp - data["xp"]
            rank = await self.get_rank(user_id)

            member = message.author
            role_awarded = await self.handle_role_rewards(member, data["level"])

            desc = (
                f"{member.mention} has leveled up to level **{data['level']}**\n"
                f"Total XP: **{data['xp']}**\n"
                f"Next level in: **{xp_to_next}** XP\n\n"
                f"Current rank: **#{rank}**"
            )
            if role_awarded:
                desc += f"\n\nCongrats! You have been awarded {role_awarded.mention} 🎉"

            embed = discord.Embed(
                title="🎉 New Level!",
                description=desc,
                color=EMBED_COLOR
            )
            await message.channel.send(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard(self, ctx: commands.Context):
        await self.send_leaderboard(ctx)

    @app_commands.command(name="leaderboard", description="Show the top 10 users by XP.")
    async def leaderboard_slash(self, interaction: discord.Interaction):
        await self.send_leaderboard(interaction)

    async def send_leaderboard(self, ctx_or_interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id, level, xp FROM users ORDER BY xp DESC LIMIT 10"
            )
            top_users = await cursor.fetchall()

        if not top_users:
            message = "No leveling data available yet."
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.response.send_message(message)
            else:
                await ctx_or_interaction.send(message)
            return

        embed = discord.Embed(
            title="🏆 Leveling Leaderboard",
            color=EMBED_COLOR
        )
        description = ""
        guild = None
        if isinstance(ctx_or_interaction, discord.Interaction):
            guild = self.bot.get_guild(ctx_or_interaction.guild_id)
        elif hasattr(ctx_or_interaction, "guild"):
            guild = ctx_or_interaction.guild

        for rank, (user_id, level, xp) in enumerate(top_users, start=1):
            member = guild.get_member(user_id) if guild else None
            name = member.display_name if member else f"User ID {user_id}"
            description += f"**#{rank}** - {name} | Level {level} | XP {xp}\n"

        embed.description = description

        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)

    @commands.command(name="rank")
    async def rank_cmd(self, ctx: commands.Context):
        await self.send_rank_embed(ctx.author, ctx)

    @app_commands.command(name="rank", description="Check your current level and XP.")
    async def rank_slash(self, interaction: discord.Interaction):
        await self.send_rank_embed(interaction.user, interaction)

    async def send_rank_embed(self, user: discord.User, destination):
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
                f"Leaderboard rank: **#{rank if rank else 'Unranked'}**"
            ),
            color=EMBED_COLOR
        )

        if isinstance(destination, discord.Interaction):
            await destination.response.send_message(embed=embed)
        else:
            await destination.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
