from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands

class MiscCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        """Simple ping command to check bot responsiveness."""
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: {latency}ms",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="server_info", description="Get server information")
    async def server_info(self, interaction: discord.Interaction):
        """Display basic server information."""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Server Information: {guild.name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MiscCog(bot))
