import discord
from discord.ext import commands
from discord import app_commands

GUILD_ID = 1329908357812981882  # Replace with your guild ID here

class Review(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.synced = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self.synced:
            return
        guild = discord.Object(id=GUILD_ID)
        self.bot.tree.copy_global_to(guild=guild)
        synced = await self.bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to guild {GUILD_ID}")
        self.synced = True

    @app_commands.command(name="reviewtest", description="Test command from Review cog")
    async def reviewtest(self, interaction: discord.Interaction):
        await interaction.response.send_message("Review cog command works!")

async def setup(bot: commands.Bot):
    await bot.add_cog(Review(bot))
