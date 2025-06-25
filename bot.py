import discord
from discord.ext import commands
import asyncio
import os

from dotenv import load_dotenv

load_dotenv(".env")         # Load public config
load_dotenv(".env.token") 
APPLICATION_ID = int(os.getenv("APPLICATION_ID"))
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if TOKEN is None:
    raise ValueError("No DISCORD_BOT_TOKEN found in environment variables")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    application_id=APPLICATION_ID
)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="High Rock"))

    # sync slash commands once
    if not getattr(bot, "_synced", False):
        await bot.tree.sync()
        bot._synced = True
        print("⏳ Slash commands synced!")

from cogs.suggestion import SuggestionView
from cogs.about_us import RankInfoView
from cogs.Rules import RegulationsView
from cogs.ticket_system import TicketButtons

# Register persistent view for suggestion voting
bot.add_view(SuggestionView(suggestion_id=0))  # 0 is a dummy id, but registers the view
# Register persistent view for About Us rank info select menu
bot.add_view(RankInfoView())
# Register persistent view for Regulations select menu
bot.add_view(RegulationsView())
# Register persistent view for ticket buttons (required for persistent buttons after restart)
bot.add_view(TicketButtons(opener_id=0, ticket_type="general", opener=None))

async def main():
    async with bot:
        await bot.load_extension("cogs.welcome")
        await bot.load_extension("cogs.verification")
        await bot.load_extension("cogs.misc")
        await bot.load_extension("cogs.leveling")
        await bot.load_extension("cogs.economy")
        await bot.load_extension("cogs.say")
        await bot.load_extension("cogs.suggestion")
        await bot.load_extension("cogs.Rules")
        await bot.load_extension("cogs.about_us")
        await bot.load_extension("cogs.applications")
        await bot.load_extension("cogs.ticket_system")
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main()) #test posting
