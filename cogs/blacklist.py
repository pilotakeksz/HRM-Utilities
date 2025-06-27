import discord
from discord.ext import commands
from discord import app_commands
import datetime
import os
import json
import random
import string

BLACKLIST_ROLE_ID = 1329910241835352064
BLACKLIST_CHANNEL_ID = 1329910470332649536
BLACKLIST_ICON = "<:HighRockMilitary:1376605942765977800>"
DATA_DIR = os.path.join(os.path.dirname(__file__), "../data")
BLACKLIST_DATA_FILE = os.path.join(DATA_DIR, "blacklists.json")

def ensure_data_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(BLACKLIST_DATA_FILE):
        with open(BLACKLIST_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

def save_blacklist_entry(entry):
    ensure_data_file()
    with open(BLACKLIST_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.append(entry)
    with open(BLACKLIST_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def generate_blacklist_id():
    # 8-char random string + timestamp
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"BL-{rand}-{int(datetime.datetime.utcnow().timestamp())}"

class BlacklistIssueModal(discord.ui.Modal, title="Issue Blacklist"):
    reason = discord.ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, required=True, max_length=512)
    hrmc_wide = discord.ui.TextInput(label="HRMC-wide? (true/false)", required=True, max_length=5)
    ban = discord.ui.TextInput(label="Ban user? (true/false)", required=True, max_length=5)

    def __init__(self, user: discord.Member, proof: discord.Attachment = None):
        super().__init__()
        self.user = user
        self.proof = proof

    async def on_submit(self, interaction: discord.Interaction):
        await BlacklistCog.issue_blacklist(
            cog=interaction.client.get_cog("BlacklistCog"),
            interaction=interaction,
            user=self.user,
            reason=self.reason.value,
            proof=self.proof,
            hrmc_wide=self.hrmc_wide.value.lower() == "true",
            ban=self.ban.value.lower() == "true"
        )

class BlacklistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="blacklist-issue", description="Issue a blacklist for a user.")
    @app_commands.describe(
        user="User to blacklist",
        reason="Reason for blacklist",
        proof="Proof (optional)",
        hrmc_wide="Is this blacklist HRMC-wide?",
        ban="Ban the user?"
    )
    @app_commands.checks.has_role(BLACKLIST_ROLE_ID)
    async def blacklist_issue(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        proof: discord.Attachment = None,
        hrmc_wide: bool = False,
        ban: bool = False
    ):
        await self.issue_blacklist(
            interaction=interaction,
            user=user,
            reason=reason,
            proof=proof,
            hrmc_wide=hrmc_wide,
            ban=ban
        )

    @staticmethod
    async def issue_blacklist(cog, interaction, user, reason, proof, hrmc_wide, ban):
        blacklist_id = generate_blacklist_id()
        now = datetime.datetime.utcnow()
        proof_url = proof.url if proof else None

        embed = discord.Embed(
            title=f"{BLACKLIST_ICON} // HRMC Blacklist",
            color=discord.Color.red(),
            timestamp=now
        )
        embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="HRMC-wide", value="Yes" if hrmc_wide else "No", inline=True)
        embed.add_field(name="Ban", value="Yes" if ban else "No", inline=True)
        embed.add_field(name="Blacklist ID", value=blacklist_id, inline=False)
        embed.set_footer(text=f"Issued by: {interaction.user} • {now.strftime('%Y-%m-%d %H:%M UTC')}")
        if proof_url:
            embed.add_field(name="Proof", value="[Attachment]({})".format(proof_url), inline=False)
            if proof.content_type and proof.content_type.startswith("image/"):
                embed.set_image(url=proof_url)

        # Save to data
        entry = {
            "id": blacklist_id,
            "user_id": user.id,
            "user_tag": str(user),
            "reason": reason,
            "proof": proof_url,
            "hrmc_wide": hrmc_wide,
            "ban": ban,
            "issued_by": interaction.user.id,
            "issued_by_tag": str(interaction.user),
            "timestamp": now.isoformat()
        }
        save_blacklist_entry(entry)

        # Ping user before embed
        channel = interaction.client.get_channel(BLACKLIST_CHANNEL_ID)
        if channel:
            await channel.send(user.mention)
            msg = await channel.send(embed=embed)
            # Publish if HRMC-wide and channel is announcement
            if hrmc_wide and getattr(channel, "is_news", lambda: False)():
                try:
                    await msg.publish()
                except Exception:
                    pass

        # DM the blacklisted user
        try:
            await user.send(embed=embed)
        except Exception:
            pass

        # Ban if needed
        if ban:
            try:
                await interaction.guild.ban(user, reason=f"HRMC Blacklist: {reason}")
            except Exception:
                pass

        await interaction.response.send_message(
            f"Blacklist issued for {user.mention} (ID: {blacklist_id})", ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(BlacklistCog(bot))