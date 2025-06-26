import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button, Modal, TextInput
import asyncio
import datetime

# Load from environment
CIVILIAN_ROLE = int(os.getenv("CIVILIAN_ROLE"))
MC_ROLE = int(os.getenv("MC_ROLE"))
HC_ROLE = int(os.getenv("HC_ROLE"))
TICKET_HANDLER_ROLE = int(os.getenv("TICKET_HANDLER_ROLE"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CATEGORY_GENERAL = int(os.getenv("CATEGORY_GENERAL"))
CATEGORY_MANAGEMENT = int(os.getenv("CATEGORY_MANAGEMENT"))
CATEGORY_ARCHIVED = int(os.getenv("CATEGORY_ARCHIVED"))
CHANNEL_TICKET_LOGS = int(os.getenv("CHANNEL_TICKET_LOGS"))
CHANNEL_ASSISTANCE = int(os.getenv("CHANNEL_ASSISTANCE"))
EMBED_COLOUR = int(os.getenv("EMBED_COLOUR"), 16)
EMBED_FOOTER = os.getenv("EMBED_FOOTER")
EMBED_ICON = os.getenv("EMBED_ICON")
EMBED1_IMAGE = os.getenv("EMBED1_IMAGE")
EMBED2_IMAGE = os.getenv("EMBED2_IMAGE")
MIA_REDIRECT = os.getenv("MIA_REDIRECT")

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

def log_transcript(channel, messages):
    filename = os.path.join(LOGS_DIR, f"transcript_{channel.id}_{int(datetime.datetime.utcnow().timestamp())}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        for msg in messages:
            time = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{time}] {msg.author} ({msg.author.id}): {msg.content}\n")
    return filename

class TicketTypeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="General Support", value="general", emoji="<:HighRockMilitary:1376605942765977800>"),
            discord.SelectOption(label="Management", value="management", emoji="<:HC:1343192841676914712>"),
            discord.SelectOption(label="MIA", value="mia", emoji="<:MIA:1364309116859715654>"),
        ]
        super().__init__(placeholder="Select ticket type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "mia":
            await interaction.response.send_message(f"Please head to our MIA server for appeals and reports: {MIA_REDIRECT}", ephemeral=True)
            return
        elif self.values[0] == "management":
            await interaction.response.send_modal(ManagementTicketModal())
        elif self.values[0] == "general":
            await interaction.response.send_modal(GeneralTicketModal())

class TicketTypeView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())

class ManagementTicketModal(Modal, title="Management Ticket"):
    request = TextInput(label="Request / Inquiry", style=discord.TextStyle.paragraph, required=True, max_length=1024)

    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(interaction, "management", self.request.value)

class GeneralTicketModal(Modal, title="General Support Ticket"):
    request = TextInput(label="Request / Inquiry", style=discord.TextStyle.paragraph, required=True, max_length=1024)

    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(interaction, "general", self.request.value)

async def create_ticket(interaction, ticket_type, request_content):
    guild = interaction.guild
    user = interaction.user
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
    }
    ticket_name = f"📨-{'m-ticket' if ticket_type == 'management' else 'g-ticket'}-{user.name}".replace(" ", "-").lower()
    category_id = CATEGORY_MANAGEMENT if ticket_type == "management" else CATEGORY_GENERAL

    # Add roles
    if ticket_type == "management":
        overwrites[guild.get_role(HC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
    else:
        overwrites[guild.get_role(HC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
        overwrites[guild.get_role(MC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)

    channel = await guild.create_text_channel(
        ticket_name,
        category=guild.get_channel(category_id),
        overwrites=overwrites,
        reason=f"Ticket opened by {user}"
    )

    # Embed 1 (image)
    embed1 = discord.Embed(color=EMBED_COLOUR)
    embed1.set_image(url=EMBED1_IMAGE)

    # Embed 2 (info)
    embed2 = discord.Embed(
        description="Our personnel will be with you shortly. Please do not ping them unnecessarily.\n\nIn the mean time, please add details your initial inquiry.\n\n**Request / Inquiry:**\n" + request_content,
        color=EMBED_COLOUR
    )
    embed2.set_image(url=EMBED2_IMAGE)
    embed2.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)

    await channel.send(content=f"<@&{TICKET_HANDLER_ROLE}>", embeds=[embed1, embed2], view=TicketActionView(channel, user, ticket_type))

    await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)

class TicketActionView(View):
    def __init__(self, channel, opener, ticket_type):
        super().__init__(timeout=None)
        self.channel = channel
        self.opener = opener
        self.ticket_type = ticket_type
        self.claimed_by = None
        self.add_item(ClaimButton(self))
        self.add_item(CloseButton(self))

class ClaimButton(Button):
    def __init__(self, parent_view):
        super().__init__(label="Claim", style=discord.ButtonStyle.success, emoji="✅")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        hc_role = interaction.guild.get_role(HC_ROLE)
        if hc_role not in interaction.user.roles:
            await interaction.response.send_message("Only HC can claim this ticket.", ephemeral=True)
            return
        self.parent_view.claimed_by = interaction.user
        # Change permissions: only claimer can type, others can view
        await self.parent_view.channel.set_permissions(hc_role, send_messages=False)
        await self.parent_view.channel.set_permissions(interaction.user, send_messages=True)
        await self.parent_view.channel.send(f"This ticket has been claimed by {interaction.user.mention}.")
        # Change button to unclaim
        self.disabled = True
        self.parent_view.clear_items()
        self.parent_view.add_item(UnclaimButton(self.parent_view))
        self.parent_view.add_item(CloseButton(self.parent_view))
        await interaction.response.edit_message(view=self.parent_view)

class UnclaimButton(Button):
    def __init__(self, parent_view):
        super().__init__(label="Unclaim", style=discord.ButtonStyle.secondary, emoji="🟦")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        hc_role = interaction.guild.get_role(HC_ROLE)
        if hc_role not in interaction.user.roles:
            await interaction.response.send_message("Only HC can unclaim this ticket.", ephemeral=True)
            return
        self.parent_view.claimed_by = None
        await self.parent_view.channel.set_permissions(hc_role, send_messages=True)
        await self.parent_view.channel.send("This ticket is now unclaimed.")
        # Change button back to claim
        self.disabled = True
        self.parent_view.clear_items()
        self.parent_view.add_item(ClaimButton(self.parent_view))
        self.parent_view.add_item(CloseButton(self.parent_view))
        await interaction.response.edit_message(view=self.parent_view)

class CloseButton(Button):
    def __init__(self, parent_view):
        super().__init__(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Confirm Close",
                description="Are you sure you want to close this ticket? This action cannot be undone.",
                color=discord.Color.red()
            ),
            view=ConfirmCloseView(self.parent_view.channel, self.parent_view.opener, self.parent_view.ticket_type),
            ephemeral=True
        )

class ConfirmCloseView(View):
    def __init__(self, channel, opener, ticket_type):
        super().__init__(timeout=60)
        self.channel = channel
        self.opener = opener
        self.ticket_type = ticket_type

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        # Archive
        await self.channel.edit(category=interaction.guild.get_channel(CATEGORY_ARCHIVED))
        await self.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await self.channel.send(embed=discord.Embed(
            description="This ticket is being archived. It will permanently be deleted in 15 minutes.",
            color=discord.Color.red()
        ))
        # Transcript
        messages = [msg async for msg in self.channel.history(limit=None, oldest_first=True)]
        transcript_path = log_transcript(self.channel, messages)
        # Wait 15 minutes
        await asyncio.sleep(15 * 60)
        await self.channel.send("This ticket will be deleted in 20 seconds.")
        await asyncio.sleep(20)
        await self.channel.delete()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Ticket close cancelled.", ephemeral=True)
        self.stop()

class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticket-system-setup", description="Setup the ticket system (admin only)")
    async def ticket_system_setup(self, interaction: discord.Interaction):
        if interaction.user.id != ADMIN_ID:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(CHANNEL_ASSISTANCE)
        if not channel:
            await interaction.response.send_message("Assistance channel not found.", ephemeral=True)
            return

        embed1 = discord.Embed(color=EMBED_COLOUR)
        embed1.set_image(url=EMBED1_IMAGE)

        embed2 = discord.Embed(
            title="📡 HRMC Assistance Hub",
            description="Welcome to the High Rock Military Corps Assistance Hub. We're here to help you with all inquiries too specific to ask in public channels. Should you be in need of help, open a ticket any time.",
            color=EMBED_COLOUR
        )
        embed2.add_field(
            name="<:HighRockMilitary:1376605942765977800> General Support",
            value="Not understanding something? Confused? Got a question too specific? No worries, feel free to open a general support ticket!",
            inline=True
        )
        embed2.add_field(
            name="<:HC:1343192841676914712> Management",
            value="Interested in speaking to a HC+ about a matter that cannot be handled in a general ticket? Open a management ticket.",
            inline=True
        )
        embed2.add_field(
            name="<:MIA:1364309116859715654> MIA",
            value="Appeals, and reports are now handled by MIA. Please head over there for such concerns.",
            inline=True
        )
        embed2.set_image(url=EMBED2_IMAGE)
        embed2.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)

        await channel.send(embeds=[embed1, embed2], view=TicketTypeView())
        await interaction.response.send_message("Ticket system setup complete.", ephemeral=True)

    @app_commands.command(name="ticket-add", description="Add a user to your ticket (civilians only)")
    @app_commands.describe(user="User to add")
    async def ticket_add(self, interaction: discord.Interaction, user: discord.Member):
        if not any(role.id == CIVILIAN_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        await interaction.channel.set_permissions(user, view_channel=True, send_messages=True, attach_files=True, embed_links=True)
        await interaction.response.send_message(f"{user.mention} has been added to the ticket.", ephemeral=True)

    @app_commands.command(name="ticket-remove", description="Remove a user from your ticket (civilians only)")
    @app_commands.describe(user="User to remove")
    async def ticket_remove(self, interaction: discord.Interaction, user: discord.Member):
        if not any(role.id == CIVILIAN_ROLE for role in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        await interaction.channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(f"{user.mention} has been removed from the ticket.", ephemeral=True)

async def setup(bot):