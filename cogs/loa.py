import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta

LOA_REQUEST_ROLE = 1329910329701830686
LOA_REVIEW_CHANNEL = 1329910558954098701
LOA_REVIEWER_ROLE = 1329910265264869387
DATA_DIR = "data"
LOGS_DIR = "logs"
LOA_DATA_FILE = os.path.join(DATA_DIR, "loa_requests.json")
LOA_LOG_FILE = os.path.join(LOGS_DIR, "loa.log")

def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

def log_loa_action(msg):
    ensure_dirs()
    with open(LOA_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.utcnow().isoformat()}] {msg}\n")

def save_loa_request(request):
    ensure_dirs()
    try:
        if os.path.exists(LOA_DATA_FILE):
            with open(LOA_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = []
    except Exception:
        data = []
    data.append(request)
    with open(LOA_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

class LOARequestModal(discord.ui.Modal, title="LOA Request"):
    reason = discord.ui.TextInput(
        label="Reason for LOA",
        style=discord.TextStyle.paragraph,
        placeholder="Why do you need a leave of absence?",
        required=True,
        max_length=300
    )
    duration = discord.ui.TextInput(
        label="Duration (days)",
        placeholder="Enter number of days (e.g. 7)",
        required=True,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Only allow if user has LOA_REQUEST_ROLE
        if not any(r.id == LOA_REQUEST_ROLE for r in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to request an LOA.", ephemeral=True)
            return
        try:
            days = int(self.duration.value)
            if days < 1 or days > 60:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Please enter a valid duration (1-60 days).", ephemeral=True)
            return

        end_date = datetime.utcnow() + timedelta(days=days)
        request = {
            "user_id": interaction.user.id,
            "user_tag": str(interaction.user),
            "reason": self.reason.value,
            "duration": days,
            "requested_at": datetime.utcnow().isoformat(),
            "end_date": end_date.isoformat(),
            "status": "Pending"
        }
        save_loa_request(request)
        log_loa_action(f"REQUESTED: {interaction.user} ({interaction.user.id}) for {days} days. Reason: {self.reason.value}")

        embed = discord.Embed(
            title="New LOA Request",
            description=f"**User:** {interaction.user.mention}\n**Duration:** {days} days\n**End Date:** <t:{int(end_date.timestamp())}:D>\n**Reason:** {self.reason.value}",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"LOA for {interaction.user.id}")
        review_channel = interaction.guild.get_channel(LOA_REVIEW_CHANNEL)
        if review_channel and isinstance(review_channel, discord.TextChannel):
            await review_channel.send(content=f"<@&{LOA_REVIEWER_ROLE}>", embed=embed, view=LOAReviewView(interaction.user.id))
            await interaction.response.send_message("Your LOA request has been submitted for review.", ephemeral=True)
        else:
            await interaction.response.send_message("Review channel not found. Please contact an admin.", ephemeral=True)

class LOAReviewView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    async def update_embed(self, interaction, status, reviewer):
        embed = interaction.message.embeds[0].copy()
        embed.add_field(name="Status", value=status, inline=False)
        embed.add_field(name="Reviewed by", value=reviewer.mention, inline=False)
        await interaction.message.edit(embed=embed, view=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success, custom_id="loa_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == LOA_REVIEWER_ROLE for r in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to review LOA requests.", ephemeral=True)
            return
        member = interaction.guild.get_member(self.user_id)
        await interaction.response.send_message(f"✅ LOA approved for {member.mention if member else self.user_id}.", ephemeral=True)
        log_loa_action(f"APPROVED: {member} ({self.user_id}) by {interaction.user} ({interaction.user.id})")
        try:
            if member:
                await member.send("✅ Your LOA request has been approved!")
        except Exception:
            pass
        await self.update_embed(interaction, "✅ Approved", interaction.user)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="loa_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id == LOA_REVIEWER_ROLE for r in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to review LOA requests.", ephemeral=True)
            return
        member = interaction.guild.get_member(self.user_id)
        await interaction.response.send_message(f"❌ LOA denied for {member.mention if member else self.user_id}.", ephemeral=True)
        log_loa_action(f"DENIED: {member} ({self.user_id}) by {interaction.user} ({interaction.user.id})")
        try:
            if member:
                await member.send("❌ Your LOA request has been denied.")
        except Exception:
            pass
        await self.update_embed(interaction, "❌ Denied", interaction.user)

class LOACog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        ensure_dirs()
        self.bot.add_view(LOAReviewView(user_id=0))  # Persistent view

    @discord.app_commands.command(name="loa_request", description="Request a Leave of Absence (LOA).")
    async def loa_request(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LOARequestModal())

async def setup(bot):
    await bot.add_cog(LOACog(bot))