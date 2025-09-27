import discord
from discord.ext import commands
from version_manager import get_current_version

class VersionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="version")
    async def version(self, ctx):
        """Display the current bot version."""
        version_num, version_string = get_current_version()
        
        embed = discord.Embed(
            title="Bot Version",
            description=f"Current version: **{version_string}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Version Number", value=str(version_num), inline=True)
        embed.set_footer(text="Version increments on each bot restart")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(VersionCog(bot))
