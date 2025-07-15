import discord
from discord.ext import commands
from discord import app_commands
import os
import re

CALLSIGN_FILE = os.path.join(os.path.dirname(__file__), "../data/callsigns.txt")
ADMIN_ID = 840949634071658507
ADMIN_ROLES = [1355842403134603275, 1329910280834252903]
REQUEST_ROLE = 1329910329701830686

# New role/callsign mapping
ROLE_CALLSIGN_MAP = {
    1355842403134603275: ("CO", "G"),
    1329910280834252903: ("CO", "S"),
    1394667511374680105: ("CO", "J"),
    1329910281903673344: ("WO", "W"),
    1329910295703064577: ("E", "S"),
    1355842399338889288: ("E", "N"),
    1329910298525696041: ("E", "J"),
}

EMBED_COLOUR = 0xd0b47b
EMBED1_IMAGE = "https://cdn.discordapp.com/attachments/1376647068092858509/1376995508890898513/callsigns.png?ex=68603900&is=685ee780&hm=43c6d4a34716adda18ac09a8f8673bc8ca7b83cd8da734ab0351062da31353c0&"
EMBED2_IMAGE = "https://cdn.discordapp.com/attachments/1376647068092858509/1376934109665824828/bottom.png?ex=685fffd1&is=685eae51&hm=f82cda74f321de0626c24fd63509c23ae372137c08637329c1d5fd1be9d902a8&"
EMBED_FOOTER = "High Rock Military Corps"
EMBED_ICON = "https://cdn.discordapp.com/attachments/1376647403712675991/1376652854391083269/image-141.png?ex=68604b61&is=685ef9e1&hm=bb374c9e0b2f4e1b20ac6f2566d20e4506d35c8733d3012bfb5f0a88c1a12946&"

LOG_CHANNEL_ID = 1343686645815181382  # Replace with your actual logs channel if different
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
    # Format: PREFIX-LETTERxx, e.g. CO-G01
    return bool(re.fullmatch(r"(CO|WO|E)-(G|S|J|W|N)[0-9]{2}", callsign))

def get_next_callsign(prefix, letter, callsigns):
    # Find all xx in use for ANY prefix/letter
    used = set()
    for cs in callsigns.values():
        m = re.fullmatch(r"(CO|WO|E)-(G|S|J|W|N)(\d{2})", cs)
        if m:
            used.add(int(m.group(3)))
    zz = 1
    while zz in used:
        zz += 1
    return f"{prefix}-{letter}{zz:02d}"

def callsign_sort_key(item):
    cs = item[1]
    # Custom order for first and second letter
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

class CallsignCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="callsign", aliases=["cs"], description="Callsign management tool")
    @app_commands.describe(user="User to check (optional)")
    async def callsign(self, ctx, user: discord.Member = None):
        # Admins can use everywhere
        is_admin = ctx.author.id == ADMIN_ID or any(r.id == 1355842403134603275 for r in getattr(ctx.author, "roles", []))
        if not is_admin:
            # Restrict !callsign to channels and roles
            if ctx.prefix and ctx.prefix.startswith("!"):
                if ctx.channel.id not in ALLOWED_CHANNELS:
                    allowed_mentions = " or ".join(f"<#{cid}>" for cid in ALLOWED_CHANNELS)
                    await ctx.send(f"Please use me in {allowed_mentions}.", ephemeral=True)
                    return
        await self.handle_callsign(ctx, user)

    async def handle_callsign(self, ctx_or_interaction, user: discord.Member = None):
        author = ctx_or_interaction.user if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author
        callsigns = load_callsigns()
        is_admin = author.id == ADMIN_ID or any(r.id == 1355842403134603275 for r in getattr(author, "roles", [])
        )
        # Admin menu access for these roles
        admin_menu_roles = {1355842403134603275, 1329910280834252903, 1394667511374680105}
        has_admin_menu = is_admin or any(r.id in admin_menu_roles for r in getattr(author, "roles", []))
        # Only main admin and CO-G role can add callsigns
        can_add_callsign = is_admin or any(r.id == 1355842403134603275 for r in getattr(author, "roles", []))

        # Log all command opens
        log_command(author, "callsign", f"user={user.id if user else 'self'}")

        # If used as !callsign @user or !cs @user, just show that user's callsign
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

    # --- Callsign Actions ---
    async def add_callsign(self, user: discord.Member, callsign: str):
        callsigns = load_callsigns()
        if not is_valid_callsign(callsign):
            return False, "Invalid callsign format."
        if callsign in callsigns.values():
            return False, "This callsign is already taken."
        callsigns[user.id] = callsign
        save_callsigns(callsigns)
        # DM the user
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
        # DM the user
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
        # Sort by X, then Y, then ZZ
        sorted_items = sorted(callsigns.items(), key=callsign_sort_key)
        return sorted_items

    async def request_callsign(self, user: discord.Member):
        callsigns = load_callsigns()
        if not any(r.id == REQUEST_ROLE for r in getattr(user, "roles", [])):
            return False, "You do not have permission to request a callsign."
        for role_id, (x, y) in ROLE_CALLSIGN_MAP.items():
            if any(r.id == role_id for r in getattr(user, "roles", [])):
                # Find all ZZs in use for ANY X/Y
                used = set()
                for cs in callsigns.values():
                    m = re.fullmatch(r"[1-6]M-[SHWLIC](\d{2})", cs)
                    if m:
                        used.add(int(m.group(1)))
                zz = 1
                while zz in used:
                    zz += 1
                # Find the lowest ZZ in use for ANY callsign
                min_zz = min(used) if used else 1
                current_callsign = callsigns.get(user.id)
                if current_callsign:
                    m = re.fullmatch(rf"{x}M-{y}(\d{{2}})", current_callsign)
                    if m and int(m.group(1)) == min_zz:
                        return False, f"Your callsign is already up to date: **{current_callsign}**"
                # Otherwise, assign the lowest available universal ZZ
                callsigns[user.id] = f"{x}M-{y}{zz:02d}"
                save_callsigns(callsigns)
                # Remove role 1371198982340083712 if user did not have a callsign before
                if not current_callsign:
                    role = user.guild.get_role(1371198982340083712)
                    if role:
                        try:
                            await user.remove_roles(role, reason="Callsign assigned")
                        except Exception:
                            pass
                return True, f"Auto-assigned callsign {callsigns[user.id]} to {user.mention}."
        return False, "You do not have a role eligible for a callsign or all are taken."

def callsign_group_title(first, second):
    # Only used for the inner group title
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

# --- Views for Menus ---

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
                    # Not matching, treat as CO-G for grouping and ordering
                    first, second = "CO", "G"
                # Section title
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
                # Subgroup title
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
            # Remove the add_callsign button if not allowed
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
                    # Not matching, treat as CO-G for grouping and ordering
                    first, second = "CO", "G"
                # Section title
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
                # Subgroup title
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