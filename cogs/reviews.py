import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import sqlite3
import os

# === CONFIG ===
ALLOWED_ROLE_ID = 1329910329701830686
ADMIN_ROLE_ID = 1355842403134603275
REVIEW_CHANNEL_ID = 1329910477404242083
LOG_CHANNEL_ID = 1343686645815181382
GUILD_ID = 1329908357812981882  # Your server ID for instant sync
BOTTOM_IMAGE_URL = "https://cdn.discordapp.com/attachments/1376647068092858509/1376934109665824828/bottom.png?ex=68980791&is=6896b611&hm=2254fc59f1199d20999cd7f212ade2cc77091ee7078d5054312897c78b0148e0&"

DATA_FOLDER = "data"
LOG_FOLDER = "logs"
DB_PATH = os.path.join(DATA_FOLDER, "reviews.db")
LOG_FILE = os.path.join(LOG_FOLDER, "actions.txt")


class Review(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        os.makedirs(DATA_FOLDER, exist_ok=True)
        os.makedirs(LOG_FOLDER, exist_ok=True)
        self.init_db()
        self.synced = False

    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER,
                reviewer_id INTEGER,
                rating INTEGER,
                reason TEXT,
                message_id INTEGER,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()

    def log_action(self, action: str):
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        log_entry = f"[{timestamp}] {action}\n"

        # Write to file log
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)

        # Send embed log to Discord log channel (fire and forget)
        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="Review System Log",
                description=action,
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            self.bot.loop.create_task(log_channel.send(embed=embed))

    def get_colour_for_rating(self, rating: int) -> discord.Color:
        if rating <= 2:
            return discord.Color.red()
        elif rating == 3:
            return discord.Color.orange()
        elif rating == 4:
            return discord.Color.gold()
        else:
            return discord.Color.green()

    def rating_to_stars(self, rating: int) -> str:
        return "⭐" * rating + "☆" * (5 - rating)

    async def cog_load(self):
        # We do not sync here to avoid _MissingSentinel error
        pass

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.synced:
            guild = discord.Object(id=GUILD_ID)
            self.bot.tree.copy_global_to(guild=guild)
            await self.bot.tree.sync(guild=guild)
            print(f"[Review Cog] Slash commands synced to guild {GUILD_ID}")
            self.synced = True

    @app_commands.command(name="review", description="Leave a review for someone with the allowed role.")
    @app_commands.describe(member="Member to review", rating="Rating from 1 to 5 stars", reason="Reason for the review")
    async def review(self, interaction: discord.Interaction, member: discord.Member, rating: int, reason: str):
        if not interaction.guild:
            return await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        if not any(role.id == ALLOWED_ROLE_ID for role in member.roles):
            return await interaction.response.send_message("That user cannot be reviewed.", ephemeral=True)
        if not (1 <= rating <= 5):
            return await interaction.response.send_message("Rating must be between 1 and 5.", ephemeral=True)
        if not reason.strip():
            return await interaction.response.send_message("You must provide a reason for the review.", ephemeral=True)

        embed = discord.Embed(
            title=f"Review for {member.display_name}",
            description=f"**Rating:** {self.rating_to_stars(rating)}\n\n**Reason:** {reason}",
            color=self.get_colour_for_rating(rating),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_image(url=BOTTOM_IMAGE_URL)
        embed.add_field(name="Reviewed by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Date", value=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), inline=True)

        review_channel = self.bot.get_channel(REVIEW_CHANNEL_ID)
        if not review_channel:
            return await interaction.response.send_message("❌ Could not find the review channel.", ephemeral=True)

        msg = await review_channel.send(embed=embed)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO reviews (target_id, reviewer_id, rating, reason, message_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (member.id, interaction.user.id, rating, reason, msg.id, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()

        self.log_action(f"{interaction.user} reviewed {member} ({rating} stars) - Reason: {reason}")
        await interaction.response.send_message("✅ Review submitted!", ephemeral=True)

    @app_commands.command(name="reviews-list", description="List all reviews for a member (admin only).")
    @app_commands.describe(member="Member whose reviews you want to see")
    async def reviews_list(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.guild or not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT id, reviewer_id, rating, reason, message_id, timestamp FROM reviews WHERE target_id = ? ORDER BY timestamp DESC",
            (member.id,)
        )
        rows = c.fetchall()
        conn.close()

        if not rows:
            return await interaction.response.send_message("No reviews found for this member.", ephemeral=True)

        embed = discord.Embed(title=f"Reviews for {member.display_name}", color=discord.Color.blurple())
        for review_id, reviewer_id, rating, reason, message_id, timestamp in rows:
            reviewer = self.bot.get_user(reviewer_id)
            msg_url = f"https://discord.com/channels/{interaction.guild.id}/{REVIEW_CHANNEL_ID}/{message_id}"
            embed.add_field(
                name=f"ID {review_id} | {self.rating_to_stars(rating)}",
                value=f"By: {reviewer.mention if reviewer else reviewer_id}\nReason: {reason}\n[View Message]({msg_url})\nDate: {timestamp}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="delete-review", description="Delete a review by ID (admin only).")
    @app_commands.describe(review_id="ID of the review to delete")
    async def delete_review(self, interaction: discord.Interaction, review_id: int):
        if not interaction.guild or not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            return await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT message_id, target_id, reviewer_id, rating, reason FROM reviews WHERE id = ?", (review_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return await interaction.response.send_message("No review found with that ID.", ephemeral=True)

        message_id, target_id, reviewer_id, rating, reason = row
        review_channel = self.bot.get_channel(REVIEW_CHANNEL_ID)
        if review_channel:
            try:
                msg = await review_channel.fetch_message(message_id)
                await msg.delete()
            except discord.NotFound:
                pass

        c.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        conn.commit()
        conn.close()

        self.log_action(f"{interaction.user} deleted review ID {review_id} (Target: {target_id}, Reviewer: {reviewer_id}, Rating: {rating}, Reason: {reason})")
        await interaction.response.send_message("✅ Review deleted.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Review(bot))
