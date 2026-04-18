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

# =========================
# CONFIG
# =========================

AUTOMOD_LOG_FILE = os.path.join("logs", "automod_protection.log")
LOG_CHANNEL_ID = 1329910577375482068

BOT_IDS = [1403146651543015445, 1387175664649506847]

PERSONNEL_ROLE_ID = 1329910329701830686
ADMIN_ROLE_ID = 1355842403134603275
QUARANTINE_ROLE_ID = 1432834406791254058
INFRACTION_CHANNEL_ID = 1384141458163896382

automodbypass = [911072161349918720, 840949634071658507, 735167992966676530]
bypassrole = 1329910230066401361

# =========================
# SAFE REGEX PATTERNS
# =========================
# FIX: all now require word boundaries to prevent "banana" type issues

BAN_PATTERN = re.compile(r"\bban\b", re.IGNORECASE)

MUTE_PATTERN = re.compile(r"\bmute\b", re.IGNORECASE)

QUARANTINE_PATTERN = re.compile(r"\bquarantine\b", re.IGNORECASE)

INFRACTION_PATTERNS = [
    re.compile(r"\b(s+|$+5+z+)[\w\W]*", re.IGNORECASE),
]

# =========================
# LOGGING
# =========================
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename=AUTOMOD_LOG_FILE,
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("Automod")

# =========================
# HELPERS
# =========================

async def collect_context_proof(message: discord.Message, limit: int = 3):
    ctx = []

    try:
        async for m in message.channel.history(limit=limit, before=message):
            ctx.append({
                "author": str(m.author),
                "content": m.content,
                "time": m.created_at.isoformat()
            })
    except:
        pass

    ctx.reverse()

    ctx.append({
        "author": str(message.author),
        "content": message.content,
        "time": message.created_at.isoformat()
    })

    markdown = "**Context:**\n"
    for i, m in enumerate(ctx):
        prefix = ">>> " if i == len(ctx) - 1 else " "
        markdown += f"{prefix}{m['author']}: {m['content']}\n"

    return markdown


# =========================
# COG
# =========================

class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Automod loaded")

    # =========================
    # MAIN HANDLER
    # =========================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot:
            return

        if not message.guild:
            return

        content = message.content or ""
        content_lower = content.lower()

        handled_as_admin = False  # IMPORTANT FLAG

        # =========================================================
        # ADMIN REPLY SYSTEM (SAFE GATED)
        # =========================================================
        if message.reference:

            try:
                replied = await message.channel.fetch_message(message.reference.message_id)
            except:
                return

            # must explicitly mention bot
            bot_mentioned = any(m.id in BOT_IDS for m in message.mentions) or self.bot.user.id in [m.id for m in message.mentions]

            if bot_mentioned:

                if not any(r.id == ADMIN_ROLE_ID for r in message.author.roles):
                    await message.reply("Admin only", mention_author=False)
                    return

                target = replied.author
                if not isinstance(target, discord.Member):
                    try:
                        target = await message.guild.fetch_member(target.id)
                    except:
                        return

                # =========================
                # STRICT ACTION MATCHING
                # =========================

                # BAN (STRICT)
                if BAN_PATTERN.fullmatch(content_lower.split()[0]):
                    await message.guild.ban(target, reason="Admin ban")
                    handled_as_admin = True
                    return

                # QUARANTINE
                if QUARANTINE_PATTERN.search(content_lower):
                    role = message.guild.get_role(QUARANTINE_ROLE_ID)
                    if role:
                        await target.add_roles(role, reason="Admin quarantine")
                    handled_as_admin = True
                    return

                # MUTE
                if MUTE_PATTERN.search(content_lower):
                    until = discord.utils.utcnow() + timedelta(minutes=60)
                    await target.timeout(until, reason="Admin mute")
                    handled_as_admin = True
                    return

                return  # STOP HERE ALWAYS AFTER ADMIN ACTION

        # =========================================================
        # HARD STOP: PREVENT ADMIN PATH LEAK INTO AUTOMOD
        # =========================================================
        if handled_as_admin:
            return

        # =========================================================
        # BYPASS SYSTEM
        # =========================================================
        if message.author.id in automodbypass:
            return

        if isinstance(message.author, discord.Member):
            if any(r.id == bypassrole for r in message.author.roles):
                return

        # =========================================================
        # AUTOMOD MATCHING (SAFE)
        # =========================================================

        matches = {
            "ban": bool(BAN_PATTERN.search(content_lower)),
            "mute": bool(MUTE_PATTERN.search(content_lower)),
            "quarantine": bool(QUARANTINE_PATTERN.search(content_lower)),
        }

        # delete only if real match
        if any(matches.values()):
            try:
                await message.delete()
            except:
                pass

        ctx = await collect_context_proof(message)

        # =========================
        # BAN
        # =========================
        if matches["ban"]:
            if isinstance(message.author, discord.Member):
                if any(r.id == PERSONNEL_ROLE_ID for r in message.author.roles):
                    await message.guild.ban(message.author, reason="Automod ban")
            return

        # =========================
        # QUARANTINE
        # =========================
        if matches["quarantine"]:
            if isinstance(message.author, discord.Member):
                role = message.guild.get_role(QUARANTINE_ROLE_ID)
                if role:
                    await message.author.add_roles(role, reason="Automod quarantine")
            return

        # =========================
        # MUTE
        # =========================
        if matches["mute"]:
            if isinstance(message.author, discord.Member):
                until = discord.utils.utcnow() + timedelta(minutes=60)
                await message.author.timeout(until, reason="Automod mute")
            return


# =========================
# SETUP
# =========================

async def setup(bot):
    await bot.add_cog(Automod(bot))