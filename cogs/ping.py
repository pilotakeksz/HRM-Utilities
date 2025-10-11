import discord
from discord.ext import commands, tasks

PING_USER_ID = 670646167448584192
PING_CHANNEL_ID = 123456789012345678  # Replace with your actual channel ID
PING_CHANNEL_MESSAGE = "https://tenor.com/view/borzoi-siren-dawg-with-the-light-on-him-sailorzoop-dog-gif-2844905554045249724"

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
                await user.send("""general squared""")
            except Exception:
                pass

        # Send message in the specified channel
        channel = self.bot.get_channel(PING_CHANNEL_ID)
        if channel:
            try:
                msg = await channel.send(PING_CHANNEL_MESSAGE)
                await msg.delete()
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(PingLoop(bot))