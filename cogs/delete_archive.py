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

    @tasks.loop(count=1)
    async def delete_task(self):
        await self.bot.wait_until_ready()
        while True:
            now = datetime.datetime.utcnow()
            # Calculate seconds until next half hour (00 or 30)
            if now.minute < 30:
                next_half = now.replace(minute=30, second=0, microsecond=0)
            else:
                next_half = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            wait_seconds = (next_half - now).total_seconds()
            await asyncio.sleep(wait_seconds)

            # Delete all channels in the archive category in all guilds
            for guild in self.bot.guilds:
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