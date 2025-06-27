import discord
from discord.ext import commands
from discord import app_commands
import os
import re

CALLSIGN_FILE = os.path.join(os.path.dirname(__file__), "../data/callsigns.txt")
ADMIN_ID = 840949634071658507
ADMIN_ROLES = [911072161349918720, 1329910241835352064]
REQUEST_ROLE = 1329910329701830686

# Role to callsign mapping for auto-assign
ROLE_CALLSIGN_MAP = {
    1329910241835352064: ("1", "S"),
    1329910265264869387: ("2", "H"),
    1329910285594525886: ("3", "W"),
    1329910295703064577: ("4", "L"),
    1329910298525696041: ("5", "I"),
    1331644226781577316: ("6", "C"),
}

EMBED_COLOUR = 0xd0b47b
EMBED1_IMAGE = "https://cdn.discordapp.com/attachments/1376647068092858509/1376995508890898513/callsigns.png?ex=68603900&is=685ee780&hm=43c6d4a34716adda18ac09a8f8673bc8ca7b83cd8da734ab0351062da31353c0&"
EMBED2_IMAGE = "https://cdn.discordapp.com/attachments/1376647068092858509/1376934109665824828/bottom.png?ex=685fffd1&is=685eae51&hm=f82cda74f321de0626c24fd63509c23ae372137c08637329c1d5fd1be9d902a8&"
EMBED_FOOTER = "High Rock Military Corps"
EMBED_ICON = "https://cdn.discordapp.com/attachments/1376647403712675991/1376652854391083269/image-141.png?ex=68604b61&is=685ef9e1&hm=bb374c9e0b2f4e1b20ac6f2566d20e4506d35c8733d3012bfb5f0a88c1a12946&"

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
    return bool(re.fullmatch(r"[1-6]M-[SHWLIC][0-9]{2}", callsign))

def get_next_callsign(x, y, callsigns):
    # Find the next available ZZ for the given X and Y
    used = set()
    for cs in callsigns.values():
        m = re.fullmatch(rf"{x}M-{y}(\d{{2}})", cs)
        if m:
            used.add(int(m.group(1)))
    zz = 1
    while zz in used:
        zz += 1
    return f"{x}M-{y}{zz:02d}"

class CallsignCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="callsign", aliases=["cs"], description="Callsign management tool")
    @app_commands.describe(user="User to check (optional)")
    async def callsign(self, ctx, user: discord.Member = None):
        await self.handle_callsign(ctx, user)

    async def handle_callsign(self, ctx_or_interaction, user: discord.Member = None):
        author = ctx_or_interaction.user if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author
        callsigns = load_callsigns()
        is_admin = author.id == ADMIN_ID
        has_admin_role = any(r.id in ADMIN_ROLES for r in getattr(author, "roles", []))
        has_request_role = any(r.id == REQUEST_ROLE for r in getattr(author, "roles", []))

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
            return

        # Always show the basic menu
        view = CallsignBasicView(self, is_admin=is_admin or has_admin_role, can_request=has_request_role, allowed_user_id=author.id)
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
        return True, f"Callsign {callsign} assigned to {user.mention}."

    async def remove_callsign(self, user: discord.Member):
        callsigns = load_callsigns()
        if user.id not in callsigns:
            return False, "User does not have a callsign."
        del callsigns[user.id]
        save_callsigns(callsigns)
        return True, f"Callsign removed from {user.mention}."

    async def view_callsign(self, user: discord.Member):
        callsigns = load_callsigns()
        return callsigns.get(user.id, "None")

    async def view_all_callsigns(self):
        callsigns = load_callsigns()
        return callsigns

    async def request_callsign(self, user: discord.Member):
        callsigns = load_callsigns()
        # Only allow if user has the request role
        if not any(r.id == REQUEST_ROLE for r in getattr(user, "roles", [])):
            return False, "You do not have permission to request a callsign."
        # Auto-assign based on roles, always give the lowest available number
        for role_id, (x, y) in ROLE_CALLSIGN_MAP.items():
            if any(r.id == role_id for r in getattr(user, "roles", [])):
                callsign = get_next_callsign(x, y, callsigns)
                callsigns[user.id] = callsign
                save_callsigns(callsigns)
                return True, f"Auto-assigned callsign {callsign} to {user.mention}."
        return False, "You do not have a role eligible for a callsign or all are taken."

# --- Views for Menus ---

class CallsignBasicView(discord.ui.View):
    def __init__(self, cog, is_admin=False, can_request=False, allowed_user_id=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.is_admin = is_admin
        self.can_request = can_request
        self.allowed_user_id = allowed_user_id
        if is_admin:
            self.add_item(CallsignAdminMenuButton(cog))

    def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.allowed_user_id:
            self.stop()
            try:
                self.bot.loop.create_task(interaction.response.send_message("You can't use this menu.", ephemeral=True))
            except Exception:
                pass
            return False
        return True

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

    @discord.ui.button(label="View All Callsigns", style=discord.ButtonStyle.blurple)
    async def view_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.interaction_check(interaction):
            await interaction.response.send_message("You can't use this menu.", ephemeral=True)
            return
        callsigns = await self.cog.view_all_callsigns()
        desc = "\n".join(f"<@{uid}>: **{cs}**" for uid, cs in callsigns.items()) or "No callsigns assigned."
        embed = discord.Embed(title="All Callsigns", description=desc, color=EMBED_COLOUR)
        embed.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Request Callsign", style=discord.ButtonStyle.green, row=1)
    async def request_callsign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.interaction_check(interaction):
            await interaction.response.send_message("You can't use this menu.", ephemeral=True)
            return
        if not self.can_request:
            await interaction.response.send_message("You do not have permission to request a callsign.", ephemeral=True)
            return
        ok, msg = await self.cog.request_callsign(interaction.user)
        await interaction.response.send_message(msg, ephemeral=True)

class CallsignAdminMenuButton(discord.ui.Button):
    def __init__(self, cog):
        super().__init__(label="Admin Menu", style=discord.ButtonStyle.red, row=1)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        view = CallsignAdminView(self.cog)
        embed = discord.Embed(title="Admin Callsign Menu", color=EMBED_COLOUR)
        embed.set_image(url=EMBED2_IMAGE)
        embed.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class CallsignAdminView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=120)
        self.cog = cog

    @discord.ui.button(label="Add Callsign", style=discord.ButtonStyle.green)
    async def add_callsign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CallsignAddModal(self.cog))

    @discord.ui.button(label="Remove Callsign", style=discord.ButtonStyle.red)
    async def remove_callsign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CallsignRemoveModal(self.cog))

    @discord.ui.button(label="View All Callsigns", style=discord.ButtonStyle.blurple)
    async def view_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        callsigns = await self.cog.view_all_callsigns()
        desc = "\n".join(f"<@{uid}>: **{cs}**" for uid, cs in callsigns.items()) or "No callsigns assigned."
        embed = discord.Embed(title="All Callsigns", description=desc, color=EMBED_COLOUR)
        embed.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class CallsignAddModal(discord.ui.Modal, title="Add Callsign"):
    user_id = discord.ui.TextInput(label="User ID", required=True)
    callsign = discord.ui.TextInput(label="Callsign (XM-YZZ)", required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = await interaction.client.fetch_user(int(self.user_id.value))
        except Exception:
            await interaction.response.send_message("Invalid user ID.", ephemeral=True)
            return
        ok, msg = await self.cog.add_callsign(user, self.callsign.value)
        await interaction.response.send_message(msg, ephemeral=True)

class CallsignRemoveModal(discord.ui.Modal, title="Remove Callsign"):
    user_id = discord.ui.TextInput(label="User ID", required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = await interaction.client.fetch_user(int(self.user_id.value))
        except Exception:
            await interaction.response.send_message("Invalid user ID.", ephemeral=True)
            return
        ok, msg = await self.cog.remove_callsign(user)
        await interaction.response.send_message(msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(CallsignCog(bot))