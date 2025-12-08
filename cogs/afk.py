
import discord
from discord.ext import commands
from discord import app_commands
import os
import datetime
import aiosqlite
import json
from typing import Optional, Dict, List
from collections import defaultdict

AFK_LOG_CHANNEL_ID = 1343686645815181382
AFK_ADMIN_ROLE_IDS = {1329910241835352064}  # Only this role can use afkremove
AFK_LOG_FILE = os.path.join("logs", "afk.txt")
AFK_DB_FILE = os.path.join("data", "afk.db")
AFK_ACTIVITY_FILE = os.path.join("data", "activity_tracking.json")
AFK_PREFIX = "[AFK] "

class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.afk_messages = {}  # user_id: (message, timestamp)
        self.activity_data = {}  # user_id: List[{"status": str, "timestamp": str}]
        self.load_activity_data()

    def load_activity_data(self):
        """Load activity tracking data from JSON file."""
        if os.path.exists(AFK_ACTIVITY_FILE):
            try:
                with open(AFK_ACTIVITY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Convert string keys to int keys
                    self.activity_data = {int(k): v for k, v in data.items()}
            except Exception as e:
                print(f"Error loading activity data: {e}")
                self.activity_data = {}
        else:
            self.activity_data = {}

    def save_activity_data(self):
        """Save activity tracking data to JSON file."""
        try:
            with open(AFK_ACTIVITY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.activity_data, f, indent=2)
        except Exception as e:
            print(f"Error saving activity data: {e}")

    def record_message_activity(self, user_id: int):
        """Record when a user sends a message in the server."""
        if user_id not in self.activity_data:
            self.activity_data[user_id] = []
        
        now = datetime.datetime.utcnow()
        timestamp = now.isoformat()
        
        # Throttle: don't record if last message was less than 1 hour ago
        # This prevents spam while still capturing meaningful activity patterns
        if self.activity_data[user_id]:
            last_entry = self.activity_data[user_id][-1]
            try:
                last_time = datetime.datetime.fromisoformat(last_entry["timestamp"])
                if (now - last_time).total_seconds() < 3600:  # Less than 1 hour
                    return  # Too soon, skip
            except Exception:
                pass
        
        self.activity_data[user_id].append({
            "timestamp": timestamp
        })
        
        # Keep only last 30 days of data to prevent file from growing too large
        cutoff = (now - datetime.timedelta(days=30)).isoformat()
        self.activity_data[user_id] = [
            entry for entry in self.activity_data[user_id]
            if entry["timestamp"] >= cutoff
        ]
        
        self.save_activity_data()

    def get_usually_active_time(self, user_id: int) -> Optional[str]:
        """Calculate and return the usually active time frame for a user based on message activity."""
        try:
            # Ensure user_id is an int
            user_id = int(user_id)
            
            if user_id not in self.activity_data or not self.activity_data[user_id]:
                return None
            
            # Count message activity by hour (UTC)
            hour_counts = defaultdict(int)
            message_entries = self.activity_data[user_id]
            
            if len(message_entries) < 5:  # Need at least 5 message data points
                return None
            
            for entry in message_entries:
                try:
                    timestamp_str = entry.get("timestamp")
                    if not timestamp_str:
                        continue
                    dt = datetime.datetime.fromisoformat(timestamp_str)
                    hour = dt.hour
                    hour_counts[hour] += 1
                except Exception:
                    continue
            
            if not hour_counts:
                return None
            
            # Find the most active hours
            sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
            if not sorted_hours:
                return None
            
            # Get hours that are at least 50% as active as the most active hour
            max_count = sorted_hours[0][1]
            threshold = max(1, max_count * 0.5)
            active_hours = [h for h, count in sorted_hours if count >= threshold]
            
            if not active_hours:
                return None
            
            # Find the continuous range
            active_hours.sort()
            if len(active_hours) == 1:
                start_hour = active_hours[0]
                end_hour = active_hours[0]
            else:
                # Find the longest continuous range
                start_hour = active_hours[0]
                end_hour = active_hours[0]
                current_start = active_hours[0]
                current_end = active_hours[0]
                
                for i in range(1, len(active_hours)):
                    if active_hours[i] == current_end + 1:
                        current_end = active_hours[i]
                    else:
                        if current_end - current_start > end_hour - start_hour:
                            start_hour = current_start
                            end_hour = current_end
                        current_start = active_hours[i]
                        current_end = active_hours[i]
                
                if current_end - current_start > end_hour - start_hour:
                    start_hour = current_start
                    end_hour = current_end
            
            # Format as short time (e.g., "2:00 PM - 8:00 PM")
            def format_hour(hour):
                if hour == 0:
                    return "12:00 AM"
                elif hour < 12:
                    return f"{hour}:00 AM"
                elif hour == 12:
                    return "12:00 PM"
                else:
                    return f"{hour - 12}:00 PM"
            
            if start_hour == end_hour:
                return format_hour(start_hour)
            else:
                return f"{format_hour(start_hour)} - {format_hour(end_hour)}"
        except Exception as e:
            print(f"Error in get_usually_active_time for user {user_id}: {e}")
            return None

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
            description=f"**AFK Message:**\n> {text}\n\nOthers will be notified if they mention you.",
            color=discord.Color.blurple()
        )
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        # Add usually active time if available
        usually_active = self.get_usually_active_time(ctx.author.id)
        if usually_active:
            embed.add_field(name="Usually Active", value=usually_active, inline=False)
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
            description=f"**AFK Message:**\n> {text}\n\nOthers will be notified if they mention you.",
            color=discord.Color.blurple()
        )
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        # Add usually active time if available
        usually_active = self.get_usually_active_time(interaction.user.id)
        if usually_active:
            embed.add_field(name="Usually Active", value=usually_active, inline=False)
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
        # Only allow users with the specific admin role
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

    @app_commands.command(name="usuallyactive", description="Check when a user usually sends messages in the server.")
    @app_commands.describe(member="The member to check (defaults to yourself)")
    async def usually_active_slash(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """Show when a user usually sends messages in the server."""
        target = member or interaction.user
        usually_active = self.get_usually_active_time(target.id)
        
        embed = discord.Embed(
            title="🕐 Usually Active",
            color=discord.Color.blurple()
        )
        embed.set_author(name=str(target), icon_url=target.display_avatar.url)
        
        if usually_active:
            embed.description = f"**Usually Active:** {usually_active}"
            embed.set_footer(text="Based on message activity in the server (UTC time)")
        else:
            embed.description = "Not enough activity data available yet.\n\nActivity tracking requires at least 5 messages to calculate usually active times."
            embed.set_footer(text="Activity is tracked automatically when you send messages in the server")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Removed on_presence_update listener - now tracking based on messages only

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Track message activity for "usually active" calculation
        # Only tracks messages in guilds (not DMs)
        if message.guild:
            self.record_message_activity(message.author.id)

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
                # Add usually active time if available
                try:
                    usually_active = self.get_usually_active_time(user_id)
                    if usually_active:
                        embed.add_field(name="Usually Active", value=usually_active, inline=False)
                except Exception as e:
                    # Silently fail if there's an error calculating usually active time
                    print(f"Error getting usually active time for user {user_id}: {e}")
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
            # Add usually active time if available
            try:
                usually_active = self.get_usually_active_time(message.author.id)
                if usually_active:
                    embed.add_field(name="Usually Active", value=usually_active, inline=False)
            except Exception as e:
                print(f"Error getting usually active time for user {message.author.id}: {e}")
            await message.channel.send(embed=embed)
            self.log_afk_action("Removed (Self)", message.author)
            if message.guild:
                await self.send_afk_log_embed(message.guild, "Removed (Self)", message.author)
#test
async def setup(bot):
    await bot.add_cog(AFK(bot))