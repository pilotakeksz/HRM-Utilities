import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
from datetime import datetime
import asyncio

DATA_DIR = "data"
LOG_DIR = "logs"
DB_PATH = os.path.join(DATA_DIR, "reviews.db")
LOG_PATH = os.path.join(LOG_DIR, "review_actions.txt")

REVIEW_CHANNEL_ID = 1329910477404242083  # Reviews channel
REVIEWER_ROLE_ID = 1329910391840702515   # Role required to review (anyone with this can review)
ADMIN_ROLE_ID = 1355842403134603275      # Role required to delete reviews

REVIEW_LOG_CHANNEL_ID = 1343686645815181382  # Action logs channel

EMBED_IMAGE_URL = "https://cdn.discordapp.com/attachments/1376647068092858509/1376934109665824828/bottom.png?ex=68980791&is=6896b611&hm=2254fc59f1199d20999cd7f212ade2cc77091ee7078d5054312897c78b0148e0&"

STAR_EMOJIS = {
    1: "⭐☆☆☆☆",
    2: "⭐⭐☆☆☆",
    3: "⭐⭐⭐☆☆",
    4: "⭐⭐⭐⭐☆",
    5: "⭐⭐⭐⭐⭐"
}

RATING_COLORS = {
    1: discord.Color.red(),
    2: discord.Color.orange(),
    3: discord.Color.gold(),
    4: discord.Color.green(),
    5: discord.Color.blue()
}

class Reviews(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)
        self.init_db()

        self._log_queue = asyncio.Queue()
        self.log_task = self.bot.loop.create_task(self._log_sender_task())

    def cog_unload(self):
        self.log_task.cancel()

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reviewer_id INTEGER NOT NULL,
                    reviewer_name TEXT NOT NULL,
                    target_id INTEGER NOT NULL,
                    target_name TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def write_log_to_file(self, message: str):
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"[{timestamp}] {message}\n"
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            print(f"Failed to write review log to file: {e}")

    async def _log_sender_task(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                message = await self._log_queue.get()
                channel = self.bot.get_channel(REVIEW_LOG_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(description=message, color=discord.Color.dark_grey(), timestamp=datetime.utcnow())
                    embed.set_author(name="Review Action Log")
                    try:
                        await channel.send(embed=embed)
                    except Exception as e:
                        print(f"Failed to send review log embed: {e}")
                self._log_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Unexpected error in review log sender task: {e}")

    def log_action(self, message: str):
        self.write_log_to_file(message)
        self._log_queue.put_nowait(message)

    @app_commands.command(name="review", description="Add a review for a user")
    @app_commands.describe(
        member="User to review",
        rating="Rating from 1 to 5 stars",
        reason="Reason for the review"
    )
    async def review(self, interaction: discord.Interaction, member: discord.Member, rating: int, reason: str):
        await interaction.response.defer(ephemeral=True)

        if REVIEWER_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.followup.send("❌ You do not have permission to add reviews.", ephemeral=True)
            return

        if rating < 1 or rating > 5:
            await interaction.followup.send("❌ Rating must be between 1 and 5.", ephemeral=True)
            return

        if not reason.strip():
            await interaction.followup.send("❌ You must provide a reason for the review.", ephemeral=True)
            return

        review_channel = self.bot.get_channel(REVIEW_CHANNEL_ID)
        if not review_channel: #TEST
            await interaction.followup.send("❌ Review channel not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"New Review for {member.display_name}",
            description=(
                f"**Rating:** {STAR_EMOJIS[rating]}\n"
                f"**Reason:** {reason}\n\n"
                f"Reviewer: {interaction.user.mention}\n"
                f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}"
            ),
            color=RATING_COLORS[rating],
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_image(url=EMBED_IMAGE_URL)

        # Temporary footer (will update)
        embed.set_footer(text=f"Review by {interaction.user}")

        review_msg = await review_channel.send(f"{member.mention}", embed=embed)

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO reviews (reviewer_id, reviewer_name, target_id, target_name, rating, reason, message_id, channel_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                interaction.user.id,
                str(interaction.user),
                member.id,
                str(member),
                rating,
                reason,
                review_msg.id,
                review_msg.channel.id,
                datetime.utcnow().isoformat()
            ))
            conn.commit()
            review_id = c.lastrowid

        embed.set_footer(text=f"Review ID: {review_id} | Reviewed by {interaction.user} on {datetime.utcnow().strftime('%Y-%m-%d')}")
        await review_msg.edit(embed=embed)

        self.log_action(f"Review ID {review_id} created by {interaction.user} for {member} with rating {rating} and reason: {reason}")

        await interaction.followup.send(f"✅ Review added for {member.mention} with ID {review_id}.", ephemeral=True)

    @app_commands.command(name="review-list", description="List reviews for a user (up to 7)")
    @app_commands.describe(member="User to list reviews for")
    async def review_list(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT id, reviewer_name, rating, reason, message_id, channel_id, created_at
                FROM reviews WHERE target_id = ? ORDER BY created_at DESC LIMIT 7
            """, (member.id,))
            reviews = c.fetchall()

        if not reviews:
            await interaction.followup.send(f"No reviews found for {member.display_name}.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Reviews for {member.display_name} (up to 7)",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        for review in reviews:
            review_id, reviewer_name, rating, reason, message_id, channel_id, created_at = review
            jump_url = f"https://discord.com/channels/{interaction.guild.id}/{channel_id}/{message_id}"
            stars = STAR_EMOJIS.get(rating, "⭐☆☆☆☆")
            created_date = created_at[:10]
            field_name = f"ID {review_id} | {stars} | By {reviewer_name} on {created_date}"
            field_value = f"**Reason:** {reason}\n[Jump to review]({jump_url})"
            embed.add_field(name=field_name, value=field_value, inline=False)

        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="delreview", description="Delete a review by its ID (Admin only)")
    @app_commands.describe(review_id="ID of the review to delete")
    async def delreview(self, interaction: discord.Interaction, review_id: int):
        await interaction.response.defer(ephemeral=True)

        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.followup.send("❌ You do not have permission to delete reviews.", ephemeral=True)
            return

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT message_id, channel_id, target_name, reviewer_name FROM reviews WHERE id=?", (review_id,))
            row = c.fetchone()
            if not row:
                await interaction.followup.send(f"❌ Review with ID {review_id} not found.", ephemeral=True)
                return

            message_id, channel_id, target_name, reviewer_name = row

            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    msg = await channel.fetch_message(message_id)
                    await msg.delete()
                except Exception:
                    pass

            c.execute("DELETE FROM reviews WHERE id=?", (review_id,))
            conn.commit()

        self.log_action(f"Review ID {review_id} deleted by {interaction.user}. Target: {target_name}, Reviewer: {reviewer_name}")

        await interaction.followup.send(f"✅ Review ID {review_id} deleted.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Reviews(bot))
# test tes e