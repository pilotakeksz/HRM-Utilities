import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = 1329908357812981882

class Training(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="trainingtest", description="Test command")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def trainingtest(self, interaction: discord.Interaction):
        await interaction.response.send_message("It works!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Training(bot))
    user = await bot.fetch_user(840949634071658507)
    await user.send("Minimal training cog loaded!")