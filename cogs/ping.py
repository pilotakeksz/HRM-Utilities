import discord
from discord.ext import commands, tasks

PING_USER_ID = 670646167448584192
PING_CHANNEL_ID = 1329910561697435669

class PingLoop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ping_task.start()

    def cog_unload(self):
        self.ping_task.cancel()

    @tasks.loop(seconds=5)
    async def ping_task(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(PING_CHANNEL_ID)
        if channel:
            try:
                msg = await channel.send(f"<@{PING_USER_ID}>")
                await msg.delete()
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(PingLoop(bot))