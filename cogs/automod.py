import discord
import os
from datetime import datetime, timedelta
from discord.ext import commands
import re
import base64
import json
import uuid
from typing import List, Dict, Any
import logging

AUTOMOD_LOG_FILE = os.path.join("logs", "automod_protection.log")
LOG_CHANNEL_ID = 1329910577375482068
BOT_IDS = [1403146651543015445, 1387175664649506847]

# Exact word lists (loaded from data file)
INFRACTION_WORDS = []
MUTE_WORDS = []
QUARANTINE_WORDS = []
BAN_WORDS = []

EXACT_WORDS_FILE = os.path.join("data", "exact_words.json")

MUTE_DURATION_MINUTES = 60
QUARANTINE_DURATION_SECONDS = 172800
INFRACT_THRESHOLD = MUTE_THRESHOLD = QUARANTINE_THRESHOLD = BAN_THRESHOLD = 1
MODERATION_TRACKING_FILE = os.path.join("data", "moderation_tracking.json")
BLOCKED_WORDS_FILE = os.path.join("data", "blocked_words.json")
PERSONNEL_ROLE_ID = 1329910329701830686
ADMIN_ROLE_ID = 1355842403134603275
automodbypass = [911072161349918720, 840949634071658507, 735167992966676530]
bypassrole = 1329910230066401361
QUARANTINE_ROLE_ID = 1432834406791254058
INFRACTION_CHANNEL_ID = 1384141458163896382  # Log channel for infraction embeds

# Infraction role routing
WARNING_1_ROLE_ID = int(os.getenv("WARNING_1_ROLE_ID", "0"))
WARNING_2_ROLE_ID = int(os.getenv("WARNING_2_ROLE_ID", "0"))
STRIKE_1_ROLE_ID = int(os.getenv("STRIKE_1_ROLE_ID", "0"))
STRIKE_2_ROLE_ID = int(os.getenv("STRIKE_2_ROLE_ID", "0"))
STRIKE_3_ROLE_ID = int(os.getenv("STRIKE_3_ROLE_ID", "0"))
SUSPENDED_ROLE_ID = int(os.getenv("SUSPENDED_ROLE_ID", "0"))

os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename=AUTOMOD_LOG_FILE, format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger('Automod')

logger.info("=" * 80)
logger.info("AUTOMOD COG LOADED - System ready")
logger.info("=" * 80)


def load_exact_words():
    """Load exact words from data file."""
    global INFRACTION_WORDS, MUTE_WORDS, QUARANTINE_WORDS, BAN_WORDS
    try:
        if os.path.exists(EXACT_WORDS_FILE):
            with open(EXACT_WORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                INFRACTION_WORDS = data.get("infraction_words", [])
                MUTE_WORDS = data.get("mute_words", [])
                QUARANTINE_WORDS = data.get("quarantine_words", [])
                BAN_WORDS = data.get("ban_words", [])
                logger.info(f"Loaded exact words: {len(INFRACTION_WORDS)} infraction, {len(MUTE_WORDS)} mute, {len(QUARANTINE_WORDS)} quarantine, {len(BAN_WORDS)} ban")
    except Exception as e:
        logger.error(f"Failed to load exact words: {e}")


# Load words on startup
load_exact_words()


async def collect_context_proof(message: discord.Message, limit: int = 3) -> tuple[str, str]:
    """Collect context messages and return (markdown, base64)."""
    ctx_msgs = []
    try:
        # Collect the most recent `limit` messages that occurred BEFORE the offending message.
        # `history(limit=..., before=message)` returns newest->oldest by default, so gather
        # them then reverse to get chronological order (oldest -> newest), then append culprit.
        recent = []
        async for m in message.channel.history(limit=limit, before=message):
            recent.append({
                "author": str(m.author),
                "author_id": m.author.id,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            })
        recent.reverse()
        ctx_msgs = recent
    except Exception:
        ctx_msgs = []

    # Append the offending message itself as the last entry
    ctx_msgs.append({
        "author": str(message.author),
        "author_id": message.author.id,
        "content": message.content,
        "created_at": message.created_at.isoformat()
    })
    
    # Build markdown
    markdown_context = "**Message Context:**\n"
    for idx, m in enumerate(ctx_msgs):
        marker = ">>> " if idx == len(ctx_msgs) - 1 else "  "
        markdown_context += f"{marker}**{m['author']}**: {m['content']}\n"
    
    # Build JSON
    payload = {
        "guild": message.guild.id if message.guild else None,
        "channel": message.channel.id,
        "context": ctx_msgs
    }
    try:
        j = json.dumps(payload, ensure_ascii=False)
        b = base64.b64encode(j.encode()).decode()
        return markdown_context, b
    except Exception:
        return markdown_context, ""


def is_blocked_word(word: str) -> bool:
    """Check if word is blocked."""
    try:
        if os.path.exists(BLOCKED_WORDS_FILE):
            with open(BLOCKED_WORDS_FILE, "r", encoding="utf-8") as f:
                blocked = json.load(f)
                return word in blocked.get("blocked_words", [])
    except Exception:
        pass
    return False


async def update_tracking(user_id: int, event: Dict[str, Any]):
    """Update moderation tracking."""
    try:
        os.makedirs(os.path.dirname(MODERATION_TRACKING_FILE), exist_ok=True)
        data = {}
        if os.path.exists(MODERATION_TRACKING_FILE):
            with open(MODERATION_TRACKING_FILE, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = {}
        user_key = str(user_id)
        data.setdefault(user_key, []).append(event)
        with open(MODERATION_TRACKING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to update tracking: {e}")


async def send_action_log(bot: commands.Bot, target_id: int, action: str, reason: str, action_id: str):
    """Send action log to LOG_CHANNEL with undo button."""
    try:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            logger.error(f"Log channel {LOG_CHANNEL_ID} not found")
            return
        
        embed = discord.Embed(
            title=f"Automod Action: {action.upper()}",
            description=f"<@{target_id}>",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Action ID", value=action_id, inline=True)
        
        # Create undo button view
        view = discord.ui.View()
        undo_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="🔄 Undo",
            custom_id=f"undo_{action_id}"
        )
        
        async def undo_callback(interaction: discord.Interaction):
            # Verify admin
            is_admin = any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)
            if not is_admin:
                await interaction.response.send_message("❌ Only admins can undo actions", ephemeral=True)
                return
            
            try:
                guild = bot.get_guild(interaction.guild_id)
                target = await guild.fetch_member(target_id)
                
                if action.lower() == "ban":
                    await guild.unban(target, reason=f"Undo: {interaction.user}")
                    await interaction.response.send_message(f"✅ Unbanned {target}", ephemeral=False)
                    logger.info(f"Unbanned {target} by {interaction.user}")
                elif action.lower() == "quarantine":
                    quar_role = guild.get_role(QUARANTINE_ROLE_ID)
                    if quar_role and quar_role in target.roles:
                        await target.remove_roles(quar_role, reason=f"Undo: {interaction.user}")
                        await interaction.response.send_message(f"✅ Unquarantined {target}", ephemeral=False)
                        logger.info(f"Unquarantined {target} by {interaction.user}")
                    else:
                        await interaction.response.send_message("❌ Quarantine role not found or already removed", ephemeral=True)
                elif action.lower() == "mute":
                    await target.timeout(None, reason=f"Undo: {interaction.user}")
                    await interaction.response.send_message(f"✅ Unmuted {target}", ephemeral=False)
                    logger.info(f"Unmuted {target} by {interaction.user}")
                else:
                    await interaction.response.send_message("❌ Cannot undo this action type", ephemeral=True)
            except Exception as e:
                logger.error(f"Undo error: {e}")
                await interaction.response.send_message(f"❌ Undo failed: {str(e)}", ephemeral=True)
        
        undo_button.callback = undo_callback
        view.add_item(undo_button)
        
        await log_channel.send(embed=embed, view=view)
    except Exception as e:
        logger.error(f"Failed to send action log: {e}")


async def send_infraction_notification(bot: commands.Bot, target: discord.Member, moderator: discord.Member, action: str, reason: str, infraction_id: str, context: str = ""):
    """Send infraction embed to log channel and DM to user."""
    try:
        # Create embed
        color_map = {
            "Warning": discord.Color.yellow(),
            "Strike": discord.Color.orange(),
            "Demotion": discord.Color.red(),
            "Termination": discord.Color.dark_red(),
            "Suspension": discord.Color.blue(),
        }
        color = color_map.get(action, discord.Color.default())
        
        embed = discord.Embed(
            title=f"Infraction: {action}",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="User", value=f"{target.mention} ({target} | {target.id})", inline=True)
        embed.add_field(name="Issued by", value=f"{moderator} ({moderator.id})", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        if context:
            embed.add_field(name="Transcript", value=context, inline=False)
        embed.add_field(name="Infraction ID", value=str(infraction_id), inline=True)
        
        # Send to log channel
        log_channel = bot.get_channel(INFRACTION_CHANNEL_ID)
        if log_channel:
            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Could not send to log channel: {e}")
        
        # Send DM to user
        try:
            await target.send(embed=embed)
        except Exception as e:
            logger.error(f"Could not send DM to {target}: {e}")
    except Exception as e:
        logger.error(f"Failed to send infraction notification: {e}")


class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info(f"Automod cog initialized with bot: {bot.user if hasattr(bot, 'user') else 'no user yet'}")

    async def update_roles(self, member, action, guild):
        """Apply infraction routing logic to update member roles."""
        roles_to_add = []
        roles_to_remove = []
        
        # Get current role states
        has_w1 = any(r.id == WARNING_1_ROLE_ID for r in member.roles)
        has_w2 = any(r.id == WARNING_2_ROLE_ID for r in member.roles)
        has_s1 = any(r.id == STRIKE_1_ROLE_ID for r in member.roles)
        has_s2 = any(r.id == STRIKE_2_ROLE_ID for r in member.roles)
        has_s3 = any(r.id == STRIKE_3_ROLE_ID for r in member.roles)
        has_susp = any(r.id == SUSPENDED_ROLE_ID for r in member.roles)

        if action == "Warning":
            # Escalate to strike if already has both warnings
            if has_w1 and has_w2:
                roles_to_remove += [WARNING_1_ROLE_ID, WARNING_2_ROLE_ID]
                # Escalate to next strike
                if has_s1 and has_s2:
                    # Already has S1 and S2, next is S3+Suspension
                    roles_to_remove += [STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID]
                    if has_s3:
                        # Already has S3, should terminate
                        return "terminate"
                    else:
                        roles_to_add += [STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID]
                elif has_s1:
                    roles_to_add.append(STRIKE_2_ROLE_ID)
                else:
                    roles_to_add.append(STRIKE_1_ROLE_ID)
            elif has_w1:
                roles_to_add.append(WARNING_2_ROLE_ID)
            else:
                roles_to_add.append(WARNING_1_ROLE_ID)
        elif action == "Strike":
            # Escalate to S3+Suspension if already has S1 and S2
            if has_s1 and has_s2:
                roles_to_remove += [STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID]
                if has_s3:
                    # Already has S3, should terminate
                    return "terminate"
                else:
                    roles_to_add += [STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID]
            elif has_s1:
                roles_to_add.append(STRIKE_2_ROLE_ID)
            else:
                roles_to_add.append(STRIKE_1_ROLE_ID)
        elif action == "Suspension":
            roles_to_add.append(SUSPENDED_ROLE_ID)
            roles_to_remove += [
                WARNING_1_ROLE_ID, WARNING_2_ROLE_ID,
                STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID, STRIKE_3_ROLE_ID
            ]
        elif action == "Termination":
            roles_to_remove += [
                WARNING_1_ROLE_ID, WARNING_2_ROLE_ID,
                STRIKE_1_ROLE_ID, STRIKE_2_ROLE_ID, STRIKE_3_ROLE_ID, SUSPENDED_ROLE_ID
            ]
        
        # Apply role changes
        for rid in roles_to_remove:
            role = guild.get_role(rid)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Infraction system discipline update")
                except Exception as e:
                    logger.error(f"Could not remove role {rid}: {e}")
        
        for rid in roles_to_add:
            role = guild.get_role(rid)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Infraction system discipline update")
                except Exception as e:
                    logger.error(f"Could not add role {rid}: {e}")
        
        return None

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"✅ Automod cog ready. Bot user: {self.bot.user}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        logger.info(f"on_message fired: author={message.author}, guild={message.guild}, content={message.content[:50] if message.content else 'empty'}")
        
        if message.author.bot:
            logger.info(f"Skipped: author is bot")
            return

        if not message.guild:
            logger.info(f"Skipped: not a guild message")
            return

        content = message.content or ""
        logger.info(f"Processing message from {message.author} in {message.guild.name}: {content[:100]}")

        # =====================================================================
        # ADMIN REPLY-TO-MESSAGE TRIGGER
        # =====================================================================
        # Bulletproof: Check reference -> bot mention -> admin -> personnel -> action
        if not message.reference:
            pass  # Skip to automod
        else:
            # This is a reply
            try:
                # Fetch the message being replied to
                target_msg = await message.channel.fetch_message(message.reference.message_id)
            except Exception as e:
                logger.error(f"Could not fetch replied message: {e}")
                return

            # Skip admin commands if replying to a bot
            if target_msg.author.bot or target_msg.author.id in BOT_IDS or target_msg.author.id == self.bot.user.id:
                logger.info(f"Reply to bot detected, skipping admin commands")
                pass  # Skip to automod
            else:
                # Check if bot was mentioned (including bot itself)
                mentioned_ids = [m.id for m in message.mentions]
                bot_mentioned = any(m_id in BOT_IDS for m_id in mentioned_ids) or self.bot.user.id in mentioned_ids
                
                logger.info(f"Reply detected - Mentioned IDs: {mentioned_ids}, Bot mentioned: {bot_mentioned}, Content: {message.content}")
                
                if not bot_mentioned:
                    logger.info(f"Reply without bot mention, skipping to automod")
                    pass  # Skip to automod
                else:
                    # Bot was mentioned in a reply
                    logger.info(f"Bot mentioned in reply by {message.author}")

                    # Check if replier is admin
                    is_replier_admin = any(role.id == ADMIN_ROLE_ID for role in message.author.roles)
                    if not is_replier_admin:
                        logger.info(f"{message.author} tried to use admin reply but is not admin")
                        await message.reply("❌ You need ADMIN role to use this", mention_author=False)
                        return

                    # Get target member
                    target_member = target_msg.author
                    if not isinstance(target_member, discord.Member):
                        try:
                            target_member = await message.guild.fetch_member(target_member.id)
                        except Exception as e:
                            logger.error(f"Could not fetch target member: {e}")
                            await message.reply("❌ Could not get target member", mention_author=False)
                            return

                    # Check if target is personnel
                    is_target_personnel = any(role.id == PERSONNEL_ROLE_ID for role in target_member.roles)
                    if not is_target_personnel:
                        logger.info(f"Target {target_member} is not personnel")
                        await message.reply("❌ Target is not personnel", mention_author=False)
                        return

                    # Target is valid, extract action and reason
                    content_lower = message.content.lower()
                    reason_text = message.content
                    
                    # Extract action and optional reason
                    action_type = None
                    infraction_type = None
                    
                    # Map action keywords to infraction types and extract reason
                    action_map = {
                        "warn": "Warning",
                        "warning": "Warning",
                        "infraction": "Warning",
                        "strike": "Strike",
                        "demotion": "Demotion",
                        "termination": "Termination",
                        "suspension": "Suspension",
                        "activity": "Activity Notice",
                        "activity notice": "Activity Notice",
                    }
                    
                    for keyword, inf_type in action_map.items():
                        if keyword in content_lower:
                            action_type = keyword
                            infraction_type = inf_type
                            # Extract reason after the keyword
                            idx = content_lower.find(keyword)
                            reason_part = message.content[idx + len(keyword):].strip()
                            # Remove bot mention if present
                            reason_part = reason_part.replace(f"<@{self.bot.user.id}>", "").strip()
                            reason_text = reason_part if reason_part else f"Admin issued {inf_type}"
                            break
                    
                    logger.info(f"Admin reply to {target_member}: action={infraction_type}, reason={reason_text}")

                    # BAN (highest priority)
                    if "ban" in content_lower:
                        try:
                            context_md, context_b64 = await collect_context_proof(target_msg)
                            ban_id = str(uuid.uuid4())
                            await send_infraction_notification(self.bot, target_member, message.author, "Termination", f"Admin: {message.content}", ban_id, context_md)
                            await message.guild.ban(target_member, reason=f"Admin: {message.content}")
                            event = {
                                "timestamp": datetime.utcnow().isoformat(),
                                "action": "ban",
                                "target_id": target_member.id,
                                "target": str(target_member),
                                "moderator_id": message.author.id,
                                "moderator": str(message.author),
                                "reason": f"Admin: {message.content}"
                            }
                            await update_tracking(target_member.id, event)
                            await send_action_log(self.bot, target_member.id, "ban", f"Admin: {message.content}", ban_id)
                            logger.info(f"✅ Banned {target_member}")
                            await message.reply(f"✅ Banned {target_member}", mention_author=False)
                            return
                        except Exception as e:
                            logger.error(f"Ban error: {e}")
                            await message.reply(f"❌ Ban failed: {str(e)}", mention_author=False)
                            return

                    # QUARANTINE
                    if "quarantine" in content_lower:
                        raid_cog = self.bot.get_cog("RaidProtection")
                        if not raid_cog:
                            logger.error("RaidProtection cog not loaded")
                            await message.reply("❌ RaidProtection cog not loaded", mention_author=False)
                            return
                        try:
                            await raid_cog.quarantine_user(target_member, f"Admin: {message.content}")
                            # Manually apply quarantine role if not already present
                            try:
                                quar_role = message.guild.get_role(QUARANTINE_ROLE_ID)
                                if quar_role and quar_role not in target_member.roles:
                                    await target_member.add_roles(quar_role, reason=f"Quarantine: {message.content}")
                                    logger.info(f"Applied quarantine role to {target_member}")
                            except Exception as e:
                                logger.error(f"Could not apply quarantine role: {e}")
                            
                            event = {
                                "timestamp": datetime.utcnow().isoformat(),
                                "action": "quarantine",
                                "target_id": target_member.id,
                                "target": str(target_member),
                                "moderator_id": message.author.id,
                                "moderator": str(message.author),
                                "reason": f"Admin: {message.content}"
                            }
                            await update_tracking(target_member.id, event)
                            quar_id = str(uuid.uuid4())
                            await send_action_log(self.bot, target_member.id, "quarantine", f"Admin: {message.content}", quar_id)
                            logger.info(f"✅ Quarantined {target_member}")
                            await message.reply(f"✅ Quarantined {target_member}", mention_author=False)
                            return
                        except Exception as e:
                            logger.error(f"Quarantine error: {e}")
                            await message.reply(f"❌ Quarantine failed: {str(e)}", mention_author=False)
                            return

                    # MUTE
                    if "mute" in content_lower:
                        try:
                            timeout_until = discord.utils.utcnow() + timedelta(minutes=MUTE_DURATION_MINUTES)
                            await target_member.timeout(timeout_until, reason=f"Admin: {message.content}")
                            event = {
                                "timestamp": datetime.utcnow().isoformat(),
                                "action": "mute",
                                "target_id": target_member.id,
                                "target": str(target_member),
                                "moderator_id": message.author.id,
                                "moderator": str(message.author),
                                "reason": f"Admin: {message.content}",
                                "duration_minutes": MUTE_DURATION_MINUTES
                            }
                            await update_tracking(target_member.id, event)
                            mute_id = str(uuid.uuid4())
                            await send_action_log(self.bot, target_member.id, "mute", f"Admin: {message.content} ({MUTE_DURATION_MINUTES} min)", mute_id)
                            logger.info(f"✅ Muted {target_member}")
                            await message.reply(f"✅ Muted {target_member} for {MUTE_DURATION_MINUTES} min", mention_author=False)
                            return
                        except Exception as e:
                            logger.error(f"Mute error: {e}")
                            await message.reply(f"❌ Mute failed: {str(e)}", mention_author=False)
                            return
                    # INFRACTION (all types: Warning, Strike, Demotion, Termination, Suspension, Activity Notice)
                    if infraction_type:
                        inf_cog = self.bot.get_cog("Infraction")
                        if not inf_cog:
                            logger.error("Infraction cog not loaded")
                            await message.reply("❌ Infraction cog not loaded", mention_author=False)
                            return
                        try:
                            context_md, context_b64 = await collect_context_proof(target_msg)
                            inf_id = str(uuid.uuid4())
                            await inf_cog.add_infraction(inf_id, target_member, message.author, infraction_type, reason_text, context_b64, None)
                            await self.update_roles(target_member, infraction_type, message.guild)
                            await send_infraction_notification(self.bot, target_member, message.author, infraction_type, reason_text, inf_id, context_md)
                            event = {
                                "timestamp": datetime.utcnow().isoformat(),
                                "action": "infraction",
                                "infraction_type": infraction_type,
                                "infraction_id": inf_id,
                                "target_id": target_member.id,
                                "target": str(target_member),
                                "moderator_id": message.author.id,
                                "moderator": str(message.author),
                                "reason": reason_text,
                                "context_b64": context_b64
                            }
                            await update_tracking(target_member.id, event)
                            logger.info(f"✅ {infraction_type} issued for {target_member}")
                            await message.reply(f"✅ {infraction_type} issued for {target_member}", mention_author=False)
                            return
                        except Exception as e:
                            logger.error(f"Infraction error: {e}")
                            await message.reply(f"❌ Infraction failed: {str(e)}", mention_author=False)
                            return

                    # No action keyword found
                    logger.info(f"No action keyword in admin reply: {content_lower}")
                    await message.reply("❌ No action found. Use: ban, warn, strike, demotion, termination, suspension, activity notice", mention_author=False)
                    return




        # =====================================================================
        # BYPASS CHECK (AFTER ADMIN REPLIES)
        # =====================================================================
        if message.author.id in automodbypass or any(role.id == bypassrole for role in getattr(message.author, "roles", [])):
            logger.info(f"Skipped: author in bypass list")
            return

        # =====================================================================
        # AUTOMATIC KEYWORD-BASED MODERATION
        # =====================================================================
        if not isinstance(message.author, discord.Member):
            return

        # Check for exact word matches (case-insensitive)
        content_words = content.lower().split()
        ban_matches = [word.strip('.,!?;:"\'-') for word in content_words if word.strip('.,!?;:"\'-') in [w.lower() for w in BAN_WORDS]]
        quarantine_matches = [word.strip('.,!?;:"\'-') for word in content_words if word.strip('.,!?;:"\'-') in [w.lower() for w in QUARANTINE_WORDS]]
        mute_matches = [word.strip('.,!?;:"\'-') for word in content_words if word.strip('.,!?;:"\'-') in [w.lower() for w in MUTE_WORDS]]
        infraction_matches = [word.strip('.,!?;:"\'-') for word in content_words if word.strip('.,!?;:"\'-') in [w.lower() for w in INFRACTION_WORDS]]

        all_matches = ban_matches + quarantine_matches + mute_matches + infraction_matches

        # Check blocked words
        if all_matches:
            for match in all_matches:
                if is_blocked_word(match):
                    logger.info(f"Skipped blocked word: {match}")
                    return

        # Delete message if match found
        if all_matches:
            try:
                await message.delete()
            except Exception:
                pass

        # Hierarchy: ban > quarantine > mute > infraction
        context_md, context_b64 = await collect_context_proof(message)

        if ban_matches:
            # Ban only applies to personnel
            if not any(role.id == PERSONNEL_ROLE_ID for role in message.author.roles):
                logger.info(f"Ban match for non-personnel {message.author}, skipping")
            else:
                ban_id = str(uuid.uuid4())
                await send_infraction_notification(self.bot, message.author, self.bot.user, "Termination", f"Automod detected: {', '.join(ban_matches)}", ban_id, context_md)
                await message.guild.ban(message.author, reason=f"Automod: {ban_matches}")
                event = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "ban",
                    "target_id": message.author.id,
                    "target": str(message.author),
                    "reason": f"Automod ban: {ban_matches}",
                    "matched_words": ban_matches,
                    "context_b64": context_b64
                }
                await update_tracking(message.author.id, event)
                await send_action_log(self.bot, message.author.id, "ban", f"Automod: {', '.join(ban_matches)}", ban_id)
                logger.info(f"Banned {message.author} for: {ban_matches}")
                return

        if quarantine_matches:
            # Quarantine only applies to personnel
            if not any(role.id == PERSONNEL_ROLE_ID for role in message.author.roles):
                logger.info(f"Quarantine match for non-personnel {message.author}, skipping")
            else:
                raid_cog = self.bot.get_cog("RaidProtection")
                if raid_cog:
                    try:
                        await raid_cog.quarantine_user(message.author, f"Automod: {quarantine_matches}")
                        # Manually apply quarantine role if not already present
                        try:
                            quar_role = message.guild.get_role(QUARANTINE_ROLE_ID)
                            if quar_role and quar_role not in message.author.roles:
                                await message.author.add_roles(quar_role, reason=f"Quarantine: {quarantine_matches}")
                                logger.info(f"Applied quarantine role to {message.author}")
                        except Exception as e:
                            logger.error(f"Could not apply quarantine role: {e}")
                        
                        event = {
                            "timestamp": datetime.utcnow().isoformat(),
                            "action": "quarantine",
                            "target_id": message.author.id,
                            "target": str(message.author),
                            "reason": f"Automod quarantine: {quarantine_matches}",
                            "matched_words": quarantine_matches,
                            "context_b64": context_b64
                        }
                        await update_tracking(message.author.id, event)
                        quar_id = str(uuid.uuid4())
                        await send_action_log(self.bot, message.author.id, "quarantine", f"Automod: {', '.join(quarantine_matches)}", quar_id)
                        logger.info(f"Quarantined {message.author} for: {quarantine_matches}")
                        return
                    except Exception as e:
                        logger.error(f"Quarantine error: {e}")

        if mute_matches:
            try:
                timeout_until = discord.utils.utcnow() + timedelta(minutes=MUTE_DURATION_MINUTES)
                await message.author.timeout(timeout_until, reason=f"Automod: {mute_matches}")
                event = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "mute",
                    "target_id": message.author.id,
                    "target": str(message.author),
                    "reason": f"Automod mute: {mute_matches}",
                    "matched_words": mute_matches,
                    "duration_minutes": MUTE_DURATION_MINUTES
                }
                await update_tracking(message.author.id, event)
                mute_id = str(uuid.uuid4())
                await send_action_log(self.bot, message.author.id, "mute", f"Automod: {', '.join(mute_matches)} ({MUTE_DURATION_MINUTES} min)", mute_id)
                logger.info(f"Muted {message.author} for: {mute_matches}")
                return
            except Exception as e:
                logger.error(f"Mute error: {e}")

        if infraction_matches:
            # Infraction only applies to personnel
            if not any(role.id == PERSONNEL_ROLE_ID for role in message.author.roles):
                logger.info(f"Infraction match for non-personnel {message.author}, skipping")
            else:
                inf_cog = self.bot.get_cog("Infraction")
                if inf_cog:
                    try:
                        inf_id = str(uuid.uuid4())
                        await inf_cog.add_infraction(inf_id, message.author, self.bot.user, "Warning", f"Automod: {infraction_matches}", context_b64, None)
                        await self.update_roles(message.author, "Warning", message.guild)
                        await send_infraction_notification(self.bot, message.author, self.bot.user, "Warning", f"Automod detected: {', '.join(infraction_matches)}", inf_id, context_md)
                        event = {
                            "timestamp": datetime.utcnow().isoformat(),
                            "action": "infraction",
                            "target_id": message.author.id,
                            "target": str(message.author),
                            "reason": f"Automod infraction: {infraction_matches}",
                            "matched_words": infraction_matches,
                            "context_b64": context_b64
                        }
                        await update_tracking(message.author.id, event)
                        logger.info(f"Warned {message.author} for: {infraction_matches}")
                    except Exception as e:
                        logger.error(f"Infraction error: {e}")


async def setup(bot):
    logger.info("🔄 Setting up Automod cog...")
    await bot.add_cog(Automod(bot))
    logger.info("✅ Automod cog added to bot")
