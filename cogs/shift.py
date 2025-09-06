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

# -------------------- CONFIG CONSTANTS --------------------
IMAGE_URL = "https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68bac05c&is=68b96edc&hm=b48ce53b741b93847d34dc04a79709fa47badfd867e95afc68a6712de4d86856&"

ROLE_MANAGE_REQUIRED = 1329910329701830686  # can use /shift manage
ROLE_SHIFT_ON = 1329910276912447608          # role when on shift
ROLE_BREAK = 1329910278195777557              # role when on break
ROLE_ADMIN = 1355842403134603275              # can use /shift admin and /shift logging

LOG_CHANNEL_ID = 1329910573739147296          # logs channel
MSG_COUNT_CHANNEL_ID = 1329910508182179900     # message-count channel

# Quotas (minutes)
DEFAULT_QUOTA = 45
QUOTA_ROLE_0 = 1329910253814550608  # quota 0
QUOTA_ROLE_15 = 1329910255584546950 # quota 15
QUOTA_ROLE_35 = 1329910389437104220 # quota 35
QUOTA_ROLE_ADMIN_0 = 1355842403134603275 # quota 0 (admins)

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
        "manage_message_ids": {str(user_id): int}  # optional: last manage message id to edit
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

# -------------------- MAIN COG --------------------
class ShiftCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = Store()
        # re-add persistent view on startup
        self.bot.add_view(ShiftManageView(bot))
        # Add the admin command group to the tree
        self.bot.tree.add_command(self.admin_group)
    
    async def cog_unload(self):
        """Clean up when the cog is unloaded"""
        # Remove the admin command group from the tree
        self.bot.tree.remove_command(self.admin_group.name)

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
            e.add_field(name="Started", value=f"<t:{st['start_ts']}:F> (\u200b<t:{st['start_ts']}:R>\u200b)", inline=True)
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
    @app_commands.describe(personnel="User to target (optional)", action="Choose an action", record_id="Record ID for void_id action")
    @app_commands.choices(action=[
        app_commands.Choice(name="Stop shift", value="stop"),
        app_commands.Choice(name="Toggle break", value="toggle_break"),
        app_commands.Choice(name="Void ongoing shift", value="void"),
        app_commands.Choice(name="Show shift records", value="records"),
        app_commands.Choice(name="Void shift by ID", value="void_id"),
    ])
    async def shift_admin_user(self, interaction: discord.Interaction, action: app_commands.Choice[str], personnel: Optional[discord.Member] = None, record_id: Optional[str] = None):
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

    @admin_group.command(name="global", description="Global admin actions when no personnel is specified.")
    @app_commands.describe(action="Choose an action", record_id="Record ID for void_id action", confirmation="Confirmation token for void_all action")
    @app_commands.choices(action=[
        app_commands.Choice(name="Void shift by ID", value="void_id"),
        app_commands.Choice(name="Void ALL shifts (requires confirmation)", value="void_all"),
        app_commands.Choice(name="Get shift statistics", value="stats"),
        app_commands.Choice(name="Get shift leaderboard (txt)", value="leaderboard_txt"),
        app_commands.Choice(name="Get shift leaderboard: met quota", value="leaderboard_met"),
        app_commands.Choice(name="Get shift leaderboard: not met quota", value="leaderboard_notmet"),
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
            self.store.save()

            await self.log_event(
                guild,
                f"⚠️ Admin {user.mention} voided **ALL** ongoing shifts ({ongoing_count}) and **{removed_count}** shift records from this week. Stats since reset restarted."
            )
            await interaction.channel.send(
                embed=self.embed_warn(
                    f"Voided all ongoing shifts ({ongoing_count}) and {removed_count} shift records from this week.\n**Stats since reset have been restarted.**"
                )
            )
            return
        elif action.value == "stats":
            num_records, total_seconds = self.store.get_statistics()
            # extra: number of people with manage role
            manage_role = guild.get_role(ROLE_MANAGE_REQUIRED)
            role_count = len(manage_role.members) if manage_role else 0
            # messages since last reset
            last_reset = int_to_ts(self.store.meta.get("last_reset_ts", ts_to_int(utcnow())))
            msg_count = await self.count_messages_since(guild, last_reset)
            emb = self.base_embed("Shift Stats (Global)", colour_info())
            emb.add_field(name="Total unique shifts", value=str(num_records), inline=True)
            emb.add_field(name="Total shift time", value=human_td(total_seconds), inline=True)
            emb.add_field(name="Since reset", value=f"<t:{ts_to_int(last_reset)}:F>", inline=True)
            emb.add_field(name="Messages since reset (in target channel)", value=str(msg_count), inline=True)
            emb.add_field(name="Members with personnel role", value=str(role_count), inline=True)
            await interaction.response.send_message(embed=emb, ephemeral=False)
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

    async def _build_leaderboard_lines(self, guild: discord.Guild, filter_mode: str = "all") -> List[str]:
        # Aggregate by member with manage role (or anyone?) -> use all members with recorded time
        totals: Dict[int, int] = {}
        for r in self.store.records:
            totals[r["user_id"]] = totals.get(r["user_id"], 0) + r["duration"]
        # include ongoing
        for uid_str, st in self.store.state.items():
            uid = int(uid_str)
            elapsed = st["accum"]
            if not st["on_break"]:
                elapsed += max(0, ts_to_int(utcnow()) - st["last_ts"])
            totals[uid] = totals.get(uid, 0) + elapsed
        # build rows
        rows: List[Tuple[int, str, int, bool]] = []  # (seconds, name, id, met_quota)
        for uid, secs in totals.items():
            member = guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            met = await self._met_quota(member, secs) if member else False
            rows.append((secs, name, uid, met))
        rows.sort(key=lambda x: x[0], reverse=True)
        # filter
        if filter_mode == "leaderboard_met":
            rows = [r for r in rows if r[3]]
        elif filter_mode == "leaderboard_notmet":
            rows = [r for r in rows if not r[3]]
        # format
        out = []
        rank = 1
        for secs, name, uid, met in rows:
            out.append(f"#{rank} <@{uid}> — {human_td(secs)} — {'✅ Met' if met else '❌ Not met'}")
            rank += 1
        if not out:
            out = ["No data."]
        return out

    async def _met_quota(self, member: Optional[discord.Member], seconds: int) -> bool:
        if member is None:
            return False
        mids = {r.id for r in member.roles}
        if QUOTA_ROLE_0 in mids or QUOTA_ROLE_ADMIN_0 in mids:
            quota = 0
        elif QUOTA_ROLE_15 in mids:
            quota = 15
        elif QUOTA_ROLE_35 in mids:
            quota = 35
        else:
            quota = DEFAULT_QUOTA
        return seconds >= quota * 60

    async def count_messages_since(self, guild: discord.Guild, since: dt.datetime) -> int:
        ch = guild.get_channel(MSG_COUNT_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            return 0
        count = 0
        async for msg in ch.history(after=since, limit=None, oldest_first=True):
            count += 1
        return count

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
        await interaction.response.send_message(embed=emb)

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

    # ---------------- LOGGING TOGGLE ----------------
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

    # --------------- LEADERBOARD (PING USERS) ---------------
    # already mentions users via <@id> in lines
async def setup(bot: commands.Bot):
    await bot.add_cog(ShiftCog(bot))