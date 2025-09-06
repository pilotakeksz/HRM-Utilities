import discord
from discord.ext import commands
import os

STAFF_CHANNEL_ID = 1329910558954098701  # Channel for embed logs
LOGS_DIR = "logs"

class RoleRequestView(discord.ui.View):
    def __init__(self, member_id, role_id, proof_url):
        super().__init__(timeout=None)
        self.member_id = member_id
        self.role_id = role_id
        self.proof_url = proof_url

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        role = interaction.guild.get_role(self.role_id)
        if member and role:
            await member.add_roles(role, reason="Role request approved")
            await interaction.response.send_message(f"✅ Approved and added {role.name} to {member.mention}.", ephemeral=True)
            await log_action(interaction.guild, f"APPROVED: {member} ({member.id}) for role {role.name} ({role.id}) by {interaction.user} ({interaction.user.id})", self.proof_url)
        else:
            await interaction.response.send_message("Failed to add role.", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.member_id)
        role = interaction.guild.get_role(self.role_id)
        await interaction.response.send_message(f"❌ Denied request for {member.mention} ({role.name}).", ephemeral=True)
        await log_action(interaction.guild, f"DENIED: {member} ({member.id}) for role {role.name} ({role.id}) by {interaction.user} ({interaction.user.id})", self.proof_url)

async def log_action(guild, message, proof_url):
    # Log to .txt
    os.makedirs(LOGS_DIR, exist_ok=True)
    logline = f"[{discord.utils.utcnow().isoformat()}] {message}\nProof: {proof_url}\n"
    with open(os.path.join(LOGS_DIR, f"{discord.utils.utcnow().date()}.txt"), "a", encoding="utf-8") as f:
        f.write(logline)
    # Log as embed
    ch = guild.get_channel(STAFF_CHANNEL_ID)
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
        staff_channel = interaction.guild.get_channel(STAFF_CHANNEL_ID)
        if staff_channel and isinstance(staff_channel, discord.TextChannel):
            await staff_channel.send(embed=embed, view=RoleRequestView(interaction.user.id, role.id, proof_url))
            await interaction.response.send_message("Your role request has been submitted to staff.", ephemeral=True)
            await log_action(interaction.guild, f"REQUESTED: {interaction.user} ({interaction.user.id}) for role {role.name} ({role.id})", proof_url)
        else:
            await interaction.response.send_message("Staff channel not found. Please contact an admin.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RoleRequestCog(bot))