from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import uuid
import os
import datetime as dt
import asyncio
from typing import Dict, Any, Optional, List, Tuple
import glob

# -------------------- CONFIG CONSTANTS --------------------
IMAGE_URL = "https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68bac05c&is=68b96edc&hm=b48ce53b741b93847d34dc04a79709fa47badfd867e95afc68a6712de4d86856&"

ROLE_MANAGE_REQUIRED = 1329910329701830686  # can use /shift manage
ROLE_SHIFT_ON = 1329910276912447608          # role when on shift
ROLE_BREAK = 1329910278195777557              # role when on break
ROLE_ADMIN = 1355842403134603275              # can use /shift admin and /shift logging

LOG_CHANNEL_ID = 1329910573739147296          # logs channel
MSG_COUNT_CHANNEL_ID = 1329910508182179900     # message-count channel
PROMOTIONS_CHANNEL_ID = 1329910502205427806    # promotions channel for ping tracking

# Quotas (minutes)
DEFAULT_QUOTA = 45
QUOTA_ROLE_0 = 1329910253814550608  # quota 0
QUOTA_ROLE_15 = 1329910255584546950 # quota 15
QUOTA_ROLE_35 = 1329910389437104220 # quota 35
QUOTA_ROLE_ADMIN_0 = 1355842403134603275 # quota 0 (admins)

# Promotion cooldowns (days)
PROMO_COOLDOWN_14 = 1355842403134603275  # 14 days
PROMO_COOLDOWN_10 = [1394667511374680105, 1329910280834252903]  # JCO/SCO: 10 days
PROMO_COOLDOWN_8 = 1329910281903673344   # 8 days
PROMO_COOLDOWN_6 = [1329910295703064577, 1355842399338889288]  # 6 days
PROMO_COOLDOWN_4 = 1329910298525696041   # 4 days

# Infraction thresholds (minutes)
WARN_THRESHOLD = 45  # under 45s is a warning
STRIKE_THRESHOLD = 30  # under 30 minutes is a strike
DEMOTION_THRESHOLD = 15  # under 15 minutes is a demotion

# -------------------- STORAGE PATHS --------------------
DATA_DIR = "data"
LOGS_DIR = os.path.join(DATA_DIR, "logs")
STATE_FILE = os.path.join(DATA_DIR, "shift_state.json")
RECORDS_FILE = os.path.join(DATA_DIR, "shift_records.json")
META_FILE = os.path.join(DATA_DIR, "meta.json")  # includes logging_enabled, last_reset_ts

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# -------------------- UTILITIES --------------------

def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def ts_to_int(ts: dt.datetime) -> int:
    return int(ts.timestamp())


def int_to_ts(t: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(t, tz=dt.timezone.utc)


def human_td(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s or not parts: parts.append(f"{s}s")
    return " ".join(parts)


def colour_ok() -> discord.Colour:
    return discord.Colour.brand_green()

def colour_warn() -> discord.Colour:
    return discord.Colour.orange()

def colour_err() -> discord.Colour:
    return discord.Colour.red()

def colour_info() -> discord.Colour:
    return discord.Colour.blurple()

# -------------------- PERSISTENCE LAYER --------------------
class Store:
    """Simple JSON-backed storage.
    state: per-user ongoing shifts
        {
          str(user_id): {
            "start_ts": int,
            "accum": int,            # accumulated seconds before current run
            "on_break": bool,
            "last_ts": int           # last timestamp of tick (for accumulation)
          }
        }
    records: list of completed shift dicts
        {
          "id": str, "user_id": int, "start_ts": int, "end_ts": int, "duration": int, "breaks": int
        }
    meta: {
        "logging_enabled": bool,
        "last_reset_ts": int,
        "manage_message_ids": {str(user_id): int},  # optional: last manage message id to edit
        "last_promotions": {str(user_id): int},  # last time user was pinged in promotions channel
        "infractions": {str(user_id): {"demotions": int, "strikes": int, "warns": int}}  # infraction counts
    }
    """

    def __init__(self):
        self.state: Dict[str, Any] = {}
        self.records: List[Dict[str, Any]] = []
        self.meta: Dict[str, Any] = {}
        self.load()

    def load(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        if os.path.exists(RECORDS_FILE):
            with open(RECORDS_FILE, "r", encoding="utf-8") as f:
                self.records = json.load(f)
        if os.path.exists(META_FILE):
            with open(META_FILE, "r", encoding="utf-8") as f:
                self.meta = json.load(f)
        # defaults
        if "logging_enabled" not in self.meta:
            self.meta["logging_enabled"] = True
        if "last_reset_ts" not in self.meta:
            self.meta["last_reset_ts"] = ts_to_int(utcnow())
        if "manage_message_ids" not in self.meta:
            self.meta["manage_message_ids"] = {}
        if "last_promotions" not in self.meta:
            self.meta["last_promotions"] = {}  # tracks when users were last pinged in promotions channel
        if "infractions" not in self.meta:
            self.meta["infractions"] = {}
        if "cooldown_extensions" not in self.meta:
            self.meta["cooldown_extensions"] = {}  # {user_id: extension_seconds}
        if "admin_cooldowns" not in self.meta:
            self.meta["admin_cooldowns"] = {}  # {user_id: admin_specified_days}

    def save(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)
        with open(RECORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.records, f, indent=2)
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, indent=2)

    # ---- Shift state helpers ----
    def is_on_shift(self, user_id: int) -> bool:
        return str(user_id) in self.state

    def get_user_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.state.get(str(user_id))

    def start_shift(self, user_id: int):
        now = ts_to_int(utcnow())
        self.state[str(user_id)] = {
            "start_ts": now,
            "accum": 0,
            "on_break": False,
            "last_ts": now,
            "breaks": 0,
        }
        self.save()

    def toggle_break(self, user_id: int) -> bool:
        now = ts_to_int(utcnow())
        st = self.state[str(user_id)]
        if st["on_break"]:
            # resume: set last_ts to now
            st["on_break"] = False
            st["last_ts"] = now
            self.save()
            return False  # now off break
        else:
            # go on break: accumulate until now
            st["accum"] += max(0, now - st["last_ts"])
            st["on_break"] = True
            st["breaks"] += 1
            self.save()
            return True   # now on break

    def stop_shift(self, user_id: int) -> Optional[Dict[str, Any]]:
        st = self.state.get(str(user_id))
        if not st:
            return None
        now = ts_to_int(utcnow())
        if not st["on_break"]:
            st["accum"] += max(0, now - st["last_ts"])
        record = {
            "id": uuid.uuid4().hex[:12],
            "user_id": user_id,
            "start_ts": st["start_ts"],
            "end_ts": now,
            "duration": st["accum"],
            "breaks": st.get("breaks", 0),
        }
        del self.state[str(user_id)]
        self.records.append(record)
        self.save()
        return record

    def void_shift(self, user_id: int) -> bool:
        if str(user_id) in self.state:
            del self.state[str(user_id)]
            self.save()
            return True
        return False

    def void_record_by_id(self, rec_id: str) -> bool:
        for i, r in enumerate(self.records):
            if r["id"] == rec_id:
                del self.records[i]
                self.save()
                return True
        return False

    def total_for_user(self, user_id: int) -> int:
        total = sum(r["duration"] for r in self.records if r["user_id"] == user_id)
        # add current active if any
        st = self.state.get(str(user_id))
        if st and not st["on_break"]:
            now = ts_to_int(utcnow())
            total += st["accum"] + max(0, now - st["last_ts"])
        elif st:
            total += st["accum"]
        return total

    def get_statistics(self) -> Tuple[int, int]:
        # number of unique shifts = number of records
        # total time = sum durations
        return len(self.records), sum(r["duration"] for r in self.records)

    def get_promotion_cooldown(self, user_id: int) -> int:
        """Get promotion cooldown in days for a user based on their highest role."""
        # This would need to be called with member roles, but for now return default
        return 4  # default cooldown

    def can_be_promoted(self, user_id: int, member_roles: List[discord.Role]) -> bool:
        """Check if user can be promoted based on cooldown."""
        role_ids = {r.id for r in member_roles}
        last_promo = self.meta["last_promotions"].get(str(user_id), 0)
        if last_promo == 0:
            return True  # never promoted before
        
        # Determine cooldown based on highest role
        cooldown_days = 4  # default
        if PROMO_COOLDOWN_14 in role_ids:
            cooldown_days = 14
        elif any(role_id in role_ids for role_id in PROMO_COOLDOWN_10):
            cooldown_days = 10
        elif PROMO_COOLDOWN_8 in role_ids:
            cooldown_days = 8
        elif any(role_id in role_ids for role_id in PROMO_COOLDOWN_6):
            cooldown_days = 6
        elif PROMO_COOLDOWN_4 in role_ids:
            cooldown_days = 4
        
        # Check if enough time has passed
        days_since_promo = (ts_to_int(utcnow()) - last_promo) / (24 * 60 * 60)
        return days_since_promo >= cooldown_days

    def record_promotion(self, user_id: int):
        """Record that a user was promoted. 
        NOTE: This method is deprecated. Promotions are now tracked automatically 
        when users are pinged in the promotions channel."""
        self.meta["last_promotions"][str(user_id)] = ts_to_int(utcnow())
        self.save()

    def get_infractions(self, user_id: int) -> Dict[str, int]:
        """Get infraction counts for a user."""
        return self.meta["infractions"].get(str(user_id), {"demotions": 0, "strikes": 0, "warns": 0})

    def add_infraction(self, user_id: int, infraction_type: str):
        """Add an infraction for a user."""
        if str(user_id) not in self.meta["infractions"]:
            self.meta["infractions"][str(user_id)] = {"demotions": 0, "strikes": 0, "warns": 0}
        self.meta["infractions"][str(user_id)][infraction_type] += 1
        self.save()


# -------------------- UI VIEWS --------------------
class ShiftManageView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def refresh_buttons(self, interaction: discord.Interaction, logging_enabled: bool, on_shift: bool, on_break: bool):
        # update button disabled states based on current status
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if not logging_enabled:
                    item.disabled = True
                else:
                    if item.custom_id == "shift_start":
                        item.disabled = on_shift  # cannot start if already on shift
                    elif item.custom_id == "shift_break":
                        item.disabled = (not on_shift) or (on_shift and on_break is None)
                        # more precise below
                        item.disabled = (not on_shift)
                    elif item.custom_id == "shift_stop":
                        item.disabled = (not on_shift) or (on_break)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Start Shift", style=discord.ButtonStyle.success, custom_id="shift_start")
    async def start_shift_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: ShiftCog = interaction.client.get_cog("ShiftCog")  # type: ignore
        assert cog is not None
        user = interaction.user
        guild = interaction.guild
        if guild is None:
            return
        # Check logging enabled
        if not cog.store.meta.get("logging_enabled", True):
            await interaction.response.edit_message(embed=cog.embed_info("Shift logging is currently disabled."), view=self)
            return
        # Check permission to use manage
        if not any(r.id == ROLE_MANAGE_REQUIRED for r in user.roles):  # type: ignore
            await interaction.response.edit_message(embed=cog.embed_error("You do not have permission to manage shifts."), view=self)
            return
        # Business logic
        st = cog.store.get_user_state(user.id)
        if st:
            # already on shift
            await interaction.response.edit_message(embed=cog.embed_warn("You're already on shift."), view=self)
            return
        cog.store.start_shift(user.id)
        # role changes
        role_on = guild.get_role(ROLE_SHIFT_ON)
        role_break = guild.get_role(ROLE_BREAK)
        try:
            if role_break and role_break in user.roles:  # type: ignore
                await user.remove_roles(role_break, reason="Shift start")  # type: ignore
            if role_on:
                await user.add_roles(role_on, reason="Shift start")  # type: ignore
        except discord.Forbidden:
            pass
        # log
        await cog.log_event(guild, f"🟢 {user.mention} started a shift.")
        # update UI with stats
        embed = await cog.build_manage_embed(user)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Toggle Break", style=discord.ButtonStyle.secondary, custom_id="shift_break")
    async def break_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: ShiftCog = interaction.client.get_cog("ShiftCog")  # type: ignore
        assert cog is not None
        user = interaction.user
        guild = interaction.guild
        if guild is None:
            return
        if not cog.store.meta.get("logging_enabled", True):
            await interaction.response.edit_message(embed=cog.embed_info("Shift logging is currently disabled."), view=self)
            return
        if not any(r.id == ROLE_MANAGE_REQUIRED for r in user.roles):  # type: ignore
            await interaction.response.edit_message(embed=cog.embed_error("You do not have permission to manage shifts."), view=self)
            return
        st = cog.store.get_user_state(user.id)
        if not st:
            await interaction.response.edit_message(embed=cog.embed_warn("You are not on a shift."), view=self)
            return
        now_on_break = cog.store.toggle_break(user.id)
        role_on = guild.get_role(ROLE_SHIFT_ON)
        role_break = guild.get_role(ROLE_BREAK)
        try:
            if now_on_break:
                if role_on and role_on in user.roles:  # type: ignore
                    await user.remove_roles(role_on, reason="Shift break")  # type: ignore
                if role_break:
                    await user.add_roles(role_break, reason="Shift break")  # type: ignore
                await cog.log_event(guild, f"⏸️ {user.mention} started a break.")
            else:
                if role_break and role_break in user.roles:  # type: ignore
                    await user.remove_roles(role_break, reason="Shift resume")  # type: ignore
                if role_on:
                    await user.add_roles(role_on, reason="Shift resume")  # type: ignore
                await cog.log_event(guild, f"▶️ {user.mention} ended their break.")
        except discord.Forbidden:
            pass
        embed = await cog.build_manage_embed(user)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stop Shift", style=discord.ButtonStyle.danger, custom_id="shift_stop")
    async def stop_shift_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: ShiftCog = interaction.client.get_cog("ShiftCog")  # type: ignore
        assert cog is not None
        user = interaction.user
        guild = interaction.guild
        if guild is None:
            return
        if not cog.store.meta.get("logging_enabled", True):
            await interaction.response.edit_message(embed=cog.embed_info("Shift logging is currently disabled."), view=self)
            return
        if not any(r.id == ROLE_MANAGE_REQUIRED for r in user.roles):  # type: ignore
            await interaction.response.edit_message(embed=cog.embed_error("You do not have permission to manage shifts."), view=self)
            return
        st = cog.store.get_user_state(user.id)
        if not st:
            await interaction.response.edit_message(embed=cog.embed_warn("You are not on a shift."), view=self)
            return
        if st.get("on_break"):
            await interaction.response.edit_message(embed=cog.embed_warn("You cannot stop while on break. End break first."), view=self)
            return
        record = cog.store.stop_shift(user.id)
        role_on = guild.get_role(ROLE_SHIFT_ON)
        role_break = guild.get_role(ROLE_BREAK)
        try:
            if role_on and role_on in user.roles:  # type: ignore
                await user.remove_roles(role_on, reason="Shift stop")  # type: ignore
            if role_break and role_break in user.roles:  # type: ignore
                await user.remove_roles(role_break, reason="Shift stop")  # type: ignore
        except discord.Forbidden:
            pass
        await cog.log_event(guild, f"🔴 {user.mention} stopped their shift. ID: `{record['id']}` Duration: **{human_td(record['duration'])}**")
        embed = await cog.build_manage_embed(user)
        await interaction.response.edit_message(embed=embed, view=self)

class ShiftLeaderboardView(discord.ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild = guild

    @discord.ui.button(label="All", style=discord.ButtonStyle.primary)
    async def all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lines = await self.cog._build_leaderboard_lines(self.guild, filter_mode="all")
        emb = self.cog.base_embed("Shift Leaderboard", colour_info())
        emb.description = "\n".join(lines)
        await interaction.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="Exempt", style=discord.ButtonStyle.secondary)
    async def exempt_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lines = await self.cog._build_leaderboard_lines(self.guild, filter_mode="exempt")
        emb = self.cog.base_embed("Exempt Leaderboard", discord.Colour.light_grey())
        emb.description = "\n".join(lines)
        await interaction.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="Met", style=discord.ButtonStyle.success)
    async def met_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lines = await self.cog._build_leaderboard_lines(self.guild, filter_mode="leaderboard_met")
        emb = self.cog.base_embed("Met Quota Leaderboard", colour_ok())
        emb.description = "\n".join(lines)
        await interaction.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="Not Met", style=discord.ButtonStyle.danger)
    async def notmet_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lines = await self.cog._build_leaderboard_lines(self.guild, filter_mode="leaderboard_notmet")
        emb = self.cog.base_embed("Not Met Quota Leaderboard", colour_err())
        emb.description = "\n".join(lines)
        await interaction.response.edit_message(embed=emb, view=self)

class ShiftListsView(discord.ui.View):
    def __init__(self, cog, guild, promo_candidates, infractions):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild = guild
        self.promo_candidates = promo_candidates
        self.infractions = infractions
        self.current_embed_type = "promotion"  # Track which embed is currently shown

    @discord.ui.button(label="Remove from Promotion List", style=discord.ButtonStyle.danger, row=0)
    async def remove_promo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Type the number of the user to remove from the promotion list.", ephemeral=True)
        def check(m):
            return m.author.id == interaction.user.id and m.channel == interaction.channel
        try:
            msg = await self.cog.bot.wait_for("message", check=check, timeout=60)
            idx = int(msg.content.strip())
            if 1 <= idx <= len(self.promo_candidates):
                member, _ = self.promo_candidates[idx-1]
                del self.promo_candidates[idx-1]
                await interaction.channel.send(f"Removed {member.mention} from promotion list.")
                # Refresh the embed
                await self.refresh_embed(interaction)
            else:
                await interaction.channel.send("Invalid number.")
        except Exception:
            await interaction.channel.send("Failed to remove user.")

    @discord.ui.button(label="Add to Promotion List by User ID", style=discord.ButtonStyle.success, row=0)
    async def add_promo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Type the user ID to add to the promotion list.", ephemeral=True)
        def check(m):
            return m.author.id == interaction.user.id and m.channel == interaction.channel
        try:
            msg = await self.cog.bot.wait_for("message", check=check, timeout=60)
            user_id = int(msg.content.strip())
            member = self.guild.get_member(user_id)
            if member:
                # Get user's total shift time
                total_seconds = self.cog.store.total_for_user(member.id)
                self.promo_candidates.append((member, total_seconds))
                # Sort by shift time (highest first)
                self.promo_candidates.sort(key=lambda x: x[1], reverse=True)
                await interaction.channel.send(f"Added {member.mention} to promotion list.")
                # Refresh the embed
                await self.refresh_embed(interaction)
            else:
                await interaction.channel.send("User not found.")
        except Exception:
            await interaction.channel.send("Failed to add user.")

    @discord.ui.button(label="Remove from Infractions List", style=discord.ButtonStyle.danger, row=1)
    async def remove_infraction(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Type the number of the user to remove from the infractions list.", ephemeral=True)
        all_infractions = self.infractions["demotions"] + self.infractions["strikes"] + self.infractions["warns"]
        def check(m):
            return m.author.id == interaction.user.id and m.channel == interaction.channel
        try:
            msg = await self.cog.bot.wait_for("message", check=check, timeout=60)
            idx = int(msg.content.strip())
            if 1 <= idx <= len(all_infractions):
                member, _ = all_infractions[idx-1]
                # Remove from appropriate category
                for category in ["demotions", "strikes", "warns"]:
                    for i, (m, _) in enumerate(self.infractions[category]):
                        if m.id == member.id:
                            del self.infractions[category][i]
                            break
                await interaction.channel.send(f"Removed {member.mention} from infractions list.")
                # Refresh the embed
                await self.refresh_embed(interaction)
            else:
                await interaction.channel.send("Invalid number.")
        except Exception:
            await interaction.channel.send("Failed to remove user.")

    @discord.ui.button(label="Add to Infractions List by User ID", style=discord.ButtonStyle.success, row=1)
    async def add_infraction(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Type the user ID to add to the infractions list.", ephemeral=True)
        def check(m):
            return m.author.id == interaction.user.id and m.channel == interaction.channel
        try:
            msg = await self.cog.bot.wait_for("message", check=check, timeout=60)
            user_id = int(msg.content.strip())
            member = self.guild.get_member(user_id)
            if member:
                # Get user's total shift time and quota to determine infraction type
                total_seconds = self.cog.store.total_for_user(member.id)
                quota_minutes = await self.cog._get_quota(member)
                
                if total_seconds < quota_minutes * 60:
                    minutes_short = quota_minutes - (total_seconds / 60)
                    if minutes_short >= 15:  # DEMOTION_THRESHOLD
                        self.infractions["demotions"].append((member, total_seconds))
                    elif minutes_short >= 30:  # STRIKE_THRESHOLD
                        self.infractions["strikes"].append((member, total_seconds))
                    else:
                        self.infractions["warns"].append((member, total_seconds))
                    
                    # Sort the category by shift time
                    if minutes_short >= 15:
                        self.infractions["demotions"].sort(key=lambda x: x[1])
                    elif minutes_short >= 30:
                        self.infractions["strikes"].sort(key=lambda x: x[1])
                    else:
                        self.infractions["warns"].sort(key=lambda x: x[1])
                    
                    await interaction.channel.send(f"Added {member.mention} to infractions list.")
                    # Refresh the embed
                    await self.refresh_embed(interaction)
                else:
                    await interaction.channel.send(f"{member.mention} meets their quota, no infraction needed.")
            else:
                await interaction.channel.send("User not found.")
        except Exception:
            await interaction.channel.send("Failed to add user.")

    @discord.ui.button(label="Get Copy-Pastable Text", style=discord.ButtonStyle.primary, row=2)
    async def copy_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_embed_type == "promotion":
            text = self._generate_promotion_text()
        else:
            text = self._generate_infractions_text()
        
        await interaction.response.send_message(f"```\n{text}\n```", ephemeral=True)

    async def refresh_embed(self, interaction: discord.Interaction):
        """Refresh the current embed with updated data."""
        if self.current_embed_type == "promotion":
            embed = await self.cog._build_promotion_embed(self.promo_candidates)
        else:
            embed = await self.cog._build_infractions_embed(self.infractions)
        
        await interaction.edit_original_response(embed=embed, view=self)

    def _generate_promotion_text(self) -> str:
        """Generate copy-pastable text for promotion list."""
        lines = [f"## <:MaplecliffNationalGaurd:1409463907294384169>  Promotions {utcnow().strftime('%Y-%m-%d')} <:MaplecliffNationalGaurd:1409463907294384169>"]
        lines.append("-#      ")
        lines.append("")
        
        if not self.promo_candidates:
            lines.append("No eligible candidates for promotion.")
        else:
            for i, (member, total_seconds) in enumerate(self.promo_candidates, 1):
                time_str = self.cog._format_duration(total_seconds)
                
                # Add cooldown information
                last_promo_ts = self.cog.store.meta["last_promotions"].get(str(member.id), 0)
                if last_promo_ts == 0:
                    cooldown_info = "🆕 First promotion"
                else:
                    from datetime import datetime, timezone
                    days_since = (int(datetime.now(timezone.utc).timestamp()) - last_promo_ts) / (24 * 60 * 60)
                    cooldown_info = f"⏰ {days_since:.0f}d since last"
                
                lines.append(f"> `{i}.` <@{member.id}> • {time_str} • {cooldown_info}")
            
            lines.append("")
            lines.append("Congratulations to all 🎉")
        
        return "\n".join(lines)

    def _generate_infractions_text(self) -> str:
        """Generate copy-pastable text for infractions list."""
        lines = [f"## <:MaplecliffNationalGaurd:1409463907294384169>  Infractions {utcnow().strftime('%Y-%m-%d')} <:MaplecliffNationalGaurd:1409463907294384169>"]
        lines.append("-#      ")
        lines.append("")
        
        # Demotions
        if self.infractions["demotions"]:
            lines.append("***__Demotions__***")
            for i, (member, total_seconds) in enumerate(self.infractions["demotions"], 1):
                time_str = self.cog._format_duration(total_seconds)
                lines.append(f"> `{i}.` <@{member.id}> • {time_str}")
            lines.append("")
        
        # Strikes
        if self.infractions["strikes"]:
            lines.append("***__Strikes__***")
            for i, (member, total_seconds) in enumerate(self.infractions["strikes"], 1):
                time_str = self.cog._format_duration(total_seconds)
                lines.append(f"> `{i}.` <@{member.id}> • {time_str}")
            lines.append("")
        
        # Warns
        if self.infractions["warns"]:
            lines.append("***__Warns__***")
            for i, (member, total_seconds) in enumerate(self.infractions["warns"], 1):
                time_str = self.cog._format_duration(total_seconds)
                lines.append(f"> `{i}.` <@{member.id}> • {time_str}")
        
        if not any(self.infractions.values()):
            lines.append("No infractions found.")
        
        return "\n".join(lines)

# -------------------- MAIN COG --------------------
class ShiftCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = Store()
        # re-add persistent view on startup
        self.bot.add_view(ShiftManageView(bot))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track when users are pinged in the promotions channel for cooldown calculation."""
        # Only track messages in the promotions channel
        if message.channel.id != PROMOTIONS_CHANNEL_ID:
            return
        
        # Skip bot messages
        if message.author.bot:
            return
        
        # Check if message contains any user mentions
        if not message.mentions:
            return
        
        # Record the timestamp for each mentioned user
        timestamp = ts_to_int(utcnow())
        guild = message.guild
        if not guild:
            return
            
        updated = False
        for user in message.mentions:
            # Get the full member object to check roles
            member = guild.get_member(user.id)
            if member and any(r.id == ROLE_MANAGE_REQUIRED for r in member.roles):
                self.store.meta["last_promotions"][str(user.id)] = timestamp
                updated = True
                print(f"🎯 Recorded ping for {user.display_name} (ID: {user.id}) in promotions channel")
                # DM notifications for cooldown start and schedule end notification
                try:
                    cooldown_days, seconds_remaining = self._calculate_member_cooldown(member)
                    if cooldown_days > 0:
                        try:
                            embed = self.base_embed("Promotion Cooldown Started", colour_warn())
                            embed.description = f"You have been placed on a promotion cooldown for **{cooldown_days} day(s)**."
                            embed.add_field(name="Cooldown Ends", value=f"<t:{timestamp + seconds_remaining}:R>", inline=True)
                            embed.add_field(name="Duration", value=human_td(seconds_remaining), inline=True)
                            embed.set_footer(text="You will be notified when your cooldown expires.")
                            await member.send(embed=embed)
                        except Exception:
                            pass
                        # schedule end DM (best-effort; not persistent across restarts)
                        asyncio.create_task(self._schedule_cooldown_end_dm(member.id, timestamp + seconds_remaining))
                except Exception as e:
                    print(f"Failed to DM cooldown info to {user.display_name}: {e}")
            elif member:
                print(f"⚠️ User {user.display_name} mentioned but doesn't have manage role")
            else:
                print(f"❌ Could not find member {user.display_name} in guild")
        
        # Save the updated data
        if updated:
            self.store.save()

    # ---------- EMBED HELPERS ----------
    def base_embed(self, title: str, colour: discord.Colour) -> discord.Embed:
        e = discord.Embed(title=title, colour=colour, timestamp=utcnow())
        e.set_image(url=IMAGE_URL)
        return e

    def embed_info(self, desc: str) -> discord.Embed:
        e = self.base_embed("Shift", colour_info())
        e.description = desc
        return e

    def embed_warn(self, desc: str) -> discord.Embed:
        e = self.base_embed("Warning", colour_warn())
        e.description = desc
        return e

    def embed_error(self, desc: str) -> discord.Embed:
        e = self.base_embed("Error", colour_err())
        e.description = desc
        return e

    async def log_event(self, guild: discord.Guild, message: str):
        # write to file
        logline = f"[{utcnow().isoformat()}] {message}\n"
        with open(os.path.join(LOGS_DIR, f"{utcnow().date()}.log"), "a", encoding="utf-8") as f:
            f.write(logline)
        # send embed
        ch = guild.get_channel(LOG_CHANNEL_ID)
        if isinstance(ch, discord.TextChannel):
            emb = self.base_embed("Shift Log", colour_info())
            emb.description = message
            await ch.send(embed=emb)

    # ---------- COMMANDS ----------
    @app_commands.command(name="shift_manage", description="Open the shift management panel.")
    async def shift_manage(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        if not any(r.id == ROLE_MANAGE_REQUIRED for r in user.roles):  # type: ignore
            await interaction.response.send_message("You do not have the required role to manage shifts.", ephemeral=True)
            return
        # if logging disabled, end all current shifts and log - handled by /shift logging, but buttons should be disabled
        view = ShiftManageView(self.bot)
        embed = await self.build_manage_embed(user)
        msg = await interaction.response.send_message(embed=embed, view=view)

    async def build_manage_embed(self, user: discord.Member) -> discord.Embed:
        st = self.store.get_user_state(user.id)
        logging_enabled = self.store.meta.get("logging_enabled", True)
        if not logging_enabled:
            colour = colour_err()
            status = "Logging Disabled"
        elif not st:
            colour = colour_err()
            status = "Not on shift"
        elif st.get("on_break"):
            colour = colour_warn()
            status = "On Break"
        else:
            colour = colour_ok()
            status = "Active"

        e = self.base_embed("Shift Manager", colour)
        e.add_field(name="Logging", value="Enabled" if logging_enabled else "Disabled", inline=True)
        e.add_field(name="Status", value=status, inline=True)
        if st:
            e.add_field(name="Started", value=f"<t:{st['start_ts']}:T> (\u200b<t:{st['start_ts']}:R>\u200b)", inline=True)
            elapsed = st["accum"]
            if not st["on_break"]:
                elapsed += max(0, ts_to_int(utcnow()) - st["last_ts"])
            # Show elapsed as a Discord timestamp (duration since start)
            elapsed_ts = st["start_ts"] + elapsed
            e.add_field(
                name="Elapsed",
                value=f"{human_td(elapsed)} (<t:{elapsed_ts}:R>)",
                inline=True
            )
        e.set_footer(text=f"User: {user.display_name}")
        return e

# ---------------- ADMIN ----------------
    admin_group = app_commands.Group(name="shift_admin", description="Administrative shift controls.")

    @admin_group.command(name="user", description="Admin actions for a specific user (optional user to target).")
    @app_commands.describe(personnel="User to target (optional)", action="Choose an action", time_minutes="Time in minutes (for add/subtract time actions)", record_id="Record ID (for void by ID action)")
    @app_commands.choices(action=[
        app_commands.Choice(name="Stop shift", value="stop"),
        app_commands.Choice(name="Toggle break", value="toggle_break"),
        app_commands.Choice(name="Void ongoing shift", value="void"),
        app_commands.Choice(name="Show shift records", value="records"),
        app_commands.Choice(name="Void shift by ID", value="void_id"),
        app_commands.Choice(name="Add shift time", value="add_time"),
        app_commands.Choice(name="Subtract shift time", value="subtract_time"),
    ])
    async def shift_admin_user(self, interaction: discord.Interaction, action: app_commands.Choice[str], personnel: Optional[discord.Member] = None, record_id: Optional[str] = None, time_minutes: Optional[int] = None):
        user = interaction.user
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        if not any(r.id == ROLE_ADMIN for r in user.roles):  # type: ignore
            await interaction.response.send_message("You lack admin role.", ephemeral=True)
            return
        target = personnel or user
        if action.value == "stop":
            rec = self.store.stop_shift(target.id)
            if rec:
                role_on = guild.get_role(ROLE_SHIFT_ON)
                role_break = guild.get_role(ROLE_BREAK)
                try:
                    if role_on and role_on in target.roles:  # type: ignore
                        await target.remove_roles(role_on, reason="Admin stop shift")  # type: ignore
                    if role_break and role_break in target.roles:  # type: ignore
                        await target.remove_roles(role_break, reason="Admin stop shift")  # type: ignore
                except discord.Forbidden:
                    pass
                await self.log_event(guild, f"🛑 Admin {user.mention} stopped {target.mention}'s shift. ID `{rec['id']}` ({human_td(rec['duration'])}).")
                emb = self.base_embed("Admin", colour_ok())
                emb.description = f"Stopped {target.mention}'s shift. ID `{rec['id']}` Duration **{human_td(rec['duration'])}**."
                await interaction.response.send_message(embed=emb, ephemeral=True)
            else:
                await interaction.response.send_message(embed=self.embed_warn("Target not on a shift."), ephemeral=True)
        elif action.value == "toggle_break":
            st = self.store.get_user_state(target.id)
            if not st:
                await interaction.response.send_message(embed=self.embed_warn("Target not on a shift."), ephemeral=True)
                return
            now_on_break = self.store.toggle_break(target.id)
            role_on = guild.get_role(ROLE_SHIFT_ON)
            role_break = guild.get_role(ROLE_BREAK)
            try:
                if now_on_break:
                    if role_on and role_on in target.roles:  # type: ignore
                        await target.remove_roles(role_on, reason="Admin set break")  # type: ignore
                    if role_break:
                        await target.add_roles(role_break, reason="Admin set break")  # type: ignore
                else:
                    if role_break and role_break in target.roles:  # type: ignore
                        await target.remove_roles(role_break, reason="Admin end break")  # type: ignore
                    if role_on:
                        await target.add_roles(role_on, reason="Admin end break")  # type: ignore
            except discord.Forbidden:
                pass
            await self.log_event(guild, f"⏯️ Admin {user.mention} toggled break for {target.mention} -> {'On Break' if now_on_break else 'Active' }.")
            emb = self.base_embed("Admin", colour_info())
            emb.description = f"Toggled break for {target.mention}. Now **{'On Break' if now_on_break else 'Active'}**."
            await interaction.response.send_message(embed=emb, ephemeral=True)
        elif action.value == "void":
            ok = self.store.void_shift(target.id)
            await self.log_event(guild, f"♻️ Admin {user.mention} voided ongoing shift for {target.mention}.")
            await interaction.response.send_message(embed=self.embed_info(f"Voided ongoing shift for {target.mention}."), ephemeral=True)
        elif action.value == "records":
            # show last 10 records
            recs = [r for r in self.store.records if r["user_id"] == target.id][-10:]
            emb = self.base_embed("Shift Records", colour_info())
            if not recs:
                emb.description = "No records."
            else:
                lines = []
                for r in recs:
                    lines.append(f"`{r['id']}` | {human_td(r['duration'])} | <t:{r['start_ts']}:F> → <t:{r['end_ts']}:F>")
                emb.description = "\n".join(lines)
            await interaction.response.send_message(embed=emb, ephemeral=True)
        elif action.value == "void_id":
            if not record_id:
                await interaction.response.send_message("Provide `record_id:` as additional option in the command.", ephemeral=True)
                return
            ok = self.store.void_record_by_id(record_id)
            await self.log_event(guild, f"🧹 Admin {user.mention} voided record `{record_id}` for {target.mention}.")
            await interaction.response.send_message(embed=self.embed_info(f"Voided record `{record_id}`."), ephemeral=True)
        elif action.value == "add_time":
            if not time_minutes:
                await interaction.response.send_message("Provide `time_minutes:` as additional option in the command.", ephemeral=True)
                return
            if time_minutes <= 0:
                await interaction.response.send_message("Time must be positive.", ephemeral=True)
                return
            # Add time to user's total by creating a fake record
            fake_record = {
                "id": f"admin_add_{uuid.uuid4().hex[:8]}",
                "user_id": target.id,
                "start_ts": ts_to_int(utcnow()) - (time_minutes * 60),
                "end_ts": ts_to_int(utcnow()),
                "duration": time_minutes * 60,
                "breaks": 0,
            }
            self.store.records.append(fake_record)
            self.store.save()
            await self.log_event(guild, f"➕ Admin {user.mention} added {time_minutes} minutes to {target.mention}'s total shift time.")
            await interaction.response.send_message(embed=self.embed_info(f"Added {time_minutes} minutes to {target.mention}'s total shift time."), ephemeral=True)
        elif action.value == "subtract_time":
            if not time_minutes:
                await interaction.response.send_message("Provide `time_minutes:` as additional option in the command.", ephemeral=True)
                return
            if time_minutes <= 0:
                await interaction.response.send_message("Time must be positive.", ephemeral=True)
                return
            # Subtract time by creating a negative duration record
            fake_record = {
                "id": f"admin_sub_{uuid.uuid4().hex[:8]}",
                "user_id": target.id,
                "start_ts": ts_to_int(utcnow()),
                "end_ts": ts_to_int(utcnow()),
                "duration": -(time_minutes * 60),  # Negative duration
                "breaks": 0,
            }
            self.store.records.append(fake_record)
            self.store.save()
            await self.log_event(guild, f"➖ Admin {user.mention} subtracted {time_minutes} minutes from {target.mention}'s total shift time.")
            await interaction.response.send_message(embed=self.embed_info(f"Subtracted {time_minutes} minutes from {target.mention}'s total shift time."), ephemeral=True)

    @admin_group.command(name="global", description="Global admin actions when no personnel is specified.")
    @app_commands.describe(action="Choose an action")
    @app_commands.choices(action=[
        app_commands.Choice(name="Void shift by ID", value="void_id"),
        app_commands.Choice(name="Void ALL shifts (requires confirmation)", value="void_all"),
        app_commands.Choice(name="Get shift statistics", value="stats"),
        app_commands.Choice(name="Get shift leaderboard (txt)", value="leaderboard_txt"),
        app_commands.Choice(name="Get shift leaderboard: met quota", value="leaderboard_met"),
        app_commands.Choice(name="Get shift leaderboard: not met quota", value="leaderboard_notmet"),
        app_commands.Choice(name="Get promotion list", value="promotion_list"),
        app_commands.Choice(name="Get infractions list", value="infractions_list"),
    ])
    async def shift_admin_global(self, interaction: discord.Interaction, action: app_commands.Choice[str], record_id: Optional[str] = None, confirmation: Optional[str] = None):
        user = interaction.user
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        if not any(r.id == ROLE_ADMIN for r in user.roles):  # type: ignore
            await interaction.response.send_message("You lack admin role.", ephemeral=True)
            return

        if action.value == "void_id":
            if not record_id:
                await interaction.response.send_message("Provide `record_id:`.", ephemeral=True)
                return
            ok = self.store.void_record_by_id(record_id)
            await self.log_event(guild, f"🧹 Admin {user.mention} voided record `{record_id}`.")
            await interaction.response.send_message(embed=self.embed_info(f"Voided record `{record_id}`."), ephemeral=True)
            return
        elif action.value == "void_all":
            token = uuid.uuid4().hex[:8]
            await interaction.response.send_message(
                f"To confirm deletion of all ongoing shifts AND all shift records from this week, type this token in chat: **{token}**",
                ephemeral=True
            )
            def check(m):
                return m.author.id == user.id and m.channel == interaction.channel
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                await interaction.channel.send("Confirmation failed (timeout). No shifts voided.")
                return
            if msg.content.strip() != token:
                await interaction.channel.send("Confirmation failed. No shifts voided.")
                return

            # Calculate start of current week (Monday 00:00 UTC)
            now = utcnow()
            week_start = now - dt.timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start_ts = ts_to_int(week_start)

            # Remove all records started this week
            before_count = len(self.store.records)
            self.store.records = [r for r in self.store.records if r["start_ts"] < week_start_ts]
            removed_count = before_count - len(self.store.records)

            # Remove all ongoing shifts
            ongoing_count = len(self.store.state)
            self.store.state = {}

            # Reset stats since last reset
            self.store.meta["last_reset_ts"] = ts_to_int(now)

            # --- NEW: Reset all infractions and promotions ---
            self.store.meta["infractions"] = {}
            self.store.meta["last_promotions"] = {}

            # --- NEW: Set all users' total shift time to 0 by clearing all records ---
            self.store.records = []

            self.store.save()

            # Remove leaderboard files in data/
            for path in glob.glob(os.path.join(DATA_DIR, "leaderboard_*.txt")):
                try:
                    os.remove(path)
                except Exception:
                    pass

            # Remove shift log files in data/logs/
            for path in glob.glob(os.path.join(LOGS_DIR, "*.log")):
                try:
                    os.remove(path)
                except Exception:
                    pass

            await self.log_event(
                guild,
                f"⚠️ Admin {user.mention} voided **ALL** ongoing shifts ({ongoing_count}) and **{removed_count}** shift records from this week. Stats since reset restarted. **All shift times set to 0.**"
            )
            await interaction.channel.send(
                embed=self.embed_warn(
                    f"Voided all ongoing shifts ({ongoing_count}) and {removed_count} shift records from this week.\n**Stats since reset have been restarted. All shift times set to 0.**"
                )
            )
            return
        elif action.value == "stats":
            try:
                num_records, total_seconds = self.store.get_statistics()
                # extra: number of people with manage role
                manage_role = guild.get_role(ROLE_MANAGE_REQUIRED)
                role_count = len(manage_role.members) if manage_role else 0
                # messages since last reset - with timeout protection
                last_reset = int_to_ts(self.store.meta.get("last_reset_ts", ts_to_int(utcnow())))
                
                # Use asyncio.wait_for to add a timeout to message counting
                try:
                    msg_count = await asyncio.wait_for(
                        self.count_messages_since(guild, last_reset), 
                        timeout=10.0  # 10 second timeout
                    )
                except asyncio.TimeoutError:
                    msg_count = 0  # Default to 0 if timeout occurs
                    print("Message counting timed out, using 0 as default")
                
                emb = self.base_embed("Shift Stats (Global)", colour_info())
                emb.add_field(name="Total unique shifts", value=str(num_records), inline=True)
                emb.add_field(name="Total shift time", value=human_td(total_seconds), inline=True)
                emb.add_field(name="Since reset", value=f"<t:{ts_to_int(last_reset)}:F>", inline=True)
                emb.add_field(name="Messages since reset (in personnel-chat channel)", value=str(msg_count), inline=True)
                emb.add_field(name="Members with personnel role", value=str(role_count), inline=True)
                await interaction.response.send_message(embed=emb, ephemeral=False)
                return
            except Exception as e:
                # Fallback response if anything goes wrong
                print(f"Error in stats command: {e}")
                emb = self.base_embed("Shift Stats (Global)", colour_err())
                emb.description = f"Error retrieving statistics: {str(e)}"
                await interaction.response.send_message(embed=emb, ephemeral=True)
                return
        elif action.value in ("leaderboard_txt", "leaderboard_met", "leaderboard_notmet"):
            # build leaderboard lines
            lines = await self._build_leaderboard_lines(guild, filter_mode=action.value)
            # write file
            path = os.path.join(DATA_DIR, f"leaderboard_{action.value}_{utcnow().date()}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            await interaction.response.send_message(file=discord.File(path), ephemeral=True)
            return
        elif action.value == "promotion_list":
            promo_candidates, infractions = await self._build_lists(guild)
            embed = await self._build_promotion_embed(promo_candidates)
            view = ShiftListsView(self, guild, promo_candidates, infractions)
            view.current_embed_type = "promotion"
            await interaction.response.send_message(embed=embed, view=view)
            return
        elif action.value == "infractions_list":
            promo_candidates, infractions = await self._build_lists(guild)
            embed = await self._build_infractions_embed(infractions)
            view = ShiftListsView(self, guild, promo_candidates, infractions)
            view.current_embed_type = "infractions"
            await interaction.response.send_message(embed=embed, view=view)
            return
        elif action.value == "set_wipe":
            # Set current time as wipe timestamp
            self.store.meta["last_wipe_ts"] = ts_to_int(utcnow())
            self.store.save()
            await self.log_event(guild, f"🔄 Admin {user.mention} set wipe timestamp to now.")
            await interaction.response.send_message(embed=self.embed_info("Wipe timestamp set to current time. Message counting will now start from this point."), ephemeral=True)
            return

    async def _build_leaderboard_lines(self, guild: discord.Guild, filter_mode: str = "all") -> List[str]:
        manage_role = guild.get_role(ROLE_MANAGE_REQUIRED)
        if not manage_role:
            return ["No data."]
        members = manage_role.members

        totals: Dict[int, int] = {}
        for member in members:
            total = self.store.total_for_user(member.id)
            totals[member.id] = total

        rows: List[Tuple[int, str, int, bool, int]] = []
        for uid, secs in totals.items():
            member = guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            quota = await self._get_quota(member)
            met = secs >= quota * 60 if member else False
            rows.append((secs, name, uid, met, quota))
        rows.sort(key=lambda x: x[0], reverse=True)
        # filter
        if filter_mode == "leaderboard_met":
            rows = [r for r in rows if r[3] and not (r[0] == 0 and r[4] == 0)]
        elif filter_mode == "leaderboard_notmet":
            rows = [r for r in rows if not r[3] and not (r[0] == 0 and r[4] == 0)]
        elif filter_mode == "exempt":
            rows = [r for r in rows if r[0] == 0 and r[4] == 0]
        # format
        out = []
        rank = 1
        for secs, name, uid, met, quota in rows:
            if secs == 0 and quota == 0:
                status = "<:maybe:1358812794585354391> Exempt"
            else:
                status = "✅ Met" if met else "❌ Not met"
            out.append(f"#{rank} <@{uid}> — {human_td(secs)} — {status}")
            rank += 1
        if not out:
            out = ["No data."]
        return out

    async def _get_quota(self, member: Optional[discord.Member]) -> int:
        if member is None:
            return DEFAULT_QUOTA
        mids = {r.id for r in member.roles}
        if QUOTA_ROLE_0 in mids or QUOTA_ROLE_ADMIN_0 in mids:
            return 0
        elif QUOTA_ROLE_15 in mids:
            return 15
        elif QUOTA_ROLE_35 in mids:
            return 30
        elif ROLE_MANAGE_REQUIRED in mids:  # Include 1329910329701830686 role in quota logic
            return DEFAULT_QUOTA
        else:
            return DEFAULT_QUOTA

    async def count_messages_since(self, guild: discord.Guild, since: dt.datetime) -> int:
        ch = guild.get_channel(MSG_COUNT_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            return 0
        
        try:
            # Use a more efficient approach with reasonable limits
            # Count messages in reverse order (newest first) for better performance
            count = 0
            max_messages = 1000  # Reasonable limit to prevent timeout
            message_count = 0
            
            async for msg in ch.history(after=since, limit=max_messages, oldest_first=False):
                message_count += 1
                count += 1
                
                # Stop if we've reached our limit
                if message_count >= max_messages:
                    break
                    
            return count
        except Exception as e:
            # If there's any error (timeout, permission, etc.), return 0
            print(f"Error counting messages: {e}")
            return 0

    async def _build_lists(self, guild: discord.Guild) -> Tuple[List[Tuple[discord.Member, int]], Dict[str, List[Tuple[discord.Member, int]]]]:
        manage_role = guild.get_role(ROLE_MANAGE_REQUIRED)
        if not manage_role:
            return [], {"demotions": [], "strikes": [], "warns": []}
        
        members = manage_role.members
        promo_candidates = []
        infractions = {"demotions": [], "strikes": [], "warns": []}
        
        for member in members:
            total_seconds = self.store.total_for_user(member.id)
            quota_minutes = await self._get_quota(member)
            mids = {r.id for r in member.roles}

            # Exemption logic
            if QUOTA_ROLE_0 in mids or QUOTA_ROLE_ADMIN_0 in mids:
                continue  # Fully exempt
            if QUOTA_ROLE_15 in mids and total_seconds >= 15 * 60:
                continue  # Exempt above 15 minutes

            # Promotion eligibility
            if total_seconds >= 90 * 60 and self.store.can_be_promoted(member.id, member.roles):
                promo_candidates.append((member, total_seconds))
            
            # Infractions
            if total_seconds < quota_minutes * 60:
                minutes_short = quota_minutes - (total_seconds / 60)
                if minutes_short >= DEMOTION_THRESHOLD:
                    infractions["demotions"].append((member, total_seconds))
                elif minutes_short >= STRIKE_THRESHOLD:
                    infractions["strikes"].append((member, total_seconds))
                elif minutes_short >= WARN_THRESHOLD / 60:
                    infractions["warns"].append((member, total_seconds))
        
        promo_candidates.sort(key=lambda x: x[1], reverse=True)
        for infraction_type in infractions:
            infractions[infraction_type].sort(key=lambda x: x[1])
        
        return promo_candidates, infractions

    async def _build_promotion_embed(self, promo_candidates: List[Tuple[discord.Member, int]]) -> discord.Embed:
        """Build the promotion list embed."""
        embed = self.base_embed("", colour_info())
        embed.title = f"<:MaplecliffNationalGaurd:1409463907294384169>  Promotions {utcnow().strftime('%Y-%m-%d')} <:MaplecliffNationalGaurd:1409463907294384169>"
        
        if not promo_candidates:
            embed.description = "No eligible candidates for promotion."
            return embed
        
        lines = []
        for i, (member, total_seconds) in enumerate(promo_candidates, 1):
            time_str = self._format_duration(total_seconds)
            
            # Add cooldown information
            last_promo_ts = self.store.meta["last_promotions"].get(str(member.id), 0)
            if last_promo_ts == 0:
                cooldown_info = "🆕 First promotion"
            else:
                days_since = (ts_to_int(utcnow()) - last_promo_ts) / (24 * 60 * 60)
                cooldown_info = f"⏰ {days_since:.0f}d since last"
            
            lines.append(f"> `{i}.` <@{member.id}> • {time_str} • {cooldown_info}")
        
        embed.description = "\n".join(lines) + "\n\nCongratulations to all 🎉"
        return embed

    async def _build_infractions_embed(self, infractions: Dict[str, List[Tuple[discord.Member, int]]]) -> discord.Embed:
        """Build the infractions list embed."""
        embed = self.base_embed("", colour_err())
        embed.title = f"<:MaplecliffNationalGaurd:1409463907294384169>  Infractions {utcnow().strftime('%Y-%m-%d')} <:MaplecliffNationalGaurd:1409463907294384169>"
        
        sections = []
        
        # Demotions
        if infractions["demotions"]:
            lines = []
            for i, (member, total_seconds) in enumerate(infractions["demotions"], 1):
                time_str = self._format_duration(total_seconds)
                lines.append(f"> `{i}.` <@{member.id}> • {time_str}")
            sections.append("***__Demotions__***\n" + "\n".join(lines))
        
        # Strikes
        if infractions["strikes"]:
            lines = []
            for i, (member, total_seconds) in enumerate(infractions["strikes"], 1):
                time_str = self._format_duration(total_seconds)
                lines.append(f"> `{i}.` <@{member.id}> • {time_str}")
            sections.append("***__Strikes__***\n" + "\n".join(lines))
        
        # Warns
        if infractions["warns"]:
            lines = []
            for i, (member, total_seconds) in enumerate(infractions["warns"], 1):
                time_str = self._format_duration(total_seconds)
                lines.append(f"> `{i}.` <@{member.id}> • {time_str}")
            sections.append("***__Warns__***\n" + "\n".join(lines))
        
        if not any(infractions.values()):
            sections.append("No infractions found.")
        
        embed.description = "\n\n".join(sections)
        return embed

    def _format_duration(self, seconds: int) -> str:
        """Format duration in a more readable way for the lists."""
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        
        parts = []
        if d: parts.append(f"{d} day{'s' if d != 1 else ''}")
        if h: parts.append(f"{h} hour{'s' if h != 1 else ''}")
        if m: parts.append(f"{m} minute{'s' if m != 1 else ''}")
        if s: parts.append(f"{s} second{'s' if s != 1 else ''}")
        
        if not parts:
            return "0 seconds"
        
        return ", ".join(parts)

    # ---------------- OTHER COMMANDS ----------------

    # ---------------- OTHER COMMANDS ----------------
    @app_commands.command(name="shift_leaderboard", description="Show the shift leaderboard.")
    async def shift_leaderboard(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        lines = await self._build_leaderboard_lines(guild, filter_mode="all")
        emb = self.base_embed("Shift Leaderboard", colour_info())
        emb.description = "\n".join(lines)
        view = ShiftLeaderboardView(self, guild)
        await interaction.response.send_message(embed=emb, view=view)

    @app_commands.command(name="shift_online", description="Show who is currently on shift and for how long.")
    async def shift_online(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        rows = []
        for uid_str, st in self.store.state.items():
            uid = int(uid_str)
            member = guild.get_member(uid)
            if not member:
                continue
            status = "On Break" if st.get("on_break") else "Active"
            elapsed = st["accum"]
            if not st["on_break"]:
                elapsed += max(0, ts_to_int(utcnow()) - st["last_ts"])
            rows.append((elapsed, member, status, st["start_ts"]))
        rows.sort(key=lambda x: x[0], reverse=True)
        emb = self.base_embed("Currently Online", colour_ok())
        if not rows:
            emb.description = "Nobody is on shift."
        else:
            desc = []
            for elapsed, member, status, start_ts in rows:
                desc.append(f"• {member.mention} — **{status}** — {human_td(elapsed)} since <t:{start_ts}:R>")
            emb.description = "\n".join(desc)
        await interaction.response.send_message(embed=emb)

    @app_commands.command(name="shift_stats", description="Show global shift statistics (admin only).")
    async def shift_stats(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        # Require admin role, mirroring admin stats access
        user = interaction.user
        if not any(r.id == ROLE_ADMIN for r in user.roles):  # type: ignore
            await interaction.response.send_message("You lack admin role.", ephemeral=True)
            return
        
        # Defer the response first to prevent timeout
        await interaction.response.defer(ephemeral=False)
        
        try:
            num_records, total_seconds = self.store.get_statistics()
            # Count members with manage role
            manage_role = guild.get_role(ROLE_MANAGE_REQUIRED)
            role_count = len(manage_role.members) if manage_role else 0
            # Messages since last reset with timeout
            last_reset = int_to_ts(self.store.meta.get("last_reset_ts", ts_to_int(utcnow())))
            try:
                msg_count = await asyncio.wait_for(self.count_messages_since(guild, last_reset), timeout=5.0)
            except asyncio.TimeoutError:
                msg_count = 0
                print("Message counting timed out, using 0 as default")
            except Exception as e:
                print(f"Error counting messages: {e}")
                msg_count = 0
            
            emb = self.base_embed("Shift Stats (Global)", colour_info())
            emb.add_field(name="Total unique shifts", value=str(num_records), inline=True)
            emb.add_field(name="Total shift time", value=human_td(total_seconds), inline=True)
            emb.add_field(name="Since reset", value=f"<t:{ts_to_int(last_reset)}:F>", inline=True)
            emb.add_field(name="Messages since reset (in personnel-chat channel)", value=str(msg_count), inline=True)
            emb.add_field(name="Members with personnel role", value=str(role_count), inline=True)
            await interaction.followup.send(embed=emb, ephemeral=False)
        except Exception as e:
            print(f"Error in shift_stats command: {e}")
            emb = self.base_embed("Shift Stats (Global)", colour_err())
            emb.description = f"Error retrieving statistics: {str(e)}"
            await interaction.followup.send(embed=emb, ephemeral=True)

    # ---------------- LOGGING TOGGLE ----------------
    @app_commands.command(name="shift_lists", description="Show promotion and infractions lists (admin only).")
    @app_commands.describe(list_type="Choose which list to show")
    @app_commands.choices(list_type=[
        app_commands.Choice(name="Promotion List", value="promotion"),
        app_commands.Choice(name="Infractions List", value="infractions"),
    ])
    async def shift_lists(self, interaction: discord.Interaction, list_type: app_commands.Choice[str]):
        user = interaction.user
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        if not any(r.id == ROLE_ADMIN for r in user.roles):  # type: ignore
            await interaction.response.send_message("You lack admin role.", ephemeral=True)
            return
        
        promo_candidates, infractions = await self._build_lists(guild)
        
        if list_type.value == "promotion":
            embed = await self._build_promotion_embed(promo_candidates)
            view = ShiftListsView(self, guild, promo_candidates, infractions)
            view.current_embed_type = "promotion"
        else:  # infractions
            embed = await self._build_infractions_embed(infractions)
            view = ShiftListsView(self, guild, promo_candidates, infractions)
            view.current_embed_type = "infractions"
        
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="shift_logging", description="Enable or disable shift logging (admin only).")
    @app_commands.describe(enabled="true/false")
    async def shift_logging(self, interaction: discord.Interaction, enabled: Optional[bool] = None):
        user = interaction.user
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        if not any(r.id == ROLE_ADMIN for r in user.roles):  # type: ignore
            await interaction.response.send_message("You lack admin role.", ephemeral=True)
            return
        if enabled is None:
            # just show status
            status = self.store.meta.get("logging_enabled", True)
            await interaction.response.send_message(embed=self.embed_info(f"Logging is **{'ENABLED' if status else 'DISABLED'}**."), ephemeral=True)
            return
        # set and if disabling: end all current shifts and log
        self.store.meta["logging_enabled"] = enabled
        self.store.save()
        if not enabled:
            # stop and log all current shifts
            ended = []
            for uid_str in list(self.store.state.keys()):
                uid = int(uid_str)
                rec = self.store.stop_shift(uid)
                if rec:
                    ended.append(rec)
            await self.log_event(guild, f"🚫 Logging disabled by {user.mention}. Ended {len(ended)} shifts.")
        else:
            await self.log_event(guild, f"✅ Logging enabled by {user.mention}.")
        await interaction.response.send_message(embed=self.embed_info(f"Set logging to **{enabled}**."), ephemeral=True)

    # Removed redundant promotion_cooldown slash command as requested

    # ---------- COOLDOWN HELPERS AND COMMANDS ----------
    def _calculate_member_cooldown(self, member: discord.Member) -> Tuple[int, int]:
        """Return (cooldown_days, seconds_remaining) for promotion cooldown based on roles and last ping."""
        last_ts = self.store.meta.get("last_promotions", {}).get(str(member.id), 0)
        if last_ts == 0:
            # Return default cooldown period based on roles
            role_ids = {r.id for r in member.roles}
            cooldown_days = 4
            if PROMO_COOLDOWN_14 in role_ids:
                cooldown_days = 14
            elif any(role_id in role_ids for role_id in PROMO_COOLDOWN_10):
                cooldown_days = 10
            elif PROMO_COOLDOWN_8 in role_ids:
                cooldown_days = 8
            elif any(role_id in role_ids for role_id in PROMO_COOLDOWN_6):
                cooldown_days = 6
            elif PROMO_COOLDOWN_4 in role_ids:
                cooldown_days = 4
            return cooldown_days, 0
        
        seconds_since = ts_to_int(utcnow()) - last_ts
        
        # Check if this is an admin-specified cooldown
        admin_cooldown_days = self.store.meta.get("admin_cooldowns", {}).get(str(member.id))
        if admin_cooldown_days is not None:
            cooldown_days = admin_cooldown_days
            cooldown_seconds = cooldown_days * 24 * 60 * 60
        else:
            # Use role-based cooldown
            role_ids = {r.id for r in member.roles}
            cooldown_days = 4
            if PROMO_COOLDOWN_14 in role_ids:
                cooldown_days = 14
            elif any(role_id in role_ids for role_id in PROMO_COOLDOWN_10):
                cooldown_days = 10
            elif PROMO_COOLDOWN_8 in role_ids:
                cooldown_days = 8
            elif any(role_id in role_ids for role_id in PROMO_COOLDOWN_6):
                cooldown_days = 6
            elif PROMO_COOLDOWN_4 in role_ids:
                cooldown_days = 4
            cooldown_seconds = cooldown_days * 24 * 60 * 60
        
        # Add any admin extensions
        extension_seconds = self.store.meta.get("cooldown_extensions", {}).get(str(member.id), 0)
        total_cooldown_seconds = cooldown_seconds + extension_seconds
        
        remaining = max(0, total_cooldown_seconds - seconds_since)
        return cooldown_days, remaining

    async def _schedule_cooldown_end_dm(self, user_id: int, end_ts: int):
        """Sleep until `end_ts` and DM the user that cooldown is over."""
        try:
            now = ts_to_int(utcnow())
            to_sleep = max(0, end_ts - now)
            await asyncio.sleep(to_sleep)
            # fetch user and DM
            user = self.bot.get_user(user_id)
            if user is None:
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception:
                    user = None
            if user:
                try:
                    embed = self.base_embed("Promotion Cooldown Expired", colour_ok())
                    embed.description = "🎉 **You're eligible for a promotion!**"
                    embed.add_field(name="Status", value="✅ Cooldown period has ended", inline=True)
                    embed.add_field(name="Next Steps", value="You can now be considered for promotion again, subject to current criteria.", inline=False)
                    embed.set_footer(text="Congratulations on completing your cooldown period!")
                    await user.send(embed=embed)
                except Exception:
                    pass
        except Exception as e:
            print(f"Cooldown end DM scheduler error for {user_id}: {e}")

    @commands.command(name="cooldown")
    async def cooldown_text(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Show promotion cooldown for yourself or another user."""
        target = user or ctx.author
        cooldown_days, remaining = self._calculate_member_cooldown(target)
        last_ts = self.store.meta.get("last_promotions", {}).get(str(target.id), 0)
        
        embed = self.base_embed("Promotion Cooldown Status", colour_info() if remaining == 0 else colour_warn())
        embed.add_field(name="User", value=target.mention, inline=True)
        embed.add_field(name="Cooldown Period", value=f"{cooldown_days} days", inline=True)
        
        if last_ts == 0:
            embed.add_field(name="Status", value="No cooldown recorded (never promoted)", inline=False)
            embed.add_field(name="Default Period", value=f"{cooldown_days} days", inline=True)
        else:
            embed.add_field(name="Last Promotion", value=f"<t:{last_ts}:F>", inline=True)
            if remaining == 0:
                embed.add_field(name="Status", value="✅ Not on cooldown", inline=True)
            else:
                embed.add_field(name="Status", value="⏳ On cooldown", inline=True)
                embed.add_field(name="Ends", value=f"<t:{last_ts + remaining}:R>", inline=True)
                embed.add_field(name="Remaining", value=human_td(remaining), inline=True)
        
        await ctx.send(embed=embed)

    @app_commands.command(name="cooldown", description="Show promotion cooldown for you or another user.")
    @app_commands.describe(user="User to check (optional)")
    async def cooldown_slash(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        member = user or interaction.user
        cooldown_days, remaining = self._calculate_member_cooldown(member)
        last_ts = self.store.meta.get("last_promotions", {}).get(str(member.id), 0)
        embed = self.base_embed("Promotion Cooldown", colour_info() if remaining == 0 else colour_warn())
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Cooldown Period", value=f"{cooldown_days} days", inline=True)
        if last_ts == 0:
            embed.add_field(name="Status", value="No cooldown recorded (never promoted)", inline=False)
        else:
            embed.add_field(name="Last Promotion", value=f"<t:{last_ts}:F>", inline=True)
            if remaining == 0:
                embed.add_field(name="Status", value="✅ Not on cooldown", inline=True)
            else:
                embed.add_field(name="Status", value="⏳ On cooldown", inline=True)
                embed.add_field(name="Ends", value=f"<t:{last_ts + remaining}:R>", inline=True)
                embed.add_field(name="Remaining", value=human_td(remaining), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="cooldown_active", description="List members currently on cooldown (admin only).")
    async def cooldown_active(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        user = interaction.user
        if not any(r.id == ROLE_ADMIN for r in user.roles):  # type: ignore
            await interaction.response.send_message("You lack admin role.", ephemeral=True)
            return
        # Check members with manage role only
        manage_role = guild.get_role(ROLE_MANAGE_REQUIRED)
        if not manage_role:
            await interaction.response.send_message("Manage role not found.", ephemeral=True)
            return
        rows = []
        for member in manage_role.members:
            cooldown_days, remaining = self._calculate_member_cooldown(member)
            last_ts = self.store.meta.get("last_promotions", {}).get(str(member.id), 0)
            if remaining > 0 and last_ts != 0:
                rows.append((remaining, member, last_ts, cooldown_days))
        rows.sort(key=lambda x: x[0], reverse=True)
        embed = self.base_embed("Active Promotion Cooldowns", colour_warn())
        if not rows:
            embed.description = "No members are currently on cooldown."
        else:
            lines = []
            for remaining, member, last_ts, cooldown_days in rows:
                lines.append(f"• {member.mention} — ends <t:{last_ts + remaining}:R> — remaining {human_td(remaining)} (period {cooldown_days}d)")
            embed.description = "\n".join(lines)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- COOLDOWN ADMIN COMMANDS ----------
    @admin_group.command(name="cooldown", description="Manage promotion cooldowns for users (admin only).")
    @app_commands.describe(
        action="Choose an action",
        user="User to manage cooldown for",
        days="Number of days to add/extend (for add/extend actions)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add cooldown", value="add"),
        app_commands.Choice(name="Remove cooldown", value="remove"),
        app_commands.Choice(name="Extend cooldown", value="extend"),
        app_commands.Choice(name="View cooldown", value="view"),
    ])
    async def cooldown_admin(self, interaction: discord.Interaction, action: app_commands.Choice[str], user: discord.Member, days: Optional[int] = None):
        """Admin commands to manage promotion cooldowns."""
        admin_user = interaction.user
        guild = interaction.guild
        
        if guild is None:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        
        if not any(r.id == ROLE_ADMIN for r in admin_user.roles):  # type: ignore
            await interaction.response.send_message("You lack admin role.", ephemeral=True)
            return
        
        if action.value == "add":
            if days is None or days <= 0:
                await interaction.response.send_message("Please provide a positive number of days.", ephemeral=True)
                return
            
            # Set cooldown by setting last_promotions to current time (start of cooldown)
            current_time = ts_to_int(utcnow())
            self.store.meta["last_promotions"][str(user.id)] = current_time
            # Store admin-specified cooldown period
            self.store.meta["admin_cooldowns"][str(user.id)] = days
            # Clear any existing extensions when adding new cooldown
            if str(user.id) in self.store.meta.get("cooldown_extensions", {}):
                del self.store.meta["cooldown_extensions"][str(user.id)]
            self.store.save()
            
            # Calculate when cooldown ends using admin-specified days
            cooldown_ts = current_time + (days * 24 * 60 * 60)
            
            # DM the user
            try:
                embed = self.base_embed("Promotion Cooldown Added", colour_warn())
                embed.description = f"An admin has placed you on a promotion cooldown for **{days} day(s)**."
                embed.add_field(name="Cooldown Ends", value=f"<t:{cooldown_ts}:R>", inline=True)
                embed.add_field(name="Duration", value=human_td(days * 24 * 60 * 60), inline=True)
                embed.set_footer(text="This cooldown was manually added by an administrator.")
                await user.send(embed=embed)
            except Exception:
                pass
            
            # Schedule end DM
            asyncio.create_task(self._schedule_cooldown_end_dm(user.id, cooldown_ts))
            
            await self.log_event(guild, f"🔒 Admin {admin_user.mention} added {days}-day cooldown for {user.mention}.")
            await interaction.response.send_message(embed=self.embed_info(f"Added {days}-day cooldown for {user.mention}. Ends <t:{cooldown_ts}:R>."), ephemeral=True)
            
        elif action.value == "remove":
            # Remove cooldown by setting last promotion to 0 and clearing extensions/admin cooldowns
            self.store.meta["last_promotions"][str(user.id)] = 0
            if str(user.id) in self.store.meta.get("cooldown_extensions", {}):
                del self.store.meta["cooldown_extensions"][str(user.id)]
            if str(user.id) in self.store.meta.get("admin_cooldowns", {}):
                del self.store.meta["admin_cooldowns"][str(user.id)]
            self.store.save()
            
            # DM the user
            try:
                embed = self.base_embed("Promotion Cooldown Removed", colour_ok())
                embed.description = "🎉 **Your promotion cooldown has been removed!**"
                embed.add_field(name="Status", value="✅ You are now eligible for promotion", inline=True)
                embed.set_footer(text="This cooldown was manually removed by an administrator.")
                await user.send(embed=embed)
            except Exception:
                pass
            
            await self.log_event(guild, f"🔓 Admin {admin_user.mention} removed cooldown for {user.mention}.")
            await interaction.response.send_message(embed=self.embed_info(f"Removed cooldown for {user.mention}. They are now eligible for promotion."), ephemeral=True)
            
        elif action.value == "extend":
            if days is None or days <= 0:
                await interaction.response.send_message("Please provide a positive number of days.", ephemeral=True)
                return
            
            # Get current cooldown status
            last_ts = self.store.meta["last_promotions"].get(str(user.id), 0)
            if last_ts == 0:
                await interaction.response.send_message(f"{user.mention} is not currently on cooldown. Use 'add' instead.", ephemeral=True)
                return
            
            # Check if currently on cooldown
            cooldown_days, remaining = self._calculate_member_cooldown(user)
            if remaining == 0:
                await interaction.response.send_message(f"{user.mention} is not currently on cooldown. Use 'add' instead.", ephemeral=True)
                return
            
            # Add extension to the extensions tracking
            extension_seconds = days * 24 * 60 * 60
            current_extension = self.store.meta.get("cooldown_extensions", {}).get(str(user.id), 0)
            self.store.meta["cooldown_extensions"][str(user.id)] = current_extension + extension_seconds
            self.store.save()
            
            # Calculate new end time
            new_remaining = remaining + extension_seconds
            new_end_ts = ts_to_int(utcnow()) + new_remaining
            
            # DM the user
            try:
                embed = self.base_embed("Promotion Cooldown Extended", colour_warn())
                embed.description = f"Your promotion cooldown has been extended by **{days} day(s)**."
                embed.add_field(name="New End Time", value=f"<t:{new_end_ts}:R>", inline=True)
                embed.add_field(name="Extension", value=human_td(extension_seconds), inline=True)
                embed.set_footer(text="This cooldown was manually extended by an administrator.")
                await user.send(embed=embed)
            except Exception:
                pass
            
            # Reschedule end DM
            asyncio.create_task(self._schedule_cooldown_end_dm(user.id, new_end_ts))
            
            await self.log_event(guild, f"⏰ Admin {admin_user.mention} extended cooldown for {user.mention} by {days} days. New end: <t:{new_end_ts}:R>.")
            await interaction.response.send_message(embed=self.embed_info(f"Extended cooldown for {user.mention} by {days} days. New end: <t:{new_end_ts}:R>."), ephemeral=True)
            
        elif action.value == "view":
            # Show current cooldown status
            cooldown_days, remaining = self._calculate_member_cooldown(user)
            last_ts = self.store.meta["last_promotions"].get(str(user.id), 0)
            
            embed = self.base_embed("Cooldown Admin View", colour_info() if remaining == 0 else colour_warn())
            embed.add_field(name="User", value=user.mention, inline=True)
            embed.add_field(name="Cooldown Period", value=f"{cooldown_days} days", inline=True)
            
            if last_ts == 0:
                embed.add_field(name="Status", value="No cooldown recorded", inline=False)
            else:
                embed.add_field(name="Last Promotion", value=f"<t:{last_ts}:F>", inline=True)
                if remaining == 0:
                    embed.add_field(name="Status", value="✅ Not on cooldown", inline=True)
                else:
                    embed.add_field(name="Status", value="⏳ On cooldown", inline=True)
                    embed.add_field(name="Ends", value=f"<t:{last_ts + remaining}:R>", inline=True)
                    embed.add_field(name="Remaining", value=human_td(remaining), inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # --------------- LEADERBOARD (PING USERS) ---------------
    # already mentions users via <@igitd> in lines eee
async def setup(bot: commands.Bot):
    await bot.add_cog(ShiftCog(bot))