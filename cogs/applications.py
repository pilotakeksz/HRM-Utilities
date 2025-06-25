
import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button

APPLICATIONS_ROLE_ID = 1329910241835352064
APPLICATIONS_CHANNEL_ID = int(os.getenv("APPLICATIONS_CHANNEL_ID", 1329910454059008101))
APPLICATIONS_COLOR = int(os.getenv("APPLICATIONS_COLOR", "0xd0b47b"), 16)
TRAINER_PING_ROLE_ID = 1329910397544960164

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

        channel = interaction.guild.get_channel(APPLICATIONS_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Applications channel not found.", ephemeral=True)
            return

        # Ping text if needed
        ping_text = f"<@&{TRAINER_PING_ROLE_ID}>\n" if ping else ""

        # Embed 1 (image)
        embed1 = discord.Embed(color=APPLICATIONS_COLOR)
        embed1.set_image(url="https://cdn.discordapp.com/attachments/1376647068092858509/1376933967386771546/applications.png?ex=685d5cb0&is=685c0b30&hm=1515149d32a78690a4e91e9d4879a9451c6f9fb0064d6aa651c256240a709ff5&")

        # Embed 2 (main info)
        embed2 = discord.Embed(
            description=(
                "Welcome to the High Rock Military Application Hub! Bellow you will find the application, and more info on the Military Personnel position you may apply for here at HRM. We wish you the best of luck, and hope to see you on our team!\n\n"
                "**Do you have a “blacklisted” role? Run `/verify` with @Bloxlink#6871 !**\n\n"
                "-# Bare in mind that any use of AI will result in a blacklist."
            ),
            color=APPLICATIONS_COLOR
        )

        # Application Status field
        if open:
            status = (
                "> <:yes:1358812809558753401> **OPEN** <:yes:1358812809558753401>\n"
                "> ⏰ **| Length: 15 Questions**\n"
                "> 📑 **| Reading Time: 1-2 days**\n"
                f"> **<:Member:1343945679390904330> | Trainer Availability: {trainer_availability.value}**"
            )
        else:
            status = (
                "> <:no:1358812780890947625> **CLOSED** <:no:1358812780890947625>\n"
                "> ⏰ **| Length: 15 Questions**\n"
                "> 📑 **| Reading Time: 1-2 days**\n"
                f"> **<:Member:1343945679390904330> | Trainer Availability: {trainer_availability.value}**"
            )
        embed2.add_field(name="Application Status", value=status, inline=False)

        view = ApplyButtonView()
        await channel.send(content=ping_text if ping else None, embed=embed1)
        await channel.send(embed=embed2, view=view)
        await interaction.response.send_message("Application embed sent.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Applications(bot))