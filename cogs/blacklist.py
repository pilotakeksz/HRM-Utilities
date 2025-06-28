import os
import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import datetime
import uuid
from typing import Optional

BLACKLIST_DB = "data/blacklist.db"
BLACKLIST_LOG_FILE = "logs/blacklist_command.log"
BLACKLIST_LOG_TEXT = os.path.join("logs", "blacklist.txt")
BLACKLIST_VIEW_CHANNEL_ID = 1329910470332649536
BLACKLIST_ROLE_ID = 1329910241835352064

def log_to_file(user_id, channel_id, message, embed=False):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(BLACKLIST_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] User: {user_id} | Channel: {channel_id} | Embed: {embed} | Message: {message}\n")
    with open(BLACKLIST_LOG_TEXT, "a", encoding="utf-8") as f:
        f.write(f"[{now}] User: {user_id} | Channel: {channel_id} | {message}\n")

def log_command_to_txt(command_name, user, channel, **fields):
    log_path = os.path.join("logs", f"{command_name}.txt")
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{now}] User: {user} ({user.id}) | Channel: {channel} ({getattr(channel, 'id', channel)})\n")
        for k, v in fields.items():
            f.write(f"  {k}: {v}\n")
        f.write("\n")

class Blacklist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = BLACKLIST_DB

    async def cog_load(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    blacklist_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    user_name TEXT,
                    moderator_id INTEGER,
                    moderator_name TEXT,
                    reason TEXT,
                    proof TEXT,
                    date TEXT,
                    message_id INTEGER,
                    hrmc_wide INTEGER DEFAULT 0,
                    ban INTEGER DEFAULT 0
                )
            """)
            await db.commit()

    async def add_blacklist(self, blacklist_id, user, issued_by, reason, proof, message_id=None, hrmc_wide=False, ban=False):
        now = datetime.datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO blacklist (
                    blacklist_id, user_id, user_name, moderator_id, moderator_name,
                    reason, proof, date, message_id, hrmc_wide, ban
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (blacklist_id, user.id, str(user), issued_by.id, str(issued_by), reason, proof, now, message_id, int(hrmc_wide), int(ban)))
            await db.commit()
        with open(BLACKLIST_LOG_TEXT, "a", encoding="utf-8") as f:
            f.write(f"[{now}] {user} ({user.id}) | By: {issued_by} ({issued_by.id}) | Reason: {reason} | Proof: {proof or 'None'} | Blacklist ID: {blacklist_id} | HRMC-wide: {hrmc_wide} | Ban: {ban}\n")

    def get_blacklist_embed(self, blacklist_id, user, issued_by, reason, proof, date, hrmc_wide, ban):
        embed = discord.Embed(
            title=f"User Blacklisted",
            color=discord.Color.dark_red(),
            timestamp=datetime.datetime.fromisoformat(date)
        )
        embed.add_field(name="User", value=f"{user}", inline=True)
        embed.add_field(name="Issued by", value=f"{issued_by}", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Proof", value=proof or "None", inline=False)
        embed.add_field(name="Blacklist ID", value=str(blacklist_id), inline=True)
        embed.add_field(name="HRMC-wide", value="Yes" if hrmc_wide else "No", inline=True)
        embed.add_field(name="Banned", value="Yes" if ban else "No", inline=True)
        return embed

    @app_commands.command(name="blacklist", description="Blacklist a user from HRMC.")
    @app_commands.describe(
        user="User to blacklist",
        reason="Reason for blacklist",
        proof="Proof file",
        hrmc_wide="Is this blacklist HRMC-wide?",
        ban="Ban the user from the server?"
    )
    async def blacklist_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        proof: Optional[discord.Attachment] = None,
        hrmc_wide: bool = False,
        ban: bool = False
    ):
        # Permission check
        if not any(r.id == BLACKLIST_ROLE_ID for r in getattr(interaction.user, "roles", [])):
            await interaction.response.send_message("You do not have permission to blacklist users.", ephemeral=True)
            return

        log_command_to_txt(
            "blacklist",
            interaction.user,
            interaction.channel,
            target_user=f"{user} ({user.id})",
            reason=reason,
            proof=proof.url if proof else "None",
            hrmc_wide=hrmc_wide,
            ban=ban
        )

        proof_url = proof.url if proof else None
        blacklist_id = str(uuid.uuid4())
        channel = interaction.guild.get_channel(BLACKLIST_VIEW_CHANNEL_ID)
        embed = self.get_blacklist_embed(
            blacklist_id, user, interaction.user, reason, proof_url, datetime.datetime.utcnow().isoformat(), hrmc_wide, ban
        )
        if proof and proof.content_type and proof.content_type.startswith("image/"):
            embed.set_image(url=proof.url)
            msg = await channel.send(content=user.mention, embed=embed)
        elif proof:
            msg = await channel.send(content=user.mention, embed=embed, file=await proof.to_file())
        else:
            msg = await channel.send(content=user.mention, embed=embed)

        # HRMC-wide: publish announcement
        if hrmc_wide and channel.is_news():
            try:
                await msg.publish()
            except Exception:
                pass

        # DM the blacklisted user
        try:
            dm_embed = discord.Embed(
                title="You have been blacklisted",
                description=(
                    f"You have been blacklisted in **{interaction.guild.name}**.\n\n"
                    f"**Reason:** {reason}\n"
                    f"**Blacklist ID:** {blacklist_id}\n"
                    f"**HRMC-wide:** {'Yes' if hrmc_wide else 'No'}\n"
                    f"**Banned:** {'Yes' if ban else 'No'}"
                ),
                color=discord.Color.dark_red()
            )
            if proof and proof.content_type and proof.content_type.startswith("image/"):
                dm_embed.set_image(url=proof.url)
            await user.send(embed=dm_embed)
        except Exception:
            pass

        # Ban if requested
        if ban:
            try:
                await user.ban(reason=f"Blacklisted: {reason}")
            except Exception:
                await interaction.followup.send("Failed to ban the user. Please check my permissions.", ephemeral=True)

        await self.add_blacklist(
            blacklist_id, user, interaction.user, reason, proof_url, msg.id, hrmc_wide, ban
        )

        log_to_file(
            interaction.user.id,
            interaction.channel.id,
            f"Blacklisted {user.id} | Reason: {reason} | Blacklist ID: {blacklist_id} | HRMC-wide: {hrmc_wide} | Ban: {ban}",
            embed=True
        )
        await interaction.response.send_message(f"User blacklisted and logged. Blacklist ID: {blacklist_id}", ephemeral=True)

    @app_commands.command(name="blacklist-view", description="View all details of a specific blacklist by its ID.")
    @app_commands.describe(blacklist_id="The blacklist ID to view")
    async def blacklist_view(self, interaction: discord.Interaction, blacklist_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT blacklist_id, user_id, user_name, moderator_id, moderator_name, reason, proof, date, hrmc_wide, ban FROM blacklist WHERE blacklist_id = ?",
                (blacklist_id,)
            )
            row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message("Blacklist not found.", ephemeral=True)
            return

        (blacklist_id, user_id, user_name, moderator_id, moderator_name, reason, proof, date, hrmc_wide, ban) = row
        embed = discord.Embed(
            title=f"Blacklist Details: {blacklist_id}",
            color=discord.Color.dark_red(),
            timestamp=datetime.datetime.fromisoformat(date)
        )
        embed.add_field(name="User", value=f"{user_name} (`{user_id}`)", inline=False)
        embed.add_field(name="Moderator", value=f"{moderator_name} (`{moderator_id}`)", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Proof", value=proof or "None", inline=False)
        embed.add_field(name="Date", value=date, inline=False)
        embed.add_field(name="HRMC-wide", value="Yes" if hrmc_wide else "No", inline=True)
        embed.add_field(name="Banned", value="Yes" if ban else "No", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="blacklist-list", description="List all blacklists for a user, paginated.")
    @app_commands.describe(user="The user to list blacklists for", page="Page number (default 1)")
    async def blacklist_list(self, interaction: discord.Interaction, user: discord.Member, page: Optional[int] = 1):
        PAGE_SIZE = 5
        offset = (page - 1) * PAGE_SIZE
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT blacklist_id, reason, date, hrmc_wide, ban FROM blacklist WHERE user_id = ? ORDER BY date DESC LIMIT ? OFFSET ?",
                (user.id, PAGE_SIZE, offset)
            )
            rows = await cursor.fetchall()
            count_cursor = await db.execute(
                "SELECT COUNT(*) FROM blacklist WHERE user_id = ?",
                (user.id,)
            )
            total = (await count_cursor.fetchone())[0]

        if not rows:
            await interaction.response.send_message("No blacklists found for this user on this page.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Blacklists for {user} (Page {page}/{(total + PAGE_SIZE - 1)//PAGE_SIZE})",
            color=discord.Color.dark_red()
        )
        for row in rows:
            blacklist_id, reason, date, hrmc_wide, ban = row
            value = (
                f"**Reason:** {reason}\n"
                f"**Date:** {date}\n"
                f"**ID:** `{blacklist_id}`\n"
                f"**HRMC-wide:** {'Yes' if hrmc_wide else 'No'}\n"
                f"**Banned:** {'Yes' if ban else 'No'}\n"
            )
            embed.add_field(name="\u200b", value=value, inline=False)
        embed.set_footer(text=f"Total Blacklists: {total}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Blacklist(bot))