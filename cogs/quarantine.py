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
import inspect

# Constants
IMMUNE_USER_ID = 840949634071658507
BOT = 1387175664649506847
IMMUNE_ROLE_ID = 1329910230066401361
QUARANTINE_ROLE_ID = 1432834406791254058
ADMIN_ROLE_ID = 1355842403134603275
LOG_CHANNEL_ID = 1432834042755289178
QUARANTINE_NOTIFY_CHANNEL_ID = 1432834815450943651
ALLOWED_CHANNEL_ID = 1329910457409994772
GUILD_ID = 1329908357812981882  # Your guild ID
SPECIAL_ROLE_ID = 1329910361347854388

# Thresholds
SPAM_MESSAGE_THRESHOLD = 10  # messages
SPAM_TIME_WINDOW = 5  # seconds
GIF_SPAM_THRESHOLD = 3  # gifs
EMOJI_ADD_LIMIT = 5  # per hour
ROLE_CHANGES_LIMIT = 30  # per hour
CHANNEL_CREATE_LIMIT = 3  # per hour
# Additional raid detection thresholds
JOIN_RAID_THRESHOLD = 8  # joins
JOIN_TIME_WINDOW = 20  # seconds
BAN_THRESHOLD = 5  # bans by one actor
BAN_TIME_WINDOW = 60  # seconds

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
        # Track recent mute events per user (timestamps)
        self.mute_events = defaultdict(list)
        self.channel_creates = defaultdict(int)
        self.join_events = defaultdict(list)  # guild_id -> list of (timestamp, member_id)
        self.ban_events = defaultdict(list)   # actor_id -> list of timestamps
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

    async def quarantine_user(self, user, reason: str):
        # Resolve to a guild Member if a User was passed (audit-log actors may be User objects)
        member = None
        try:
            if isinstance(user, discord.Member):
                member = user
            else:
                guild = self.bot.get_guild(GUILD_ID)
                if guild:
                    # try cached member first
                    member = guild.get_member(getattr(user, 'id', None))
                    if member is None and getattr(user, 'id', None) is not None:
                        try:
                            member = await guild.fetch_member(user.id)
                        except Exception:
                            member = None
        except Exception:
            member = None

        if member is None:
            logger.error(f"Cannot resolve guild member to quarantine for user id {getattr(user, 'id', None)}")
            return

        # Use member from here on
        user = member

        # Final bypass check - only one check needed (protected user OR protected role)
        if self.has_bypass(user):
            return

        # Store roles before removing (exclude @everyone and the quarantine role itself)
        roles = [role.id for role in user.roles if role != user.guild.default_role and role.id != QUARANTINE_ROLE_ID]

        # Remove roles top-down (highest position first) - sort by position descending
        roles_to_remove = [
            role for role in user.roles 
            if role != user.guild.default_role and role.id != QUARANTINE_ROLE_ID
        ]
        
        # Sort by position (highest position = highest number = remove first)
        roles_to_remove.sort(key=lambda r: r.position, reverse=True)

        # Remove roles one-by-one with error handling (top-down order)
        for role in roles_to_remove:
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
        try:
            self.save_quarantine_data()
        except Exception:
            pass

        # Attempt to timeout (mute) the user for the quarantine duration
        try:
            until = datetime.now(timezone.utc) + timedelta(seconds=QUARANTINE_DURATION)
            try:
                await user.timeout(until=until)
            except TypeError:
                try:
                    await user.timeout(timedelta(seconds=QUARANTINE_DURATION))
                except Exception as e:
                    logger.error(f"Failed to timeout/quarantine member {user.id}: {e}")
        except Exception as e:
            logger.error(f"Failed to apply timeout to quarantined user {user.id}: {e}")
        

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
                    # defer because restoring roles may take time and make it public
                    try:
                        await interaction.response.defer()
                    except Exception:
                        pass

                    self.used = True
                    roles = self.cog.quarantined_users.get(str(user.id), {}).get("roles", [])

                    # send an initial progress message to update live
                    try:
                        progress_embed = discord.Embed(
                            title="Unquarantining user...",
                            description=f"Restoring roles to {user.mention}",
                            color=discord.Color.green()
                        )
                        progress_embed.add_field(name="Roles restored", value="0", inline=True)
                        progress_embed.add_field(name="Last role added", value="None", inline=True)
                        progress_msg = await interaction.followup.send(embed=progress_embed, wait=True)
                    except Exception:
                        progress_msg = None

                    added = await self.cog.restore_roles(user, roles, progress_message=progress_msg)
                    try:
                        del self.cog.quarantined_users[str(user.id)]
                        self.cog.save_quarantine_data()
                    except KeyError:
                        pass
                    
                    embed = discord.Embed(
                        title="User Unquarantined",
                        description=f"{user.mention} has been unquarantined by {interaction.user.mention}",
                        color=discord.Color.green()
                    )
                    embed.add_field(name="Roles restored", value=f"{added} roles restored", inline=False)
                    await self.disable_all_buttons()
                    try:
                        await interaction.message.edit(view=self)
                    except Exception:
                        pass

                    # Edit the progress message into the final embed if possible
                    try:
                        if progress_msg:
                            await progress_msg.edit(embed=embed)
                        else:
                            await interaction.followup.send(embed=embed)
                    except Exception:
                        try:
                            await interaction.followup.send(embed=embed)
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"Failed to unquarantine: {e}")
                    try:
                        await interaction.followup.send(f"Error: {str(e)}")
                    except Exception:
                        try:
                            await interaction.response.send_message(f"Error: {str(e)}")
                        except Exception:
                            pass

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
                    # Try to DM the user before kicking so they are notified
                    try:
                        em = discord.Embed(
                            title="You have been kicked",
                            description=f"You have been kicked from **{interaction.guild.name}** by {interaction.user} for: Suspicious activity",
                            color=discord.Color.blue(),
                            timestamp=datetime.now(timezone.utc)
                        )
                        em.set_footer(text="Contact server staff for appeal")
                        await user.send(embed=em)
                    except Exception:
                        pass
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
                    # Try to DM the user before banning so they are notified
                    try:
                        em = discord.Embed(
                            title="You have been banned",
                            description=f"You have been banned from **{interaction.guild.name}** by {interaction.user} for: Suspicious activity",
                            color=discord.Color.red(),
                            timestamp=datetime.now(timezone.utc)
                        )
                        em.set_footer(text="Contact server staff for appeal")
                        await user.send(embed=em)
                    except Exception:
                        pass
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

        # DM user with embed
        try:
            em = discord.Embed(
                title="You have been quarantined",
                description=f"You have been quarantined in **{user.guild.name}** for: {reason}",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            em.set_footer(text="Contact server staff for help")
            await user.send(embed=em)
        except Exception:
            pass

        await self.log_action("QUARANTINE", user, reason, QUARANTINE_DURATION)

    async def _fetch_audit_actor(self, guild: discord.Guild, action: discord.AuditLogAction, target_check=None, attempts: int = 3, delay: float = 1.0):
        """Try to fetch the audit log entry actor for a given action. Retries a few times because audit logs can be delayed."""
        try:
            for attempt in range(attempts):
                try:
                    logger.debug(f"Searching audit logs for action={action} (attempt {attempt+1}/{attempts})")
                    async for entry in guild.audit_logs(limit=50, action=action):
                        if target_check is None:
                            return entry.user

                        try:
                            result = target_check(entry)
                            # If target_check returned a coroutine, await it
                            if inspect.isawaitable(result):
                                result = await result
                        except Exception as e:
                            logger.error(f"Error in target_check: {e}")
                            result = False

                        if result:
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

    def _prune_old(self, lst, window_seconds: int):
        """Prune timestamps older than window_seconds from a list of datetimes/seconds in-place."""
        cutoff = datetime.now(timezone.utc).timestamp() - window_seconds
        # support list of tuples (timestamp, id) or plain timestamps
        if not lst:
            return lst
        if isinstance(lst[0], tuple):
            return [item for item in lst if item[0] >= cutoff]
        else:
            return [ts for ts in lst if ts >= cutoff]

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

    def detect_mass_ping(self, message: discord.Message):
        """Bulletproof detection of @everyone, @here, and mass pings.
        Returns (should_quarantine, reason)"""
        content = message.content or ""
        content_lower = content.lower()
        
        # Bulletproof @everyone/@here detection - check multiple ways
        has_everyone = False
        has_here = False
        
        # PRIMARY: Check Discord's built-in flag (most reliable - catches all @everyone/@here)
        # Discord's mention_everyone flag is True for BOTH @everyone and @here
        if message.mention_everyone:
            # Check content to determine which one(s) were used
            if "@here" in content_lower or "@\u200bhere" in content_lower or "@\u200chere" in content_lower:
                has_here = True
            # If mention_everyone is True, it's either @everyone or both
            # We'll treat it as @everyone if @here isn't explicitly found
            if not has_here or "@everyone" in content_lower:
                has_everyone = True
        
        # SECONDARY: Check content for various @everyone/@here patterns (case-insensitive)
        # This catches edge cases where Discord's flag might miss (very rare)
        everyone_patterns = [
            "@everyone",  # Normal
            "@\u200beveryone", "@\u200ceveryone", "@\u200deveryone",  # Zero-width spaces
            "@ｅｖｅｒｙｏｎｅ",  # Full-width characters
            "@ｅveryone", "@everyｏne",  # Mixed
            "@everyonе",  # Cyrillic 'е' instead of 'e'
        ]
        
        here_patterns = [
            "@here",  # Normal
            "@\u200bhere", "@\u200chere", "@\u200dhere",  # Zero-width spaces
            "@ｈｅｒｅ",  # Full-width characters
            "@hｅre", "@herｅ",  # Mixed
            "@hеre",  # Cyrillic 'е' instead of 'e'
        ]
        
        # Check for patterns in content (backup detection)
        if not has_everyone:
            for pattern in everyone_patterns:
                if pattern.lower() in content_lower:
                    has_everyone = True
                    break
        
        if not has_here:
            for pattern in here_patterns:
                if pattern.lower() in content_lower:
                    has_here = True
                    break
        
        # Count mentions (users + roles) - this is separate from @everyone/@here
        mention_count = len(message.mentions) + len(message.role_mentions)
        
        # Check for mass mentions (lower threshold for better detection)
        mass_mention_threshold = 8  # Lowered from 10 for better detection
        
        should_quarantine = False
        reason_parts = []
        
        # @everyone and @here are ALWAYS quarantine-worthy
        if has_everyone:
            should_quarantine = True
            reason_parts.append("@everyone detected")
        
        if has_here:
            should_quarantine = True
            reason_parts.append("@here detected")
        
        # Mass mentions are also quarantine-worthy
        if mention_count >= mass_mention_threshold:
            should_quarantine = True
            reason_parts.append(f"Mass mention: {mention_count} mentions")
        
        if should_quarantine:
            details = []
            if has_everyone:
                details.append("@everyone")
            if has_here:
                details.append("@here")
            if message.mentions:
                details.append(f"Users: {len(message.mentions)}")
            if message.role_mentions:
                role_names = [r.name for r in message.role_mentions]
                details.append(f"Roles: {', '.join(role_names[:5])}" + ("..." if len(role_names) > 5 else ""))
            
            reason = "Mass ping/mention detected: " + " | ".join(reason_parts)
            if details:
                reason += "\nDetails: " + " | ".join(details)
            
            return True, reason
        
        return False, ""

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        # Only check bypass once - if protected, skip all checks
        if self.has_bypass(message.author):
            return
        
        # Check if user is interacting with a quarantined user
        # 1. Check if message mentions any quarantined users
        for mentioned_user in message.mentions:
            if self.is_quarantined(mentioned_user.id):
                try:
                    await message.delete()
                except:
                    pass
                await self.quarantine_user(
                    message.author, 
                    f"Interacted with quarantined user: {mentioned_user.name} ({mentioned_user.id})"
                )
                return
        
        # 2. Check if message is a reply to a quarantined user's message
        if message.reference and message.reference.resolved:
            referenced_message = message.reference.resolved
            if isinstance(referenced_message, discord.Message) and referenced_message.author:
                if self.is_quarantined(referenced_message.author.id):
                    try:
                        await message.delete()
                    except:
                        pass
                    await self.quarantine_user(
                        message.author,
                        f"Replied to quarantined user's message: {referenced_message.author.name} ({referenced_message.author.id})"
                    )
                    return
        
        # 3. Check if message is in a thread started by a quarantined user
        if message.channel and hasattr(message.channel, 'owner_id') and message.channel.owner_id:
            if self.is_quarantined(message.channel.owner_id):
                try:
                    await message.delete()
                except:
                    pass
                await self.quarantine_user(
                    message.author,
                    f"Interacted in thread created by quarantined user (thread owner: {message.channel.owner_id})"
                )
                return
            
        # Bulletproof mass ping and @everyone/@here check
        should_quarantine, reason = self.detect_mass_ping(message)
        
        if should_quarantine:
            try:
                # Try to delete the message first
                await message.delete()
            except:
                pass
            await self.quarantine_user(message.author, reason)
            return

        # Check if message author is quarantined (prevent them from sending messages)
        if self.is_quarantined(message.author.id):
            try:
                await message.delete()
            except:
                pass
            return

        # Spam check
        now_dt = datetime.now(timezone.utc)
        author_id = getattr(message.author, 'id', None)
        if author_id is None:
            return

        self.message_counts[author_id].append(now_dt)
        recent_messages = [t for t in self.message_counts[author_id]
                         if (now_dt - t).seconds <= SPAM_TIME_WINDOW]
        self.message_counts[author_id] = recent_messages

        if len(recent_messages) >= SPAM_MESSAGE_THRESHOLD:
            # Resolve to a guild Member so we can apply a timeout even if the user has no roles
            member = message.author
            if not isinstance(member, discord.Member):
                try:
                    if message.guild:
                        member = message.guild.get_member(author_id) or await message.guild.fetch_member(author_id)
                except Exception:
                    member = None

            if not member:
                logger.info(f"Unable to resolve member for timeout: {author_id}")
            else:
                # Skip immune users
                if not self.has_bypass(member):
                    # Check bot permissions in this guild before attempting timeout
                    try:
                        bot_member = member.guild.me or member.guild.get_member(self.bot.user.id)
                        bot_perms = bot_member.guild_permissions if bot_member else None
                        bot_has_mod = bool(bot_perms and getattr(bot_perms, 'moderate_members', False))
                        bot_has_admin = bool(bot_perms and getattr(bot_perms, 'administrator', False))
                        logger.info(f"Attempting timeout for member={member.id} guild={member.guild.id} bot_has_mod={bot_has_mod} bot_has_admin={bot_has_admin}")
                    except Exception:
                        bot_has_mod = False
                        bot_has_admin = False

                    if not (bot_has_mod or bot_has_admin):
                        logger.warning(f"Bot lacks Moderate Members/Admin permission in guild {member.guild.id}; cannot apply timeout to {member.id}")
                        try:
                            ch = self.bot.get_channel(LOG_CHANNEL_ID)
                            if ch:
                                await ch.send(f"Warning: Unable to timeout member {member.mention} ({member.id}) in guild {member.guild.id} — bot lacks Moderate Members permission.")
                        except Exception:
                            pass
                    else:
                        # Member.timeout expects an 'until' datetime in newer discord.py versions
                        try:
                            until = datetime.now(timezone.utc) + timedelta(seconds=MUTE_DURATION)
                            await member.timeout(until=until)
                            logger.info(f"Timed out member {member.id} for {MUTE_DURATION}s")
                        except TypeError:
                            # Fallback: try passing a timedelta
                            try:
                                await member.timeout(timedelta(seconds=MUTE_DURATION))
                                logger.info(f"Timed out member {member.id} for {MUTE_DURATION}s (timedelta fallback)")
                            except Exception as e:
                                logger.error(f"Failed to timeout member {member.id}: {e}")
                        except Exception as e:
                            logger.error(f"Failed to timeout member {member.id}: {e}")
                        await self.log_action("MUTE", member, "Message spam", MUTE_DURATION)
                        # Record mute event and quarantine if muted twice within 10 minutes
                        try:
                            now_ts = datetime.now(timezone.utc).timestamp()
                            self.mute_events[member.id].append(now_ts)
                            # prune to 10 minutes (600 seconds)
                            self.mute_events[member.id] = self._prune_old(self.mute_events[member.id], 600)
                            if len(self.mute_events[member.id]) >= 2:
                                # Quarantine the offending member
                                try:
                                    await self.quarantine_user(member, "Repeated mutes within 10 minutes")
                                except Exception as e:
                                    logger.error(f"Failed to auto-quarantine after repeated mutes for {member.id}: {e}")
                                # Notify quarantine notify channel
                                try:
                                    notify_ch = self.bot.get_channel(QUARANTINE_NOTIFY_CHANNEL_ID)
                                    if notify_ch:
                                        em = discord.Embed(
                                            title="User Auto-Quarantined",
                                            description=f"{member.mention} was quarantined for repeated mutes",
                                            color=discord.Color.red(),
                                            timestamp=datetime.now(timezone.utc)
                                        )
                                        em.add_field(name="Reason", value="Repeated mutes within 10 minutes")
                                        await notify_ch.send(content=f"<@&{ADMIN_ROLE_ID}>", embed=em)
                                except Exception:
                                    pass
                                # clear recent mute events for this user to avoid repeat
                                self.mute_events[member.id] = []
                        except Exception as e:
                            logger.error(f"Error handling mute events for {member.id}: {e}")

        # GIF spam check
        if any(attach.filename.endswith('.gif') for attach in message.attachments):
            now_dt = datetime.now(timezone.utc)
            author_id = getattr(message.author, 'id', None)
            if author_id is None:
                return
            self.gif_counts[author_id].append(now_dt)
            recent_gifs = [t for t in self.gif_counts[author_id]
                         if (now_dt - t).seconds <= SPAM_TIME_WINDOW]
            self.gif_counts[author_id] = recent_gifs

            if len(recent_gifs) >= GIF_SPAM_THRESHOLD:
                # Resolve to a guild Member so we can apply a timeout even if the user has no roles
                member = message.author
                if not isinstance(member, discord.Member):
                    try:
                        if message.guild:
                            member = message.guild.get_member(author_id) or await message.guild.fetch_member(author_id)
                    except Exception:
                        member = None

                if not member:
                    logger.info(f"Unable to resolve member for GIF timeout: {author_id}")
                else:
                    if not self.has_bypass(member):
                        # Check bot permissions before attempting timeout
                        try:
                            bot_member = member.guild.me or member.guild.get_member(self.bot.user.id)
                            bot_perms = bot_member.guild_permissions if bot_member else None
                            bot_has_mod = bool(bot_perms and getattr(bot_perms, 'moderate_members', False))
                            bot_has_admin = bool(bot_perms and getattr(bot_perms, 'administrator', False))
                            logger.info(f"Attempting GIF timeout for member={member.id} guild={member.guild.id} bot_has_mod={bot_has_mod} bot_has_admin={bot_has_admin}")
                        except Exception:
                            bot_has_mod = False
                            bot_has_admin = False

                        if not (bot_has_mod or bot_has_admin):
                            logger.warning(f"Bot lacks Moderate Members/Admin permission in guild {member.guild.id}; cannot apply timeout to {member.id}")
                            try:
                                ch = self.bot.get_channel(LOG_CHANNEL_ID)
                                if ch:
                                    await ch.send(f"Warning: Unable to timeout member {member.mention} ({member.id}) in guild {member.guild.id} — bot lacks Moderate Members permission.")
                            except Exception:
                                pass
                        else:
                            try:
                                until = datetime.now(timezone.utc) + timedelta(seconds=MUTE_DURATION)
                                await member.timeout(until=until)
                                logger.info(f"Timed out member {member.id} for GIF spam ({MUTE_DURATION}s)")
                            except TypeError:
                                try:
                                    await member.timeout(timedelta(seconds=MUTE_DURATION))
                                    logger.info(f"Timed out member {member.id} for GIF spam ({MUTE_DURATION}s) (timedelta fallback)")
                                except Exception as e:
                                    logger.error(f"Failed to timeout member {member.id}: {e}")
                            except Exception as e:
                                logger.error(f"Failed to timeout member {member.id}: {e}")
                            await self.log_action("MUTE", member, "GIF spam", MUTE_DURATION)
                            # Record mute event and quarantine if muted twice within 10 minutes
                            try:
                                now_ts = datetime.now(timezone.utc).timestamp()
                                self.mute_events[member.id].append(now_ts)
                                self.mute_events[member.id] = self._prune_old(self.mute_events[member.id], 600)
                                if len(self.mute_events[member.id]) >= 2:
                                    try:
                                        await self.quarantine_user(member, "Repeated mutes within 10 minutes")
                                    except Exception as e:
                                        logger.error(f"Failed to auto-quarantine after repeated GIF mutes for {member.id}: {e}")
                                    try:
                                        notify_ch = self.bot.get_channel(QUARANTINE_NOTIFY_CHANNEL_ID)
                                        if notify_ch:
                                            em = discord.Embed(
                                                title="User Auto-Quarantined",
                                                description=f"{member.mention} was quarantined for repeated mutes",
                                                color=discord.Color.red(),
                                                timestamp=datetime.now(timezone.utc)
                                            )
                                            em.add_field(name="Reason", value="Repeated mutes within 10 minutes")
                                            await notify_ch.send(content=f"<@&{ADMIN_ROLE_ID}>", embed=em)
                                    except Exception:
                                        pass
                                    self.mute_events[member.id] = []
                            except Exception as e:
                                logger.error(f"Error handling mute events for {member.id}: {e}")

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
    async def on_reaction_add(self, reaction: discord.Reaction, user):
        """Detect when someone reacts to a quarantined user's message."""
        if user.bot:
            return
        
        # Only check bypass once - if protected, skip all checks
        # Convert User to Member if needed for bypass check
        if isinstance(user, discord.User) and reaction.message.guild:
            member = reaction.message.guild.get_member(user.id)
            if member and self.has_bypass(member):
                return
        elif isinstance(user, discord.Member):
            if self.has_bypass(user):
                return
        
        # Check if the message author is quarantined
        if reaction.message.author and self.is_quarantined(reaction.message.author.id):
            try:
                await reaction.remove(user)
            except:
                pass
            # Resolve user to member for quarantine
            if isinstance(user, discord.User) and reaction.message.guild:
                member = reaction.message.guild.get_member(user.id)
                if member:
                    await self.quarantine_user(
                        member,
                        f"Reacted to quarantined user's message: {reaction.message.author.name} ({reaction.message.author.id})"
                    )
            elif isinstance(user, discord.Member):
                await self.quarantine_user(
                    user,
                    f"Reacted to quarantined user's message: {reaction.message.author.name} ({reaction.message.author.id})"
                )
            return

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Detect when someone modifies roles of a quarantined user."""
        if before.guild.id != GUILD_ID:
            return
        
        # Check if roles changed
        if before.roles == after.roles:
            return
        
        # Check if the member being updated is quarantined
        if not self.is_quarantined(after.id):
            return
        
        # Get the roles that were added/removed
        roles_before = set(before.roles)
        roles_after = set(after.roles)
        roles_added = roles_after - roles_before
        roles_removed = roles_before - roles_after
        
        # Ignore if only the quarantine role was added (that's expected)
        quarantine_role = after.guild.get_role(QUARANTINE_ROLE_ID)
        if quarantine_role:
            roles_added.discard(quarantine_role)
            roles_removed.discard(quarantine_role)
        
        # If no meaningful role changes, skip
        if not roles_added and not roles_removed:
            return
        
        # Fetch the audit log actor who made the change
        def check_target(e):
            try:
                return getattr(e.target, 'id', None) == after.id
            except Exception:
                return False
        
        actor = await self._fetch_audit_actor(
            after.guild, 
            discord.AuditLogAction.member_role_update,
            target_check=check_target
        )
        
        if actor is None:
            logger.info(f"Role change detected on quarantined user {after.id} but actor not found in audit logs")
            return
        
        # Check bypass
        if self.has_bypass(actor):
            return
        
        # Build reason with details
        reason_parts = [f"Modified roles of quarantined user: {after.name} ({after.id})"]
        if roles_added:
            role_names = [r.name for r in roles_added]
            reason_parts.append(f"Added roles: {', '.join(role_names[:5])}" + ("..." if len(role_names) > 5 else ""))
        if roles_removed:
            role_names = [r.name for r in roles_removed]
            reason_parts.append(f"Removed roles: {', '.join(role_names[:5])}" + ("..." if len(role_names) > 5 else ""))
        
        reason = " | ".join(reason_parts)
        
        # Quarantine the actor
        await self.quarantine_user(actor, reason)
        
        # Restore the quarantined user's roles to what they should be (remove added roles, re-add removed ones if they were original)
        try:
            # Remove any roles that were added
            if roles_added:
                await after.remove_roles(*roles_added, reason="Quarantine protection: removing unauthorized role additions")
            
            # Re-add roles that were removed (if they were part of the original roles)
            if roles_removed:
                # Check if removed roles were in the original stored roles
                stored_data = self.quarantined_users.get(str(after.id), {})
                original_roles = stored_data.get("roles", [])
                roles_to_restore = [r for r in roles_removed if r.id in original_roles]
                if roles_to_restore:
                    await after.add_roles(*roles_to_restore, reason="Quarantine protection: restoring removed roles")
        except Exception as e:
            logger.error(f"Error restoring roles for quarantined user {after.id} after unauthorized change: {e}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        try:
            if role.guild.id != GUILD_ID:
                return

            def check_target(e):
                try:
                    # role create entries may have target with id
                    return getattr(e.target, 'id', None) == role.id
                except Exception:
                    return False

            actor = await self._fetch_audit_actor(role.guild, discord.AuditLogAction.role_create, target_check=check_target)
            if actor is None:
                logger.info(f"Role created but actor not found in audit logs: {role.name} ({role.id})")
                return

            if not self.has_bypass(actor):
                # increment role change counter (uses same limit)
                now_ts = datetime.now(timezone.utc).timestamp()
                # store a timestamp list using role_changes mapping by replacing int with list if needed
                # we'll temporarily use role_changes as a list store by keying with actor.id in a separate structure
                if not hasattr(self, 'role_change_events'):
                    self.role_change_events = defaultdict(list)
                self.role_change_events[actor.id].append(now_ts)
                # prune
                self.role_change_events[actor.id] = self._prune_old(self.role_change_events[actor.id], 3600)
                if len(self.role_change_events[actor.id]) > ROLE_CHANGES_LIMIT:
                    await self.quarantine_user(actor, f"Excessive role changes ({len(self.role_change_events[actor.id])} in 1h)")
        except Exception as e:
            logger.error(f"Error in role create event: {str(e)}")

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
            # Debug: log that the event fired and show before/after counts
            try:
                logger.info(f"on_guild_emojis_update fired for guild {guild.id}: before={len(before)} after={len(after)}")
            except Exception:
                logger.info(f"on_guild_emojis_update fired for guild {getattr(guild, 'id', None)}")

            # Compare by ID to avoid object-equality quirks
            before_emojis = {e.id: e for e in before}
            after_emojis = {e.id: e for e in after}
            removed_emojis = {id: emoji for id, emoji in before_emojis.items() if id not in after_emojis}
            added_emojis = {id: emoji for id, emoji in after_emojis.items() if id not in before_emojis}

            logger.info(f"Emoji diff: removed={list(removed_emojis.keys())} added={list(added_emojis.keys())}")

            # Handle deletions
            if removed_emojis:
                # For each removed emoji, try to find the responsible audit log entry and attribute to that actor.
                for eid, emo in removed_emojis.items():
                    logger.info(f"Processing removed emoji {emo.name} ({eid})")
                    def _check(entry, _eid=eid, _ename=emo.name):
                        try:
                            # Check target_id if available
                            if getattr(entry, 'target_id', None) == _eid:
                                return True
                            # Some audit entries set entry.target to the emoji; compare id
                            if getattr(getattr(entry, 'target', None), 'id', None) == _eid:
                                return True
                            # Some entries include changes listing the old name/value; check that too
                            for ch in getattr(entry, 'changes', []) or []:
                                try:
                                    # changes may be dict-like for emoji objects
                                    old = getattr(ch, 'old', None)
                                    new = getattr(ch, 'new', None)
                                    attr = getattr(ch, 'attribute', None)
                                    # If old/new are dicts that contain 'id' or 'name'
                                    if isinstance(old, dict):
                                        if old.get('id') == _eid or old.get('name') == _ename:
                                            return True
                                    if isinstance(new, dict):
                                        if new.get('id') == _eid or new.get('name') == _ename:
                                            return True
                                    if attr in ('name',) and old == _ename:
                                        return True
                                except Exception:
                                    continue
                            return False
                        except Exception:
                            return False

                    # Increase attempts/delay to catch slightly delayed audit entries
                    actor = await self._fetch_audit_actor(guild, discord.AuditLogAction.emoji_delete, target_check=_check, attempts=5, delay=1.0)
                    if not actor:
                        # fallback: try generic emoji_delete entry (may be delayed)
                        actor = await self._fetch_audit_actor(guild, discord.AuditLogAction.emoji_delete, target_check=None, attempts=5, delay=1.0)

                    if not actor:
                        logger.info(f"Emoji deleted but actor not found for {emo.name} ({eid})")
                    else:
                        logger.info(f"Attributed deleted emoji {emo.name} ({eid}) to actor {actor} ({getattr(actor, 'id', None)})")

                    if actor and not self.has_bypass(actor):
                        self.emoji_counts[actor.id] += 1
                        # build deleted info for logging/notification
                        deleted_info = f"- {emo.name} ({emo.id}) {str(emo)}"
                        if self.emoji_counts[actor.id] > EMOJI_ADD_LIMIT:
                            await self.quarantine_user(actor, f"Unauthorized emoji deletion\nDeleted emoji:\n{deleted_info}\nDeleted by: {actor.name} ({actor.id})")

            # Handle additions
            if added_emojis:
                for aid, emo in added_emojis.items():
                    logger.info(f"Processing added emoji {emo.name} ({aid})")
                    def _check_add(entry, _aid=aid, _ename=emo.name):
                        try:
                            if getattr(entry, 'target_id', None) == _aid:
                                return True
                            if getattr(getattr(entry, 'target', None), 'id', None) == _aid:
                                return True
                            for ch in getattr(entry, 'changes', []) or []:
                                try:
                                    old = getattr(ch, 'old', None)
                                    new = getattr(ch, 'new', None)
                                    attr = getattr(ch, 'attribute', None)
                                    if isinstance(old, dict):
                                        if old.get('id') == _aid or old.get('name') == _ename:
                                            return True
                                    if isinstance(new, dict):
                                        if new.get('id') == _aid or new.get('name') == _ename:
                                            return True
                                    if attr in ('name',) and new == _ename:
                                        return True
                                except Exception:
                                    continue
                            return False
                        except Exception:
                            return False

                    actor = await self._fetch_audit_actor(guild, discord.AuditLogAction.emoji_create, target_check=_check_add, attempts=5, delay=1.0)
                    if not actor:
                        actor = await self._fetch_audit_actor(guild, discord.AuditLogAction.emoji_create, target_check=None, attempts=5, delay=1.0)

                    if not actor:
                        logger.info(f"Emoji created but actor not found for {emo.name} ({aid})")
                    else:
                        logger.info(f"Attributed added emoji {emo.name} ({aid}) to actor {actor} ({getattr(actor, 'id', None)})")

                    if actor and not self.has_bypass(actor):
                        self.emoji_counts[actor.id] += 1
                        added_info = f"- {emo.name} ({emo.id}) {str(emo)}"
                        if self.emoji_counts[actor.id] > EMOJI_ADD_LIMIT:
                            await self.quarantine_user(actor, f"Excessive emoji additions\nAdded emoji:\n{added_info}\nAdded by: {actor.name} ({actor.id})")
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
                    # Try to DM the user before banning so they are notified (may fail if user left or DMs closed)
                    try:
                        await member.send(f"You have been banned from {member.guild.name} for: {reason}")
                    except Exception:
                        pass
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
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Track bans and quarantine actors who ban many users in a short window."""
        try:
            if guild.id != GUILD_ID:
                return
            # Try to find the actor in audit logs
            def target_check(entry):
                try:
                    return getattr(entry.target, 'id', None) == user.id
                except Exception:
                    return False

            actor = await self._fetch_audit_actor(guild, discord.AuditLogAction.ban, target_check=target_check)
            if actor is None:
                return

            if self.has_bypass(actor):
                return

            now_ts = datetime.now(timezone.utc).timestamp()
            self.ban_events[actor.id].append(now_ts)
            # prune
            self.ban_events[actor.id] = self._prune_old(self.ban_events[actor.id], BAN_TIME_WINDOW)

            if len(self.ban_events[actor.id]) >= BAN_THRESHOLD:
                await self.quarantine_user(actor, f"Excessive bans detected ({len(self.ban_events[actor.id])} bans in {BAN_TIME_WINDOW}s)")
        except Exception as e:
            logger.error(f"Error in on_member_ban: {e}")

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

        # --- Join-raid detection ---
        try:
            # record join event
            now_ts = datetime.now(timezone.utc).timestamp()
            self.join_events[member.guild.id].append((now_ts, member.id))
            # prune old events
            self.join_events[member.guild.id] = self._prune_old(self.join_events[member.guild.id], JOIN_TIME_WINDOW)

            recent = self.join_events[member.guild.id]
            if len(recent) >= JOIN_RAID_THRESHOLD:
                # Quarantine recent joiners (the last JOIN_RAID_THRESHOLD entries)
                to_quarantine = [mid for (_, mid) in recent[-JOIN_RAID_THRESHOLD:]]
                quarantined = []
                for mid in to_quarantine:
                    try:
                        m = member.guild.get_member(int(mid))
                        if m and not self.has_bypass(m):
                            await self.quarantine_user(m, "Detected mass join raid")
                            quarantined.append(m.id)
                    except Exception as e:
                        logger.error(f"Failed to quarantine joiner {mid}: {e}")

                if quarantined:
                    logger.info(f"Auto-quarantined join-raid accounts: {quarantined}")
                    # Clear events for these quarantined users to avoid repeated action
                    self.join_events[member.guild.id] = [ev for ev in self.join_events[member.guild.id] if ev[1] not in quarantined]
        except Exception as e:
            logger.error(f"Error in join-raid detection: {e}")

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

        # Acknowledge interaction early to avoid "interaction failed" and make it public
        try:
            await interaction.response.defer()
        except Exception:
            pass

        # Store roles before removing them (exclude @everyone and the quarantine role)
        stored_roles = [role.id for role in user.roles if role != user.guild.default_role and role.id != QUARANTINE_ROLE_ID]
        
        # Build list of roles to remove (exclude @everyone and quarantine role)
        roles_to_remove = [r for r in user.roles if r != user.guild.default_role and r.id != QUARANTINE_ROLE_ID]
        
        # Sort roles top-down (highest position first)
        roles_to_remove.sort(key=lambda r: r.position, reverse=True)

        # Send an initial public progress embed so we can update live
        try:
            progress_embed = discord.Embed(
                title="Quarantining user...",
                description=f"Preparing to remove {len(roles_to_remove)} roles from {user.mention}",
                color=discord.Color.red()
            )
            progress_embed.add_field(name="Roles removed", value="0", inline=True)
            progress_embed.add_field(name="Last role removed", value="None", inline=True)
            progress_msg = await interaction.followup.send(embed=progress_embed, wait=True)
        except Exception:
            progress_msg = None

        # Remove roles one by one with error handling and live updates (top-down order)
        removed_count = 0
        for role in roles_to_remove:
            try:
                await user.remove_roles(role, reason="Quarantine")
                removed_count += 1
                last_name = role.name
                # update progress embed
                if progress_msg:
                    try:
                        progress_embed = discord.Embed(
                            title="Quarantining user...",
                            description=f"Removing roles from {user.mention}",
                            color=discord.Color.red()
                        )
                        progress_embed.add_field(name="Roles removed", value=f"{removed_count}/{len(roles_to_remove)}", inline=True)
                        progress_embed.add_field(name="Last role removed", value=last_name or "Unknown", inline=True)
                        await progress_msg.edit(embed=progress_embed)
                    except Exception:
                        pass
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
                # update progress with quarantine role added
                if progress_msg:
                    try:
                        progress_embed = discord.Embed(
                            title="User quarantined",
                            description=f"{user.mention} has been assigned the quarantine role",
                            color=discord.Color.red()
                        )
                        progress_embed.add_field(name="Roles removed", value=f"{removed_count}/{len(roles_to_remove)}", inline=True)
                        progress_embed.add_field(name="Last role removed", value=last_name if removed_count else "None", inline=True)
                        progress_embed.add_field(name="Quarantine role", value=quarantine_role.name, inline=False)
                        await progress_msg.edit(embed=progress_embed)
                    except Exception:
                        pass
            else:
                logger.error(f"Quarantine role {QUARANTINE_ROLE_ID} not found")
                try:
                    await interaction.followup.send(
                        "Error: Quarantine role not found. Please check configuration."
                    )
                except Exception:
                    pass
                return
        except Exception as e:
            logger.error(f"Error adding quarantine role to {user.id}: {str(e)}")
            try:
                await interaction.followup.send(
                    f"Error adding quarantine role: {str(e)}"
                )
            except Exception:
                pass
            return

        # Store quarantine data
        self.quarantined_users[str(user.id)] = {
            "roles": stored_roles,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).timestamp(),
            "duration": duration_seconds
        }
        self.save_quarantine_data()

        # Attempt to timeout (mute) the user for the quarantine duration
        try:
            until = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
            try:
                await user.timeout(until=until)
            except TypeError:
                # fallback: try passing a timedelta
                try:
                    await user.timeout(timedelta(seconds=duration_seconds))
                except Exception as e:
                    logger.error(f"Failed to timeout/quarantine member {user.id}: {e}")
        except Exception as e:
            logger.error(f"Failed to apply timeout to quarantined user {user.id}: {e}")

        # Create embed for response (include roles removed count)
        roles_removed_count = len(stored_roles)
        embed = discord.Embed(
            title="Manual Quarantine",
            description=f"{user.mention} has been quarantined",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Duration", value=f"{duration} days")
        embed.add_field(name="Quarantined by", value=interaction.user.mention)
        embed.add_field(name="Roles removed", value=f"{roles_removed_count} roles removed", inline=False)

        # Log the action
        await self.log_action(
            "MANUAL_QUARANTINE",
            user,
            f"Quarantined by {interaction.user} for: {reason}",
            duration_seconds
        )

        # Try to DM the user with an embed
        try:
            em = discord.Embed(
                title="You have been quarantined",
                description=(
                    f"You have been quarantined in **{interaction.guild.name}** for: {reason}\n"
                    f"Duration: {duration} days\n"
                    "Should you leave the server before you resolve your quarantine, you will be banned."
                ),
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            em.set_footer(text="Contact server staff for help")
            await user.send(embed=em)
        except Exception:
            embed.add_field(
                name="Note",
                value="Could not DM user about quarantine",
                inline=False
            )

        # Send final response as followup (we deferred earlier) if we didn't already update a progress message
        try:
            if progress_msg is None:
                await interaction.followup.send(embed=embed)
            else:
                # edit progress message to the final summary embed
                try:
                    await progress_msg.edit(embed=embed)
                except Exception:
                    # fallback to sending a new followup
                    await interaction.followup.send(embed=embed)
        except Exception:
            try:
                await interaction.response.send_message(embed=embed)
            except Exception as e2:
                logger.error(f"Failed to send interaction response for quarantine_command: {e2}")

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
        # Acknowledge interaction early to avoid "interaction failed" and make it public
        try:
            await interaction.response.defer()
        except Exception:
            pass

        # Send initial progress message so we can update live
        try:
            progress_embed = discord.Embed(
                title="Unquarantining user...",
                description=f"Restoring roles to {user.mention}",
                color=discord.Color.green()
            )
            progress_embed.add_field(name="Roles restored", value="0", inline=True)
            progress_embed.add_field(name="Last role added", value="None", inline=True)
            progress_msg = await interaction.followup.send(embed=progress_embed, wait=True)
        except Exception:
            progress_msg = None

        # restore roles and remove quarantine role (with progress)
        try:
            added = await self.restore_roles(user, roles, progress_message=progress_msg)
        except Exception as e:
            logger.error(f"Error restoring roles for unquarantine {user.id}: {e}")
            added = 0

        # remove from persisted quarantine list
        try:
            del self.quarantined_users[str(user.id)]
            self.save_quarantine_data()
        except KeyError:
            pass

        # DM the user with an embed
        try:
            em = discord.Embed(
                title="You have been unquarantined",
                description=f"You have been unquarantined in **{interaction.guild.name}** by {interaction.user}.",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            em.set_footer(text="If something is wrong, contact server staff")
            await user.send(embed=em)
        except Exception:
            pass

        try:
            await self.log_action("MANUAL_UNQUARANTINE", user, f"Unquarantined by {interaction.user}")
        except Exception:
            logger.exception("Failed to log manual unquarantine")

        # Finalize progress message or send a summary followup
        try:
            summary = discord.Embed(
                title="User Unquarantined",
                description=f"{user.mention} has been unquarantined",
                color=discord.Color.green()
            )
            summary.add_field(name="Roles restored", value=f"{added}", inline=False)
            if progress_msg:
                try:
                    await progress_msg.edit(embed=summary)
                except Exception:
                    await interaction.followup.send(embed=summary)
            else:
                await interaction.followup.send(embed=summary)
        except Exception:
            try:
                await interaction.response.send_message(f"Unquarantined {user.mention} — Roles restored: {added}")
            except Exception as e2:
                logger.error(f"Failed to send interaction response for unquarantine_command: {e2}")

    async def restore_roles(self, member: discord.Member, role_ids: List[int], progress_message: Optional[discord.Message] = None):
        """Restore roles to a member after quarantine. Optionally update a progress_message embed live.

        Returns the number of roles successfully restored.
        """
        try:
            # Remove quarantine role if present
            quarantine_role = member.guild.get_role(QUARANTINE_ROLE_ID)
            if quarantine_role and quarantine_role in member.roles:
                try:
                    await member.remove_roles(quarantine_role)
                except Exception:
                    # ignore failures removing the quarantine role
                    pass

            total = len(role_ids or [])
            added_count = 0
            last_added = None

            for role_id in role_ids:
                try:
                    role = member.guild.get_role(role_id)
                    if not role:
                        continue
                    try:
                        await member.add_roles(role)
                        added_count += 1
                        last_added = role.name
                    except Exception as e:
                        logger.error(f"Failed to add role {role.id} to {member.id}: {e}")

                    # Update progress message if provided
                    if progress_message:
                        try:
                            prog = discord.Embed(
                                title="Restoring roles...",
                                description=f"Restoring roles for {member.mention}",
                                color=discord.Color.green()
                            )
                            prog.add_field(name="Roles restored", value=f"{added_count}/{total}", inline=True)
                            prog.add_field(name="Last role added", value=last_added or "None", inline=True)
                            await progress_message.edit(embed=prog)
                        except Exception:
                            pass
                except Exception:
                    continue

            # Log the restoration
            try:
                await self.log_action(
                    "ROLES_RESTORED",
                    member,
                    f"Restored {added_count} roles after quarantine"
                )
            except Exception:
                pass

            # Try to DM user
            try:
                em = discord.Embed(
                    title="Your roles have been restored",
                    description=f"Your roles in **{member.guild.name}** have been restored.",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )
                em.set_footer(text="If something is wrong, contact server staff")
                await member.send(embed=em)
            except Exception:
                pass

            return added_count
        except discord.Forbidden:
            logger.error(f"Failed to restore roles for {member.id} - Missing Permissions")
            return 0
        except Exception as e:
            logger.error(f"Failed to restore roles for {member.id} - {str(e)}")
            return 0

    def has_bypass(self, user) -> bool:
        """Check if user has bypass protection. Only checks ONE protected user OR ONE protected role."""
        try:
            # Check if user ID matches protected user
            user_id = getattr(user, 'id', None)
            if user_id == IMMUNE_USER_ID:
                return True
            if user_id == BOT:
                return True
            
            # Check if user has protected role (only if we can access roles)
            if hasattr(user, 'roles'):
                roles = getattr(user, 'roles', None)
                if roles:
                    return any(role.id == IMMUNE_ROLE_ID for role in roles)
            
            return False
        except Exception:
            return False

    def is_quarantined(self, user_id) -> bool:
        """Check if a user is currently quarantined."""
        try:
            user_id_str = str(user_id)
            return user_id_str in self.quarantined_users
        except Exception:
            return False

async def setup(bot):
    await bot.add_cog(RaidProtection(bot))
