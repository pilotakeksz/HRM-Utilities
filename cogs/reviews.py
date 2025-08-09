import os
import datetime
import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import get

# === CONFIG ===
GUILD_ID = 1329908357812981882  # Your testing server's guild ID
ALLOWED_ROLE_ID = 1329910230066401361  # Replace with your allowed role ID

FOOTER_ICON = "https://images-ext-1.discordapp.net/external/_d7d0RmGwlFEwwKlYDfachyeC_skH7txYK5GzDan4ZI/https/cdn.discordapp.com/icons/1329908357812981882/fa763c9516fc5a9982b48c69c0a18e18.png"
FOOTER_TEXT = "High Rock Military Corps"
EMBED_COLOR = 0xd0b37b

LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, "reviews_command.log")


def log_review(user_id, member_id, rating, reason):
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"[{timestamp}] User: {user_id} reviewed Member: {member_id} | Rating: {rating} | Reason: {reason}\n"
        )


class Reviews(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[Reviews Cog] Initialized")

    async def cog_load(self):
        guild = discord.Object(id=GUILD_ID)
        self.bot.tree.copy_global_to(guild=guild)
        synced = await self.bot.tree.sync(guild=guild)
        print(f"[Reviews Cog] Synced {len(synced)} commands to guild {GUILD_ID}")

    @app_commands.command(
        name="review",
        description="Leave a review for someone with the allowed role."
    )
    @app_commands.describe(
        member="Member to review",
        rating="Rating from 1 to 5",
        reason="Reason for the review"
    )
    async def review(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        rating: int,
        reason: str,
    ):
        print(f"[DEBUG] /review called by {interaction.user} for {member} rating {rating}")

        # Permission check
        if not get(interaction.user.roles, id=ALLOWED_ROLE_ID):
            await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
            print(f"[DEBUG] User {interaction.user} lacks role {ALLOWED_ROLE_ID}")
            return

        if rating < 1 or rating > 5:
            await interaction.response.send_message(
                "Rating must be between 1 and 5.", ephemeral=True
            )
            print(f"[DEBUG] Invalid rating {rating} by user {interaction.user}")
            return

        # Log the review
        log_review(
            user_id=interaction.user.id,
            member_id=member.id,
            rating=rating,
            reason=reason
        )
        print(f"[DEBUG] Review logged")

        # Create embed for the review
        embed = discord.Embed(
            title=f"Review for {member.display_name}",
            description=reason,
            color=EMBED_COLOR,
            timestamp=datetime.datetime.utcnow(),
        )
        embed.add_field(name="Rating", value=f"{rating}/5", inline=True)
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

        # Send confirmation privately
        await interaction.response.send_message(
            f"Review submitted for {member.mention}.", ephemeral=True
        )

        # Send the embed in the channel where the command was invoked
        await interaction.channel.send(embed=embed)

    @app_commands.command(
        name="reviews-list",
        description="List recent reviews (example placeholder)."
    )
    async def reviews_list(self, interaction: discord.Interaction):
        print(f"[DEBUG] /reviews-list called by {interaction.user}")
        await interaction.response.send_message("This is a placeholder for reviews listing.", ephemeral=True)

#eeeeeee
async def setup(bot: commands.Bot):
    await bot.add_cog(Reviews(bot))
