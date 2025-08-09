import discord
from discord import app_commands
from discord.ext import commands
import os
import traceback

DATA_FOLDER = "data/reviews"
LOG_FOLDER = "logs/reviews"
GUILD_ID = 1090386781609140860  # replace with your guild ID as int

class Review(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[Review Cog] Initializing...")
        os.makedirs(DATA_FOLDER, exist_ok=True)
        os.makedirs(LOG_FOLDER, exist_ok=True)
        self.init_db()
        print("[Review Cog] Initialization complete.")

    def init_db(self):
        # Your DB init code here, or just pass if none
        pass

    async def cog_load(self):
        print("[Review Cog] Loading cog and syncing commands...")
        try:
            guild = discord.Object(id=GUILD_ID)
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            print(f"[Review Cog] Synced {len(synced)} commands to guild {GUILD_ID}")
        except Exception as e:
            print(f"[Review Cog] Failed to sync commands:")
            traceback.print_exc()

    @app_commands.command(
        name="reviews",
        description="Show all reviews for a given user."
    )
    @app_commands.describe(user="The user to display reviews for")
    async def reviews(self, interaction: discord.Interaction, user: discord.User):
        print(f"[Review Command] Invoked by {interaction.user} for user {user}")
        # Example response, replace with your actual logic
        try:
            # Load reviews from database or file (placeholder)
            reviews_list = ["Great helper!", "Very friendly.", "Needs improvement."]

            # Create an embed to display reviews nicely
            embed = discord.Embed(
                title=f"Reviews for {user}",
                description="\n".join(f"- {review}" for review in reviews_list),
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            print("[Review Command] Response sent successfully.")
        except Exception as e:
            print(f"[Review Command] Error handling command:")
            traceback.print_exc()
            await interaction.response.send_message("An error occurred while fetching reviews.", ephemeral=True)

async def setup(bot: commands.Bot):
    print("[Review Cog] Setup starting...")
    await bot.add_cog(Review(bot))
    print("[Review Cog] Cog added.")
