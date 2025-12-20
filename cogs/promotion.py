import os
import discord
from discord.ext import commands
import asyncio
import json
import datetime
import re
from .about_us import OWNER_ID

# Configuration
PROMOTION_CHANNEL_ID = 1329910502205427806
AUTH_ROLE_ID = 1355842403134603275
LOGS_DIR = os.path.join(os.path.dirname(__file__), "../logs")
os.makedirs(LOGS_DIR, exist_ok=True)
PING_STATE_FILE = os.path.join(LOGS_DIR, "promotion_pings.json")

# Section role IDs
SECTION_ROLES = {
    "ENLISTED": 1331644226781577316,
    "JUNIOR_ENLISTED": 1329910298525696041,
    "NCO": 1355842399338889288,
    "SNCO": 1329910295703064577,
    "WO": 1329910281903673344,
    "OFFICER": 1329910265264869387,
    "JCO": 1394667511374680105,
    "SCO": 1329910280834252903,
}

# Map granular roles -> section name
TRIGGER_TO_SECTION = {
    # JE (map to JUNIOR_ENLISTED)
    1329910321745494038: "JUNIOR_ENLISTED",
    1329910320352985099: "JUNIOR_ENLISTED",
    1329910319346221077: "JUNIOR_ENLISTED",
    1329910305106694245: "JUNIOR_ENLISTED",

    # NCO
    1329910303990878248: "NCO",
    1329910302887641170: "NCO",
    1329910301788868759: "NCO",

    # SNCO
    1329910300862054480: "SNCO",
    1329910299385663509: "SNCO",
    1329910293547188407: "SNCO",
    1329910292615794810: "SNCO",
    1394664225791807489: "SNCO",
    1329910291584127046: "SNCO",

    # WO
    1329910290619437158: "WO",
    1329910289444900916: "WO",
    1329910285594525886: "WO",
    1329910283392778351: "WO",
    1329910282851455057: "WO",

    # JCO
    1329910264103047261: "JCO",
    1329910267466743920: "JCO",
    1329910261242663014: "JCO",

    # SCO
    1329910260588220447: "SCO",
    1329910259090854008: "SCO",
    1329910257589162086: "SCO",
}

# Ordered rank sequences for promoting within a section (bottom -> top)
RANK_SEQUENCES = {
    "JUNIOR_ENLISTED": [
        1329910321745494038,
        1329910320352985099,
        1329910319346221077,
        1329910305106694245,
    ],
    "NCO": [
        1329910303990878248,
        1329910302887641170,
        1329910301788868759,
    ],
    "SNCO": [
        1329910300862054480,
        1329910299385663509,
        1329910293547188407,
        1329910292615794810,
        1394664225791807489,
        1329910291584127046,
    ],
    "WO": [
        1329910282851455057,
        1329910283392778351,
        1329910285594525886,
        1329910289444900916,
        1329910290619437158,
    ],
    "JCO": [
        1329910261242663014,
        1329910267466743920,
        1329910264103047261,
    ],
    "SCO": [
        1329910260588220447,
        1329910259090854008,
        1329910257589162086,
    ],
}

# Section progression when a member reaches the top rank of a section
SECTION_ORDER = [
    "JUNIOR_ENLISTED",
    "NCO",
    "SNCO",
    "WO",
    "JCO",
    "SCO",
    "OFFICER",
]

# Map specific rank role IDs to the abbreviation used in About Us (e.g., CPL, CW4, SSG)
ROLE_ABBREVIATIONS = {
    # JUNIOR_ENLISTED (actual role names -> abbreviations)
    1329910305106694245: "SPC",  # Specialist
    1329910319346221077: "PFC",  # Private First Class
    1329910320352985099: "PV2",  # Private Second Class
    1329910321745494038: "PVT",  # Private

    # NCO
    1329910303990878248: "CPL",  # Corporal
    1329910302887641170: "SGT",  # Sergeant
    1329910301788868759: "SSG",  # Staff Sergeant

    # SNCO
    1329910291584127046: "SMA",  # Sergeant Major of the Army
    1394664225791807489: "MSG",
    1329910292615794810: "1SG",
    1329910293547188407: "SGM",
    1329910299385663509: "CSM",
    1329910300862054480: "SFC",

    # WO
    1329910282851455057: "WO1",
    1329910283392778351: "CW2",
    1329910285594525886: "CW3",
    1329910289444900916: "CW4",
    1329910290619437158: "CW5",

    # JCO (Junior Officers)
    1329910261242663014: "2LT",
    1329910267466743920: "1LT",
    1329910264103047261: "CPT",

    # SCO (Senior Officers)
    1329910260588220447: "MAJ",
    1329910259090854008: "LTC",
    1329910257589162086: "COL",
}

# Allowed prefixes (empty set = allow any uppercase prefix). Default to abbreviations listed above.
ALLOWED_PREFIXES = set(ROLE_ABBREVIATIONS.values())

# File to log promotion actions (nickname changes, failures)
PROMOTION_LOG = os.path.join(LOGS_DIR, "promotion_actions.txt")


def log_action(msg: str):
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(PROMOTION_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.utcnow().isoformat()}] {msg}\n")
    except Exception:
        pass

# Prefix text for nickname (fallback / section labels)
SECTION_PREFIX = {
    "ENLISTED": "ENLISTED",
    "JUNIOR_ENLISTED": "JUNIOR ENLISTED",
    "NCO": "NCO",
    "SNCO": "SNCO",
    "WO": "WO",
    "OFFICER": "OFFICER",
    "JCO": "JCO",
    "SCO": "SCO",
}

COOLDOWN_SECONDS = 12 * 60 * 60  # 12 hours
# Short anti-repeat cooldown (prevent multi-step cascades in quick succession)
SMALL_COOLDOWN_SECONDS = 0  # 60 seconds (1 minute)

# Utilities for persistence

def load_ping_state():
    if not os.path.exists(PING_STATE_FILE):
        return {}
    try:
        with open(PING_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_ping_state(state):
    try:
        with open(PING_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


class ConfirmPromotionView(discord.ui.View):
    def __init__(self, bot, pinger_id, targets):
        super().__init__(timeout=120)
        self.bot = bot
        self.pinger_id = pinger_id
        # targets: list of tuples (member_id, current_sections, target_section)
        self.targets = targets
        self.result = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.pinger_id:
            await interaction.response.send_message("Only the original requester can confirm.", ephemeral=True)
            return
        await interaction.response.send_message("Confirmed — proceeding with promotions.", ephemeral=True)
        self.result = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.pinger_id:
            await interaction.response.send_message("Only the original requester can cancel.", ephemeral=True)
            return
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        self.result = False
        self.stop()


class PromotionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()
        self.ping_state = load_ping_state()
        # Load optional overrides from JSON config so you can edit mappings by hand
        self._config_path = os.path.join(LOGS_DIR, "promotion_config.json")
        self._load_config()

    def _find_current_rank(self, member: discord.Member):
        """Return the member's current highest rank as (section, index, role_id), or None.

        This searches all rank sequences, preferring higher sections (per SECTION_ORDER)
        and higher indices within a section so that when members accidentally have
        multiple rank roles, we treat their highest-held rank as the current one.
        """
        best = None
        best_section_idx = -1
        best_idx = -1
        # Use SECTION_ORDER for section priority to ensure consistent comparison
        for sec_idx, section in enumerate(SECTION_ORDER):
            seq = RANK_SEQUENCES.get(section, [])
            # scan from top to bottom in the section to find the highest rank they hold
            for idx in range(len(seq) - 1, -1, -1):
                rid = seq[idx]
                if any(r.id == rid for r in member.roles):
                    if sec_idx > best_section_idx or (sec_idx == best_section_idx and idx > best_idx):
                        best = (section, idx, rid)
                        best_section_idx = sec_idx
                        best_idx = idx
                    # once found highest in this section, no need to check lower indices here
                    break
        return best

    def _get_next_rank(self, section: str, index: int):
        """Return (next_section, next_rank_role_id) or None if no next rank."""
        seq = RANK_SEQUENCES.get(section)
        if not seq:
            return None
        if index + 1 < len(seq):
            return (section, seq[index + 1])
        # move to first rank of next section if available
        try:
            next_idx = SECTION_ORDER.index(section) + 1
        except Exception:
            return None
        if next_idx >= len(SECTION_ORDER):
            return None
        next_section = SECTION_ORDER[next_idx]
        next_seq = RANK_SEQUENCES.get(next_section)
        if not next_seq:
            return None
        return (next_section, next_seq[0])
    def _determine_target_section(self, member: discord.Member):
        # Check member roles for any trigger roles
        for role in member.roles:
            sec = TRIGGER_TO_SECTION.get(role.id)
            if sec:
                return sec
        return None

    def _load_config(self):
        """Load overrides from promotion_config.json in LOGS_DIR. You can edit the file manually."""
        try:
            if not os.path.exists(self._config_path):
                # create a template if missing
                with open(self._config_path, "w", encoding="utf-8") as f:
                    f.write("{}")
                log_action(f"Created empty promotion config at {self._config_path}")
                return
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # role_abbreviations
            ra = data.get("role_abbreviations") or {}
            for k, v in ra.items():
                try:
                    self_id = int(k)
                    ROLE_ABBREVIATIONS[self_id] = v
                except Exception:
                    continue
            # rank_sequences (optional overrides)
            rs = data.get("rank_sequences") or {}
            for section, arr in rs.items():
                if isinstance(arr, list):
                    RANK_SEQUENCES[section] = [int(x) for x in arr]
            # section_order override
            so = data.get("section_order")
            if isinstance(so, list):
                global SECTION_ORDER
                SECTION_ORDER = [s for s in so]
            # section_roles override (allows manual section role IDs)
            sr = data.get("section_roles") or {}
            if isinstance(sr, dict):
                for sec_name, rid in sr.items():
                    try:
                        SECTION_ROLES[sec_name] = int(rid)
                    except Exception:
                        continue
            log_action(f"Loaded promotion config from {self._config_path}")
        except Exception as e:
            log_action(f"Failed to load promotion config {self._config_path}: {e}")

    async def _update_nickname(self, member: discord.Member, prefix: str):
        # Try to load callsign from callsign module if available
        callsign = None
        try:
            from .callsign import load_callsigns
            callsigns = load_callsigns()
            callsign = callsigns.get(member.id)
        except Exception:
            callsign = None

        # If callsign not found in store, try to extract from existing display name (preserve it)
        if not callsign:
            m = re.search(r"(CO|WO|E)-(G|S|J|W|N)\d{2}$", member.display_name)
            if m:
                callsign = m.group(0)

        # Base name: remove existing prefix pattern and any existing callsign suffix
        base = member.display_name
        base = re.sub(r"^[^|]{1,20}\s*\|\s*", "", base)
        base = re.sub(r"\s*\|\s*(CO|WO|E)-(G|S|J|W|N)\d{2}$", "", base)
        base = base.strip()
        parts = [prefix, base]
        if callsign:
            parts.append(callsign)
        new_nick = " | ".join(parts)
        # Ensure <=32 chars
        if len(new_nick) > 32:
            # try to trim base name
            allowed_base = 32 - (len(prefix) + (3 if callsign else 0) + (len(callsign) if callsign else 0)) - 4
            base_trunc = base[:max(0, allowed_base)]
            parts = [prefix, base_trunc]
            if callsign:
                parts.append(callsign)
            new_nick = " | ".join(parts)
        try:
            if member.nick != new_nick:
                await member.edit(nick=new_nick, reason="Promotion prefix update")
                log_action(f"Changed nickname for {member} ({member.id}) to '{new_nick}'")
        except Exception as e:
            # Log permission errors or other failures
            log_action(f"Failed to change nickname for {member} ({member.id}) to '{new_nick}': {e}")
            # Ignore permission errors
            pass

    def _has_proper_name_format(self, name: str) -> bool:
        """Return True if name matches 'PREFIX | NAME | CALLSIGN' or 'PREFIX | NAME' and prefix is allowed (if ALLOWED_PREFIXES set)."""
        pattern = r"^[A-Z0-9]{1,6} \| [^|]+(?: \| (?:CO|WO|E)-(?:G|S|J|W|N)\d{2})?$"
        if not re.match(pattern, name):
            return False
        # Validate prefix against allowed set (if non-empty)
        prefix = name.split("|")[0].strip()
        if ALLOWED_PREFIXES and prefix not in ALLOWED_PREFIXES:
            return False
        return True
    def _build_new_nick(self, member: discord.Member, prefix: str) -> str:
        """Build the new nickname string without applying it."""
        # Try to load callsign
        callsign = None
        try:
            from .callsign import load_callsigns
            callsigns = load_callsigns()
            callsign = callsigns.get(member.id)
        except Exception:
            callsign = None
        # If callsign not found in store, try to extract from existing display name (preserve it)
        if not callsign:
            m = re.search(r"(CO|WO|E)-(G|S|J|W|N)\d{2}$", member.display_name)
            if m:
                callsign = m.group(0)
        base = re.sub(r"^[^|]{1,20}\s*\|\s*", "", member.display_name)
        base = re.sub(r"\s*\|\s*(CO|WO|E)-(G|S|J|W|N)\d{2}$", "", base).strip()
        parts = [prefix, base]
        if callsign:
            parts.append(callsign)
        new_nick = " | ".join(parts)
        if len(new_nick) > 32:
            allowed_base = 32 - (len(prefix) + (3 if callsign else 0) + (len(callsign) if callsign else 0)) - 4
            base_trunc = base[:max(0, allowed_base)]
            parts = [prefix, base_trunc]
            if callsign:
                parts.append(callsign)
            new_nick = " | ".join(parts)
        return new_nick

    async def _apply_promotion(self, guild: discord.Guild, member: discord.Member, next_rank_role_id: int, prev_rank_role_id: int, next_section: str):
        """Apply the next rank role (by id), remove previous rank role, manage section roles, and update nickname."""
        next_role = guild.get_role(next_rank_role_id)
        if not next_role:
            return False
        prev_role = guild.get_role(prev_rank_role_id) if prev_rank_role_id else None
        # Determine next section role object
        next_section_role = guild.get_role(SECTION_ROLES.get(next_section)) if next_section else None
        try:
            # Add the new rank role
            await member.add_roles(next_role, reason="Promotion via ping")
            # Remove any previous granular rank roles the member may still have (avoid multiple rank roles)
            try:
                all_rank_ids = {rid for seq in RANK_SEQUENCES.values() for rid in seq}
                current_rank_roles = [rid for rid in all_rank_ids if guild.get_role(rid) and guild.get_role(rid) in member.roles]
                if current_rank_roles:
                    log_action(f"Member {member} ({member.id}) had existing rank roles before promotion: {current_rank_roles}")
                to_remove = [guild.get_role(rid) for rid in current_rank_roles if rid != next_rank_role_id]
                if to_remove:
                    try:
                        await member.remove_roles(*to_remove, reason="Removing leftover rank roles during promotion")
                        log_action(f"Removed leftover rank roles { [r.id for r in to_remove] } from {member} ({member.id})")
                    except Exception:
                        # Fall back to individual removals
                        for r in to_remove:
                            try:
                                await member.remove_roles(r, reason="Removing leftover rank roles during promotion")
                            except Exception:
                                pass
            except Exception as e:
                # ignore errors while trying to clean up roles but log the exception
                log_action(f"Error while cleaning previous rank roles for {member} ({member.id}): {e}")
                pass
            # Remove other section roles that aren't the target section
            for sec_name, rid in SECTION_ROLES.items():
                r = guild.get_role(rid)
                if r and r in member.roles and (not next_section_role or r.id != next_section_role.id):
                    try:
                        await member.remove_roles(r, reason="Updated section role")
                    except Exception:
                        pass
            # Add the next section role if not present
            if next_section_role and next_section_role not in member.roles:
                try:
                    await member.add_roles(next_section_role, reason="Assigned section role")
                except Exception:
                    pass
                # Update nickname prefix using the configured abbreviation for the rank role (no brackets)
            abbr = ROLE_ABBREVIATIONS.get(next_rank_role_id, next_role.name)
            prefix = abbr
            await self._update_nickname(member, prefix)
            log_action(f"Set nickname for {member} ({member.id}) to start with prefix '{prefix}' after assigning role {next_role.name} ({next_role.id})")
            return True
        except Exception:
            return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots
        if message.author and getattr(message.author, "bot", False):
            return
        if message.channel.id != PROMOTION_CHANNEL_ID:
            return
        author = message.author
        # Must have auth role
        if not any(r.id == AUTH_ROLE_ID for r in getattr(author, "roles", [])):
            return
        if not message.mentions:
            return

        guild = message.guild
        to_process = []  # list of (member, next_section, next_rank_role_id, current_section, current_rank_role_id)
        for member in message.mentions:
            # Find the member's current rank and compute the next rank in sequence
            cur = self._find_current_rank(member)
            if not cur:
                # No known rank found for this member; skip
                continue
            cur_section, cur_idx, cur_role_id = cur
            nxt = self._get_next_rank(cur_section, cur_idx)
            if not nxt:
                # No next rank available (already at top)
                continue
            next_section, next_rank_role_id = nxt
            # Skip if they already have that next rank role
            if any(r.id == next_rank_role_id for r in member.roles):
                continue
            to_process.append((member, next_section, next_rank_role_id, cur_section, cur_role_id))

        if not to_process:
            return

        async with self._lock:
            now_ts = datetime.datetime.utcnow().timestamp()
            immediate = []
            needs_confirm = []
            for member, next_section, next_rank_role_id, cur_section, cur_role_id in to_process:
                last = self.ping_state.get(str(member.id), 0)
                # Short anti-repeat cooldown: skip if promoted very recently
                if now_ts - last < SMALL_COOLDOWN_SECONDS:
                    log_action(f"Skipping rapid repeat promotion for {member} ({member.id}); last promo {now_ts - last:.1f}s ago")
                    continue
                # Bypass long cooldown if pinged by owner/admin id 840949634071658507
                if author.id == 840949634071658507 or now_ts - last >= COOLDOWN_SECONDS:
                    immediate.append((member, next_section, next_rank_role_id, cur_section, cur_role_id))
                else:
                    needs_confirm.append((member, next_section, next_rank_role_id, cur_section, cur_role_id))

            # Apply immediate promotions
            results = []
            for member, next_section, next_rank_role_id, cur_section, cur_role_id in immediate:
                # Check existing display name format and notify if not correct
                role_obj = guild.get_role(next_rank_role_id)
                abbr = ROLE_ABBREVIATIONS.get(role_obj.id) if role_obj else SECTION_PREFIX.get(next_section)
                if not self._has_proper_name_format(member.display_name):
                    # Build the intended new nickname so we can show it to both parties
                    new_nick = self._build_new_nick(member, abbr)
                    # Notify the pinger (author) via DM; fall back to channel message
                    try:
                        await author.send(f"Note: {member.mention} does not have the required name format 'PREFIX | NAME | CALLSIGN'. I will set their nickname to: {new_nick}")
                    except Exception:
                        try:
                            await message.channel.send(f"{author.mention}: Note — {member.mention} does not have the required name format. I will set their nickname to: {new_nick}")
                        except Exception:
                            pass
                    # DM the member to notify them
                    try:
                        await member.send(f"Your display name is not in the required format 'PREFIX | NAME | CALLSIGN'. When promoted to {abbr} I will set your nickname to: {new_nick}")
                    except Exception:
                        pass
                ok = await self._apply_promotion(guild, member, next_rank_role_id, cur_role_id, next_section)
                if ok:
                    self.ping_state[str(member.id)] = now_ts
                    results.append((member, next_rank_role_id, True))
                    # Notify the member via DM with the rank abbreviation
                    try:
                        rname = abbr
                        await member.send(f"You have been promoted to **{rname}**.")
                    except Exception:
                        pass
                else:
                    results.append((member, next_rank_role_id, False))

            save_ping_state(self.ping_state)

            # For needs_confirm, DM the pinger asking to confirm
            if needs_confirm:
                lines = []
                for m, next_section, next_rank_role_id, cur_section, cur_role_id in needs_confirm:
                    role = guild.get_role(next_rank_role_id)
                    rname = ROLE_ABBREVIATIONS.get(role.id) if role else SECTION_PREFIX.get(next_section)
                    # Notify user if name format is not correct
                    if not self._has_proper_name_format(m.display_name):
                        try:
                            new_nick = self._build_new_nick(m, rname)
                            await m.send(f"Your display name is not in the required format 'PREFIX | NAME | CALLSIGN'. If promoted to {rname} your nickname will be set to: {new_nick}")
                        except Exception:
                            pass
                        lines.append(f"{m.mention} -> {rname} (name not in correct format)")
                    else:
                        lines.append(f"{m.mention} -> {rname}")
                    # log that we prepared a notification for this user
                    log_action(f"Prepared promotion notification for {m} ({m.id}) to {rname}; name_format_ok={self._has_proper_name_format(m.display_name)}")
                content = (
                    "The following users were pinged within the last 12 hours and require confirmation to re-role:\n"
                    + "\n".join(lines)
                )
                # Send DM to the author with confirmation buttons
                try:
                    view = ConfirmPromotionView(self.bot, author.id, [(m.id, next_rank_role_id) for m, next_section, next_rank_role_id, cur_section, cur_role_id in needs_confirm])
                    dm = await author.send(content, view=view)
                    await view.wait()
                    if view.result:
                        for m, next_section, next_rank_role_id, cur_section, cur_role_id in needs_confirm:
                            ok = await self._apply_promotion(guild, m, next_rank_role_id, cur_role_id, next_section)
                            if ok:
                                self.ping_state[str(m.id)] = now_ts
                                try:
                                    role = guild.get_role(next_rank_role_id)
                                    rname = ROLE_ABBREVIATIONS.get(role.id) if role else SECTION_PREFIX.get(next_section)
                                    await m.send(f"You have been promoted to **{rname}**.")
                                except Exception:
                                    pass
                    else:
                        # log that no promotions were applied after confirmation dialog
                        log_action(f"Pinger {author} ({author.id}) cancelled promotions for: {', '.join(str(m.id) for m, *_ in needs_confirm)}")
                        # notify the author that no changes were made
                        try:
                            await author.send("No promotions were applied.")
                        except Exception:
                            pass
                    save_ping_state(self.ping_state)
                except Exception:
                    # If we cannot DM the pinger, post in-channel requesting confirmation
                    try:
                        await message.channel.send(f"{author.mention}: I couldn't DM you. Please confirm promotions manually for: {', '.join(m.mention for m, *_ in needs_confirm)}")
                    except Exception:
                        pass

            # Summarize immediate results in channel
            if results:
                msgs = []
                for member, role_id, ok in results:
                    role = guild.get_role(role_id)
                    rname = ROLE_ABBREVIATIONS.get(role.id, role.name if role else "rank")
                    display = member.display_name if hasattr(member, 'display_name') else str(member)
                    if ok:
                        msgs.append(f"Assigned **{rname}** to {display}")
                    else:
                        msgs.append(f"Failed to assign **{rname}** to {display}")
                try:
                    await message.channel.send("\n".join(msgs))
                except Exception:
                    pass


    def _authorized(self, user: discord.User) -> bool:
        return user.id == 840949634071658507 or any(r.id == AUTH_ROLE_ID for r in getattr(user, "roles", []))

    @commands.command(name="promotion-reload")
    async def promotion_reload(self, ctx: commands.Context):
        if not self._authorized(ctx.author):
            await ctx.send("You do not have permission to run this command.", delete_after=10)
            return
        self._load_config()
        await ctx.send("Promotion config reloaded.", delete_after=10)
        log_action(f"Config reloaded by {ctx.author} ({ctx.author.id})")

    @commands.command(name="promotion-config")
    async def promotion_config(self, ctx: commands.Context):
        if not self._authorized(ctx.author):
            await ctx.send("You do not have permission to run this command.", delete_after=10)
            return
        lines = [
            "Promotion config summary:",
            f"File: {self._config_path}",
            "Section roles:",
        ]
        for k, v in SECTION_ROLES.items():
            lines.append(f"  {k}: {v}")
        lines.append("Abbreviations:")
        for k, v in ROLE_ABBREVIATIONS.items():
            lines.append(f"  {k}: {v}")
        try:
            await ctx.author.send("\n".join(lines))
            await ctx.send("Sent config summary to your DMs.", delete_after=10)
        except Exception:
            # fallback to channel (truncated to avoid spamming)
            await ctx.send("Unable to DM you. Here are the first lines:\n" + "\n".join(lines[:8]), delete_after=20)

    @commands.command(name="promotion-inspect")
    async def promotion_inspect(self, ctx: commands.Context, member: discord.Member):
        """Inspect a member's current rank and the next rank that would be assigned."""
        if not self._authorized(ctx.author):
            await ctx.send("You do not have permission to run this command.", delete_after=10)
            return
        cur = self._find_current_rank(member)
        if not cur:
            await ctx.send(f"No rank found for {member.mention}.")
            return
        section, idx, role_id = cur
        role = ctx.guild.get_role(role_id)
        next_info = self._get_next_rank(section, idx)
        if next_info:
            next_section, next_role_id = next_info
            next_role = ctx.guild.get_role(next_role_id)
            abbr = ROLE_ABBREVIATIONS.get(next_role_id, next_role.name if next_role else str(next_role_id))
            new_nick = self._build_new_nick(member, abbr)
            # detect mismatches between role.name and our abbreviation mapping
            cur_abbr = ROLE_ABBREVIATIONS.get(role_id, role.name if role else str(role_id))
            cur_mismatch = bool(role and cur_abbr and cur_abbr not in (role.name or ""))
            next_mismatch = bool(next_role and abbr and abbr not in (next_role.name or ""))
            lines = []
            lines.append(f"{member.mention} current: {role.name if role else role_id} ({cur_abbr}) at idx {idx}")
            if cur_mismatch:
                lines.append(f"  ⚠️ Current role name and abbreviation differ — using abbreviation '{cur_abbr}' for prefixes.")
            lines.append(f"Next -> {next_role.name if next_role else next_role_id} ({abbr}) in section {next_section}")
            if next_mismatch:
                lines.append(f"  ⚠️ Next role name and abbreviation differ — using abbreviation '{abbr}' for prefixes.")
            lines.append(f"Would set nickname to: {new_nick}")
            msg = "\n".join(lines)
        else:
            msg = f"{member.mention} is at the top rank of section {section}; no next rank available."
        await ctx.author.send(msg)
        await ctx.send("Sent inspection result to your DMs.", delete_after=10)

    @commands.command(name="promotion-next")
    async def promotion_next(self, ctx: commands.Context, *, role_input: str):
        """Show the next rank for a given rank role id, mention, or exact role name.

        Usage: `!promotion-next 1329910303990878248`
               `!promotion-next @RoleMention`
               `!promotion-next "Corps Sergeant"` (exact role name)
        """
        if not self._authorized(ctx.author):
            await ctx.send("You do not have permission to run this command.", delete_after=10)
            return
        if not ctx.guild:
            await ctx.send("This command must be run in a server channel.", delete_after=10)
            return
        # try parse a mention like <@&id>
        m = re.match(r"^<@&?(\d+)>$", role_input.strip())
        role_id = None
        if m:
            role_id = int(m.group(1))
        elif role_input.strip().isdigit():
            role_id = int(role_input.strip())
        else:
            # try exact role name match (case-sensitive)
            role_obj = discord.utils.get(ctx.guild.roles, name=role_input.strip())
            if role_obj:
                role_id = role_obj.id
        if not role_id:
            await ctx.send("Could not parse role. Provide a role ID, role mention, or the exact role name.", delete_after=15)
            return
        found = None
        for section, seq in RANK_SEQUENCES.items():
            if role_id in seq:
                idx = seq.index(role_id)
                found = (section, idx)
                break
        if not found:
            await ctx.send(f"Role id {role_id} not found in rank sequences.", delete_after=15)
            return
        section, idx = found
        nxt = self._get_next_rank(section, idx)
        if not nxt:
            await ctx.send(f"Role {role_id} is the top rank in section {section}; no next rank.", delete_after=15)
            return
        next_section, next_role_id = nxt
        await ctx.send(f"Next rank after {role_id} in {section} is {next_role_id} ({ROLE_ABBREVIATIONS.get(next_role_id, next_role_id)}) in section {next_section}")

    @commands.command(name="promotion-audit")
    async def promotion_audit(self, ctx: commands.Context):
        """Audit configured rank mappings vs guild role names and report mismatches."""
        if not self._authorized(ctx.author):
            await ctx.send("You do not have permission to run this command.", delete_after=10)
            return
        guild = ctx.guild
        mismatches = []
        for section, seq in RANK_SEQUENCES.items():
            for rid in seq:
                role = guild.get_role(rid)
                abbr = ROLE_ABBREVIATIONS.get(rid)
                if not role:
                    mismatches.append((section, rid, abbr, None, "missing role"))
                    continue
                rn = role.name or ""
                if abbr and abbr not in rn:
                    mismatches.append((section, rid, abbr, rn, "name mismatch"))
        if not mismatches:
            await ctx.send("No mismatches found.")
            return
        lines = []
        for sec, rid, abbr, rn, reason in mismatches:
            if rn is None:
                lines.append(f"{sec}: role id {rid} missing in guild (expected {abbr})")
            else:
                lines.append(f"{sec}: role {rid} name '{rn}' doesn't include abbreviation '{abbr}'")
        try:
            await ctx.author.send("Promotion audit results:\n" + "\n".join(lines))
            await ctx.send("Audit sent to your DMs.", delete_after=20)
        except Exception:
            await ctx.send("Audit results:\n" + "\n".join(lines[:8]), delete_after=30)

    @commands.command(name="promotion-validate-order")
    async def promotion_validate_order(self, ctx: commands.Context, action: str = "preview", confirm: str = None):
        """Preview or apply fixes to rank sequence ordering within sections.

        Usage: `!promotion-validate-order preview`
               `!promotion-validate-order apply confirm`  # applies corrected ordering based on role positions
        """
        if not self._authorized(ctx.author):
            await ctx.send("You do not have permission to run this command.", delete_after=10)
            return
        guild = ctx.guild
        if not guild:
            await ctx.send("This command must be used in a server channel.", delete_after=10)
            return
        issues = []
        for section, seq in RANK_SEQUENCES.items():
            roles = [guild.get_role(rid) for rid in seq]
            if any(r is None for r in roles):
                issues.append((section, "missing", seq, [r.id if r else None for r in roles]))
                continue
            positions = [r.position for r in roles]
            # check monotonic increasing (bottom->top)
            is_increasing = all(positions[i] < positions[i+1] for i in range(len(positions)-1))
            is_decreasing = all(positions[i] > positions[i+1] for i in range(len(positions)-1))
            if is_increasing:
                continue
            elif is_decreasing:
                corrected = list(reversed(seq))
                issues.append((section, "reversed", seq, corrected, [r.name for r in roles]))
            else:
                issues.append((section, "unordered", seq, [r.name for r in roles], positions))
        if not issues:
            await ctx.send("All sections appear ordered correctly (bottom->top).", delete_after=10)
            return
        if action == "preview":
            lines = []
            for item in issues:
                if item[1] == "missing":
                    lines.append(f"{item[0]}: missing roles or not in guild: {item[2]}")
                elif item[1] == "reversed":
                    sec, _, old, corrected, names = item
                    lines.append(f"{sec}: reversed. Current: {[(guild.get_role(r).name,r) for r in old]} -> Suggested: {[(guild.get_role(r).name,r) for r in corrected]}")
                else:
                    lines.append(f"{item[0]}: unordered positions: {item[3]} positions: {item[4]}")
            try:
                await ctx.author.send("Promotion order validation:\n" + "\n".join(lines))
                await ctx.send(f"Validation sent to your DMs ({len(lines)} issues). Run `!promotion-validate-order apply confirm` to apply fixes.", delete_after=30)
            except Exception:
                await ctx.send("Validation:\n" + "\n".join(lines[:8]), delete_after=60)
            return
        if action == "apply":
            if confirm != "confirm":
                await ctx.send("To apply fixes, re-run with `confirm`: `!promotion-validate-order apply confirm`", delete_after=20)
                return
            # Backup and apply fixes for reversed sections
            try:
                logpath = os.path.join(LOGS_DIR, "sequence_fix_log.json")
                entry = {"timestamp": datetime.datetime.utcnow().isoformat() + "Z", "executor": ctx.author.id, "guild_id": guild.id, "changes": []}
                for issue in issues:
                    if issue[1] == "reversed":
                        sec = issue[0]
                        old = issue[2]
                        corrected = issue[3]
                        # apply change
                        RANK_SEQUENCES[sec] = corrected
                        entry["changes"].append({"section": sec, "old": old, "new": corrected})
                # write to log
                logs = []
                if os.path.exists(logpath):
                    with open(logpath, "r", encoding="utf-8") as fh:
                        try:
                            logs = json.load(fh) or []
                        except Exception:
                            logs = []
                logs.append(entry)
                with open(logpath, "w", encoding="utf-8") as fh:
                    json.dump(logs, fh, indent=2)
                # write to config file to persist rank_sequences
                cfg = {}
                if os.path.exists(self._config_path):
                    with open(self._config_path, "r", encoding="utf-8") as fh:
                        try:
                            cfg = json.load(fh) or {}
                        except Exception:
                            cfg = {}
                cfg_rs = cfg.get("rank_sequences", {})
                for sec in [c["section"] for c in entry["changes"]]:
                    cfg_rs[sec] = [int(x) for x in RANK_SEQUENCES[sec]]
                cfg["rank_sequences"] = cfg_rs
                with open(self._config_path, "w", encoding="utf-8") as fh:
                    json.dump(cfg, fh, indent=2)
                log_action(f"Applied rank sequence fixes by {ctx.author} ({ctx.author.id}): {entry['changes']}")
                await ctx.send(f"Applied fixes for {len(entry['changes'])} sections; details DM'd.", delete_after=10)
                try:
                    await ctx.author.send("Applied sequence fixes:\n" + "\n".join([json.dumps(x) for x in entry["changes"]]))
                except Exception:
                    pass
            except Exception as e:
                await ctx.send(f"Failed to apply fixes: {e}", delete_after=20)
            return

    @commands.command(name="promotion-fix-names")
    async def promotion_fix_names(self, ctx: commands.Context, action: str = "preview", confirm: str = None, format_style: str = "prefix"):
        """Owner-only: preview/apply/undo role renames to include abbreviations.

        Usage:
          `!promotion-fix-names preview`                    - list suggested renames (default)
          `!promotion-fix-names apply confirm`               - apply suggested renames (requires confirm)
          `!promotion-fix-names undo`                       - revert the last applied batch
        Format styles supported: `prefix` (default) => "ABB | Role Name".
        """
        # Owner-only
        try:
            from .about_us import OWNER_ID
        except Exception:
            OWNER_ID = None
        if OWNER_ID is None or ctx.author.id != OWNER_ID:
            await ctx.send("Only the bot owner may run this command.", delete_after=15)
            return

        guild = ctx.guild
        if not guild:
            await ctx.send("This command must be run in a server channel.", delete_after=10)
            return

        # Build current mismatches (same as audit)
        mismatches = []  # (role_obj, abbr)
        for section, seq in RANK_SEQUENCES.items():
            for rid in seq:
                role = guild.get_role(rid)
                abbr = ROLE_ABBREVIATIONS.get(rid)
                if not role or not abbr:
                    continue
                rn = role.name or ""
                if abbr not in rn:
                    mismatches.append((role, abbr))

        if action == "preview":
            if not mismatches:
                await ctx.send("No role name mismatches found.")
                return
            lines = []
            for role, abbr in mismatches:
                suggested = f"{abbr} | {role.name}" if format_style == "prefix" else f"{role.name} ({abbr})"
                lines.append(f"{role.id}: '{role.name}' -> '{suggested}'")
            # DM owner the full preview, and send a short summary in-channel
            try:
                await ctx.author.send("Promotion rename preview:\n" + "\n".join(lines))
                await ctx.send(f"Preview sent to your DMs ({len(lines)} suggestions). Run `!promotion-fix-names apply confirm` to apply.", delete_after=30)
            except Exception:
                await ctx.send("Rename preview:\n" + "\n".join(lines[:8]), delete_after=60)
            return

        if action == "apply":
            if confirm != "confirm":
                await ctx.send("To apply renames, re-run with the `confirm` token: `!promotion-fix-names apply confirm`", delete_after=20)
                return

            # Check bot permissions
            me = guild.me
            if not me.guild_permissions.manage_roles:
                await ctx.send("I do not have Manage Roles permission and cannot rename roles.", delete_after=20)
                return

            changes = []
            for role, abbr in mismatches:
                suggested = f"{abbr} | {role.name}" if format_style == "prefix" else f"{role.name} ({abbr})"
                # Can't edit roles at/above bot's top role
                if role.position >= me.top_role.position:
                    changes.append({"role_id": role.id, "old": role.name, "new": suggested, "status": "failed", "reason": "insufficient_role_position"})
                    continue
                try:
                    old = role.name
                    await role.edit(name=suggested, reason=f"Applied by promotion-fix-names (by {ctx.author})")
                    changes.append({"role_id": role.id, "old": old, "new": suggested, "status": "ok"})
                except Exception as e:
                    changes.append({"role_id": role.id, "old": role.name, "new": suggested, "status": "failed", "reason": str(e)})

            # Log the batch for undo
            logpath = os.path.join(LOGS_DIR, "role_rename_log.json")
            entry = {"timestamp": datetime.datetime.utcnow().isoformat() + "Z", "executor": ctx.author.id, "guild_id": guild.id, "changes": changes}
            try:
                logs = []
                if os.path.exists(logpath):
                    with open(logpath, "r", encoding="utf-8") as fh:
                        logs = json.load(fh) or []
                logs.append(entry)
                with open(logpath, "w", encoding="utf-8") as fh:
                    json.dump(logs, fh, indent=2)
            except Exception:
                pass

            ok = [c for c in changes if c["status"] == "ok"]
            failed = [c for c in changes if c["status"] != "ok"]
            await ctx.send(f"Rename applied: {len(ok)} succeeded, {len(failed)} failed. Details DM'd to owner.")
            try:
                await ctx.author.send("Rename results:\n" + "\n".join([json.dumps(x) for x in changes]))
            except Exception:
                pass
            return

        if action == "undo":
            logpath = os.path.join(LOGS_DIR, "role_rename_log.json")
            if not os.path.exists(logpath):
                await ctx.send("No rename log found to undo.", delete_after=20)
                return
            try:
                with open(logpath, "r", encoding="utf-8") as fh:
                    logs = json.load(fh) or []
            except Exception:
                await ctx.send("Could not read rename log.", delete_after=20)
                return
            if not logs:
                await ctx.send("No rename log found to undo.", delete_after=20)
                return
            last = logs.pop()  # remove last
            if last.get("guild_id") != guild.id:
                await ctx.send("Last rename batch was for a different guild; aborting.", delete_after=20)
                return
            results = []
            me = guild.me
            for c in last.get("changes", []):
                rid = c.get("role_id")
                old = c.get("old")
                role = guild.get_role(rid)
                if not role:
                    results.append({"role_id": rid, "status": "failed", "reason": "role_missing"})
                    continue
                if role.position >= me.top_role.position:
                    results.append({"role_id": rid, "status": "failed", "reason": "insufficient_role_position"})
                    continue
                try:
                    await role.edit(name=old, reason=f"Undo rename batch by {ctx.author}")
                    results.append({"role_id": rid, "status": "ok"})
                except Exception as e:
                    results.append({"role_id": rid, "status": "failed", "reason": str(e)})
            # write logs back (with last popped)
            try:
                with open(logpath, "w", encoding="utf-8") as fh:
                    json.dump(logs, fh, indent=2)
            except Exception:
                pass
            await ctx.send(f"Undo complete: {len([r for r in results if r['status']=='ok'])} succeeded, {len([r for r in results if r['status']!='ok'])} failed.")
            try:
                await ctx.author.send("Undo details:\n" + "\n".join([json.dumps(x) for x in results]))
            except Exception:
                pass
            return

        await ctx.send("Unknown action. Use `preview`, `apply confirm`, or `undo`.", delete_after=20)


async def setup(bot):
    await bot.add_cog(PromotionCog(bot))
