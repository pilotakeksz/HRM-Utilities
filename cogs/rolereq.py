import discord
from discord.ext import commands
import os

REVIEW_CHANNEL_ID = 1425949939925516368
LOG_CHANNEL_ID = 1343686645815181382
REVIEWER_ROLE_ID = 1375598194456658030
LOGS_DIR = "logs"

class RoleRequestView(discord.ui.View):
    def __init__(self, member_id, role_id, proof_url):
        super().__init__(timeout=None)
        self.member_id = member_id
        self.role_id = role_id
        self.proof_url = proof_url

    async def update_embed(self, interaction, status, reviewer):
        embed = interaction.message.embeds[0].copy()
        embed.add_field(name="Status", value=status, inline=False)
        embed.add_field(name="Reviewed by", value=reviewer.mention, inline=False)
        await interaction.message.edit(embed=embed, view=None)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only reviewers can approve
        if not any(r.id == REVIEWER_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to review requests.", ephemeral=True)
            return
        member = interaction.guild.get_member(self.member_id)
        role = interaction.guild.get_role(self.role_id)
        if member and role:
            await member.add_roles(role, reason="Role request approved")
            await interaction.response.send_message(f"✅ Approved and added {role.name} to {member.mention}.", ephemeral=True)
            await log_action(interaction.guild, f"APPROVED: {member} ({member.id}) for role {role.name} ({role.id}) by {interaction.user} ({interaction.user.id})", self.proof_url)
            # DM notify
            try:
                await member.send(f"✅ Your role request for **{role.name}** was approved!")
            except Exception:
                pass
            await self.update_embed(interaction, "✅ Approved", interaction.user)
        else:
            await interaction.response.send_message("Failed to add role.", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only reviewers can deny
        if not any(r.id == REVIEWER_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to review requests.", ephemeral=True)
            return
        member = interaction.guild.get_member(self.member_id)
        role = interaction.guild.get_role(self.role_id)
        await interaction.response.send_message(f"❌ Denied request for {member.mention} ({role.name}).", ephemeral=True)
        await log_action(interaction.guild, f"DENIED: {member} ({member.id}) for role {role.name} ({role.id}) by {interaction.user} ({interaction.user.id})", self.proof_url)
        # DM notify
        try:
            await member.send(f"❌ Your role request for **{role.name}** was denied.")
        except Exception:
            pass
        await self.update_embed(interaction, "❌ Denied", interaction.user)

async def log_action(guild, message, proof_url):
    # Log to .txt
    os.makedirs(LOGS_DIR, exist_ok=True)
    logline = f"[{discord.utils.utcnow().isoformat()}] {message}\nProof: {proof_url}\n"
    with open(os.path.join(LOGS_DIR, f"{discord.utils.utcnow().date()}.txt"), "a", encoding="utf-8") as f:
        f.write(logline)
    # Log as embed in LOG_CHANNEL_ID
    ch = guild.get_channel(LOG_CHANNEL_ID)
    if isinstance(ch, discord.TextChannel):
        emb = discord.Embed(title="Role Request Log", description=message, color=discord.Color.purple())
        if proof_url:
            emb.set_image(url=proof_url)
        await ch.send(embed=emb)

class RoleRequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="role_request", description="Request a decorative role from staff.")
    @discord.app_commands.describe(role="Select the role to request", proof="Upload proof of eligibility (image)")
    async def role_request(self, interaction: discord.Interaction, role: discord.Role, proof: discord.Attachment):
        # Only allow decorative roles (no admin/management perms)
        if role.permissions.administrator or role.permissions.manage_roles or role.permissions.kick_members or role.permissions.ban_members or role.managed or role.name == "@everyone":
            await interaction.response.send_message("You can only request decorative roles.", ephemeral=True)
            return
        proof_url = proof.url if proof else None
        embed = discord.Embed(
            title="New Role Request",
            description=f"**User:** {interaction.user.mention}\n**Role Requested:** {role.mention}",
            color=discord.Color.blue()
        )
        if proof_url:
            embed.set_image(url=proof_url)
        review_channel = interaction.guild.get_channel(REVIEW_CHANNEL_ID)
        if review_channel and isinstance(review_channel, discord.TextChannel):
            # Ping reviewer role
            await review_channel.send(content=f"<@&{REVIEWER_ROLE_ID}>", embed=embed, view=RoleRequestView(interaction.user.id, role.id, proof_url))
            await interaction.response.send_message("Your role request has been submitted to staff.", ephemeral=True)
            await log_action(interaction.guild, f"REQUESTED: {interaction.user} ({interaction.user.id}) for role {role.name} ({role.id})", proof_url)
        else:
            await interaction.response.send_message("Staff channel not found. Please contact an admin.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RoleRequestCog(bot))