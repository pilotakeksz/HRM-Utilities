import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button

APPLICATIONS_ROLE_ID = 1329910397544960164
APPLICATIONS_CHANNEL_ID = int(os.getenv("APPLICATIONS_CHANNEL_ID", 1329910454059008101))
EMBED_COLOUR = int(os.getenv("EMBED_COLOUR", "0xd0b47b"), 16)
TRAINER_PING_ROLE_ID = 1329910397544960164

FOOTER_TEXT = "High Rock Military Corps"
FOOTER_ICON = "https://images-ext-1.discordapp.net/external/_d7d0RmGwlFEwwKlYDfachyeC_skH7txYK5GzDan4ZI/https/cdn.discordapp.com/icons/1329908357812981882/fa763c9516fc5a9982b48c69c0a18e18.png"
BOTTOM_IMAGE = "https://cdn.discordapp.com/attachments/1409252771978280973/1409308813835894875/bottom.png?ex=68ace89c&is=68ab971c&hm=c73c5e2a743578a77cbe94f2c9aefa25b27ca7165b182bdc6659af5d72d07274&"

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "applications_command.log")

def log_application_command(user_id, open_status, trainer_availability, ping):
    import datetime
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"[{timestamp}] User: {user_id} | Open: {open_status} | Trainer Availability: {trainer_availability} | Ping: {ping}\n"
        )

class ApplyButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            Button(
                label="Apply today!",
                style=discord.ButtonStyle.link,
                url="https://melonly.xyz/forms/7286780001045712896",
                emoji="<:edit_message:1343948876599787602>"
            )
        )

class Applications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="send-application", description="Send the application embed (managers only)")
    @app_commands.describe(
        open="Is the application open?",
        trainer_availability="Trainer availability (Low, Medium, High)",
        ping="Ping the trainer role?"
    )
    @app_commands.choices(trainer_availability=[
        app_commands.Choice(name="Low", value="Low"),
        app_commands.Choice(name="Medium", value="Medium"),
        app_commands.Choice(name="High", value="High"),
    ])
    async def send_application(
        self,
        interaction: discord.Interaction,
        open: bool,
        trainer_availability: app_commands.Choice[str],
        ping: bool = False
    ):
        # Permission check
        if not any(role.id == APPLICATIONS_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return

        # Log the command usage
        log_application_command(
            user_id=interaction.user.id,
            open_status=open,
            trainer_availability=trainer_availability.value,
            ping=ping
        )

        channel = interaction.guild.get_channel(APPLICATIONS_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Applications channel not found.", ephemeral=True)
            return

        # Ping text if needed
        ping_text = f"<@&{TRAINER_PING_ROLE_ID}>\n" if ping else ""

        # Embed 1 (image)
        embed1 = discord.Embed(color=EMBED_COLOUR)
        embed1.set_image(url="https://media.discordapp.net/attachments/1409252771978280973/1409314341764861993/APPLICATIONS.png?ex=68acedc2&is=68ab9c42&hm=526afa60758bbd9e8ea32521386df0c0ce0d20f10ce50a78a223dc6aa07f95be&=&format=webp&quality=lossless&width=2576&height=862")

        # Embed 2 (main info)
        embed2 = discord.Embed(
            description=(
                "Welcome to the High Rock Military Application Hub! Bellow you will find the application, and more info on the Military Personnel position you may apply for here at HRM. We wish you the best of luck, and hope to see you on our team!\n\n"
                "**Do you have a “blacklisted” role? Run `/verify` with <@426537812993638400> !**\n\n"
                "-# Bare in mind that any use of AI will result in a blacklist."
            ),
            color=EMBED_COLOUR
        )

        # Application Status field (formatted as requested)
        if open:
            status = (
                "> <:yes:1358812809558753401> **OPEN** <:yes:1358812809558753401>\n"
                "> ⏰ **| Length: 15 Questions**\n"
                f"> <:Member:1343945679390904330> **| Trainer Availability: {trainer_availability.value}**"
            )
        else:
            status = (
                "> <:no:1358812780890947625> **CLOSED** <:no:1358812780890947625>\n"
                "> ⏰ **| Length: 15 Questions**\n"
                f"> <:Member:1343945679390904330> **| Trainer Availability: {trainer_availability.value}**"
            )

        embed2.add_field(
            name="Application Status",
            value=status,
            inline=False
        )
        embed2.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
        embed2.set_image(url=BOTTOM_IMAGE)

        # Send message
        await channel.send(
            content=ping_text,
            embeds=[embed1, embed2],
            view=ApplyButtonView()
        )

        await interaction.response.send_message("Application embed sent!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Applications(bot))