import discord
import os
from datetime import datetime, timedelta
from discord.ext import commands
import re
import base64
import json
import aiosqlite
import uuid
import asyncio
from typing import List, Dict, Any
from discord import app_commands

AUTOMOD_LOG_FILE = os.path.join("logs", "automod_protection.log")

LOG_CHANNEL_ID = 1329910577375482068
TIMEOUT_MINUTES = 10


PHRASES_B64 = (
    ""

# Decode at runtime into the `phrases` list (JSON array stored in the blob)
_PHRASE_LIST = json.loads(base64.b64decode(PHRASES_B64).decode())

# Keep original variable for backwards compatibility
phrases = list(_PHRASE_LIST)

# Use same list for infractions/quarantine/ban by default (you can paste different lists into the blobs)
AUTO_INFRACT_WORDS = list(_PHRASE_LIST)
AUTO_QUARANTINE_WORDS = list(_PHRASE_LIST)
AUTO_BAN_WORDS = list(_PHRASE_LIST)

# Thresholds (matches required). Default 1 for immediate action.
INFRACT_THRESHOLD = int(os.getenv("AUTOMOD_INFRACT_THRESHOLD", "1"))
QUARANTINE_THRESHOLD = int(os.getenv("AUTOMOD_QUARANTINE_THRESHOLD", "1"))
BAN_THRESHOLD = int(os.getenv("AUTOMOD_BAN_THRESHOLD", "1"))

# Files and storage for tracking/logging
AUTOMOD_ACTIONS_LOG = os.path.join("logs", "automod_actions.log")  # base64 JSON lines
AUTOMOD_TRACKING_FILE = os.path.join("data", "automod_tracking.json")

# Infraction DB and channel (mirror infract.py env usage where available)
INFRACTION_DB = os.getenv("INFRACTION_DB", "data/infractions.db")
INFRACTION_CHANNEL_ID = int(os.getenv("INFRACTION_CHANNEL_ID")) if os.getenv("INFRACTION_CHANNEL_ID") else None

# Quarantine config
QUARANTINE_ROLE_ID = int(os.getenv("QUARANTINE_ROLE_ID", "1432834406791254058"))
QUARANTINE_DATA_FILE = os.path.join("data", "quarantine_data.json")

# Admin and personnel
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", "1355842403134603275"))
PERSONNEL_ROLE_ID_AUTO = int(os.getenv("PERSONNEL_ROLE_ID_AUTO", "1329910329701830686"))

automodbypass = [911072161349918720, 840949634071658507, 735167992966676530]
bypassrole = 1329910230066401361

class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _collect_context_proof(self, message: discord.Message, limit: int = 3) -> str:
        """Collect up to `limit` messages before `message` and include the message itself.
        Returns a base64-encoded JSON string containing the context.
        """
        ctx_msgs = []
        try:
            async for m in message.channel.history(limit=limit, before=message, oldest_first=True):
                ctx_msgs.append({
                    "author": str(m.author),
                    "author_id": m.author.id,
                    "content": m.content,
                    "created_at": m.created_at.isoformat()
                })
        except Exception:
            ctx_msgs = []
        # include offending message as last item
        ctx_msgs.append({
            "author": str(message.author),
            "author_id": message.author.id,
            "content": message.content,
            "created_at": message.created_at.isoformat()
        })
        payload = {"guild": message.guild.id if message.guild else None, "channel": message.channel.id, "context": ctx_msgs}
        try:
            j = json.dumps(payload, ensure_ascii=False)
            b = base64.b64encode(j.encode()).decode()
            return b
        except Exception:
            return ""

    async def _write_action_log(self, entry: Dict[str, Any]):
        try:
            line = base64.b64encode(json.dumps(entry, ensure_ascii=False).encode()).decode()
            os.makedirs(os.path.dirname(AUTOMOD_ACTIONS_LOG), exist_ok=True)
            with open(AUTOMOD_ACTIONS_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    async def _update_tracking(self, user_id: int, event: Dict[str, Any]):
        try:
            os.makedirs(os.path.dirname(AUTOMOD_TRACKING_FILE), exist_ok=True)
            data = {}
            if os.path.exists(AUTOMOD_TRACKING_FILE):
                with open(AUTOMOD_TRACKING_FILE, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except Exception:
                        data = {}
            user_key = str(user_id)
            data.setdefault(user_key, []).append(event)
            with open(AUTOMOD_TRACKING_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    async def _perform_infraction(self, member: discord.Member, issued_by: discord.User, action: str = "Warning", reason: str = "Automod", proof_message: discord.Message = None, proof_text: str = None):
        infraction_id = str(uuid.uuid4())
        proof_b64 = proof_text or (await self._collect_context_proof(proof_message)) if proof_message else (proof_text or "")
        now = datetime.datetime.utcnow().isoformat()
        # Insert into infractions DB similar to infract.py
        try:
            async with aiosqlite.connect(INFRACTION_DB) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS infractions (
                        infraction_id TEXT PRIMARY KEY,
                        user_id INTEGER,
                        user_name TEXT,
                        moderator_id INTEGER,
                        moderator_name TEXT,
                        action TEXT,
                        reason TEXT,
                        proof TEXT,
                        date TEXT,
                        message_id INTEGER,
                        voided INTEGER DEFAULT 0,
                        void_reason TEXT
                    )
                """)
                await db.execute(
                    "INSERT INTO infractions (infraction_id, user_id, user_name, moderator_id, moderator_name, action, reason, proof, date, message_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (infraction_id, member.id, str(member), issued_by.id if issued_by else 0, str(issued_by) if issued_by else "Auto", action, reason, proof_b64, now, None)
                )
                await db.commit()
        except Exception:
            pass

        # Send embed to infraction channel if configured
        try:
            if INFRACTION_CHANNEL_ID:
                ch = member.guild.get_channel(INFRACTION_CHANNEL_ID)
                if ch:
                    embed = discord.Embed(title=f"Infraction: {action}", color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
                    embed.add_field(name="User", value=f"{member}", inline=True)
                    embed.add_field(name="Issued by", value=f"{issued_by}", inline=True)
                    embed.add_field(name="Reason", value=reason, inline=False)
                    embed.add_field(name="Infraction ID", value=infraction_id, inline=True)
                    embed.add_field(name="Proof (base64)", value=(proof_b64[:1000] if proof_b64 else "None"), inline=False)
                    await ch.send(content=member.mention, embed=embed)
        except Exception:
            pass

        # Log action and tracking
        log_entry = {
            "timestamp": now,
            "action": "infraction",
            "infraction_id": infraction_id,
            "target_id": member.id,
            "target": str(member),
            "moderator_id": issued_by.id if issued_by else 0,
            "moderator": str(issued_by) if issued_by else "Auto",
            "reason": reason,
            "proof_b64": proof_b64
        }
        await self._write_action_log(log_entry)
        await self._update_tracking(member.id, log_entry)

    async def _perform_quarantine(self, member: discord.Member, issued_by: discord.User, reason: str = "Automod quarantine", proof_message: discord.Message = None, proof_text: str = None):
        now = datetime.datetime.utcnow().isoformat()
        proof_b64 = proof_text or (await self._collect_context_proof(proof_message)) if proof_message else (proof_text or "")
        # store roles and remove them
        try:
            prev_roles = [r.id for r in member.roles if r != member.guild.default_role and r.id != QUARANTINE_ROLE_ID]
            data = {}
            if os.path.exists(QUARANTINE_DATA_FILE):
                try:
                    with open(QUARANTINE_DATA_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data[str(member.id)] = {"roles": prev_roles, "timestamp": now, "moderator_id": issued_by.id if issued_by else 0, "reason": reason}
            os.makedirs(os.path.dirname(QUARANTINE_DATA_FILE), exist_ok=True)
            with open(QUARANTINE_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # remove roles and add quarantine role
            remove_roles = [member.guild.get_role(rid) for rid in prev_roles if member.guild.get_role(rid) is not None]
            if remove_roles:
                await member.remove_roles(*remove_roles, reason="Automod quarantine")
            qrole = member.guild.get_role(QUARANTINE_ROLE_ID)
            if qrole:
                await member.add_roles(qrole, reason="Automod quarantine")
        except Exception:
            pass

        # Add an infraction entry marking the quarantine (Suspension)
        await self._perform_infraction(member, issued_by, action="Suspension", reason=reason, proof_text=proof_b64)

        # Log action
        log_entry = {
            "timestamp": now,
            "action": "quarantine",
            "target_id": member.id,
            "target": str(member),
            "moderator_id": issued_by.id if issued_by else 0,
            "moderator": str(issued_by) if issued_by else "Auto",
            "reason": reason,
            "proof_b64": proof_b64
        }
        await self._write_action_log(log_entry)
        await self._update_tracking(member.id, log_entry)

    async def _perform_ban(self, member: discord.Member, issued_by: discord.User, reason: str = "Automod ban", proof_message: discord.Message = None, proof_text: str = None):
        now = datetime.datetime.utcnow().isoformat()
        proof_b64 = proof_text or (await self._collect_context_proof(proof_message)) if proof_message else (proof_text or "")
        try:
            await member.guild.ban(member, reason=reason)
        except Exception:
            pass

        # create infraction record for ban
        infraction_id = str(uuid.uuid4())
        log_entry = {
            "timestamp": now,
            "action": "ban",
            "infraction_id": infraction_id,
            "target_id": member.id,
            "target": str(member),
            "moderator_id": issued_by.id if issued_by else 0,
            "moderator": str(issued_by) if issued_by else "Auto",
            "reason": reason,
            "proof_b64": proof_b64
        }
        await self._write_action_log(log_entry)
        await self._update_tracking(member.id, log_entry)

    @app_commands.command(name="automod-history", description="Show automod action history for a user (personnel only).")
    @app_commands.describe(user="Member to view history for")
    async def automod_history(self, interaction: discord.Interaction, user: discord.Member = None):
        # permission: personnel role
        if not any(r.id == PERSONNEL_ROLE_ID_AUTO for r in getattr(interaction.user, "roles", [])):
            await interaction.response.send_message("You do not have permission to view automod history.", ephemeral=True)
            return
        target = user or interaction.user
        data = {}
        if os.path.exists(AUTOMOD_TRACKING_FILE):
            try:
                with open(AUTOMOD_TRACKING_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        entries = data.get(str(target.id), [])
        if not entries:
            await interaction.response.send_message("No automod history for that user.", ephemeral=True)
            return
        # show last 10 entries
        last = entries[-10:]
        embed = discord.Embed(title=f"Automod History: {target}", color=discord.Color.blurple())
        for e in reversed(last):
            ts = e.get("timestamp")
            act = e.get("action")
            reason = e.get("reason")
            mid = e.get("infraction_id") or e.get("target_id")
            embed.add_field(name=f"{act} @ {ts}", value=f"Reason: {reason}\nID: {mid}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if (message.author.id in automodbypass or any(role.id == bypassrole for role in message.author.roles)):
            return
 
        content = message.content or ""
        content_l = content.lower()
 
        # find matches against configured lists
        def count_matches(word_list: List[str]) -> int:
            if not word_list:
                return 0
            pattern = "(" + "|".join(map(re.escape, word_list)) + ")"
            return len(re.findall(pattern, content_l, re.IGNORECASE))
 
        matches_phrases = re.findall("(" + "|".join(map(re.escape, phrases)) + ")", content_l, re.IGNORECASE)
        inf_matches = count_matches(AUTO_INFRACT_WORDS)
        q_matches = count_matches(AUTO_QUARANTINE_WORDS)
        b_matches = count_matches(AUTO_BAN_WORDS)
 
        # reply-to-message personnel trigger: personnel can reply to a target message, mention bot and request an action
        if message.reference and any(role.id == PERSONNEL_ROLE_ID_AUTO for role in getattr(message.author, "roles", [])) and self.bot.user in message.mentions:
            ref = message.reference
            try:
                target_msg = await message.channel.fetch_message(ref.message_id)
                target_member = target_msg.author
            except Exception:
                target_member = None
            if target_member:
                mtxt = message.content.lower()
                # determine requested action from moderator message
                if "ban" in mtxt:
                    await self._perform_ban(target_member, message.author, reason=f"Staff requested ban via reply: {message.content}", proof_message=target_msg)
                    await message.reply(f"Requested ban executed for {target_member.mention}")
                    return
                if "quarantine" in mtxt or "mute" in mtxt:
                    await self._perform_quarantine(target_member, message.author, reason=f"Staff requested quarantine via reply: {message.content}", proof_message=target_msg)
                    await message.reply(f"Requested quarantine executed for {target_member.mention}")
                    return
                if "infraction" in mtxt or "warn" in mtxt or "strike" in mtxt:
                    await self._perform_infraction(target_member, message.author, action="Warning", reason=f"Staff requested infraction via reply: {message.content}", proof_message=target_msg)
                    await message.reply(f"Requested infraction issued for {target_member.mention}")
                    return
 
        # Automated reaction to matched phrases
        if matches_phrases:
            # delete offending message and timeout as before
            try:
                await message.delete()
            except Exception:
                pass
 
            try:
                timeout_until = discord.utils.utcnow() + timedelta(minutes=TIMEOUT_MINUTES)
                await message.author.timeout(timeout_until, reason="MCNG utils automoderation")
            except Exception:
                pass
 
            # build contextual proof (3 preceding messages + offending)
            proof = await self._collect_context_proof(message)
 
            # Decide auto actions
            if inf_matches >= INFRACT_THRESHOLD:
                await self._perform_infraction(message.author, self.bot.user, action="Warning", reason=f"Automod keywords matched: {set(matches_phrases)}", proof_message=message, proof_text=proof)
            if q_matches >= QUARANTINE_THRESHOLD:
                await self._perform_quarantine(message.author, self.bot.user, reason=f"Automod keywords matched: {set(matches_phrases)}", proof_message=message, proof_text=proof)
            if b_matches >= BAN_THRESHOLD:
                await self._perform_ban(message.author, self.bot.user, reason=f"Automod keywords matched: {set(matches_phrases)}", proof_message=message, proof_text=proof)
 
            # Send a short log embed to the configured log channel
            log_channel = message.guild.get_channel(LOG_CHANNEL_ID)
            embed = discord.Embed(
                title="Automod Triggered",
                description="User was automatically actioned by automod.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="User", value=f"{message.author} ({message.author.id})", inline=False)
            embed.add_field(name="Channel", value=message.channel.mention, inline=False)
            embed.add_field(name="Matched Phrases", value=", ".join(set(matches_phrases))[:1000], inline=False)
            if log_channel:
                try:
                    await log_channel.send(embed=embed)
                except Exception:
                    pass
                
async def setup(bot):
    await bot.add_cog(Automod(bot))
