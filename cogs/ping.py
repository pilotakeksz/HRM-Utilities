import discord
from discord.ext import commands, tasks

PING_USER_ID = 774973267089293323

class PingLoop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ping_task.start()

    def cog_unload(self):
        self.ping_task.cancel()

    @tasks.loop(seconds=5)
    async def ping_task(self):
        await self.bot.wait_until_ready()
        user = self.bot.get_user(PING_USER_ID)
        if not user:
            # If the user isn't cached, fetch them
            try:
                user = await self.bot.fetch_user(PING_USER_ID)
            except Exception:
                return
        
        if user:
            try:
                await user.send("ur coming back to hrm lil bro")
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(PingLoop(bot))