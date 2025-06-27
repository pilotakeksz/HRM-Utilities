import discord
from discord.ext import commands, tasks
import datetime
import asyncio

ARCHIVE_CATEGORY_ID = 1367771350877470720  # Replace with your archive category ID

class DeleteArchiveCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.delete_task.start()

    def cog_unload(self):
        self.delete_task.cancel()

    @tasks.loop(minutes=1)
    async def delete_task(self):
        now = datetime.datetime.utcnow()
        # Run only at the exact half hour (minute == 0 or 30, and second == 0)
        if now.second != 0:
            return
        if now.minute not in (0, 30):
            return

        guilds = self.bot.guilds
        for guild in guilds:
            category = guild.get_channel(ARCHIVE_CATEGORY_ID)
            if not category or not isinstance(category, discord.CategoryChannel):
                continue
            for channel in list(category.channels):
                try:
                    await channel.delete(reason="Scheduled archive cleanup at half hour.")
                except Exception as e:
                    print(f"Failed to delete channel {channel.id}: {e}")

    @delete_task.before_loop
    async def before_delete_task(self):
        await self.bot.wait_until_ready()

async def setup(bot):
   await bot.add_cog(DeleteArchiveCog(bot))