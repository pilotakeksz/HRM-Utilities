import discord
from discord.ext import commands
from discord import app_commands, ui
import os
import datetime
import json
import asyncio
import requests

ARREST_ROLE = 1329910329701830686
DEPLOY_ROLES = {
    1329910280834252903,
    1394667511374680105,
    1355842403134603275,
    1329910281903673344,
    1329910295703064577,
}
LOG_CHANNEL_ID = 1343686645815181382
DEPLOY_ANNOUNCE_CHANNEL_ID = 1329910519892807763
TAN = 0xd0b37b
YELLOW = 0xffd966
RED = 0xe74c3c
DEPLOY_STATE_FILE = os.path.join("data", "deployment_state.json")
LOG_FILE = os.path.join("logs", "mdt_log.txt")
ARREST_LOG_CHANNEL_ID = 1379091390478159972
ARREST_ID_FILE = os.path.join("data", "arrest_id.json")

def ensure_data_dirs():
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

def log_action(user, action, details):
    ensure_data_dirs()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {user} | {action} | {details}\n")
# test
async def log_to_discord(bot, user, action, details):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        # Choose color based on action
        if "arrest" in action.lower():
            color = 0x8d5524  # brown for arrest log
        elif "deployment started" in action.lower():
            color = 0x2ecc40  # green for deployment start
        elif "deployment ended" in action.lower():
            color = 0xe74c3c  # red for deployment end
        elif "location change" in action.lower() or "move" in action.lower():
            color = 0xffd966  # yellow for move
        else:
            color = TAN  # default tan

        embed = discord.Embed(
            title="MDT Action Log",
            color=color,
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="User", value=f"{user} ({getattr(user, 'id', 'N/A')})", inline=False)
        embed.add_field(name="Action", value=action, inline=False)
        embed.add_field(name="Details", value=details, inline=False)
        await channel.send(embed=embed)

def load_deploy_state():
    ensure_data_dirs()
    if not os.path.exists(DEPLOY_STATE_FILE):
        return {"active": False, "last_start": 0, "last_move": 0, "last_end": 0, "data": {}}
    with open(DEPLOY_STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_deploy_state(state):
    ensure_data_dirs()
    with open(DEPLOY_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)

def has_arrest_role(interaction):
    return any(r.id == ARREST_ROLE for r in getattr(interaction.user, "roles", []))

def has_deploy_role(interaction):
    return any(r.id in DEPLOY_ROLES for r in getattr(interaction.user, "roles", []))

def get_next_arrest_id():
    ensure_data_dirs()
    if not os.path.exists(ARREST_ID_FILE):
        with open(ARREST_ID_FILE, "w", encoding="utf-8") as f:
            json.dump({"id": 1}, f)
        return 1
    with open(ARREST_ID_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    arrest_id = data.get("id", 1)
    data["id"] = arrest_id + 1
    with open(ARREST_ID_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return arrest_id

def get_roblox_user_info(username):
    # Get userId and displayName from username
    url = "https://users.roblox.com/v1/usernames/users"
    resp = requests.post(url, json={"usernames": [username], "excludeBannedUsers": False}, timeout=10)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not data["data"]:
        return None
    user = data["data"][0]
    return {
        "userId": user["id"],
        "username": user["name"],
        "displayName": user.get("displayName", user["name"])
    }

def get_roblox_avatar_url(user_id, size=420):
    url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size={size}x{size}&format=Png&isCircular=false"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data["data"] and "imageUrl" in data["data"][0]:
            return data["data"][0]["imageUrl"]
    except Exception:
        pass
    # fallback
    return "https://tr.rbxcdn.com/6c6b8e6b7b7e7b7b7b7b7b7b7b7b7b/420/420/AvatarHeadshot/Png"

class ArrestLogModal(ui.Modal, title="Log Arrest"):
    roblox_username = ui.TextInput(label="Roblox Username", required=True)
    charges = ui.TextInput(label="Charges", required=True)
    notes = ui.TextInput(label="Notes", required=False)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        username = self.roblox_username.value.strip()
        charges = self.charges.value.strip()
        notes = self.notes.value.strip()
        arrest_id = get_next_arrest_id()

        # Try to get Roblox info and validate username
        info = None
        avatar_url = None
        try:
            info = get_roblox_user_info(username)
            if not info:
                await interaction.response.send_message(
                    f"❌ Roblox user `{username}` does not exist. Please check the username and try again.",
                    ephemeral=True
                )
                return
            avatar_url = get_roblox_avatar_url(info["userId"])
        except Exception:
            avatar_url = "https://tr.rbxcdn.com/6c6b8e6b7b7e7b7b7b7b7b7b7b7b7b/420/420/AvatarHeadshot/Png"

        display_name = info["displayName"] if info else username
        roblox_username = info["username"] if info else username

        embed = discord.Embed(
            title="<:MCNG:1409463907294384169> // Arrest Log",
            color=TAN,
            description=(
                f"> **Username:** {roblox_username}\n"
                f"> **Display Name:** {display_name}\n\n"
                f"> **Charges:** {charges}\n"
                f"> **Notes:** {notes or 'None'}\n\n"
                f"> Detained By: {interaction.user.mention}"
            )
        )
        embed.set_thumbnail(url=avatar_url)
        embed.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        embed.set_footer(text=f"ID: {arrest_id}")

        # Log to file
        log_action(
            interaction.user,
            "Arrest Log",
            f"ID: {arrest_id} | Username: {roblox_username} | Display: {display_name} | Charges: {charges} | Notes: {notes}"
        )

        # Log to Discord
        await log_to_discord(
            self.bot,
            interaction.user,
            "Arrest Log",
            f"ID: {arrest_id} | Username: {roblox_username} | Display: {display_name} | Charges: {charges} | Notes: {notes}"
        )

        # Send to arrest log channel
        channel = interaction.client.get_channel(ARREST_LOG_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)

        await interaction.response.send_message("Arrest logged.", ephemeral=True)

class MDTView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Log Arrest", style=discord.ButtonStyle.primary, custom_id="mdt_log_arrest")
    async def log_arrest(self, interaction: discord.Interaction, button: ui.Button):
        if not has_arrest_role(interaction):
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return
        await interaction.response.send_modal(ArrestLogModal(self.bot))
        log_action(interaction.user, "Log Arrest", "Opened Arrest Log Modal")
        await log_to_discord(self.bot, interaction.user, "Log Arrest", "Opened Arrest Log Modal")

    @ui.button(label="Deployment Management", style=discord.ButtonStyle.secondary, custom_id="mdt_deploy_mgmt")
    async def deploy_mgmt(self, interaction: discord.Interaction, button: ui.Button):
        if not has_deploy_role(interaction):
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return
        state = load_deploy_state()
        now = datetime.datetime.utcnow().timestamp()
        can_start = not state["active"]
        can_move = state["active"]
        can_end = state["active"]
        # Build deployment management embed
        embed1 = discord.Embed(color=TAN)
        embed1.set_image(url="https://media.discordapp.net/attachments/1409252771978280973/1409314343748898988/DEPLOYMENT.png?ex=68acedc3&is=68ab9c43&hm=0f4fadd73244618fd0072320859b41b50afd2d5596625b2f2834a58524f31593&=&format=webp&quality=lossless&width=2576&height=862")
        embed2 = discord.Embed(
            title="<:MCNG:1409463907294384169> // Deployment Management",
            description="Manage deployments below.",
            color=TAN
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        view = DeploymentView(self.bot, can_start, can_move, can_end)
        await interaction.response.edit_message(embeds=[embed1, embed2], view=view)
        log_action(interaction.user, "Deployment Management", "Opened deployment management")
        await log_to_discord(self.bot, interaction.user, "Deployment Management", "Opened deployment management")

class DeploymentView(ui.View):
    def __init__(self, bot, can_start, can_move, can_end):
        super().__init__(timeout=None)
        self.bot = bot
        self.can_start = can_start
        self.can_move = can_move
        self.can_end = can_end

    @ui.button(label="Start Deployment", style=discord.ButtonStyle.success, custom_id="start_deploy", row=0)
    async def start_deploy(self, interaction: discord.Interaction, button: ui.Button):
        state = load_deploy_state()
        now = datetime.datetime.utcnow().timestamp()
        if state["active"]:
            await interaction.response.send_message("A deployment is already active.", ephemeral=True)
            return
        if now - state.get("last_start", 0) < 1800:
            await interaction.response.send_message("Deployment start is on cooldown (30 min).", ephemeral=True)
            return
        modal = StartDeploymentModal(self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Move Location", style=discord.ButtonStyle.primary, custom_id="move_deploy", row=0)
    async def move_deploy(self, interaction: discord.Interaction, button: ui.Button):
        state = load_deploy_state()
        now = datetime.datetime.utcnow().timestamp()
        if not state["active"]:
            await interaction.response.send_message("No deployment is currently active.", ephemeral=True)
            return
        if now - state.get("last_move", 0) < 420:
            await interaction.response.send_message("Move location is on cooldown (7 min).", ephemeral=True)
            return
        modal = MoveDeploymentModal(self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Close Deployment", style=discord.ButtonStyle.danger, custom_id="close_deploy", row=0)
    async def close_deploy(self, interaction: discord.Interaction, button: ui.Button):
        state = load_deploy_state()
        now = datetime.datetime.utcnow().timestamp()
        if not state["active"]:
            await interaction.response.send_message("No deployment is currently active.", ephemeral=True)
            return
        if now - state.get("last_end", 0) < 420:
            await interaction.response.send_message("Close deployment is on cooldown (7 min).", ephemeral=True)
            return
        # End deployment
        state["active"] = False
        state["last_end"] = now
        save_deploy_state(state)
        # Announce in deployment channel
        channel = interaction.client.get_channel(DEPLOY_ANNOUNCE_CHANNEL_ID)
        ping = "<@&1329910276912447608>"
        embed1 = discord.Embed(color=RED)
        embed1.set_image(url="https://media.discordapp.net/attachments/1409252771978280973/1409314343748898988/DEPLOYMENT.png?ex=68acedc3&is=68ab9c43&hm=0f4fadd73244618fd0072320859b41b50afd2d5596625b2f2834a58524f31593&=&format=webp&quality=lossless&width=2576&height=862")
        embed2 = discord.Embed(
            title="<:MCNG:1409463907294384169> // Deployment Ended",
            description="**The most recent deployment has ended.**",
            color=RED
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        embed2.set_footer(text=f"Ended by {interaction.user}")
        await channel.send(content=ping, embeds=[embed1, embed2])
        await interaction.response.send_message("Deployment ended.", ephemeral=True)
        log_action(interaction.user, "Deployment Ended", "Deployment ended")
        await log_to_discord(self.bot, interaction.user, "Deployment Ended", "Deployment ended")

class StartDeploymentModal(ui.Modal, title="Start Deployment"):
    deployment_type = ui.TextInput(label="Deployment Type", required=True)
    location = ui.TextInput(label="Location", required=True)
    notes = ui.TextInput(label="Notes", required=False)
    entry_code = ui.TextInput(label="Entry Code", required=True)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        state = load_deploy_state()
        now = datetime.datetime.utcnow().timestamp()
        state["active"] = True
        state["last_start"] = now
        state["data"] = {
            "type": self.deployment_type.value,
            "location": self.location.value,
            "notes": self.notes.value,
            "entry_code": self.entry_code.value,
            "by": interaction.user.id
        }
        save_deploy_state(state)
        # Announce in deployment channel
        channel = interaction.client.get_channel(DEPLOY_ANNOUNCE_CHANNEL_ID)
        ping = "<@&1329910394831114281>"
        embed1 = discord.Embed(color=TAN)
        embed1.set_image(url="https://media.discordapp.net/attachments/1409252771978280973/1409314343748898988/DEPLOYMENT.png?ex=68acedc3&is=68ab9c43&hm=0f4fadd73244618fd0072320859b41b50afd2d5596625b2f2834a58524f31593&=&format=webp&quality=lossless&width=2576&height=862")
        embed2 = discord.Embed(
            title="<:MCNG:1409463907294384169> // Deployment",
            description=f"{interaction.user.mention} has **started a deployment.**\n\n"
                        f"> - Type: **{self.deployment_type.value}**\n"
                        f"> - Location: **{self.location.value}**\n"
                        f"> - Entry code: **{self.entry_code.value}**\n"
                        f"> - Notes: **{self.notes.value or 'None'}**",
            color=TAN
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        await channel.send(content=ping, embeds=[embed1, embed2], view=DeploymentJoinView())
        await interaction.response.send_message("Deployment started.", ephemeral=True)
        log_action(interaction.user, "Deployment Started", f"Type: {self.deployment_type.value} | Location: {self.location.value} | Entry: {self.entry_code.value} | Notes: {self.notes.value}")
        await log_to_discord(self.bot, interaction.user, "Deployment Started", f"Type: {self.deployment_type.value} | Location: {self.location.value} | Entry: {self.entry_code.value} | Notes: {self.notes.value}")

class MoveDeploymentModal(ui.Modal, title="Move Deployment Location"):
    location = ui.TextInput(label="New Location", required=True)
    notes = ui.TextInput(label="Notes", required=False)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        state = load_deploy_state()
        now = datetime.datetime.utcnow().timestamp()
        state["last_move"] = now
        state["data"]["location"] = self.location.value
        state["data"]["notes"] = self.notes.value
        save_deploy_state(state)
        # Announce in deployment channel
        channel = interaction.client.get_channel(DEPLOY_ANNOUNCE_CHANNEL_ID)
        ping = "<@&1329910276912447608>"
        embed1 = discord.Embed(color=YELLOW)
        embed1.set_image(url="https://media.discordapp.net/attachments/1409252771978280973/1409314343748898988/DEPLOYMENT.png?ex=68acedc3&is=68ab9c43&hm=0f4fadd73244618fd0072320859b41b50afd2d5596625b2f2834a58524f31593&=&format=webp&quality=lossless&width=2576&height=862")
        embed2 = discord.Embed(
            title="<:MCNG:1409463907294384169> // Deployment Location Change",
            description=f"> - Location: **{self.location.value}**\n> - Notes: **{self.notes.value or 'None'}**",
            color=YELLOW
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        await channel.send(content=ping, embeds=[embed1, embed2])
        await interaction.response.send_message("Deployment location updated.", ephemeral=True)
        log_action(interaction.user, "Deployment Location Change", f"Location: {self.location.value} | Notes: {self.notes.value}")
        await log_to_discord(self.bot, interaction.user, "Deployment Location Change", f"Location: {self.location.value} | Notes: {self.notes.value}")

class DeploymentJoinView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.yes_users = set()
        self.maybe_users = set()

    @ui.button(label=None, style=discord.ButtonStyle.success, custom_id='deploy_yes', emoji='<:yes:1358812809558753401>')
    async def yes_button(self, interaction: discord.Interaction, button: ui.Button):
        self.yes_users.add(interaction.user)
        self.maybe_users.discard(interaction.user)
        await interaction.response.send_message('You are marked as joining!', ephemeral=True)

    @ui.button(label=None, style=discord.ButtonStyle.primary, custom_id='deploy_maybe', emoji='<:maybe:1358812794585354391>')
    async def maybe_button(self, interaction: discord.Interaction, button: ui.Button):
        self.maybe_users.add(interaction.user)
        self.yes_users.discard(interaction.user)
        await interaction.response.send_message('You are marked as joining late!', ephemeral=True)

    @ui.button(label=None, style=discord.ButtonStyle.secondary, custom_id='deploy_members', emoji='<:Member:1343945679390904330>')
    async def member_button(self, interaction: discord.Interaction, button: ui.Button):
        yes_mentions = [user.mention for user in self.yes_users]
        maybe_mentions = [user.mention for user in self.maybe_users]
        msg = '**Joining:**\n' + ('\n'.join(yes_mentions) if yes_mentions else 'None')
        msg += '\n\n**Joining Late:**\n' + ('\n'.join(maybe_mentions) if maybe_mentions else 'None')
        await interaction.response.send_message(msg, ephemeral=True)

class MDT(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mdt", description="Open the Mobile Data Terminal.")
    @app_commands.check(lambda i: has_arrest_role(i) or has_deploy_role(i))
    async def mdt_slash(self, interaction: discord.Interaction):
        # Embed 1: just image
        embed1 = discord.Embed(color=TAN)
        embed1.set_image(url="https://media.discordapp.net/attachments/1409252771978280973/1409314345267105812/MDT.png?ex=68acedc3&is=68ab9c43&hm=034e65555a01653c020d1fb830abe7982ce495b4a2754621dcb8ad02e2617145&=&format=webp&quality=lossless&width=2576&height=862")
        # Embed 2: main interface
        embed2 = discord.Embed(
            title="<:MCNG:1409463907294384169> // Mobile Data Terminal",
            color=TAN
        )
        embed2.set_image(url="https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&")
        embed2.add_field(name="Log arrest", value="Log an arrest in the system.", inline=True)
        embed2.add_field(name="Deployment Management", value="Manage deployments and locations.", inline=True)
        await interaction.response.send_message(embeds=[embed1, embed2], view=MDTView(self.bot), ephemeral=True)
        log_action(interaction.user, "Opened MDT", "Opened MDT interface")
        await log_to_discord(self.bot, interaction.user, "Opened MDT", "Opened MDT interface")

async def setup(bot):
    await bot.add_cog(MDT(bot))