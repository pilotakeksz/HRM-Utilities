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
BLACKLIST_LOG_CHANNEL_ID = 1343686645815181382  # Use your logging channel ID here
BLACKLIST_ROLE_ID = 1355842403134603275
BLACKLISTED_ROLE_ID = 1329910361347854388

EMOJI_HRMC = "<:HighRockMilitary:1376605942765977800>"
EMOJI_MEMBER = "<:Member:1343945679390904330>"
EMOJI_REASON = "<:regulations:1343313357121392733>"
EMOJI_ID = "<:id:1343961756124315668>"
EMOJI_PERMISSION = "<:Permission:1343959785095168111>"
EMOJI_VOIDED = "<:edit_message:1343948876599787602>"

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
                    ban INTEGER DEFAULT 0,
                    voided INTEGER DEFAULT 0,
                    void_reason TEXT
                )
            """)
            await db.commit()

    async def add_blacklist(self, blacklist_id, user, issued_by, reason, proof, message_id=None, hrmc_wide=False, ban=False):
        now = datetime.datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO blacklist (
                    blacklist_id, user_id, user_name, moderator_id, moderator_name,
                    reason, proof, date, message_id, hrmc_wide, ban, voided, void_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
            """, (blacklist_id, user.id, str(user), issued_by.id, str(issued_by), reason, proof, now, message_id, int(hrmc_wide), int(ban)))
            await db.commit()

    

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
        # Only send the embed to the log channel, with only the ping in content
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

        # DM the blacklisted user (simple embed, not the log embed)
        try:
            dm_embed = discord.Embed(
                title=f"{EMOJI_HRMC} // HRMC Blacklist",
                description=(
                    f"You have been blacklisted in **{interaction.guild.name}**.\n\n"
                    f"{EMOJI_REASON} **Reason:** {reason}\n"
                    f"{EMOJI_ID} **Blacklist ID:** {blacklist_id}\n"
                    f"{EMOJI_PERMISSION} **HRMC-wide:** {'Yes' if hrmc_wide else 'No'}\n"
                    f"{EMOJI_PERMISSION} **Banned:** {'Yes' if ban else 'No'}"
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

        # Add blacklisted role
        try:
            role = interaction.guild.get_role(BLACKLISTED_ROLE_ID)
            if role and role not in user.roles:
                await user.add_roles(role, reason="HRMC Blacklisted")
        except Exception:
            pass

        await self.add_blacklist(
            blacklist_id, user, interaction.user, reason, proof_url, msg.id, hrmc_wide, ban
        )

        log_to_file(
            interaction.user.id,
            interaction.channel.id,
            f"Blacklisted {user.id} | Reason: {reason} | Blacklist ID: {blacklist_id} | HRMC-wide: {hrmc_wide} | Ban: {ban}",
            embed=True
        )

        # Log to logging channel
        log_channel = interaction.guild.get_channel(BLACKLIST_LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="Blacklist Issued",
                color=discord.Color.dark_red(),
                timestamp=datetime.datetime.utcnow()
            )
            log_embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
            log_embed.add_field(name="By", value=f"{interaction.user} ({interaction.user.id})", inline=False)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.add_field(name="Blacklist ID", value=blacklist_id, inline=False)
            log_embed.add_field(name="HRMC-wide", value="Yes" if hrmc_wide else "No", inline=True)
            log_embed.add_field(name="Banned", value="Yes" if ban else "No", inline=True)
            log_embed.set_footer(text=f"Logged at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            await log_channel.send(embed=log_embed)

        # Only send a simple confirmation to the moderator, not the embed
        await interaction.response.send_message(f"User blacklisted and logged. Blacklist ID: {blacklist_id}", ephemeral=True)

    @app_commands.command(name="blacklist-void", description="Void (remove) a blacklist by its ID.")
    @app_commands.describe(blacklist_id="The blacklist ID to void", reason="Reason for voiding this blacklist")
    async def blacklist_void(self, interaction: discord.Interaction, blacklist_id: str, reason: str):
        try:
            if not any(r.id == BLACKLIST_ROLE_ID for r in getattr(interaction.user, "roles", [])):
                await interaction.response.send_message("You do not have permission to void blacklists.", ephemeral=True)
                return

            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT user_id, user_name, moderator_id, moderator_name, reason, proof, date, message_id, hrmc_wide, ban, voided FROM blacklist WHERE blacklist_id = ?",
                    (blacklist_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    await interaction.response.send_message("Blacklist not found.", ephemeral=True)
                    return
                user_id, user_name, moderator_id, moderator_name, orig_reason, proof, date, message_id, hrmc_wide, ban, voided = row

                if voided:
                    await interaction.response.send_message("This blacklist is already voided.", ephemeral=True)
                    return

                await db.execute(
                    "UPDATE blacklist SET voided = 1, void_reason = ? WHERE blacklist_id = ?",
                    (reason, blacklist_id)
                )
                await db.commit()

            # Remove blacklisted role if present
            try:
                member = interaction.guild.get_member(user_id)
                role = interaction.guild.get_role(BLACKLISTED_ROLE_ID)
                if member and role and role in member.roles:
                    await member.remove_roles(role, reason="Blacklist voided")
            except Exception:
                pass

            # Edit the original blacklist message to show voided status
            channel = interaction.guild.get_channel(BLACKLIST_VIEW_CHANNEL_ID)
            if channel and message_id:
                try:
                    msg = await channel.fetch_message(message_id)
                    voided_embed = self.get_blacklist_embed(
                        blacklist_id, user_name, moderator_name, orig_reason, proof, date, hrmc_wide, ban, voided=True, void_reason=reason
                    )
                    await msg.edit(
                        embed=voided_embed,
                        content=f"{user_name}"
                    )
                except Exception:
                    pass

            # DM the user if not banned
            try:
                if not ban:
                    user = await interaction.guild.fetch_member(user_id)
                    dm_embed = discord.Embed(
                        title="Your Blacklist Was Voided",
                        description=(
                            f"Your blacklist in **{interaction.guild.name}** has been voided.\n\n"
                            f"**Original Reason:** {orig_reason}\n"
                            f"**Voided By:** {interaction.user.mention}\n"
                            f"**Void Reason:** {reason}"
                        ),
                        color=discord.Color.green()
                    )
                    now_utc = datetime.datetime.utcnow().strftime("UTC %Y-%m-%d %H:%M")
                    dm_embed.set_footer(text=f"Voided: {now_utc}")
                    await user.send(embed=dm_embed)
            except Exception:
                pass

            # Log to logging channel
            log_channel = interaction.guild.get_channel(BLACKLIST_LOG_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(
                    title="Blacklist Voided",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.utcnow()
                )
                log_embed.add_field(name="Blacklist ID", value=blacklist_id, inline=False)
                log_embed.add_field(name="User", value=f"{user_name} ({user_id})", inline=False)
                log_embed.add_field(name="By", value=f"{interaction.user} ({interaction.user.id})", inline=False)
                log_embed.add_field(name="Original Reason", value=orig_reason, inline=False)
                log_embed.add_field(name="Void Reason", value=reason, inline=False)
                log_embed.set_footer(text=f"Logged at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
                await log_channel.send(embed=log_embed)

            # Only send the embed to the moderator as confirmation
            embed = self.get_blacklist_embed(
                blacklist_id, user_name, moderator_name, orig_reason, proof, date, hrmc_wide, ban, voided=True, void_reason=reason
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

        except Exception as e:
            try:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @app_commands.command(name="blacklist-view", description="View all details of a specific blacklist by its ID.")
    @app_commands.describe(blacklist_id="The blacklist ID to view")
    async def blacklist_view(self, interaction: discord.Interaction, blacklist_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT blacklist_id, user_id, user_name, moderator_id, moderator_name, reason, proof, date, hrmc_wide, ban, voided, void_reason FROM blacklist WHERE blacklist_id = ?",
                (blacklist_id,)
            )
            row = await cursor.fetchone()
        if not row:
            await interaction.response.send_message("Blacklist not found.", ephemeral=True)
            return

        (blacklist_id, user_id, user_name, moderator_id, moderator_name, reason, proof, date, hrmc_wide, ban, voided, void_reason) = row
        embed = self.get_blacklist_embed(
            blacklist_id, user_name, moderator_name, reason, proof, date, hrmc_wide, ban, voided=voided, void_reason=void_reason
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="blacklist-list", description="List all blacklists for a user, paginated.")
    @app_commands.describe(user="The user to list blacklists for", page="Page number (default 1)")
    async def blacklist_list(self, interaction: discord.Interaction, user: discord.Member, page: Optional[int] = 1):
        PAGE_SIZE = 5
        offset = (page - 1) * PAGE_SIZE
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT blacklist_id, reason, date, hrmc_wide, ban, voided, void_reason FROM blacklist WHERE user_id = ? ORDER BY date DESC LIMIT ? OFFSET ?",
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
            title=f"{EMOJI_HRMC} // Blacklists for {user} (Page {page}/{(total + PAGE_SIZE - 1)//PAGE_SIZE})",
            color=discord.Color.dark_red()
        )
        for row in rows:
            blacklist_id, reason, date, hrmc_wide, ban, voided, void_reason = row
            value = (
                f"{EMOJI_REASON} **Reason:** {reason}\n"
                f"**Date:** {date}\n"
                f"{EMOJI_ID} **ID:** `{blacklist_id}`\n"
                f"{EMOJI_PERMISSION} **HRMC-wide:** {'Yes' if hrmc_wide else 'No'}\n"
                f"{EMOJI_PERMISSION} **Banned:** {'Yes' if ban else 'No'}\n"
            )
            if voided:
                value += f"**VOIDED**: {void_reason or 'No reason provided.'}\n"
            embed.add_field(name="\u200b", value=value, inline=False)
        now_utc = datetime.datetime.utcnow().strftime("UTC %Y-%m-%d %H:%M:%S")
        embed.set_footer(text=f"Generated: {now_utc}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="blacklist-by-id", description="Blacklist a user from HRMC by user ID (useful if they're not in the server).")
    @app_commands.describe(
        user_id="User ID to blacklist",
        reason="Reason for blacklist",
        proof="Proof file",
        hrmc_wide="Is this blacklist HRMC-wide?",
        ban="Ban the user from the server?"
    )
    async def blacklist_by_id_command(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str,
        proof: Optional[discord.Attachment] = None,
        hrmc_wide: bool = False,
        ban: bool = False
    ):
        if not any(r.id == BLACKLIST_ROLE_ID for r in getattr(interaction.user, "roles", [])):
            await interaction.response.send_message("You do not have permission to blacklist users.", ephemeral=True)
            return

        try:
            user_obj = await self.bot.fetch_user(int(user_id))
            user_display = f"{user_obj} ({user_obj.id})"
        except Exception:
            user_obj = None
            user_display = f"Unknown User ({user_id})"

        log_command_to_txt(
            "blacklist-by-id",
            interaction.user,
            interaction.channel,
            target_user=user_display,
            reason=reason,
            proof=proof.url if proof else "None",
            hrmc_wide=hrmc_wide,
            ban=ban
        )

        proof_url = proof.url if proof else None
        blacklist_id = str(uuid.uuid4())
        channel = interaction.guild.get_channel(BLACKLIST_VIEW_CHANNEL_ID)
        embed = self.get_blacklist_embed(
            blacklist_id, user_display, interaction.user, reason, proof_url, datetime.datetime.utcnow().isoformat(), hrmc_wide, ban
        )
        # Only send the embed to the log channel, with only the ping in content (no ping if user not in server)
        content = user_obj.mention if user_obj and hasattr(user_obj, "mention") else user_display
        if proof and proof.content_type and proof.content_type.startswith("image/"):
            embed.set_image(url=proof.url)
            msg = await channel.send(content=content, embed=embed)
        elif proof:
            msg = await channel.send(content=content, embed=embed, file=await proof.to_file())
        else:
            msg = await channel.send(content=content, embed=embed)

        # HRMC-wide: publish announcement
        if hrmc_wide and channel.is_news():
            try:
                await msg.publish()
            except Exception:
                pass

        # DM the blacklisted user (if possible)
        if user_obj:
            try:
                dm_embed = discord.Embed(
                    title=f"{EMOJI_HRMC} // HRMC Blacklist",
                    description=(
                        f"You have been blacklisted in **{interaction.guild.name}**.\n\n"
                        f"{EMOJI_REASON} **Reason:** {reason}\n"
                        f"{EMOJI_ID} **Blacklist ID:** {blacklist_id}\n"
                        f"{EMOJI_PERMISSION} **HRMC-wide:** {'Yes' if hrmc_wide else 'No'}\n"
                        f"{EMOJI_PERMISSION} **Banned:** {'Yes' if ban else 'No'}"
                    ),
                    color=discord.Color.dark_red()
                )
                if proof and proof.content_type and proof.content_type.startswith("image/"):
                    dm_embed.set_image(url=proof.url)
                await user_obj.send(embed=dm_embed)
            except Exception:
                pass

        # Ban if requested (only if user is in the guild)
        member = None
        try:
            member = await interaction.guild.fetch_member(int(user_id))
        except Exception:
            pass
        if ban and member:
            try:
                await member.ban(reason=f"Blacklisted: {reason}")
            except Exception:
                await interaction.followup.send("Failed to ban the user. Please check my permissions.", ephemeral=True)

        # Add blacklisted role if user is in the guild
        try:
            if member:
                role = interaction.guild.get_role(BLACKLISTED_ROLE_ID)
                if role and role not in member.roles:
                    await member.add_roles(role, reason="HRMC Blacklisted")
        except Exception:
            pass

        await self.add_blacklist(
            blacklist_id, user_display, interaction.user, reason, proof_url, msg.id, hrmc_wide, ban
        )

        log_to_file(
            interaction.user.id,
            interaction.channel.id,
            f"Blacklisted {user_display} | Reason: {reason} | Blacklist ID: {blacklist_id} | HRMC-wide: {hrmc_wide} | Ban: {ban}",
            embed=True
        )

        # Log to logging channel
        log_channel = interaction.guild.get_channel(BLACKLIST_LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="Blacklist Issued (by ID)",
                color=discord.Color.dark_red(),
                timestamp=datetime.datetime.utcnow()
            )
            log_embed.add_field(name="User", value=user_display, inline=False)
            log_embed.add_field(name="By", value=f"{interaction.user} ({interaction.user.id})", inline=False)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.add_field(name="Blacklist ID", value=blacklist_id, inline=False)
            log_embed.add_field(name="HRMC-wide", value="Yes" if hrmc_wide else "No", inline=True)
            log_embed.add_field(name="Banned", value="Yes" if ban else "No", inline=True)
            log_embed.set_footer(text=f"Logged at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            await log_channel.send(embed=log_embed)

        await interaction.response.send_message(f"User blacklisted by ID and logged. Blacklist ID: {blacklist_id}", ephemeral=True)

    @app_commands.command(name="blacklist-test", description="Test the blacklist command with a user ID.")
    @app_commands.describe(user_id="User ID to test with")
    async def blacklist_test_command(self, interaction: discord.Interaction, user_id: str):
        try:
            user_obj = await self.bot.fetch_user(int(user_id))
            await interaction.response.send_message(f"User found: {user_obj} (ID: {user_obj.id})", ephemeral=True)
        except Exception:
            await interaction.response.send_message(f"User not found for ID: {user_id}", ephemeral=True)

    @app_commands.command(name="blacklist-remove-role", description="Remove the blacklisted role from a user.")
    @app_commands.describe(user="User to remove the role from")
    async def blacklist_remove_role_command(self, interaction: discord.Interaction, user: discord.Member):
        try:
            if not any(r.id == BLACKLIST_ROLE_ID for r in getattr(interaction.user, "roles", [])):
                await interaction.response.send_message("You do not have permission to remove blacklisted roles.", ephemeral=True)
                return

            role = interaction.guild.get_role(BLACKLISTED_ROLE_ID)
            if not role:
                await interaction.response.send_message("Blacklisted role not found.", ephemeral=True)
                return

            if role not in user.roles:
                await interaction.response.send_message("User does not have the blacklisted role.", ephemeral=True)
                return

            await user.remove_roles(role, reason="Blacklist removed")
            await interaction.response.send_message(f"Removed blacklisted role from {user}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="blacklist-info", description="Get information about your blacklist status.")
    async def blacklist_info_command(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT blacklist_id, reason, date, hrmc_wide, ban, voided, void_reason FROM blacklist WHERE user_id = ? ORDER BY date DESC",
                    (user_id,)
                )
                rows = await cursor.fetchall()

            if not rows:
                await interaction.response.send_message("You are not blacklisted.", ephemeral=True)
                return

            # Create an embed for the blacklist information
            embed = discord.Embed(
                title="Your Blacklist Information",
                color=discord.Color.orange()
            )
            for row in rows:
                blacklist_id, reason, date, hrmc_wide, ban, voided, void_reason = row
                value = (
                    f"{EMOJI_REASON} **Reason:** {reason}\n"
                    f"**Date:** {date}\n"
                    f"{EMOJI_ID} **ID:** `{blacklist_id}`\n"
                    f"{EMOJI_PERMISSION} **HRMC-wide:** {'Yes' if hrmc_wide else 'No'}\n"
                    f"{EMOJI_PERMISSION} **Banned:** {'Yes' if ban else 'No'}\n"
                )
                if voided:
                    value += f"**VOIDED**: {void_reason or 'No reason provided.'}\n"
                embed.add_field(name="\u200b", value=value, inline=False)
            now_utc = datetime.datetime.utcnow().strftime("UTC %Y-%m-%d %H:%M:%S")
            embed.set_footer(text=f"Generated: {now_utc}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    # ...inside the Blacklist class...
    def get_blacklist_embed(self, blacklist_id, user, issued_by, reason, proof, date, hrmc_wide, ban, voided=False, void_reason=None):
        try:
            dt = datetime.datetime.fromisoformat(date)
            date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            date_str = date

        separator = "------------------------------"

        embed = discord.Embed(
            color=discord.Color.green() if voided else discord.Color.dark_red()
        )
        embed.add_field(
            name=f"{EMOJI_HRMC} // HRMC Blacklist",
            value=user.mention if hasattr(user, "mention") else str(user),
            inline=False
        )
        embed.add_field(name=f"{EMOJI_MEMBER} User", value=f"{user}", inline=True)
        embed.add_field(name=f"{EMOJI_MEMBER} Issued by", value=f"{issued_by}", inline=True)
        embed.add_field(name=separator, value=separator, inline=False)
        embed.add_field(name=f"{EMOJI_REASON} Reason", value=reason, inline=False)
        embed.add_field(name=f"{EMOJI_ID} Blacklist ID", value=f"`{blacklist_id}`", inline=False)
        embed.add_field(name=separator, value=separator, inline=False)
        embed.add_field(name=f"{EMOJI_PERMISSION} HRMC-wide", value="Yes" if hrmc_wide else "No", inline=True)
        embed.add_field(name=f"{EMOJI_PERMISSION} Banned", value="Yes" if ban else "No", inline=True)
        embed.add_field(name="Proof", value=proof or "None", inline=True)
        if voided:
            embed.add_field(
                name=f"{EMOJI_VOIDED} Voided",
                value="Yes",
                inline=True
            )
            embed.add_field(
                name=f"{EMOJI_REASON} Voided Reason",
                value=void_reason or 'No reason provided.',
                inline=True
            )
        embed.set_footer(text=f"{date_str}")
        return embed

async def setup(bot: commands.Bot):
    await bot.add_cog(Blacklist(bot))