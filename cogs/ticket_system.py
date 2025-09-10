import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button, Modal, TextInput
import asyncio
import datetime
import logging

CIVILIAN_ROLE = int(os.getenv("CIVILIAN_ROLE"))
MC_ROLE = int(os.getenv("MC_ROLE"))
HC_ROLE = int(os.getenv("HC_ROLE"))
TICKET_HANDLER_ROLE = int(os.getenv("TICKET_HANDLER_ROLE"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CATEGORY_GENERAL = int(os.getenv("CATEGORY_GENERAL"))
CATEGORY_MANAGEMENT = int(os.getenv("CATEGORY_MANAGEMENT"))
CATEGORY_APPEAL = int(os.getenv("CATEGORY_APPEAL"))
CATEGORY_ARCHIVED = int(os.getenv("CATEGORY_ARCHIVED"))
CHANNEL_TICKET_LOGS = int(os.getenv("CHANNEL_TICKET_LOGS"))
CHANNEL_ASSISTANCE = int(os.getenv("CHANNEL_ASSISTANCE"))
EMBED_COLOUR = int(os.getenv("EMBED_COLOUR"), 16)
EMBED_FOOTER = "Maplecliff National Guard"
EMBED_ICON = "https://cdn.discordapp.com/emojis/1409463907294384169.webp?size=240"
EMBED1_IMAGE = os.getenv("EMBED1_IMAGE")
EMBED2_IMAGE = os.getenv("EMBED2_IMAGE")
MIA_REDIRECT = os.getenv("MIA_REDIRECT")

LOGS_DIR = os.path.join(os.path.dirname(__file__), "../transcripts")
LOGS_DIR = os.path.abspath(LOGS_DIR)
os.makedirs(LOGS_DIR, exist_ok=True)

PERSIST_FILE = os.path.join(LOGS_DIR, "ticket_embed_id.txt")
DELETION_SCHEDULE_FILE = os.path.join(LOGS_DIR, "pending_ticket_deletions.txt")

def log_transcript(channel, messages):
    transcripts_dir = "transcripts"
    os.makedirs(transcripts_dir, exist_ok=True)
    filename = os.path.join(transcripts_dir, f"transcript_{channel.id}_{int(datetime.datetime.utcnow().timestamp())}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        for msg in messages:
            time = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{time}] {msg.author} ({msg.author.id}): {msg.content}\n")
    return filename

async def send_transcript_and_logs(channel, opener, guild):
    # Transcript
    messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
    transcript_path = log_transcript(channel, messages)
    html_transcript = generate_html_transcript(channel, messages)
    html_path = os.path.join("transcripts", f"transcript_{channel.id}_{int(datetime.datetime.utcnow().timestamp())}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_transcript)

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

    # Send summary embed + transcript and html to logging channel (embed on top, files below)
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
        summary_embed.set_footer(text="Transcript attached.")
        files = [
            discord.File(transcript_path),
            discord.File(html_path, filename="transcript.html")
        ]
        await log_channel.send(embed=summary_embed)
        await log_channel.send(files=files)
        await log_channel.send(f"Transcript for closed ticket {channel.mention} ({channel.id}):", files=files)

class TicketTypeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="General Support", value="general", emoji="<:MCNG:1409463907294384169>"),
            discord.SelectOption(label="Management", value="management", emoji="<:HC:1343192841676914712>"),
            discord.SelectOption(label="IA", value="appeal", emoji="📝"),
        ]
        super().__init__(
            placeholder="Select ticket type...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "appeal":
            await interaction.response.send_modal(AppealTicketModal())
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
        channel = await create_ticket(interaction, "management", self.request.value)
        await interaction.response.send_message(
            f"Your ticket has been created: {channel.mention}", ephemeral=True
        )

class GeneralTicketModal(Modal, title="General Support Ticket"):
    request = TextInput(label="Request / Inquiry", style=discord.TextStyle.paragraph, required=True, max_length=1024)

    async def on_submit(self, interaction: discord.Interaction):
        channel = await create_ticket(interaction, "general", self.request.value)
        await interaction.response.send_message(
            f"Your ticket has been created: {channel.mention}", ephemeral=True
        )

class AppealTicketModal(Modal, title="Appeal Ticket"):
    request = TextInput(label="Appeal Details", style=discord.TextStyle.paragraph, required=True, max_length=1024)

    async def on_submit(self, interaction: discord.Interaction):
        channel = await create_ticket(interaction, "appeal", self.request.value)
        await interaction.response.send_message(
            f"Your IA ticket has been created: {channel.mention}", ephemeral=True
        )

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
    elif ticket_type == "appeal":
        category_id = CATEGORY_APPEAL
        overwrites[guild.get_role(HC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
        overwrites[guild.get_role(MC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
    else:
        category_id = CATEGORY_GENERAL
        overwrites[guild.get_role(HC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
        overwrites[guild.get_role(MC_ROLE)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)

    # --- FIX: Ensure category exists ---
    category = guild.get_channel(category_id)
    if not category or not isinstance(category, discord.CategoryChannel):
        await interaction.response.send_message(
            "Ticket category not found or is not a category channel. Please contact an administrator.",
            ephemeral=True
        )
        return None

    # Store opener ID in topic for accurate transcript delivery
    channel = await guild.create_text_channel(
        ticket_name,
        category=category,
        overwrites=overwrites,
        reason=f"Ticket opened by {user}",
        topic=f"Ticket opener: {user.id}"
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

    await channel.send(content=f"<@&{TICKET_HANDLER_ROLE}>", embeds=[embed1, embed2], view=TicketActionView())

    # Return the channel so the modal can redirect the user
    return channel

class TicketActionView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ClaimButton())
        self.add_item(CloseButton())

class ClaimButton(Button):
    def __init__(self):
        super().__init__(
            label="Claim",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id="claim_button"
        )

    async def callback(self, interaction: discord.Interaction):
        hc_role = interaction.guild.get_role(HC_ROLE)
        ticket_handler_role = interaction.guild.get_role(TICKET_HANDLER_ROLE)
        general_role = interaction.guild.get_role(1329910281903673344)
        opener_id = None
        if interaction.channel.topic and "Ticket opener:" in interaction.channel.topic:
            try:
                opener_id = int(interaction.channel.topic.split("Ticket opener:")[1].strip().split()[0])
            except Exception:
                opener_id = None
        opener = interaction.guild.get_member(opener_id) if opener_id else None

        # Only allow claim by HC or Ticket Handler
        if hc_role not in interaction.user.roles and ticket_handler_role not in interaction.user.roles:
            await interaction.response.send_message("Only HC or Ticket Handlers can claim this ticket.", ephemeral=True)
            return

        # Set permissions: only claimer and opener can send messages, staff can view
        overwrites = {
            interaction.channel.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
        }
        if opener:
            overwrites[opener] = discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
        # General tickets: both roles can view
        overwrites[general_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
        overwrites[ticket_handler_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
        overwrites[hc_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)

        await interaction.channel.edit(overwrites=overwrites)
        await interaction.channel.send(f"This ticket has been claimed by {interaction.user.mention}. Only you and the ticket opener can reply.")
        await interaction.response.edit_message(view=TicketActionView())

class CloseButton(Button):
    def __init__(self):
        super().__init__(
            label="Close",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id="close_button"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Confirm Close",
                description="Are you sure you want to close this ticket? This action cannot be undone.",
                color=discord.Color.red()
            ),
            view=ConfirmCloseView(),
            ephemeral=True
        )

class ConfirmCloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, custom_id="confirm_close_button")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        # Archive
        await interaction.channel.edit(category=interaction.guild.get_channel(CATEGORY_ARCHIVED))
        # Only allow opener, HC, MC (if general), and ticket handler to view archived ticket
        overwrites = {
            interaction.channel.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=False),
            interaction.channel.guild.get_role(HC_ROLE): discord.PermissionOverwrite(view_channel=True, send_messages=False),
            interaction.channel.guild.get_role(TICKET_HANDLER_ROLE): discord.PermissionOverwrite(view_channel=True, send_messages=False),
        }
        await interaction.channel.edit(overwrites=overwrites)

        # Find the opener from the channel topic (robust against message order)
        opener_id = None
        if interaction.channel.topic and "Ticket opener:" in interaction.channel.topic:
            try:
                opener_id = int(interaction.channel.topic.split("Ticket opener:")[1].strip().split()[0])
            except Exception:
                opener_id = None

        opener = None
        if opener_id:
            opener = interaction.guild.get_member(opener_id) or await interaction.guild.fetch_member(opener_id)
        else:
            # fallback to old logic
            messages = [msg async for msg in interaction.channel.history(limit=None, oldest_first=True)]
            for msg in messages:
                if not msg.author.bot:
                    opener = msg.author
                    break
            if opener is None:
                opener = interaction.user

        # Calculate next exact half hour in UTC
        now = datetime.datetime.utcnow()
        if now.minute < 30:
            next_half_hour = now.replace(minute=30, second=0, microsecond=0)
        else:
            # Move to next hour
            next_half_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        delete_at = next_half_hour.timestamp()
        time_str = next_half_hour.strftime('%H:%M UTC')

        await interaction.channel.send(embed=discord.Embed(
            description=f"This ticket is being archived. It will be permanently deleted at **{time_str}**.",
            color=discord.Color.red()
        ))
        # Transcript and logs
        await send_transcript_and_logs(interaction.channel, opener, interaction.guild)
        # Schedule deletion
        save_pending_deletion(interaction.channel.id, delete_at)
        interaction.client.loop.create_task(schedule_ticket_deletion(interaction.client, interaction.channel.id, delete_at))
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
    logging.info(f"[TicketSystem] Scheduling deletion for channel {channel_id} in {wait_time:.2f} seconds.")
    if wait_time > 0:
        await asyncio.sleep(wait_time)
    # Try to get the channel from cache
    channel = bot.get_channel(int(channel_id))
    if not channel:
        # Try to fetch the channel from API
        try:
            channel = await bot.fetch_channel(int(channel_id))
            logging.info(f"[TicketSystem] Successfully fetched channel {channel_id} from API.")
        except Exception as e:
            logging.error(f"[TicketSystem] Could not fetch channel {channel_id}: {e}")
            remove_pending_deletion(channel_id)
            return
    if channel:
        try:
            await channel.send("This ticket will be deleted in 20 seconds.")
            await asyncio.sleep(20)
            await channel.delete()
            logging.info(f"[TicketSystem] Deleted ticket channel {channel_id}.")
        except discord.Forbidden:
            logging.error(f"[TicketSystem] Missing permissions to delete channel {channel_id}.")
        except Exception as e:
            logging.error(f"[TicketSystem] Failed to delete ticket channel {channel_id}: {e}")
    else:
        logging.error(f"[TicketSystem] Channel {channel_id} not found for deletion.")
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
        title="📡 MCNG Assistance Hub",
        description="Welcome to the Maplecliff National Guard Assistance Hub. We're here to help you with all inquiries too specific to ask in public channels. Should you be in need of help, open a ticket any time.",
        color=EMBED_COLOUR
    )
    embed2.add_field(
        name="<:MCNG:1409463907294384169> General Support",
        value="Not understanding something? Confused? Got a question too specific? No worries, feel free to open a general support ticket!",
        inline=True
    )
    embed2.add_field(
        name="<:HC:1343192841676914712> Management",
        value="Interested in speaking to a JCO+ about a matter that cannot be handled in a general ticket? Open a management ticket.",
        inline=True
    )
    embed2.add_field(
        name="📝 IA",
        value="Want to appeal a punishment or report a personnel member? Open an IA ticket and our team will review your case promptly.",
        inline=True
    )
    embed2.set_image(url=EMBED2_IMAGE)
    embed2.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)
    sent = await channel.send(embeds=[embed1, embed2], view=TicketTypeView())
    with open(PERSIST_FILE, "w") as f:
        f.write(str(sent.id))

async def resume_pending_deletions(bot):
    if not os.path.exists(DELETION_SCHEDULE_FILE):
        return
    with open(DELETION_SCHEDULE_FILE, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    for line in lines:
        if ":" in line:
            channel_id, delete_at = line.split(":", 1)
            try:
                bot.loop.create_task(schedule_ticket_deletion(bot, int(channel_id), float(delete_at)))
            except Exception:
                continue

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

class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self._startup_embed())
        self.bot.loop.create_task(resume_pending_deletions(self.bot))
        self.bot.add_view(TicketTypeView())
        self.bot.add_view(TicketActionView())

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
            title="📡 MCNG Assistance Hub",
            description="Welcome to the Maplecliff National Guard Assistance Hub. We're here to help you with all inquiries too specific to ask in public channels. Should you be in need of help, open a ticket any time.",
            color=EMBED_COLOUR
        )
        embed2.add_field(
            name="<:MCNG:1409463907294384169> General Support",
            value="Not understanding something? Confused? Got a question too specific? No worries, feel free to open a general support ticket!",
            inline=True
        )
        embed2.add_field(
            name="<:HC:1343192841676914712> Management",
            value="Interested in speaking to a JCO+ about a matter that cannot be handled in a general ticket? Open a management ticket.",
            inline=True
        )
        embed2.add_field(
            name="📝 IA",
            value="Want to appeal a punishment or report a personnel member? Open an IA ticket and our team will review your case promptly.",
            inline=True
        )
        embed2.set_image(url=EMBED2_IMAGE)
        embed2.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)

        sent = await channel.send(embeds=[embed1, embed2], view=TicketTypeView())
        with open(PERSIST_FILE, "w") as f:
            f.write(str(sent.id))
        await ctx.send("Assistance embed sent.", delete_after=10)

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

    @commands.command(name="force_delete_ticket")
    @commands.has_permissions(administrator=True)
    async def force_delete_ticket(self, ctx):
        try:
            await ctx.channel.delete()
        except Exception as e:
            await ctx.send(f"Failed to delete: {e}", delete_after=10)

async def setup(bot):
    await bot.add_cog(TicketSystem(bot))