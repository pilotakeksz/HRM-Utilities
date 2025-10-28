import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
import string
from collections import defaultdict

# Constants
IMMUNE_USER_ID = 840949634071658507
IMMUNE_ROLE_ID = 1329910230066401361
QUARANTINE_ROLE_ID = 1432834406791254058
ADMIN_ROLE_ID = 1355842403134603275
LOG_CHANNEL_ID = 1432834042755289178
QUARANTINE_NOTIFY_CHANNEL_ID = 1355842403134603275
ALLOWED_CHANNEL_ID = 1329910457409994772
GUILD_ID = 1329908357812981882  # Your guild ID

# Thresholds
SPAM_MESSAGE_THRESHOLD = 5  # messages
SPAM_TIME_WINDOW = 3  # seconds
GIF_SPAM_THRESHOLD = 3  # gifs
EMOJI_ADD_LIMIT = 5  # per hour
ROLE_CHANGES_LIMIT = 30  # per hour
CHANNEL_CREATE_LIMIT = 3  # per hour

# Punishments
MUTE_DURATION = 180  # 3 minutes
QUARANTINE_DURATION = 172800  # 2 days

# File paths
DATA_DIR = "data"
LOGS_DIR = "logs"
QUARANTINE_FILE = os.path.join(DATA_DIR, "quarantine_data.json")
ACTION_LOG_FILE = os.path.join(LOGS_DIR, "raid_protection.log")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(
    filename=ACTION_LOG_FILE,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('RaidProtection')

class RaidProtection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_counts = defaultdict(list)
        self.gif_counts = defaultdict(list)
        self.emoji_counts = defaultdict(int)
        self.role_changes = defaultdict(int)
        self.channel_creates = defaultdict(int)
        self.quarantined_users = {}
        self.load_quarantine_data()
        self.check_quarantines.start()
        self.reset_counters.start()
        
    def cog_unload(self):
        self.check_quarantines.cancel()
        self.reset_counters.cancel()

    def load_quarantine_data(self):
        try:
            with open(QUARANTINE_FILE, 'r') as f:
                self.quarantined_users = json.load(f)
        except FileNotFoundError:
            self.quarantined_users = {}

    def save_quarantine_data(self):
        with open(QUARANTINE_FILE, 'w') as f:
            json.dump(self.quarantined_users, f)

    async def log_action(self, action: str, user: discord.Member, reason: str, duration: Optional[int] = None):
        embed = discord.Embed(
            title=f"Raid Protection: {action}",
            description=f"Action taken against {user.mention}",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Reason", value=reason)
        if duration:
            embed.add_field(name="Duration", value=f"{duration} seconds")
        
        # Log to file
        logger.info(f"{action}: {user.id} - {reason}")
        
        # Log to channel
        channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)

    async def quarantine_user(self, user: discord.Member, reason: str):
        if user.id == IMMUNE_USER_ID or any(role.id == IMMUNE_ROLE_ID for role in user.roles):
            return

        # Store roles before removing
        roles = [role.id for role in user.roles if role.id != user.guild.id]
        
        # Remove roles and add quarantine role
        await user.remove_roles(*user.roles)
        quarantine_role = user.guild.get_role(QUARANTINE_ROLE_ID)
        await user.add_roles(quarantine_role)
        
        # Store quarantine data
        self.quarantined_users[str(user.id)] = {
            "roles": roles,
            "reason": reason,
            "timestamp": datetime.utcnow().timestamp(),
            "duration": QUARANTINE_DURATION
        }
        self.save_quarantine_data()

        # Create confirmation buttons
        class QuarantineActions(discord.ui.View):
            def __init__(self, cog: 'RaidProtection'):
                super().__init__(timeout=None)
                self.token = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
                self.cog = cog

            @discord.ui.button(label="Unquarantine", style=discord.ButtonStyle.green)
            async def unquarantine(self, interaction: discord.Interaction, button: discord.ui.Button):
                if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
                    await interaction.response.send_message("You don't have permission.", ephemeral=True)
                    return
                
                try:
                    roles = self.cog.quarantined_users.get(str(user.id), {}).get("roles", [])
                    await self.cog.restore_roles(user, roles)
                    del self.cog.quarantined_users[str(user.id)]
                    self.cog.save_quarantine_data()
                    await interaction.response.send_message(f"Unquarantined {user.mention}", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

            @discord.ui.button(label="Kick", style=discord.ButtonStyle.orange)
            async def kick(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.get_role(ADMIN_ROLE_ID):
                    await interaction.response.send_message(f"To confirm kick, type: {self.token}", ephemeral=True)
                    
                    def check(m):
                        return m.author == interaction.user and m.content == self.token
                    
                    try:
                        await interaction.client.wait_for('message', timeout=30.0, check=check)
                        await user.kick(reason="Suspicious activity")
                        await interaction.followup.send(f"Kicked {user.name}")
                    except asyncio.TimeoutError:
                        await interaction.followup.send("Kick cancelled", ephemeral=True)

            @discord.ui.button(label="Ban", style=discord.ButtonStyle.red)
            async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.get_role(ADMIN_ROLE_ID):
                    await interaction.response.send_message(f"To confirm ban, type: {self.token}", ephemeral=True)
                    
                    def check(m):
                        return m.author == interaction.user and m.content == self.token
                    
                    try:
                        await interaction.client.wait_for('message', timeout=30.0, check=check)
                        await user.ban(reason="Suspicious activity")
                        await interaction.followup.send(f"Banned {user.name}")
                    except asyncio.TimeoutError:
                        await interaction.followup.send("Ban cancelled", ephemeral=True)

        # Send notification
        notify_channel = self.bot.get_channel(QUARANTINE_NOTIFY_CHANNEL_ID)
        if notify_channel:
            embed = discord.Embed(
                title="User Quarantined",
                description=f"{user.mention} has been quarantined",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason)
            embed.add_field(name="Duration", value="2 days")
            await notify_channel.send(
                content=f"<@&{ADMIN_ROLE_ID}>",
                embed=embed,
                view=QuarantineActions(self)  # Pass self (cog instance)
            )

        # DM user
        try:
            await user.send(f"You have been quarantined in {user.guild.name} for: {reason}")
        except:
            pass

        await self.log_action("QUARANTINE", user, reason, QUARANTINE_DURATION)

    @tasks.loop(minutes=5)
    async def check_quarantines(self):
        try:
            now = datetime.utcnow().timestamp()
            for user_id, data in list(self.quarantined_users.items()):
                if now - data["timestamp"] >= data["duration"]:
                    guild = self.bot.get_guild(1329908357812981882)
                    if guild:
                        member = guild.get_member(int(user_id))
                        if member:
                            await self.restore_roles(member, data["roles"])
                            del self.quarantined_users[user_id]
                            self.save_quarantine_data()
                            logger.info(f"Auto-unquarantined user {user_id}")
        except Exception as e:
            logger.error(f"Error in check_quarantines: {str(e)}")

    @check_quarantines.before_loop
    async def before_check_quarantines(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Spam check
        self.message_counts[message.author.id].append(datetime.utcnow())
        recent_messages = [t for t in self.message_counts[message.author.id] 
                         if (datetime.utcnow() - t).seconds <= SPAM_TIME_WINDOW]
        self.message_counts[message.author.id] = recent_messages

        if len(recent_messages) >= SPAM_MESSAGE_THRESHOLD:
            await message.author.timeout(duration=MUTE_DURATION)
            await self.log_action("MUTE", message.author, "Message spam", MUTE_DURATION)

        # GIF spam check
        if any(attach.filename.endswith('.gif') for attach in message.attachments):
            self.gif_counts[message.author.id].append(datetime.utcnow())
            recent_gifs = [t for t in self.gif_counts[message.author.id]
                         if (datetime.utcnow() - t).seconds <= SPAM_TIME_WINDOW]
            self.gif_counts[message.author.id] = recent_gifs

            if len(recent_gifs) >= GIF_SPAM_THRESHOLD:
                await message.author.timeout(duration=MUTE_DURATION)
                await self.log_action("MUTE", message.author, "GIF spam", MUTE_DURATION)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        try:
            # Ensure we're in the right guild
            if channel.guild.id != GUILD_ID:
                return
                
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                if entry.created_at < (datetime.utcnow() - timedelta(seconds=5)):
                    return
                    
                if not self.has_bypass(entry.user):
                    logger.info(f"Channel delete detected by {entry.user}")
                    await self.quarantine_user(entry.user, "Unauthorized channel deletion")
        except Exception as e:
            logger.error(f"Error in channel delete event: {str(e)}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        try:
            if channel.guild.id != GUILD_ID:
                return
                
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                if entry.created_at < (datetime.utcnow() - timedelta(seconds=5)):
                    return
                    
                if not self.has_bypass(entry.user):
                    self.channel_creates[entry.user.id] += 1
                    if self.channel_creates[entry.user.id] > CHANNEL_CREATE_LIMIT:
                        await self.quarantine_user(entry.user, "Excessive channel creation")
        except Exception as e:
            logger.error(f"Error in channel create event: {str(e)}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        try:
            if role.guild.id != GUILD_ID:
                return
                
            async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
                if entry.created_at < (datetime.utcnow() - timedelta(seconds=5)):
                    return
                    
                if not self.has_bypass(entry.user):
                    await self.quarantine_user(entry.user, "Unauthorized role deletion")
        except Exception as e:
            logger.error(f"Error in role delete event: {str(e)}")

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        try:
            if guild.id != GUILD_ID:
                return
                
            # Check if emojis were removed
            removed_emojis = set(before) - set(after)
            added_emojis = set(after) - set(before)
            
            if removed_emojis or added_emojis:
                async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.emoji_update):
                    if entry.created_at < (datetime.utcnow() - timedelta(seconds=5)):
                        return
                        
                    if not self.has_bypass(entry.user):
                        self.emoji_counts[entry.user.id] += 1
                        if self.emoji_counts[entry.user.id] > EMOJI_ADD_LIMIT:
                            reason = "Excessive emoji changes"
                            if removed_emojis:
                                reason = "Unauthorized emoji deletion"
                            await self.quarantine_user(entry.user, reason)
        except Exception as e:
            logger.error(f"Error in emoji update event: {str(e)}")

    # Add this method to reset counters periodically
    @tasks.loop(hours=1)
    async def reset_counters(self):
        """Reset all counters every hour"""
        self.emoji_counts.clear()
        self.channel_creates.clear()
        self.role_changes.clear()
        logger.info("Reset all action counters")

    @app_commands.command(name="quarantine", description="Manually quarantine a user")
    @app_commands.describe(
        user="The user to quarantine",
        reason="Reason for quarantine",
        duration="Duration in days (default: 2)"
    )
    async def quarantine_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        duration: Optional[float] = 2.0
    ):
        # Check if user has admin role
        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message(
                "You need the admin role to use this command.",
                ephemeral=True
            )
            return

        # Check if target user has immunity
        if self.has_bypass(user):
            await interaction.response.send_message(
                "This user has immunity from quarantine.",
                ephemeral=True
            )
            return

        # Convert days to seconds
        duration_seconds = int(duration * 86400)  # 86400 seconds in a day

        # Store original duration for later use
        self.quarantined_users[str(user.id)] = {
            "roles": [role.id for role in user.roles if role.id != user.guild.id],
            "reason": reason,
            "timestamp": datetime.utcnow().timestamp(),
            "duration": duration_seconds
        }
        self.save_quarantine_data()

        # Remove roles and add quarantine role
        await user.remove_roles(*user.roles)
        quarantine_role = interaction.guild.get_role(QUARANTINE_ROLE_ID)
        if quarantine_role:
            await user.add_roles(quarantine_role)

        # Create embed for response
        embed = discord.Embed(
            title="Manual Quarantine",
            description=f"{user.mention} has been quarantined",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Duration", value=f"{duration} days")
        embed.add_field(name="Quarantined by", value=interaction.user.mention)

        # Log the action
        await self.log_action(
            "MANUAL_QUARANTINE",
            user,
            f"Quarantined by {interaction.user} for: {reason}",
            duration_seconds
        )

        # Try to DM the user
        try:
            await user.send(
                f"You have been quarantined in {interaction.guild.name} for: {reason}\n"
                f"Duration: {duration} days"
            )
        except:
            embed.add_field(
                name="Note",
                value="Could not DM user about quarantine",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    async def restore_roles(self, member: discord.Member, role_ids: List[int]):
        """Restore roles to a member after quarantine"""
        try:
            # Remove quarantine role
            quarantine_role = member.guild.get_role(QUARANTINE_ROLE_ID)
            if quarantine_role and quarantine_role in member.roles:
                await member.remove_roles(quarantine_role)

            # Add back original roles
            roles_to_add = []
            for role_id in role_ids:
                role = member.guild.get_role(role_id)
                if role:
                    roles_to_add.append(role)
            
            if roles_to_add:
                await member.add_roles(*roles_to_add)
                
            # Log the restoration
            await self.log_action(
                "ROLES_RESTORED", 
                member, 
                f"Restored {len(roles_to_add)} roles after quarantine"
            )
            
            # Try to DM user
            try:
                await member.send(f"Your roles in {member.guild.name} have been restored.")
            except:
                pass

        except discord.Forbidden:
            logger.error(f"Failed to restore roles for {member.id} - Missing Permissions")
        except Exception as e:
            logger.error(f"Failed to restore roles for {member.id} - {str(e)}")

    def has_bypass(self, user: discord.Member) -> bool:
        return (user.id == IMMUNE_USER_ID or 
                any(role.id == IMMUNE_ROLE_ID for role in user.roles))

async def setup(bot):
    await bot.add_cog(RaidProtection(bot))