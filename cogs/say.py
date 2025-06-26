import os
import datetime
import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import get

ALLOWED_ROLE_ID = 1329910230066401361
FOOTER_ICON = "https://images-ext-1.discordapp.net/external/_d7d0RmGwlFEwwKlYDfachyeC_skH7txYK5GzDan4ZI/https/cdn.discordapp.com/icons/1329908357812981882/fa763c9516fc5a9982b48c69c0a18e18.png"
FOOTER_TEXT = "High Rock Military Corps"
EMBED_COLOR = 0xd0b37b

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "say_command.log")

def log_say_command(user_id, channel_id, message, send_as_embed):
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"[{timestamp}] User: {user_id} | Channel: {channel_id} | Embed: {send_as_embed} | Message: {message}\n"
        )

class Say(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="say",
        description="Send a message as the bot to a channel (requires special role)."
    )
    @app_commands.describe(
        message="The message to send",
        channel="The channel to send the message to",
        send_as_embed="Send as an embed (true/false)"
    )
    async def say(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: discord.TextChannel,
        send_as_embed: bool = False
    ):
        # Permission check
        if not get(interaction.user.roles, id=ALLOWED_ROLE_ID):
            await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
            return

        # Log the command usage
        log_say_command(
            user_id=interaction.user.id,
            channel_id=channel.id,
            message=message,
            send_as_embed=send_as_embed
        )

        if send_as_embed:
            embed = discord.Embed(
                description=message,
                color=EMBED_COLOR
            )
            embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
            await channel.send(embed=embed)
        else:
            await channel.send(message)

        await interaction.response.send_message(
            f"Message sent to {channel.mention}.", ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Say(bot))