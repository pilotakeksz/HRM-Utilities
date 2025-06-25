import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction, SelectOption, ButtonStyle
import os
import datetime
import asyncio

# --- CONFIGURATION ---
CIVILIAN_ROLE = 1329910391840702515
MC_ROLE = 1329910285594525886
HC_ROLE = 1329910265264869387
TICKET_HANDLER_ROLE = 1329910341219389440
ADMIN_ID = 840949634071658507

CATEGORY_GENERAL = 1330504054744416308
CATEGORY_MANAGEMENT = 1340667032835723285
CATEGORY_ARCHIVED = 1367771350877470720

CHANNEL_TICKET_LOGS = 1331665561372852275
CHANNEL_ASSISTANCE = 1329910457409994772

EMBED_COLOUR = 0xd0b47b
EMBED_FOOTER = "High Rock Military Corps"
EMBED_ICON = "https://images-ext-1.discordapp.net/external/88RDdZ0JKsH7btZpsxKfyhbsbyHLz4hF2VUTFdaLXSA/https/images-ext-1.discordapp.net/external/_d7d0RmGwlFEwwKlYDfachyeC_skH7txYK5GzDan4ZI/https/cdn.discordapp.com/icons/1329908357812981882/fa763c9516fc5a9982b48c69c0a18e18.png"
EMBED1_IMAGE = "https://cdn.discordapp.com/attachments/1376647068092858509/1376933977125818469/assistance.png?ex=685d5cb2&is=685c0b32&hm=58fd22c756178ca6fc40c446cd68b5dcc0408777675394c5a324592d746ea05e&"
EMBED2_IMAGE = "https://cdn.discordapp.com/attachments/1376647068092858509/1376648782359433316/bottom.png?ex=685cfbd6&is=685baa56&hm=8e024541f2cdf6bc41b83e1ab03f3da441b653dc98fa03f5c58aa2ccee0e3ad4&"
MIA_REDIRECT = "https://discord.gg/xRashKPAKt"

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# --- TICKET TYPES ---
class TicketType:
    GENERAL = "general"
    MANAGEMENT = "management"
    MIA = "mia"

# --- SELECT MENU ---
class TicketSelect(ui.Select):
    def __init__(self):
        options = [
            SelectOption(label="General Support", value=TicketType.GENERAL, emoji="<:HighRockMilitary:1376605942765977800>"),
            SelectOption(label="Management", value=TicketType.MANAGEMENT, emoji="<:HC:1343192841676914712>"),
            SelectOption(label="MIA", value=TicketType.MIA, emoji="<:MIA:1364309116859715654>")
        ]
        super().__init__(placeholder="Choose ticket type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: Interaction):
        if self.values[0] == TicketType.MIA:
            await interaction.response.send_message(
                f"Appeals and reports are now handled by MIA. Please head over there: {MIA_REDIRECT}",
                ephemeral=True
            )
            return
        await interaction.response.send_modal(TicketModal(self.values[0]))

# --- TICKET MODAL ---
class TicketModal(ui.Modal, title="Open a Ticket"):
    concern = ui.TextInput(label="Concern / Inquiry", style=discord.TextStyle.paragraph, required=True, max_length=500)
    def __init__(self, ticket_type):
        super().__init__()
        self.ticket_type = ticket_type

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        user = interaction.user
        guild = interaction.guild

        # Channel name and category
        if self.ticket_type == TicketType.GENERAL:
            cat_id = CATEGORY_GENERAL
            channel_name = f"general-ticket-{user.name}".replace(" ", "-").lower()
            allowed_roles = [MC_ROLE, HC_ROLE]
        elif self.ticket_type == TicketType.MANAGEMENT:
            cat_id = CATEGORY_MANAGEMENT
            channel_name = f"management-ticket-{user.name}".replace(" ", "-").lower()
            allowed_roles = [HC_ROLE]
        else:
            await interaction.followup.send("Invalid ticket type.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.get_role(TICKET_HANDLER_ROLE): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for role_id in allowed_roles:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel = await guild.create_text_channel(
            channel_name,
            category=guild.get_channel(cat_id),
            overwrites=overwrites,
            reason=f"Ticket opened by {user} ({user.id})"
        )

        # Log ticket creation
        log_channel = guild.get_channel(CHANNEL_TICKET_LOGS)
        now = discord.utils.utcnow()
        log_msg = (
            f"Ticket opened: {channel.mention}\n"
            f"Type: {self.ticket_type}\n"
            f"Opener: {user.mention} ({user.id})\n"
            f"Reason: {self.concern.value}\n"
            f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        if log_channel:
            await log_channel.send(log_msg)

        # Ping ticket handlers in the ticket channel (not in embed)
        await channel.send(f"{guild.get_role(TICKET_HANDLER_ROLE).mention}")

        # Send embeds in ticket channel
        embed1 = discord.Embed(colour=EMBED_COLOUR)
        embed1.set_image(url=EMBED1_IMAGE)

        embed2 = discord.Embed(
            description=(
                "Our personnel will be with you shortly. Please do not ping them unnecessarily.\n\n"
                "In the mean time, please add details your initial inquiry.\n\n"
                f"**Request / Inquiry:**\n\"{self.concern.value}\""
            ),
            colour=EMBED_COLOUR
        )
        embed2.set_image(url=EMBED2_IMAGE)
        embed2.set_footer(text=EMBED_FOOTER, icon_url=EMBED_ICON)

        view = TicketButtons(opener_id=user.id, ticket_type=self.ticket_type, opener=user)
        await channel.send(embeds=[embed1, embed2], view=view)

        await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)

# --- BUTTONS VIEW ---
class TicketButtons(ui.View):
    def __init__(self, opener_id, ticket_type, opener):
        super().__init__(timeout=None)
        self.opener_id = opener_id
        self.ticket_type = ticket_type
        self.claimed_by = None
        self.opener = opener

    @ui.button(label="Claim", style=ButtonStyle.green, custom_id="ticket_claim")
    async def claim(self, interaction: Interaction, button: ui.Button):
        # Only MC and HC can claim
        if not any(role.id in [MC_ROLE, HC_ROLE] for role in interaction.user.roles):
            await interaction.response.send_message("Only MC and HC can claim tickets.", ephemeral=True)
            return
        if self.claimed_by:
            await interaction.response.send_message(f"Already claimed by <@{self.claimed_by}>.", ephemeral=True)
            return
        self.claimed_by = interaction.user.id
        channel = interaction.channel
        guild = interaction.guild
        handler_role = guild.get_role(TICKET_HANDLER_ROLE)
        # Only claimer can send messages, others read only
        for member in channel.members:
            if handler_role in member.roles:
                overwrite = channel.overwrites_for(member)
                if member.id == self.claimed_by:
                    overwrite.send_messages = True
                else:
                    overwrite.send_messages = False
                await channel.set_permissions(member, overwrite=overwrite)
        await interaction.response.send_message(f"Ticket claimed by {interaction.user.mention}. You now have exclusive write access as a handler.", ephemeral=False)
        await channel.send(f"{interaction.user.mention} has claimed this ticket and will assist you shortly.")

        # Log claim
        log_channel = guild.get_channel(CHANNEL_TICKET_LOGS)
        now = discord.utils.utcnow()
        log_msg = (
            f"Ticket claimed: {channel.mention}\n"
            f"Claimed by: {interaction.user.mention} ({interaction.user.id})\n"
            f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        if log_channel:
            await log_channel.send(log_msg)

    @ui.button(label="Close", style=ButtonStyle.red, custom_id="ticket_close")
    async def close(self, interaction: Interaction, button: ui.Button):
        confirm_view = ConfirmCloseView(self, self.opener)
        await interaction.channel.send(
            f"{interaction.user.mention} Are you sure you want to close this ticket? Click the button below to confirm.",
            view=confirm_view
        )
        await interaction.response.send_message("Confirmation sent in channel.", ephemeral=True)

class ConfirmCloseView(ui.View):
    def __init__(self, ticket_view, opener):
        super().__init__(timeout=60)
        self.ticket_view = ticket_view
        self.opener = opener

    @ui.button(label="Confirm Close", style=ButtonStyle.red)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        channel = interaction.channel
        guild = interaction.guild
        await channel.send("Archiving this ticket and restricting permissions. The channel will be deleted in 15 minutes.")
        await channel.edit(category=guild.get_channel(CATEGORY_ARCHIVED))
        for member in channel.members:
            await channel.set_permissions(member, send_messages=False, read_message_history=True, view_channel=True)
        await interaction.response.send_message("Ticket archived. This channel will be deleted in 15 minutes.", ephemeral=True)
        transcript_path = await save_transcript(channel)
        log_channel = guild.get_channel(CHANNEL_TICKET_LOGS)
        now = discord.utils.utcnow()
        log_msg = (
            f"Ticket closed: {channel.mention}\n"
            f"Closed by: {interaction.user.mention} ({interaction.user.id})\n"
            f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Transcript attached."
        )
        if log_channel and transcript_path:
            with open(transcript_path, "rb") as f:
                await log_channel.send(log_msg, file=discord.File(f, filename=os.path.basename(transcript_path)))
        if self.opener:
            try:
                if transcript_path:
                    with open(transcript_path, "rb") as f:
                        await self.opener.send(
                            "Your ticket has been closed. Here is the transcript:",
                            file=discord.File(f, filename=os.path.basename(transcript_path))
                        )
            except Exception:
                pass
        # Wait 15 minutes then delete the channel
        await asyncio.sleep(900)
        try:
            await channel.send("Deleting this ticket channel now. Thank you for contacting support!")
        except Exception:
            pass
        try:
            await channel.delete()
        except Exception:
            pass

# --- TRANSCRIPT ---
async def save_transcript(channel):
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        time = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = f"{msg.author} ({msg.author.id})"
        content = msg.content
        messages.append(f"[{time}] {author}: {content}")
    filename = os.path.join(LOGS_DIR, f"{channel.name}_{channel.id}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(messages))
    return filename

# --- MAIN COG ---
class TicketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticket-system-setup", description="Setup the ticket system (admin only)")
    async def ticket_system_setup(self, interaction: Interaction):
        if interaction.user.id != ADMIN_ID:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        embed1 = discord.Embed(colour=EMBED_COLOUR)
        embed1.set_image(url=EMBED1_IMAGE)
        embed2 = discord.Embed(
            title="🛰️ Assistance",
            description=(
                "Welcome to the HRMC Assistance Hub. We're here to help with all inquiries too specific for public channels. "
                "Should you be in need of help, open a ticket any time."
            ),
            colour=EMBED_COLOUR
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

        view = ui.View()
        view.add_item(TicketSelect())

        channel = interaction.guild.get_channel(CHANNEL_ASSISTANCE)
        await channel.send(embed=embed1)
        await channel.send(embed=embed2, view=view)
        await interaction.response.send_message("Ticket system setup complete.", ephemeral=True)

    @app_commands.command(name="ticket-add", description="Add a user to a ticket (MC/HC only)")
    @app_commands.describe(user="User to add")
    async def ticket_add(self, interaction: Interaction, user: discord.Member):
        if not any(role.id in [MC_ROLE, HC_ROLE] for role in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        channel = interaction.channel
        await channel.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(f"{user.mention} added to the ticket.", ephemeral=False)

    @app_commands.command(name="ticket-remove", description="Remove a user from a ticket (MC/HC only)")
    @app_commands.describe(user="User to remove")
    async def ticket_remove(self, interaction: Interaction, user: discord.Member):
        if not any(role.id in [MC_ROLE, HC_ROLE] for role in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        channel = interaction.channel
        await channel.set_permissions(user, overwrite=None)
        await interaction.response.send_message(f"{user.mention} removed from the ticket.", ephemeral=False)

async def setup(bot: commands.Bot):
    bot.add_view(TicketButtons(opener_id=0, ticket_type="general", opener=None))  # Register persistent view for ticket buttons
    await bot.add_cog(TicketSystem(bot))