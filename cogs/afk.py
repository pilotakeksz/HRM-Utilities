import discord
from discord.ext import commands
from discord import app_commands
import os
import datetime
import aiosqlite
from typing import Optional

AFK_LOG_CHANNEL_ID = 1343686645815181382
AFK_ADMIN_ROLE_IDS = {1329910265264869387, 1329910241835352064}
AFK_LOG_FILE = os.path.join("logs", "afk.txt")
AFK_DB_FILE = os.path.join("data", "afk.db")
AFK_PREFIX = "[AFK] "

class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.afk_messages = {}  # user_id: (message, timestamp)

    async def cog_load(self):
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        async with aiosqlite.connect(AFK_DB_FILE) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS afk (
                    user_id INTEGER PRIMARY KEY,
                    message TEXT,
                    timestamp TEXT
                )
            """)
            await db.commit()
            async with db.execute("SELECT user_id, message, timestamp FROM afk") as cursor:
                async for row in cursor:
                    self.afk_messages[row[0]] = (row[1], row[2])

    async def set_afk(self, user: discord.Member, message: str):
        timestamp = datetime.datetime.utcnow().isoformat()
        self.afk_messages[user.id] = (message, timestamp)
        async with aiosqlite.connect(AFK_DB_FILE) as db:
            await db.execute(
                "INSERT OR REPLACE INTO afk (user_id, message, timestamp) VALUES (?, ?, ?)",
                (user.id, message, timestamp)
            )
            await db.commit()
        await self.set_afk_nick(user)

    async def remove_afk(self, user: discord.Member):
        self.afk_messages.pop(user.id, None)
        async with aiosqlite.connect(AFK_DB_FILE) as db:
            await db.execute("DELETE FROM afk WHERE user_id = ?", (user.id,))
            await db.commit()
        await self.remove_afk_nick(user)

    def log_afk_action(self, action: str, user: discord.User, moderator: discord.abc.User = None, reason: str = None):
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open(AFK_LOG_FILE, "a", encoding="utf-8") as f:
            if moderator:
                f.write(f"[{now}] {action} | User: {user} ({user.id}) | By: {moderator} ({moderator.id}) | Reason: {reason or ''}\n")
            else:
                f.write(f"[{now}] {action} | User: {user} ({user.id})\n")

    async def send_afk_log_embed(self, guild, action, user, moderator=None, reason=None, afk_message=None):
        channel = guild.get_channel(AFK_LOG_CHANNEL_ID)
        if not channel:
            return
        emoji = "💤" if action == "Set" else ("✅" if action.startswith("Removed") else "⚠️")
        embed = discord.Embed(
            title=f"{emoji} AFK {action}",
            color=discord.Color.blue() if action == "Set" else (discord.Color.green() if action.startswith("Removed") else discord.Color.orange()),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        if moderator:
            embed.add_field(name="By", value=f"{moderator} ({moderator.id})", inline=False)
        if afk_message:
            embed.add_field(name="AFK Message", value=afk_message, inline=False)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        await channel.send(embed=embed)

    async def set_afk_nick(self, member: discord.Member):
        if not member.display_name.startswith(AFK_PREFIX):
            try:
                await member.edit(nick=f"{AFK_PREFIX}{member.display_name}"[:32], reason="Set AFK")
            except discord.Forbidden:
                pass

    async def remove_afk_nick(self, member: discord.Member):
        if member.display_name.startswith(AFK_PREFIX):
            try:
                await member.edit(nick=member.display_name[len(AFK_PREFIX):], reason="Remove AFK")
            except discord.Forbidden:
                pass

    @commands.command(name="afk")
    async def afk_command(self, ctx, *, text: str = "AFK"):
        """Set your AFK message."""
        await self.set_afk(ctx.author, text)
        embed = discord.Embed(
            title="💤 You are now AFK!",
            description=f"**AFK Message:**\n> {text}\n\n"
                        f"Others will be notified if they mention you.",
            color=discord.Color.blurple()
        )
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Use !afkremove or send a message to remove AFK.")
        await ctx.send(embed=embed)
        self.log_afk_action("Set", ctx.author)
        await self.send_afk_log_embed(ctx.guild, "Set", ctx.author, afk_message=text)

    @app_commands.command(name="afk", description="Set your AFK message.")
    @app_commands.describe(text="Your AFK message")
    async def afk_slash(self, interaction: discord.Interaction, text: str = "AFK"):
        member = interaction.guild.get_member(interaction.user.id)
        if member:
            await self.set_afk(member, text)
        embed = discord.Embed(
            title="💤 You are now AFK!",
            description=f"**AFK Message:**\n> {text}\n\n"
                        f"Others will be notified if they mention you.",
            color=discord.Color.blurple()
        )
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="Use /afkremove or send a message to remove AFK.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.log_afk_action("Set", interaction.user)
        await self.send_afk_log_embed(interaction.guild, "Set", interaction.user, afk_message=text)

    @commands.command(name="afkremove")
    @commands.has_any_role(*AFK_ADMIN_ROLE_IDS)
    async def afk_remove_command(self, ctx, member: discord.Member, *, reason: str = None):
        """Admin: Remove someone's AFK status."""
        if member.id in self.afk_messages:
            await self.remove_afk(member)
            embed = discord.Embed(
                title="✅ AFK Removed",
                description=f"{member.mention}'s AFK status has been **removed**.\n"
                            f"{'**Reason:** ' + reason if reason else ''}",
                color=discord.Color.green()
            )
            embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
            embed.set_footer(text="AFK status managed by admin.")
            await ctx.send(embed=embed)
            self.log_afk_action("Removed (Admin)", member, ctx.author, reason)
            await self.send_afk_log_embed(ctx.guild, "Removed (Admin)", member, moderator=ctx.author, reason=reason)
        else:
            await ctx.send(f"{member.mention} is not AFK.", delete_after=10)

    @app_commands.command(name="afkremove", description="Admin: Remove someone's AFK status.")
    @app_commands.describe(member="The member to remove AFK from", reason="Reason for removal")
    async def afk_remove_slash(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
        if not any(r.id in AFK_ADMIN_ROLE_IDS for r in getattr(interaction.user, "roles", [])):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        if member.id in self.afk_messages:
            await self.remove_afk(member)
            embed = discord.Embed(
                title="✅ AFK Removed",
                description=f"{member.mention}'s AFK status has been **removed**.\n"
                            f"{'**Reason:** ' + reason if reason else ''}",
                color=discord.Color.green()
            )
            embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text="AFK status managed by admin.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.log_afk_action("Removed (Admin)", member, interaction.user, reason)
            await self.send_afk_log_embed(interaction.guild, "Removed (Admin)", member, moderator=interaction.user, reason=reason)
        else:
            await interaction.response.send_message(f"{member.mention} is not AFK.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # If someone is mentioned and is AFK, respond with their AFK message (no pings)
        mentioned_ids = {user.id for user in message.mentions if not user.bot}
        for user_id in mentioned_ids:
            if user_id in self.afk_messages:
                afk_text, timestamp = self.afk_messages[user_id]
                embed = discord.Embed(
                    title="💤 AFK Notice",
                    description=f"**That user is currently AFK:**\n> {afk_text}",
                    color=discord.Color.blurple()
                )
                embed.set_footer(text="They will see your message when they return.")
                await message.channel.send(embed=embed)

        # If the author is AFK and sends a message, remove their AFK (but not if they're using the afk command)
        if message.author.id in self.afk_messages and not message.content.lower().startswith("!afk") and not message.content.lower().startswith("/afk"):
            await self.remove_afk(message.author)
            embed = discord.Embed(
                title="✅ Welcome Back!",
                description="Your AFK status has been **removed**. Others will no longer see your AFK message.",
                color=discord.Color.green()
            )
            embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
            await message.channel.send(embed=embed)
            self.log_afk_action("Removed (Self)", message.author)
            if message.guild:
                await self.send_afk_log_embed(message.guild, "Removed (Self)", message.author)

async def setup(bot):
    await bot.add_cog(AFK(bot))