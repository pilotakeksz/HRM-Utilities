from discord.ext import commands

class TokenEditor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="e")
    async def edit_token(self, ctx, *, line: str):
        if not isinstance(ctx.channel, commands.dm.DMChannel):
            return

        with open(".env", "w") as f:
            f.write(line.strip() + "\n")

        await ctx.send("Updated.")

async def setup(bot):
    await bot.add_cog(TokenEditor(bot))
