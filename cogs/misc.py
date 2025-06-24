import discord
from discord.ext import commands

class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Check bot latency")
    async def ping(self, ctx: commands.Context):
        latency_ms = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! Latency: {latency_ms} ms")

async def setup(bot):
    await bot.add_cog(Misc(bot))
