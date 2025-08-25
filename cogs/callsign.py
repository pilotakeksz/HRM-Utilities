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
                if not current_callsign:
                    role = user.guild.get_role(1371198982340083712)
                    if role:
                        try:
                            await user.remove_roles(role, reason="Callsign assigned")
                        except Exception:
                            pass
                # Always use new_callsign in the confirmation message
                return True, f"Auto-assigned callsign **{new_callsign}** to {user.mention}."
            return False, "No available callsign numbers left."

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