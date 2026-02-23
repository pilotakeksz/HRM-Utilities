# These are test commands that will either get removed or get added.

import discord
from discord.ext import commands

class JoinVC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="join")
    async def join(self, ctx, *, channel: discord.VoiceChannel):
        """Joins a voice channel DOES NOTHING OTHER THAN JOIN THE VC."""

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()
        await ctx.send(content="Joined voice channel.")

async def setup(bot):
    await bot.add_cog(JoinVC(bot))