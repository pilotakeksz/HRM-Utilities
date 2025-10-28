import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import logging
import asyncio
from datetime import datetime, timedelta, timezone
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
QUARANTINE_NOTIFY_CHANNEL_ID = 1432834815450943651
ALLOWED_CHANNEL_ID = 1329910457409994772
GUILD_ID = 1329908357812981882  # Your guild ID
SPECIAL_ROLE_ID = 1329910361347854388

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
LEFT_RESTORE_FILE = os.path.join(DATA_DIR, "left_restore.json")

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
        self.left_restore = {}
        self.load_quarantine_data()
        self.load_left_restore()
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

    def load_left_restore(self):
        try:
            with open(LEFT_RESTORE_FILE, 'r') as f:
                self.left_restore = json.load(f)
        except FileNotFoundError:
            self.left_restore = {}

    def save_left_restore(self):
        with open(LEFT_RESTORE_FILE, 'w') as f:
            json.dump(self.left_restore, f)

    async def log_action(self, action: str, user: discord.Member, reason: str, duration: Optional[int] = None):
        embed = discord.Embed(
            title=f"Raid Protection: {action}",
            description=f"Action taken against {user.mention}",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
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

        # Store roles before removing (exclude @everyone and the quarantine role itself)
        roles = [role.id for role in user.roles if role != user.guild.default_role and role.id != QUARANTINE_ROLE_ID]

        # Remove roles one-by-one with error handling to avoid Unknown Role or permission errors
        for role in list(user.roles):
            # Skip @everyone and any already-quarantine role
            if role == user.guild.default_role or role.id == QUARANTINE_ROLE_ID:
                continue
            try:
                await user.remove_roles(role, reason="Quarantine")
            except discord.NotFound:
                logger.warning(f"Role {role.id} not found while removing from user {user.id}")
            except discord.Forbidden:
                logger.warning(f"Missing permission to remove role {role.id} from user {user.id}")
            except Exception as e:
                logger.error(f"Error removing role {role.id} from user {user.id}: {e}")

        # Add the quarantine role if available
        quarantine_role = user.guild.get_role(QUARANTINE_ROLE_ID)
        if quarantine_role:
            try:
                await user.add_roles(quarantine_role, reason="Quarantine")
            except Exception as e:
                logger.error(f"Failed to add quarantine role {QUARANTINE_ROLE_ID} to user {user.id}: {e}")
        else:
            logger.error(f"Quarantine role {QUARANTINE_ROLE_ID} not found in guild {user.guild.id}")
        
        # Store quarantine data
        self.quarantined_users[str(user.id)] = {
            "roles": roles,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).timestamp(),
            "duration": QUARANTINE_DURATION
        }
        

        # Create confirmation buttons
        class QuarantineActions(discord.ui.View):
            def __init__(self, cog: 'RaidProtection'):
                super().__init__(timeout=None)
                self.token = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
                self.cog = cog
                self.used = False

            async def disable_all_buttons(self):
                for item in self.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True
                return self

            async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
                logger.error(f"Error in button interaction: {error}")
                await interaction.response.send_message("An error occurred processing this action.", ephemeral=True)

            @discord.ui.button(label="Unquarantine", style=discord.ButtonStyle.success)
            async def unquarantine(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.used:
                    await interaction.response.send_message("This action has already been used.", ephemeral=True)
                    return

                if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
                    await interaction.response.send_message("You don't have permission.", ephemeral=True)
                    return
                
                try:
                    self.used = True
                    roles = self.cog.quarantined_users.get(str(user.id), {}).get("roles", [])
                    await self.cog.restore_roles(user, roles)
                    del self.cog.quarantined_users[str(user.id)]
                    self.cog.save_quarantine_data()
                    
                    embed = discord.Embed(
                        title="User Unquarantined",
                        description=f"{user.mention} has been unquarantined by {interaction.user.mention}",
                        color=discord.Color.green()
                    )
                    await self.disable_all_buttons()
                    await interaction.message.edit(view=self)
                    await interaction.response.send_message(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to unquarantine: {e}")
                    await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

            @discord.ui.button(label="Kick", style=discord.ButtonStyle.blurple)
            async def kick(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.used:
                    await interaction.response.send_message("This action has already been used.", ephemeral=True)
                    return

                if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
                    await interaction.response.send_message("You don't have permission.", ephemeral=True)
                    return

                # Ask for confirmation token from the admin
                await interaction.response.send_message(f"To confirm kick, type: {self.token}", ephemeral=True)

                def check(m):
                    return m.author == interaction.user and m.content == self.token

                try:
                    await interaction.client.wait_for('message', timeout=30.0, check=check)
                    await user.kick(reason="Suspicious activity")
                    self.used = True
                    
                    embed = discord.Embed(
                        title="User Kicked",
                        description=f"{user.name} has been kicked by {interaction.user.mention}",
                        color=discord.Color.blue()
                    )
                    await self.disable_all_buttons()
                    await interaction.message.edit(view=self)
                    await interaction.followup.send(embed=embed)
                except asyncio.TimeoutError:
                    await interaction.followup.send("Kick cancelled", ephemeral=True)

            @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger)
            async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.used:
                    await interaction.response.send_message("This action has already been used.", ephemeral=True)
                    return

                if not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
                    await interaction.response.send_message("You don't have permission.", ephemeral=True)
                    return

                # Ask for confirmation token from the admin
                await interaction.response.send_message(f"To confirm ban, type: {self.token}", ephemeral=True)

                def check(m):
                    return m.author == interaction.user and m.content == self.token

                try:
                    await interaction.client.wait_for('message', timeout=30.0, check=check)
                    await user.ban(reason="Suspicious activity")
                    self.used = True
                    
                    embed = discord.Embed(
                        title="User Banned",
                        description=f"{user.name} has been banned by {interaction.user.mention}",
                        color=discord.Color.red()
                    )
                    await self.disable_all_buttons()
                    await interaction.message.edit(view=self)
                    await interaction.followup.send(embed=embed)
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

    async def _fetch_audit_actor(self, guild: discord.Guild, action: discord.AuditLogAction, target_check=None, attempts: int = 3, delay: float = 1.0):
        """Try to fetch the audit log entry actor for a given action. Retries a few times because audit logs can be delayed."""
        try:
            for attempt in range(attempts):
                try:
                    async for entry in guild.audit_logs(limit=10, action=action):
                        if target_check is None or target_check(entry):
                            return entry.user
                except discord.Forbidden:
                    logger.error("Missing permission to read audit logs")
                    return None
                except Exception as e:
                    logger.error(f"Error reading audit logs: {e}")
                await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"_fetch_audit_actor failed: {e}")
        return None

    @tasks.loop(minutes=5)
    async def check_quarantines(self):
        try:
            now = datetime.now(timezone.utc).timestamp()
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
            
        # Mass ping and @everyone/@here check
        if not self.has_bypass(message.author):
            mention_count = len(message.mentions) + len(message.role_mentions)
            has_everyone = message.mention_everyone
            
            if has_everyone or mention_count >= 10:
                ping_details = []
                if has_everyone:
                    if "@everyone" in message.content:
                        ping_details.append("@everyone")
                    if "@here" in message.content:
                        ping_details.append("@here")
                
                if message.mentions:
                    ping_details.append(f"Users mentioned: {', '.join([f'{u.name} ({u.id})' for u in message.mentions])}")
                if message.role_mentions:
                    ping_details.append(f"Roles mentioned: {', '.join([f'{r.name} ({r.id})' for r in message.role_mentions])}")
                
                reason = "Mass ping detected\n" + "\n".join(ping_details)
                try:
                    # Try to delete the message first
                    await message.delete()
                except:
                    pass
                await self.quarantine_user(message.author, reason)
                return

        # Spam check
        now_dt = datetime.now(timezone.utc)
        self.message_counts[message.author.id].append(now_dt)
        recent_messages = [t for t in self.message_counts[message.author.id]
                         if (now_dt - t).seconds <= SPAM_TIME_WINDOW]
        self.message_counts[message.author.id] = recent_messages

        if len(recent_messages) >= SPAM_MESSAGE_THRESHOLD:
            # Member.timeout expects an 'until' datetime in newer discord.py versions
            try:
                until = datetime.now(timezone.utc) + timedelta(seconds=MUTE_DURATION)
                await message.author.timeout(until=until)
            except TypeError:
                # Fallback: some versions accept a seconds integer; try that
                try:
                    await message.author.timeout(MUTE_DURATION)
                except Exception as e:
                    logger.error(f"Failed to timeout member {message.author.id}: {e}")
            except Exception as e:
                logger.error(f"Failed to timeout member {message.author.id}: {e}")
            await self.log_action("MUTE", message.author, "Message spam", MUTE_DURATION)

        # GIF spam check
        if any(attach.filename.endswith('.gif') for attach in message.attachments):
            now_dt = datetime.now(timezone.utc)
            self.gif_counts[message.author.id].append(now_dt)
            recent_gifs = [t for t in self.gif_counts[message.author.id]
                         if (now_dt - t).seconds <= SPAM_TIME_WINDOW]
            self.gif_counts[message.author.id] = recent_gifs

            if len(recent_gifs) >= GIF_SPAM_THRESHOLD:
                try:
                    until = datetime.now(timezone.utc) + timedelta(seconds=MUTE_DURATION)
                    await message.author.timeout(until=until)
                except TypeError:
                    try:
                        await message.author.timeout(MUTE_DURATION)
                    except Exception as e:
                        logger.error(f"Failed to timeout member {message.author.id}: {e}")
                except Exception as e:
                    logger.error(f"Failed to timeout member {message.author.id}: {e}")
                await self.log_action("MUTE", message.author, "GIF spam", MUTE_DURATION)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        try:
            # Ensure we're in the right guild
            if channel.guild.id != GUILD_ID:
                return
            # Try to find the actor from audit logs (with retry)
            def check_target(e):
                try:
                    return getattr(e.target, 'id', None) == channel.id
                except Exception:
                    return False

            actor = await self._fetch_audit_actor(channel.guild, discord.AuditLogAction.channel_delete, target_check=check_target)
            if actor is None:
                logger.info(f"Channel deleted but actor not found in audit logs: {channel.name} ({channel.id})")
                return

            if not self.has_bypass(actor):
                channel_info = f"Channel Details:\n- Name: #{channel.name}\n- ID: {channel.id}\n- Type: {str(channel.type)}"
                if hasattr(channel, 'category') and channel.category:
                    channel_info += f"\n- Category: {channel.category.name} ({channel.category.id})"
                
                logger.info(f"Channel delete detected by {actor} ({actor.id})")
                await self.quarantine_user(actor, f"Unauthorized channel deletion\n{channel_info}\nDeleted by: {actor.name} ({actor.id})")
        except Exception as e:
            logger.error(f"Error in channel delete event: {str(e)}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        try:
            if channel.guild.id != GUILD_ID:
                return
            def check_target(e):
                try:
                    return getattr(e.target, 'id', None) == channel.id
                except Exception:
                    return False

            actor = await self._fetch_audit_actor(channel.guild, discord.AuditLogAction.channel_create, target_check=check_target)
            if actor is None:
                logger.info(f"Channel created but actor not found in audit logs: {channel.name} ({channel.id})")
                return

            if not self.has_bypass(actor):
                self.channel_creates[actor.id] += 1
                if self.channel_creates[actor.id] > CHANNEL_CREATE_LIMIT:
                    await self.quarantine_user(actor, "Excessive channel creation")
        except Exception as e:
            logger.error(f"Error in channel create event: {str(e)}")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        try:
            if role.guild.id != GUILD_ID:
                return
            def check_target(e):
                try:
                    return getattr(e.target, 'id', None) == role.id
                except Exception:
                    return False

            actor = await self._fetch_audit_actor(role.guild, discord.AuditLogAction.role_delete, target_check=check_target)
            if actor is None:
                logger.info(f"Role deleted but actor not found in audit logs: {role.name} ({role.id})")
                return

            if not self.has_bypass(actor):
                await self.quarantine_user(actor, "Unauthorized role deletion")
        except Exception as e:
            logger.error(f"Error in role delete event: {str(e)}")

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        try:
            if guild.id != GUILD_ID:
                return
            # Compare by ID to avoid object-equality quirks
            before_emojis = {e.id: e for e in before}
            after_emojis = {e.id: e for e in after}
            removed_emojis = {id: emoji for id, emoji in before_emojis.items() if id not in after_emojis}
            added_emojis = {id: emoji for id, emoji in after_emojis.items() if id not in before_emojis}

            # Handle deletions
            if removed_emojis:
                actor = await self._fetch_audit_actor(guild, discord.AuditLogAction.emoji_delete, target_check=None)
                if actor and not self.has_bypass(actor):
                    deleted_info = "\n".join([f"- {e.name} ({e.id}) {str(e)}" for e in removed_emojis.values()])
                    self.emoji_counts[actor.id] += len(removed_emojis)
                    if self.emoji_counts[actor.id] > EMOJI_ADD_LIMIT:
                        await self.quarantine_user(actor, f"Unauthorized emoji deletion\nDeleted emojis:\n{deleted_info}\nDeleted by: {actor.name} ({actor.id})")

            # Handle additions
            if added_emojis:
                actor = await self._fetch_audit_actor(guild, discord.AuditLogAction.emoji_create, target_check=None)
                if actor and not self.has_bypass(actor):
                    added_info = "\n".join([f"- {e.name} ({e.id}) {str(e)}" for e in added_emojis.values()])
                    self.emoji_counts[actor.id] += len(added_emojis)
                    if self.emoji_counts[actor.id] > EMOJI_ADD_LIMIT:
                        await self.quarantine_user(actor, f"Excessive emoji additions\nAdded emojis:\n{added_info}\nAdded by: {actor.name} ({actor.id})")
        except Exception as e:
            logger.error(f"Error in emoji update event: {str(e)}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Auto-ban users who leave while quarantined or holding SPECIAL_ROLE_ID.

        If a user leaves the guild while they have the quarantine role (or the special role),
        ban them to prevent evasion. Record the action in the quarantine file for auditing.
        """
        try:
            # member.guild may be None in some edge cases; guard
            if not member.guild or member.guild.id != GUILD_ID:
                return

            role_ids = [r.id for r in member.roles if r.id != member.guild.id]
            had_quarantine = QUARANTINE_ROLE_ID in role_ids
            had_special = SPECIAL_ROLE_ID in role_ids
            if had_quarantine or had_special:
                reason = "Left while quarantined or held special role"
                try:
                    await member.guild.ban(member, reason=reason, delete_message_days=0)
                    logger.info(f"Auto-banned user {member.id} for leaving while quarantined/special")
                except Exception as e:
                    logger.error(f"Failed to ban user {member.id} on leave: {e}")

                # Record in quarantine file for audit/history
                self.quarantined_users[str(member.id)] = {
                    "roles": role_ids,
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                    "duration": 0,
                    "banned_on_leave": True
                }
                self.save_quarantine_data()

                await self.log_action("AUTO_BAN_ON_LEAVE", member, reason)
        except Exception as e:
            logger.error(f"Error in on_member_remove: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Restore roles for users who rejoin and were recorded in left_restore."""
        try:
            if member.guild.id != GUILD_ID:
                return
            entry = self.left_restore.get(str(member.id))
            if not entry:
                return

            role_ids = entry.get("roles", [])
            roles_to_add = []
            for rid in role_ids:
                role = member.guild.get_role(int(rid))
                if role:
                    roles_to_add.append(role)

            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add, reason="Restore on rejoin")
                    logger.info(f"Restored {len(roles_to_add)} roles to rejoining user {member.id}")
                except Exception as e:
                    logger.error(f"Failed to restore roles on join for {member.id}: {e}")

            # remove stored entry
            try:
                del self.left_restore[str(member.id)]
                self.save_left_restore()
            except KeyError:
                pass
        except Exception as e:
            logger.error(f"Error in on_member_join: {e}")

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

        # Store roles before removing them
        stored_roles = [role.id for role in user.roles if role.id != user.guild.id]
        
        # Remove roles one by one with error handling
        for role in user.roles:
            if role != user.guild.default_role:  # Skip removing @everyone role
                try:
                    await user.remove_roles(role, reason="Quarantine")
                except discord.NotFound:
                    logger.warning(f"Role {role.id} not found while quarantining {user.id}")
                    continue
                except discord.Forbidden:
                    logger.warning(f"Cannot remove role {role.id} from {user.id} - Missing Permissions")
                    continue
                except Exception as e:
                    logger.error(f"Error removing role {role.id} from {user.id}: {str(e)}")
                    continue

        # Convert days to seconds
        duration_seconds = int(duration * 86400)

        # Add quarantine role
        try:
            quarantine_role = interaction.guild.get_role(QUARANTINE_ROLE_ID)
            if quarantine_role:
                await user.add_roles(quarantine_role, reason="Quarantine")
            else:
                logger.error(f"Quarantine role {QUARANTINE_ROLE_ID} not found")
                await interaction.response.send_message(
                    "Error: Quarantine role not found. Please check configuration.",
                    ephemeral=True
                )
                return
        except Exception as e:
            logger.error(f"Error adding quarantine role to {user.id}: {str(e)}")
            await interaction.response.send_message(
                f"Error adding quarantine role: {str(e)}",
                ephemeral=True
            )
            return

        # Store quarantine data
        self.quarantined_users[str(user.id)] = {
            "roles": stored_roles,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).timestamp(),
            "duration": duration_seconds
        }
        self.save_quarantine_data()

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
                f"Duration: {duration} days\n"
                f"Should you leave the server before you resolve your quarantine, you will be banned."
            )
        except:
            embed.add_field(
                name="Note",
                value="Could not DM user about quarantine",
                inline=False
            )

        try:
            await interaction.response.send_message(embed=embed)
        except (discord.NotFound, discord.HTTPException) as e:
            try:
                await interaction.followup.send(embed=embed)
            except Exception as e2:
                logger.error(f"Failed to send interaction response for quarantine_command: {e}; {e2}")

    @app_commands.command(name="unquarantine", description="Unquarantine a user (admin only)")
    @app_commands.describe(user="The user to unquarantine")
    async def unquarantine_command(self, interaction: discord.Interaction, user: discord.Member):
        # Permission check
        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You need the admin role to use this command.", ephemeral=True)
            return

        entry = self.quarantined_users.get(str(user.id))
        if not entry:
            await interaction.response.send_message("That user is not in the quarantine list.", ephemeral=True)
            return

        roles = entry.get("roles", [])
        # restore roles and remove quarantine role
        try:
            await self.restore_roles(user, roles)
        except Exception as e:
            logger.error(f"Error restoring roles for unquarantine {user.id}: {e}")

        # remove from persisted quarantine list
        try:
            del self.quarantined_users[str(user.id)]
            self.save_quarantine_data()
        except KeyError:
            pass

        # DM and respond
        try:
            await user.send(f"You have been unquarantined in {interaction.guild.name} by {interaction.user}.")
        except:
            pass

        try:
            await self.log_action("MANUAL_UNQUARANTINE", user, f"Unquarantined by {interaction.user}")
        except Exception:
            logger.exception("Failed to log manual unquarantine")

        try:
            await interaction.response.send_message(f"Unquarantined {user.mention}")
        except (discord.NotFound, discord.HTTPException) as e:
            try:
                await interaction.followup.send(f"Unquarantined {user.mention}")
            except Exception as e2:
                logger.error(f"Failed to send interaction response for unquarantine_command: {e}; {e2}")

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