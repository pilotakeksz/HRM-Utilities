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

LOGS_DIR = os.path.join(os.path.dirname(__file__), "../transcripts")
LOGS_DIR = os.path.abspath(LOGS_DIR)
os.makedirs(LOGS_DIR, exist_ok=True)

PERSIST_FILE = os.path.join(LOGS_DIR, "ticket_embed_id.txt")
DELETION_SCHEDULE_FILE = os.path.join(LOGS_DIR, "pending_ticket_deletions.txt")

def log_transcript(channel, messages):
    transcripts_dir = "transcripts"  # <-- changed from "logs" to "transcripts"
    os.makedirs(transcripts_dir, exist_ok=True)
    filename = os.path.join(transcripts_dir, f"transcript_{channel.id}_{int(datetime.datetime.utcnow().timestamp())}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        for msg in messages:
            time = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{time}] {msg.author} ({msg.author.id}): {msg.content}\n")
    return filename

# Add a log for ticket actions
def log_ticket_action(channel_id, action, user):
    log_file = os.path.join(LOGS_DIR, f"ticket_{channel_id}_actions.txt")
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {action} by {user} ({user.id})\n")

async def send_transcript_and_logs(channel, opener, guild):
    # Transcript
    messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
    transcript_path = log_transcript(channel, messages)
    html_transcript = generate_html_transcript(channel, messages)
    html_path = os.path.join("transcripts", f"transcript_{channel.id}_{int(datetime.datetime.utcnow().timestamp())}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_transcript)

    # Action log
    action_log_path = os.path.join(LOGS_DIR, f"ticket_{channel.id}_actions.txt")

    # DM transcript to opener (embed + .txt transcript file)
    try:
        summary_embed = discord.Embed(
            title="Your Ticket Transcript",
            description=f"Here is the transcript for your ticket **{channel.name}**.\n"
                        f"Opened: <t:{int(channel.created_at.timestamp())}:f>\n"
                        f"Closed: <t:{int(datetime.datetime.utcnow().timestamp())}:f>\n"
                        f"Messages: {len(messages)}",
            color=discord.Color.blue()
        )
        summary_embed.set_footer(text="Thank you for contacting support!")
        await opener.send(embed=summary_embed)
        await opener.send(file=discord.File(transcript_path))
    except Exception:
        pass

    # Send summary embed + transcript and action log to logging channel (embed on top, files below)
    log_channel = guild.get_channel(CHANNEL_TICKET_LOGS)
    if log_channel:
        summary_embed = discord.Embed(
            title="Ticket Closed",
            description=f"**Ticket:** {channel.mention} (`{channel.id}`)\n"
                        f"**Opened by:** {opener.mention} (`{opener.id}`)\n"
                        f"**Closed at:** <t:{int(datetime.datetime.utcnow().timestamp())}:f>\n"
                        f"**Messages:** {len(messages)}",
            color=discord.Color.blue()
        )
        summary_embed.set_footer(text="Transcript and action log attached.")
        files = [
            discord.File(transcript_path),
            discord.File(html_path, filename="transcript.html")
        ]
        if os.path.exists(action_log_path):
            files.append(discord.File(action_log_path))
        # Send embed first, then files as a followup message
        await log_channel.send(embed=summary_embed)
        await log_channel.send(files=files)
        await log_channel.send(f"Transcript and logs for closed ticket {channel.mention} ({channel.id}):",
            files=files
        )

class TicketTypeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="General Support", value="general", emoji="<:HighRockMilitary:1376605942765977800>"),
            discord.SelectOption(label="Management", value="management", emoji="<:HC:1343192841676914712>"),
            discord.SelectOption(label="MIA", value="mia", emoji="<:MIA:1364309116859715654>"),
        ]
        super().__init__(
            placeholder="Select ticket type...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_select"  # <-- Add this
        )

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
    ticket_name = f"📨-ticket-{user.name}".replace(" ", "-").lower()
    if ticket_type == "management":
        category_id = CATEGORY_MANAGEMENT
        overwrites[guild.get_role(HC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
    else:
        category_id = CATEGORY_GENERAL
        overwrites[guild.get_role(HC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
        overwrites[guild.get_role(MC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
    channel = await guild.create_text_channel(
        ticket_name,
        category=guild.get_channel(category_id),
        overwrites=overwrites,
        reason=f"Ticket opened by {user}"
    )

    # Log open
    log_ticket_action(channel.id, "OPEN", user)

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
        super().__init__(
            label="Claim",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id="claim_button"  # <-- Add this
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        hc_role = interaction.guild.get_role(HC_ROLE)
        ticket_handler_role = interaction.guild.get_role(TICKET_HANDLER_ROLE)
        # Allow both HC and ticket handler to claim
        if hc_role not in interaction.user.roles and ticket_handler_role not in interaction.user.roles:
            await interaction.response.send_message("Only HC or Ticket Handlers can claim this ticket.", ephemeral=True)
            return
        self.parent_view.claimed_by = interaction.user
        # Change permissions: only claimer can type, others can view
        await self.parent_view.channel.set_permissions(hc_role, send_messages=False)
        await self.parent_view.channel.set_permissions(ticket_handler_role, send_messages=False)
        await self.parent_view.channel.set_permissions(interaction.user, send_messages=True)
        await self.parent_view.channel.send(f"This ticket has been claimed by {interaction.user.mention}.")
        log_ticket_action(self.parent_view.channel.id, "CLAIM", interaction.user)
        # Change button to unclaim
        self.disabled = True
        self.parent_view.clear_items()
        self.parent_view.add_item(UnclaimButton(self.parent_view))
        self.parent_view.add_item(CloseButton(self.parent_view))
        await interaction.response.edit_message(view=self.parent_view)

class UnclaimButton(Button):
    def __init__(self, parent_view):
        super().__init__(
            label="Unclaim",
            style=discord.ButtonStyle.secondary,
            emoji="🟦",
            custom_id="unclaim_button"  # <-- Add this
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        hc_role = interaction.guild.get_role(HC_ROLE)
        ticket_handler_role = interaction.guild.get_role(TICKET_HANDLER_ROLE)
        if hc_role not in interaction.user.roles and ticket_handler_role not in interaction.user.roles:
            await interaction.response.send_message("Only HC or Ticket Handlers can unclaim this ticket.", ephemeral=True)
            return
        self.parent_view.claimed_by = None
        await self.parent_view.channel.set_permissions(hc_role, send_messages=True)
        await self.parent_view.channel.set_permissions(ticket_handler_role, send_messages=True)
        await self.parent_view.channel.send("This ticket is now unclaimed.")
        log_ticket_action(self.parent_view.channel.id, "UNCLAIM", interaction.user)
        # Change button back to claim
        self.disabled = True
        self.parent_view.clear_items()
        self.parent_view.add_item(ClaimButton(self.parent_view))
        self.parent_view.add_item(CloseButton(self.parent_view))
        await interaction.response.edit_message(view=self.parent_view)

class CloseButton(Button):
    def __init__(self, parent_view):
        super().__init__(
            label="Close",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id="close_button"  # <-- Add this
        )
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
        super().__init__(timeout=None)  # <-- Make persistent
        self.channel = channel
        self.opener = opener
        self.ticket_type = ticket_type

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, custom_id="confirm_close_button")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        # Archive
        await self.channel.edit(category=interaction.guild.get_channel(CATEGORY_ARCHIVED))
        # Only allow opener, HC, MC (if general), and ticket handler to view archived ticket
        overwrites = {
            self.channel.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.opener: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            self.channel.guild.get_role(HC_ROLE): discord.PermissionOverwrite(view_channel=True, send_messages=False),
            self.channel.guild.get_role(TICKET_HANDLER_ROLE): discord.PermissionOverwrite(view_channel=True, send_messages=False),
        }
        if self.ticket_type != "management":
            overwrites[self.channel.guild.get_role(MC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
        await self.channel.edit(overwrites=overwrites)
        await self.channel.send(embed=discord.Embed(
            description="This ticket is being archived. It will permanently be deleted in 15 minutes.",
            color=discord.Color.red()
        ))
        log_ticket_action(self.channel.id, "CLOSE", interaction.user)
        # Transcript and logs
        await send_transcript_and_logs(self.channel, self.opener, interaction.guild)
        # Schedule deletion
        delete_at = (datetime.datetime.utcnow() + datetime.timedelta(minutes=15)).timestamp()
        save_pending_deletion(self.channel.id, delete_at)
        asyncio.create_task(schedule_ticket_deletion(interaction.client, self.channel.id, delete_at))
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="cancel_close_button")
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Ticket close cancelled.", ephemeral=True)
        self.stop()

def save_pending_deletion(channel_id, delete_at):
    lines = []
    if os.path.exists(DELETION_SCHEDULE_FILE):
        with open(DELETION_SCHEDULE_FILE, "r") as f:
            lines = [line.strip() for line in f if line.strip()]
    # Remove any existing entry for this channel
    lines = [line for line in lines if not line.startswith(f"{channel_id}:")]
    lines.append(f"{channel_id}:{delete_at}")
    with open(DELETION_SCHEDULE_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")

def remove_pending_deletion(channel_id):
    if not os.path.exists(DELETION_SCHEDULE_FILE):
        return
    with open(DELETION_SCHEDULE_FILE, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    lines = [line for line in lines if not line.startswith(f"{channel_id}:")]
    with open(DELETION_SCHEDULE_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")

async def schedule_ticket_deletion(bot, channel_id, delete_at):
    now = datetime.datetime.utcnow().timestamp()
    wait_time = delete_at - now
    if wait_time > 0:
        await asyncio.sleep(wait_time)
    channel = bot.get_channel(int(channel_id))
    if channel:
        try:
            await channel.send("This ticket will be deleted in 20 seconds.")
            await asyncio.sleep(20)
            await channel.delete()
        except Exception:
            pass
    remove_pending_deletion(channel_id)

async def ensure_persistent_ticket_embed(bot):
    channel = bot.get_channel(CHANNEL_ASSISTANCE)
    if not channel:
        return
    embed_id = None
    if os.path.exists(PERSIST_FILE):
        with open(PERSIST_FILE, "r") as f:
            try:
                embed_id = int(f.read().strip())
            except Exception:
                embed_id = None
    message = None
    if embed_id:
        try:
            message = await channel.fetch_message(embed_id)
            # If message exists, do nothing (don't resend)
            return
        except Exception:
            message = None
    # If message doesn't exist, send it and store the ID
    embed1 = discord.Embed(color=EMBED_COLOUR)
    embed1.set_image(url=EMBED1_IMAGE)
    embed2 = discord.Embed(
        title="📡 HRMC Assistance Hub",
        description="Welcome to the High Rock Military Corps Assistance Hub. We're here to help you with all inquiries too specific to ask in public channels. Should you be in need of help, open a ticket any time.",
        color=EMBED_COLOUR
    )
    embed2.add_field(
        name=" General Support",
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
    sent = await channel.send(embeds=[embed1, embed2], view=TicketTypeView())
    with open(PERSIST_FILE, "w") as f:
        f.write(str(sent.id))

# On bot startup, resume pending deletions
async def resume_pending_deletions(bot):
    if not os.path.exists(DELETION_SCHEDULE_FILE):
        return
    with open(DELETION_SCHEDULE_FILE, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    for line in lines:
        if ":" in line:
            channel_id, delete_at = line.split(":", 1)
            try:
                asyncio.create_task(schedule_ticket_deletion(bot, int(channel_id), float(delete_at)))
            except Exception:
                continue

class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self._startup_embed())
        self.bot.loop.create_task(resume_pending_deletions(self.bot))
        # Only register views that do NOT require arguments
        self.bot.add_view(TicketTypeView())  # This is safe and persistent

    async def _startup_embed(self):
        await self.bot.wait_until_ready()
        await ensure_persistent_ticket_embed(self.bot)

    @commands.command(name="assistance")
    async def assistance_command(self, ctx):
        if ctx.author.id != ADMIN_ID:
            await ctx.send("You do not have permission to use this command.", delete_after=10)
            return

        channel = ctx.guild.get_channel(CHANNEL_ASSISTANCE)
        if not channel:
            await ctx.send("Assistance channel not found.", delete_after=10)
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

        sent = await channel.send(embeds=[embed1, embed2], view=TicketTypeView())
        with open(PERSIST_FILE, "w") as f:
            f.write(str(sent.id))
        await ctx.send("Assistance embed sent.", delete_after=10)

    # Keep /ticket-add and /ticket-remove as slash commands
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

def generate_html_transcript(channel, messages):
    html = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Ticket Transcript</title>",
        "<style>body{font-family:sans-serif;background:#222;color:#eee;} .msg{margin:10px 0;padding:10px;border-radius:8px;background:#333;} .author{font-weight:bold;} .avatar{width:32px;height:32px;vertical-align:middle;border-radius:50%;margin-right:8px;} .time{color:#aaa;font-size:0.9em;margin-left:8px;}</style>",
        "</head><body>",
        f"<h2>Transcript for #{channel.name}</h2>"
    ]
    for msg in messages:
        avatar_url = msg.author.display_avatar.url if hasattr(msg.author, "display_avatar") else msg.author.avatar_url
        time = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        content = discord.utils.escape_markdown(msg.content)
        html.append(
            f"<div class='msg'><img class='avatar' src='{avatar_url}'/>"
            f"<span class='author'>{msg.author}</span>"
            f"<span class='time'>{time}</span><br>{content}</div>"
        )
    html.append("</body></html>")
    return "\n".join(html)

async def setup(bot):
    await bot.add_cog(TicketSystem(bot))