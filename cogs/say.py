import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import get

ALLOWED_ROLE_ID = 1329910230066401361
FOOTER_ICON = "https://images-ext-1.discordapp.net/external/_d7d0RmGwlFEwwKlYDfachyeC_skH7txYK5GzDan4ZI/https/cdn.discordapp.com/icons/1329908357812981882/fa763c9516fc5a9982b48c69c0a18e18.png"
FOOTER_TEXT = "High Rock Military Corps"
EMBED_COLOR = 0xd0b37b

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