import discord
from discord.ext import commands
from version_manager import get_current_version, get_version_info
import os
import json

class VersionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="version")
    async def version(self, ctx):
        """Display the current bot version with additional information."""
        version_num, version_string = get_current_version()
        
        # Try to get additional info from metadata
        version_info = {}
        meta_file = os.path.join("data", "version_meta.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    version_info = json.load(f)
            except Exception:
                pass
        
        embed = discord.Embed(
            title="Bot Version",
            description=f"Current version: **{version_string}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Version Number", value=str(version_num), inline=True)
        
        # Add git information if available (commit message only, no hash)
        if version_info.get("commit_message"):
            commit_msg = version_info['commit_message'][:100] + "..." if len(version_info['commit_message']) > 100 else version_info['commit_message']
            embed.add_field(name="Last Commit", value=commit_msg, inline=False)
        
        # Add last updated cogs if available
        if version_info.get("updated_cogs"):
            cogs_list = ", ".join(version_info['updated_cogs'])
            if len(cogs_list) > 100:
                cogs_list = cogs_list[:100] + "..."
            embed.add_field(name="Last Updated Cogs", value=cogs_list, inline=False)
        
        embed.set_footer(text="Made with love by Tuna 🐟")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(VersionCog(bot))
