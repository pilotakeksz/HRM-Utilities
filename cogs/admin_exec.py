import discord
from discord.ext import commands
import subprocess

class AdminExec(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Replace with your Discord user ID and secret key here
        self.authorized_user_id = 840949634071658507
        self.secret = "myVerySecretPassword"

    @commands.command(name="exec")
    async def exec_command(self, ctx, key: str, *, cmd: str):
        if ctx.author.id != self.authorized_user_id:
            await ctx.send("❌ Unauthorized user.")
            return
        if key != self.secret:
            await ctx.send("❌ Wrong key.")
            return

        try:
            output = subprocess.getoutput(cmd)
            if len(output) > 1900:
                output = output[:1900] + "\n[...truncated]"
            await ctx.send(f"```{output}```")
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")

def setup(bot):
    bot.add_cog(AdminExec(bot))
