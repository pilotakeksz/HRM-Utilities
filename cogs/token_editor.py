from discord.ext import commands

ALLOWED_USER_IDS = [840949634071658507]  # Replace with your Discord user ID(s)

class TokenEditor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="e")
    async def edit_token(self, ctx, *, line: str):
        if ctx.author.id not in ALLOWED_USER_IDS:
            await ctx.send("❌ You are not authorized to use this command.")
            return

        with open(".env", "w") as f:
            f.write(line.strip() + "\n")

        await ctx.send("✅ `.env` updated. Please restart the bot.")

async def setup(bot):
    await bot.add_cog(TokenEditor(bot))
