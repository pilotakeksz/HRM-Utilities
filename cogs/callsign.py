import discord
from discord.ext import commands
from discord import app_commands
import os
import re
import asyncio

CALLSIGN_FILE = os.path.join(os.path.dirname(__file__), "../data/callsigns.txt")
ADMIN_ID = 840949634071658507
ADMIN_ROLES = [1355842403134603275, 1329910280834252903]
REQUEST_ROLE = 1329910329701830686

ROLE_CALLSIGN_MAP = {
    1355842403134603275: ("CO", "G"),
    1329910280834252903: ("CO", "S"),
    1394667511374680105: ("CO", "J"),
    1329910281903673344: ("WO", "W"),
    1329910295703064577: ("E", "S"),
    1355842399338889288: ("E", "N"),
    1329910298525696041: ("E", "J"),
}
PROMOTION_CHANNEL_ID = 1329910502205427806

EMBED_COLOUR = 0xd0b47b
EMBED1_IMAGE = "https://media.discordapp.net/attachments/1409252771978280973/1409314343178207322/CALLSIGNS.png?ex=68acedc3&is=68ab9c43&hm=91d3756a48e0ac2cb895b757f5b54762e3ace2c382e1f9375709aa7ef267b7f6&=&format=webp&quality=lossless&width=2576&height=862"
EMBED2_IMAGE = "https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&"
EMBED_FOOTER = "High Rock Military Corps"
EMBED_ICON = "https://cdn.discordapp.com/emojis/1409463907294384169.webp?size=240"

LOG_CHANNEL_ID = 1343686645815181382
COMMAND_ROLE = 774973267089293323
ALLOWED_CHANNELS = [1329910474581479495, 1329910518659551272]
LOGS_DIR = os.path.join(os.path.dirname(__file__), "../logs")
LOG_FILE = os.path.join(LOGS_DIR, "callsign_commands.txt")

def ensure_callsign_file():
    os.makedirs(os.path.dirname(CALLSIGN_FILE), exist_ok=True)
    if not os.path.exists(CALLSIGN_FILE):
        with open(CALLSIGN_FILE, "w", encoding="utf-8") as f:
            f.write("")

def load_callsigns():
    ensure_callsign_file()
    callsigns = {}
    with open(CALLSIGN_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "|" not in line:
                continue
            user_id, callsign = line.split("|", 1)
            callsigns[int(user_id)] = callsign
    return callsigns

def save_callsigns(callsigns):
    ensure_callsign_file()
    with open(CALLSIGN_FILE, "w", encoding="utf-8") as f:
        for user_id, callsign in callsigns.items():
            f.write(f"{user_id}|{callsign}\n")

def is_valid_callsign(callsign):
    return bool(re.fullmatch(r"(CO|WO|E)-(G|S|J|W|N)[0-9]{2}", callsign))

def callsign_sort_key(item):
    cs = item[1]
    first_order = {"CO": 0, "WO": 1, "E": 2}
    second_order = {
        "CO": {"G": 0, "S": 1, "J": 2},
        "WO": {"W": 0},
        "E": {"S": 0, "N": 1, "J": 2}
    }
    m = re.fullmatch(r"(CO|WO|E)-(G|S|J|W|N)(\d{2})", cs)
    if m:
        first = m.group(1)
        second = m.group(2)
        num = int(m.group(3))
        return (
            first_order.get(first, 99),
            second_order.get(first, {}).get(second, 99),
            num
        )
    return (99, 99, 999)

def log_command(user, command, detail=""):
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{discord.utils.utcnow()}] {user} ({user.id}) ran {command}: {detail}\n")

def callsign_group_title(first, second):
    if first == "CO":
        if second == "G":
            return "**__General Officers__**"
        elif second == "S":
            return "**__Senior Officers__**"
        elif second == "J":
            return "**__Junior Officers__**"
        else:
            return "**__General Officers__**"
    elif first == "WO":
        return "**__Warrant Officers__**"
    elif first == "E":
        if second == "S":
            return "**__Senior NCOs__**"
        elif second == "N":
            return "**__Non-Commissioned Officers__**"
        elif second == "J":
            return "**__Junior Enlisted Ranks__**"
        else:
            return "**__General Officers__**"
    else:
        return "**__General Officers__**"

class CallsignCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.callsign_lock = asyncio.Lock()
        # pending promotions: guild_id -> set(user_id)
        self._promotion_pending = {}
        self._promotion_task = None
        self._promotion_lock = asyncio.Lock()

    @commands.hybrid_command(name="callsign", aliases=["cs"], description="Callsign management tool")
    @app_commands.describe(user="User to check (optional)")
    async def callsign(self, ctx, user: discord.Member = None):
        is_admin = ctx.author.id == ADMIN_ID or any(r.id == 1355842403134603275 for r in getattr(ctx.author, "roles", []))
        if not is_admin:
            if ctx.prefix and ctx.prefix.startswith("!"):
                if ctx.channel.id not in ALLOWED_CHANNELS:
                    allowed_mentions = " or ".join(f"<#{cid}>" for cid in ALLOWED_CHANNELS)
                    await ctx.send(f"Please use me in {allowed_mentions}.", ephemeral=True)
                    return
        await self.handle_callsign(ctx, user)

    async def handle_callsign(self, ctx_or_interaction, user: discord.Member = None):
        author = ctx_or_interaction.user if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author
        callsigns = load_callsigns()
        is_admin = author.id == ADMIN_ID or any(r.id == 1355842403134603275 for r in getattr(author, "roles", []))
        admin_menu_roles = {1355842403134603275, 1329910280834252903, 1394667511374680105}
        has_admin_menu = is_admin or any(r.id in admin_menu_roles for r in getattr(author, "roles", []))
        can_add_callsign = is_admin or any(r.id == 1355842403134603275 for r in getattr(author, "roles", []))
        log_command(author, "callsign", f"user={user.id if user else 'self'}")
        if user:
            embed = discord.Embed(
                title="Callsign Lookup",
                description=f"{user.mention}'s callsign: **{callsigns.get(user.id, 'None')}**",
                color=EMBED_COLOUR
            )
            embed.set_image(url=EMBED1_IMAGE)
            embed.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
            await self._respond(ctx_or_interaction, embed)
            log_command(author, "view_callsign", f"target={user.id}")
            return
        can_request = author.id == ADMIN_ID or any(r.id == REQUEST_ROLE for r in getattr(author, "roles", []))
        view = CallsignBasicView(
            self,
            is_admin=has_admin_menu,
            can_request=can_request,
            allowed_user_id=author.id,
            has_command_role=can_add_callsign
        )
        await self._send_menu(ctx_or_interaction, "Callsign Menu", view)

    async def _send_menu(self, ctx_or_interaction, title, view):
        embed1 = discord.Embed(color=EMBED_COLOUR)
        embed1.set_image(url=EMBED1_IMAGE)
        embed2 = discord.Embed(title=title, color=EMBED_COLOUR)
        embed2.set_image(url=EMBED2_IMAGE)
        embed2.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
        if hasattr(ctx_or_interaction, "response"):
            await ctx_or_interaction.response.send_message(embeds=[embed1, embed2], view=view, ephemeral=True)
        else:
            await ctx_or_interaction.send(embeds=[embed1, embed2], view=view, ephemeral=True)

    async def _respond(self, ctx_or_interaction, embed):
        if hasattr(ctx_or_interaction, "response"):
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await ctx_or_interaction.send(embed=embed, ephemeral=True)

    async def add_callsign(self, user: discord.Member, callsign: str):
        callsigns = load_callsigns()
        if not is_valid_callsign(callsign):
            return False, "Invalid callsign format."
        if callsign in callsigns.values():
            return False, "This callsign is already taken."
        callsigns[user.id] = callsign
        save_callsigns(callsigns)
        try:
            await user.send(f"You have been assigned the callsign: **{callsign}**.")
        except Exception:
            pass
        return True, f"Callsign {callsign} assigned to {user.mention}."

    async def remove_callsign(self, user: discord.Member):
        callsigns = load_callsigns()
        if user.id not in callsigns:
            return False, "User does not have a callsign."
        removed = callsigns[user.id]
        del callsigns[user.id]
        save_callsigns(callsigns)
        try:
            await user.send(f"Your callsign **{removed}** has been removed.")
        except Exception:
            pass
        return True, f"Callsign removed from {user.mention}."

    async def view_callsign(self, user: discord.Member):
        callsigns = load_callsigns()
        return callsigns.get(user.id, "None")

    async def view_all_callsigns(self):
        callsigns = load_callsigns()
        sorted_items = sorted(callsigns.items(), key=callsign_sort_key)
        return sorted_items

    async def request_callsign(self, user: discord.Member):
        async with self.callsign_lock:
            callsigns = load_callsigns()
            if user.id != ADMIN_ID and not any(r.id == REQUEST_ROLE for r in getattr(user, "roles", [])):
                return False, "You do not have permission to request a callsign."
            eligible = None
            for role_id, (x, y) in ROLE_CALLSIGN_MAP.items():
                if any(r.id == role_id for r in getattr(user, "roles", [])):
                    eligible = (x, y)
                    break
            if not eligible:
                return False, "You do not have a role eligible for a callsign or all are taken."
            x, y = eligible
            used = set()
            for cs in callsigns.values():
                m = re.search(r"(\d{2})$", cs)
                if m:
                    used.add(m.group(1))
            for zz in range(1, 100):
                zz_str = f"{zz:02d}"
                if zz_str in used:
                    continue
                new_callsign = f"{x}-{y}{zz_str}"
                current_callsign = callsigns.get(user.id)
                if current_callsign == new_callsign:
                    return False, f"Your callsign is already up to date: **{current_callsign}**"
                callsigns[user.id] = new_callsign
                save_callsigns(callsigns)
                # Always remove the role when callsign is requested
                role = user.guild.get_role(1371198982340083712)
                if role:
                    try:
                        await user.remove_roles(role, reason="Callsign assigned")
                    except Exception:
                        pass
                # Append callsign to end of their nickname or username as ' | CS'
                try:
                    display = user.display_name
                    # Remove existing ' | CS' suffix if present
                    display = re.sub(r"\s*\|\s*(CO|WO|E)-(G|S|J|W|N)\d{2}$", "", display)
                    new_nick = f"{display} | {new_callsign}"
                    if len(new_nick) > 32:
                        # Truncate base name to fit
                        base_allowed = 32 - (3 + len(new_callsign))
                        new_nick = f"{display[:max(0, base_allowed)]} | {new_callsign}"
                    try:
                        if user.nick != new_nick:
                            await user.edit(nick=new_nick, reason="Callsign assigned")
                    except Exception:
                        pass
                except Exception:
                    pass
                # Always use new_callsign in the confirmation message
                return True, f"Auto-assigned callsign **{new_callsign}** to {user.mention}."
            return False, "No available callsign numbers left."

    def _parse_callsign(self, callsign: str):
        m = re.fullmatch(r"(CO|WO|E)-(G|S|J|W|N)(\d{2})", callsign)
        if not m:
            return None
        return (m.group(1), m.group(2), m.group(3))

    def _find_prefix_for_member(self, member: discord.Member):
        # Find a ROLE_CALLSIGN_MAP entry matching any of the member's roles
        for role_id, (first, second) in ROLE_CALLSIGN_MAP.items():
            if any(r.id == role_id for r in getattr(member, "roles", [])):
                return (first, second)
        return None

    def _allocate_number_for_prefix(self, first: str, second: str, callsigns: dict):
        # Find lowest available two-digit number for given prefix
        used = set()
        for cs in callsigns.values():
            m = re.fullmatch(rf"{first}-{second}(\d{{2}})", cs)
            if m:
                used.add(m.group(1))
        for i in range(1, 100):
            s = f"{i:02d}"
            if s not in used:
                return s
        return None

    async def _auto_promote_if_needed(self, member: discord.Member):
        # Only consider members with an existing callsign
        callsigns = load_callsigns()
        current = callsigns.get(member.id)
        if not current:
            return False, "no_callsign"
        parsed = self._parse_callsign(current)
        if not parsed:
            return False, "invalid_callsign"
        cur_first, cur_second, cur_num = parsed

        target = self._find_prefix_for_member(member)
        if not target:
            return False, "no_target_role"
        target_first, target_second = target

        if (cur_first, cur_second) == (target_first, target_second):
            return False, "no_change"

        # Build new callsign using same numeric suffix if possible, otherwise allocate
        new_num = cur_num or self._allocate_number_for_prefix(target_first, target_second, callsigns)
        if not new_num:
            return False, "no_number"
        new_callsign = f"{target_first}-{target_second}{new_num}"

        # Ensure uniqueness (should be unique by allocation, but double-check)
        if new_callsign in callsigns.values():
            # If collision, allocate a different number
            alt = self._allocate_number_for_prefix(target_first, target_second, callsigns)
            if not alt:
                return False, "no_number"
            new_callsign = f"{target_first}-{target_second}{alt}"

        # Update persistent store
        callsigns[member.id] = new_callsign
        save_callsigns(callsigns)

        # Update display name / nickname: try to replace existing callsign in display_name
        try:
            display = member.display_name
            # Pattern for existing callsign occurrences
            display_new = re.sub(r"(\[?)(CO|WO|E)-(G|S|J|W|N)(\d{2})(\]?)", new_callsign, display)
            if display_new == display:
                # Prepend if not found
                display_new = f"{new_callsign} {display}"
            # Truncate to Discord nickname limit (32)
            if len(display_new) > 32:
                display_new = display_new[:32]
            try:
                # Only attempt nickname change if it differs
                if member.nick != display_new:
                    await member.edit(nick=display_new, reason="Callsign auto-updated due to promotion")
            except Exception:
                # Lack of permission or hierarchy; ignore but proceed
                pass
        except Exception:
            pass

        # Notify the user via DM
        try:
            await member.send(f"Your callsign has been updated from **{current}** to **{new_callsign}** due to a promotion. Your nickname was updated if permitted.")
        except Exception:
            pass

        log_command(member, "auto_promote_callsign", f"{current} -> {new_callsign}")
        return True, new_callsign

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and non-promotion channels
        if message.author and getattr(message.author, "bot", False):
            return
        if message.channel.id != PROMOTION_CHANNEL_ID:
            return
        # If message mentions users, check each mentioned user
        if not message.mentions:
            return
        guild_id = message.guild.id if message.guild else None
        if not guild_id:
            return
        async with self._promotion_lock:
            s = self._promotion_pending.get(guild_id)
            if s is None:
                s = set()
                self._promotion_pending[guild_id] = s
            for member in message.mentions:
                try:
                    s.add(member.id)
                except Exception:
                    pass
            # Start a single delayed task if not already running
            if self._promotion_task is None or self._promotion_task.done():
                self._promotion_task = asyncio.create_task(self._process_pending_promotions())

    async def _process_pending_promotions(self, delay_seconds: int = 600):
        # Wait delay then process accumulated promotion mentions in batches per guild
        try:
            await asyncio.sleep(delay_seconds)
            async with self._promotion_lock:
                pending = dict(self._promotion_pending)
                self._promotion_pending.clear()
            for guild_id, user_ids in pending.items():
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                updates = []
                # Process sequentially with small delay to avoid rate limits
                for uid in list(user_ids):
                    try:
                        member = guild.get_member(uid) or await guild.fetch_member(uid)
                    except Exception:
                        continue
                    try:
                        promoted, info = await self._auto_promote_if_needed(member)
                        if promoted:
                            updates.append((member, info))
                    except Exception:
                        continue
                    await asyncio.sleep(0.25)
                # If any updates, announce in channel and then delete after 10s
                if updates:
                    # Choose the promotions channel in guild
                    ch = guild.get_channel(PROMOTION_CHANNEL_ID)
                    if ch:
                        lines = [f"{m.mention} -> **{cs}**" for m, cs in updates]
                        try:
                            sent = await ch.send("Updated callsigns:\n" + "\n".join(lines))
                            await asyncio.sleep(10)
                            try:
                                await sent.delete()
                            except Exception:
                                pass
                        except Exception:
                            pass
                    # Also ensure DMs were sent by _auto_promote_if_needed
        except Exception:
            pass

    @commands.command(name="promote_check", help="Admin: force a promote-check for a user (tests auto-promote behavior)")
    async def promote_check(self, ctx, member: discord.Member):
        is_admin = ctx.author.id == ADMIN_ID or any(r.id == 1355842403134603275 for r in getattr(ctx.author, "roles", []))
        if not is_admin:
            await ctx.send("You don't have permission to use this command.")
            return
        try:
            promoted, info = await self._auto_promote_if_needed(member)
            if promoted:
                await ctx.send(f"Promote check: updated callsign for {member.mention} to **{info}**")
            else:
                await ctx.send(f"Promote check: no change ({info})")
        except Exception as e:
            await ctx.send(f"Error during promote check: {e}")

class CallsignBasicView(discord.ui.View):
    def __init__(self, cog, is_admin=False, can_request=False, allowed_user_id=None, has_command_role=False):
        super().__init__(timeout=120)
        self.cog = cog
        self.is_admin = is_admin
        self.can_request = can_request
        self.has_command_role = has_command_role

        if is_admin:
            self.add_item(CallsignAdminMenuButton(cog, show_add=has_command_role))

    @discord.ui.button(label="View Callsign", style=discord.ButtonStyle.blurple)
    async def view_callsign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        callsign = await self.cog.view_callsign(interaction.user)
        embed = discord.Embed(
            title="Your Callsign",
            description=f"Your callsign: **{callsign}**",
            color=EMBED_COLOUR
        )
        embed.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_command(interaction.user, "view_callsign")

    @discord.ui.button(label="View All Callsigns", style=discord.ButtonStyle.blurple)
    async def view_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        callsigns = await self.cog.view_all_callsigns()
        if not callsigns:
            desc = "No callsigns assigned."
        else:
            desc = ""
            last_first = None
            last_second = None
            for uid, cs in callsigns:
                m = re.fullmatch(r"(CO|WO|E)-(G|S|J|W|N)(\d{2})", cs)
                if m:
                    first, second, num = m.group(1), m.group(2), m.group(3)
                else:
                    first, second = "CO", "G"
                if first != last_first:
                    if last_first is not None:
                        desc += "\n"
                    if first == "CO":
                        desc += "=== Commissioned Officers ===\n"
                    elif first == "WO":
                        desc += "=== Warrant Officers ===\n"
                    elif first == "E":
                        desc += "=== Enlisted Personnel ===\n"
                    last_first = first
                    last_second = None
                if second != last_second:
                    desc += f"{callsign_group_title(first, second)}\n"
                    last_second = second
                desc += f"<@{uid}>: **{cs}**\n"
        embed = discord.Embed(title="All Callsigns", description=desc, color=EMBED_COLOUR)
        embed.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_command(interaction.user, "view_all_callsigns")

    @discord.ui.button(label="Request Callsign", style=discord.ButtonStyle.green, row=1)
    async def request_callsign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.can_request:
            await interaction.response.send_message("You do not have permission to request a callsign.", ephemeral=True)
            return
        ok, msg = await self.cog.request_callsign(interaction.user)
        await interaction.response.send_message(msg, ephemeral=True)
        log_command(interaction.user, "request_callsign", msg)

class CallsignAdminMenuButton(discord.ui.Button):
    def __init__(self, cog, show_add=False):
        super().__init__(label="Admin Menu", style=discord.ButtonStyle.red, row=1)
        self.cog = cog
        self.show_add = show_add

    async def callback(self, interaction: discord.Interaction):
        view = CallsignAdminView(self.cog, show_add=self.show_add)
        embed = discord.Embed(
            title="Admin Callsign Menu",
            description=(
                "Callsigns are currently being updated by myself and the rest of the GCO team. "
                "Until the GCO team has said that the roles have been __finalized__,\n\n"
                "**__Please do not edit or request callsigns.__**"
            ),
            color=EMBED_COLOUR
        )
        embed.set_image(url=EMBED2_IMAGE)
        embed.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        log_command(interaction.user, "open_admin_menu")

class CallsignAdminView(discord.ui.View):
    def __init__(self, cog, show_add=False):
        super().__init__(timeout=120)
        self.cog = cog
        self.show_add = show_add

        if not self.show_add:
            for item in list(self.children):
                if isinstance(item, discord.ui.Button) and item.label == "Add Callsign":
                    self.remove_item(item)

    @discord.ui.button(label="Add Callsign", style=discord.ButtonStyle.green)
    async def add_callsign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.show_add:
            await interaction.response.send_message("You do not have permission to add callsigns.", ephemeral=True)
            return
        await interaction.response.send_modal(CallsignAddModal(self.cog))
        log_command(interaction.user, "add_callsign_modal_open")

    @discord.ui.button(label="Remove Callsign", style=discord.ButtonStyle.red)
    async def remove_callsign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CallsignRemoveModal(self.cog))
        log_command(interaction.user, "remove_callsign_modal_open")

    @discord.ui.button(label="View All Callsigns", style=discord.ButtonStyle.blurple)
    async def view_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        callsigns = await self.cog.view_all_callsigns()
        if not callsigns:
            desc = "No callsigns assigned."
        else:
            desc = ""
            last_first = None
            last_second = None
            for uid, cs in callsigns:
                m = re.fullmatch(r"(CO|WO|E)-(G|S|J|W|N)(\d{2})", cs)
                if m:
                    first, second, num = m.group(1), m.group(2), m.group(3)
                else:
                    first, second = "CO", "G"
                if first != last_first:
                    if last_first is not None:
                        desc += "\n"
                    if first == "CO":
                        desc += "=== Commissioned Officers ===\n"
                    elif first == "WO":
                        desc += "=== Warrant Officers ===\n"
                    elif first == "E":
                        desc += "=== Enlisted Personnel ===\n"
                    last_first = first
                    last_second = None
                if second != last_second:
                    desc += f"{callsign_group_title(first, second)}\n"
                    last_second = second
                desc += f"<@{uid}>: **{cs}**\n"
        embed = discord.Embed(title="All Callsigns", description=desc, color=EMBED_COLOUR)
        embed.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log_command(interaction.user, "admin_view_all_callsigns")

class CallsignAddModal(discord.ui.Modal, title="Add Callsign"):
    user_id = discord.ui.TextInput(label="User ID", required=True)
    callsign = discord.ui.TextInput(label="Callsign (XM-YZZ)", required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild or interaction.client.get_guild(interaction.guild_id)
        try:
            user = guild.get_member(int(self.user_id.value))
            if user is None:
                user = await guild.fetch_member(int(self.user_id.value))
        except Exception:
            await interaction.response.send_message("Invalid user ID or user not in server.", ephemeral=True)
            return
        ok, msg = await self.cog.add_callsign(user, self.callsign.value)
        await interaction.response.send_message(msg, ephemeral=True)
        log_command(interaction.user, "add_callsign", f"target={self.user_id.value} result={msg}")

class CallsignRemoveModal(discord.ui.Modal, title="Remove Callsign"):
    user_id = discord.ui.TextInput(label="User ID", required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild or interaction.client.get_guild(interaction.guild_id)
        try:
            user = guild.get_member(int(self.user_id.value))
            if user is None:
                user = await guild.fetch_member(int(self.user_id.value))
        except Exception:
            await interaction.response.send_message("Invalid user ID or user not in server.", ephemeral=True)
            return
        ok, msg = await self.cog.remove_callsign(user)
        await interaction.response.send_message(msg, ephemeral=True)
        log_command(interaction.user, "remove_callsign", f"target={self.user_id.value} result={msg}")

async def setup(bot):
    await bot.add_cog(CallsignCog(bot))